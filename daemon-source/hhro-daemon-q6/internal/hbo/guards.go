package hbo

import "fmt"

// ApplyStabilityGuards post-processes the selected action through safety
// checks: emergency override, direction lock, capacity guard, scale-in guard.
func ApplyStabilityGuards(a Action, bn Bottleneck, risk RiskSet, s SystemState, f FeatureSet, p PressureSet, timers *Timers, cfg Cfg) (Action, string) {
	// Emergency: a severe QoS violation overrides the direction lock to add capacity
	// NOW — but ONLY for scale-OUT. A scale-OUT's OWN migration/reload transiently
	// blackholes packets (DropUP spikes) at the ru3→peak boundary; that spike made
	// emergency=true, which BYPASSED the 300s direction lock for the very next tick's
	// SCALE-IN → the just-added UPF/VyOS was immediately removed (8→7→8 / 3→2→3 flap).
	// An emergency means "need MORE capacity", so it must never let a SCALE-IN slip the
	// lock and reverse a fresh scale-out. Gate the override on scale-out actions only;
	// scale-in/delete always honor the direction lock.
	emergency := (risk.CP >= cfg.RiskCritical ||
		risk.UP >= cfg.RiskCritical ||
		risk.Vyos >= cfg.RiskCritical ||
		(metricAvailable(f.DropUP) && norm(f.DropUP.P90_60, cfg.MaxDropPPS) >= cfg.DropCritical)) &&
		a.IsScaleOut()

	// Direction lock
	if !emergency {
		if blocked, reason := timers.DirectionLockBlocks(a); blocked {
			return ActNone, reason
		}
	}

	// UPF boot window: never stack a second clone while the previous one is
	// still coming up (Pending/booting). The KSM-derived free-CPU state lags
	// pod creation by up to two scrape intervals, so back-to-back mid-ticks
	// double-fired scale-out past physical capacity (v44: upf-5 AND upf-6
	// created within the lag window, both stranded Pending). ReadyUP/RepUP
	// come from deployment status — the same lag — but a not-yet-visible
	// clone also hasn't moved them, so this still serializes the ladder.
	if a == ActScaleOutUP && (s.ReadyUP < s.RepUP || s.PodPendingCount > 0) {
		return ActNone, "UPF boot window: previous clone not Ready yet"
	}

	// CNF scale-out capacity guard
	if a == ActScaleOutCP || a == ActScaleOutUP {
		if !HasWorkerCapacity(s, cfg) {
			if s.WorkerCount < cfg.MaxWorkers && !timers.CooldownActive(ActCreateWorker) {
				return ActCreateWorker, "CNF scale-out redirected to CREATE_WORKER (insufficient worker capacity)"
			}
			return ActNone, "CNF scale-out blocked: no worker capacity and worker max/cooldown"
		}
	}

	// Scale-in guard — per-layer (an over-provisioned layer may shrink while
	// another layer is still warm; the old all-layers gate deadlocked UPF
	// scale-in on VyOS pressure through the whole ramp-down).
	switch a {
	case ActScaleInUP:
		if ok, reason := ShouldScaleInUP(f, p, s, timers, cfg); !ok {
			return ActNone, "scale-in guard: " + reason
		}
	case ActScaleInCP:
		if ok, reason := ShouldScaleInCP(f, p, s, timers, cfg); !ok {
			return ActNone, "scale-in guard: " + reason
		}
	}

	// Worker delete safety
	if a == ActDeleteWorker {
		if ok, reason := WorkerSafeToDelete(s, f, p, timers, cfg); !ok {
			return ActNone, "worker delete guard: " + reason
		}
	}

	// VyOS delete safety
	if a == ActDeleteVyOS {
		if ok, reason := VyosSafeToDelete(s, f, p, timers, cfg); !ok {
			return ActNone, "VyOS delete guard: " + reason
		}
	}

	return a, ""
}

// scaleInSafety holds the layer-independent safety checks shared by every
// scale-in path: never shrink anything while packets are dropping, pods are
// unschedulable, or a node is under pressure.
func scaleInSafety(f FeatureSet, s SystemState, cfg Cfg) (bool, string) {
	// Drop safety must be RELATIVE to throughput, not an absolute pps count.
	// During ramp-down, killing UEs tears down sessions → ~25 pps transient
	// drops; on a 700k pps system that's 0.003% — utterly benign. The old
	// absolute gate (norm(P90_60, MaxDropPPS=1000) >= DropSafe=0.01 → 10 pps)
	// tripped on that teardown noise and blocked EVERY ramp-down scale-in
	// (v44 / v4.12 — the real reason scale-in only ever fired at full idle).
	// Gate on the drop RATIO instead: only sustained loss that is a real
	// fraction of traffic blocks; transient teardown noise passes. Fall back to
	// the absolute gate at near-zero throughput (ratio undefined).
	if metricAvailable(f.DropUP) {
		if metricAvailable(f.PktRateUP) && f.PktRateUP.Avg60 > 1000 {
			// v4.22: Avg60, NOT P90_60. A migrate/rehome re-arm causes a brief
			// drop SPIKE (stale TEID/route for a second) that P90_60 holds for
			// the whole 60s window → scale-in blocked through the ENTIRE
			// ramp-down, deferred to cool (v4.19/v4.21). Avg60 smooths the
			// transient spike and still blocks genuinely-sustained loss.
			if f.DropUP.Avg60/f.PktRateUP.Avg60 >= cfg.DropSafeRatio {
				return false, "drop_up not safe (ratio)"
			}
		} else if norm(f.DropUP.P90_60, cfg.MaxDropPPS) >= cfg.DropSafe {
			return false, "drop_up not safe"
		}
	}
	if s.PodPendingCount > 0 {
		return false, "pods pending"
	}
	if s.NodePressure {
		return false, "node pressure active"
	}
	return true, ""
}

// ShouldScaleInUP gates UPF scale-in on UP-layer signals ONLY. The old
// all-layers gate required C_vyos sustained low too, which blocked UPF
// scale-in through the whole ramp-down (the 1-vCPU VyOS pool stays >VYOS_LOW
// at moderate load) so UPFs only shrank at full idle. UP scale-in is safe
// whenever the UP layer itself can absorb the load with one fewer replica.
func ShouldScaleInUP(f FeatureSet, p PressureSet, s SystemState, timers *Timers, cfg Cfg) (bool, string) {
	// v4.63: DECOUPLE from the UPF drop-safety (mirror VyOS v4.48). scaleInSafety
	// gates on the UPF drop RATIO, but during ramp-down the rehome/migration churn
	// ITSELF raises that ratio → it blocked the very scale-in that the ramp-down
	// calls for (UPF stuck at 8 through ramp-down, released only in cool). A UPF
	// scale-in is an SMF session reduce + sender route cleanup whose loss is the
	// migration cost, not a reason to keep the UPF — gate only on INFRA safety.
	if s.PodPendingCount > 0 {
		return false, "pods pending"
	}
	if s.NodePressure {
		return false, "node pressure active"
	}
	// UE churn guard: don't shrink while UE count is actively growing.
	if metricAvailable(f.UECount) && s.UECount > cfg.LowUEMax && f.UECount.Slope300 > 0 {
		return false, "UE count rising"
	}
	lowUP := p.UP < cfg.UpLow
	if metricAvailable(f.HhroUpScore) {
		lowUP = f.HhroUpScore.P95_300 < cfg.UpLow
	}
	if lowUP {
		// fully idle path — still keep a short dwell to ride out blips
		if !timers.LowDwellReached(cfg.LowDwellTicks) {
			return false, "low dwell not reached"
		}
		return true, ""
	}
	// Aggregate-capacity path: even if the busiest UPF isn't idle, scale in
	// when the TOTAL UPF load fits on RepUP-1 replicas with headroom.
	// Uses Avg60, NOT P95_300: a p95 over a long window tracks a step-DOWN in
	// load only after ~95% of the window has refreshed (~3min), which made the
	// gate miss every 240s ramp-down stage entirely (v41: now=0.72 while
	// P95_180=1.92). Avg60 follows within a minute; stability comes from the
	// rising-slope guard below + the 60s scale-in cooldown between steps.
	// v4.62: project on THROUGHPUT (PktRateUP = Σ UPF RX+TX pps), NOT SumCpuUP. The
	// CPU projection SumCpuUP/(N-1) was dominated by each pod's IDLE-BASELINE CPU
	// (~0.5/pod even near-idle): dividing the all-baselines total by N-1 OVER-charged
	// the survivors with the removed pod's baseline → projected stayed > target → UPF
	// "needs all UPFs" right through ramp-down, releasing only in cool (run36: rep
	// stuck at 8 at rd1/rd2). Throughput has NO idle baseline, so total/(N-1) is the
	// TRUE post-removal per-UPF load. Scale in while that stays ≤ the per-UPF safe
	// capacity (UpfPpsCap): at peak each UPF sustained ~400k RX+TX (8×=3.2M at 1.6M
	// offered), so a 250k cap leaves headroom ⇒ rebound-free. Trajectory it yields:
	// rd1(1.6M RX+TX)→7 (1.6M/7=228k<250, /6=267k>250 stops), rd2→4, rd3→2, cool→1.
	if s.RepUP > cfg.MinUP && metricAvailable(f.PktRateUP) {
		// v4.88: BACK to the original Avg60 projection (the tuned ramp-down pacer:
		// "rd1 1.6M/7=228k<250→7, /6=267k>250 stops; rd2→4; rd3→2"). The v4.81-86
		// detours (max(Avg60,Now)/P90_60/UEcount-demand) were all attempts to stop the
		// peak REBOUND at the projection layer — but the real cause was the emergency
		// override bypassing the direction lock (fixed in ApplyStabilityGuards above), so
		// the projection no longer needs to be rebound-proof. Those detours also made
		// ramp-down OVER-shoot (rd1 8→5 instead of →7). Restoring Avg60 restores the
		// tuned pacing; the direction lock now blocks any boundary/dip rebound.
		projectedPerUpfPps := f.PktRateUP.Avg60 / float64(s.RepUP-1)
		if projectedPerUpfPps < cfg.UpfPpsCap {
			// don't scale in while load is RISING (rebound guard), scale-aware slope.
			if f.PktRateUP.Slope120 > cfg.MaxPktRateSlope*float64(s.RepUP) {
				return false, "total UP throughput rising (rebound risk)"
			}
			return true, ""
		}
	}
	return false, "C_up not low and total throughput needs all UPFs"
}

// ShouldScaleInCP gates CP scale-in on CP-layer signals only.
func ShouldScaleInCP(f FeatureSet, p PressureSet, s SystemState, timers *Timers, cfg Cfg) (bool, string) {
	if ok, reason := scaleInSafety(f, s, cfg); !ok {
		return false, reason
	}
	lowCP := p.CP < cfg.CpLow
	if metricAvailable(f.HhroCpScore) {
		lowCP = f.HhroCpScore.P95_300 < cfg.CpLow
	}
	if !lowCP {
		return false, "C_cp not sustained low"
	}
	if !timers.LowDwellReached(cfg.LowDwellTicks) {
		return false, "low dwell not reached"
	}
	return true, ""
}

// WorkerSafeToDelete checks if it's safe to delete a worker node.
// An IDLE worker (Ready >10min, zero UPF pods) is deletable by definition —
// regardless of how busy the OTHER workers are. Without an idle target, fall
// back to the conservative aggregate checks (the cool phase).
func WorkerSafeToDelete(s SystemState, f FeatureSet, p PressureSet, timers *Timers, cfg Cfg) (bool, string) {
	if s.WorkerCount <= cfg.MinWorkers {
		return false, "at min workers"
	}
	if s.PodPendingCount > 0 {
		return false, "pods pending"
	}
	if s.NodePressure {
		return false, "node pressure"
	}
	if s.IdleWorker != "" {
		return true, ""
	}
	if f.WorkerCpu.P95_600 >= cfg.WorkerCpuLow {
		return false, "worker CPU not sustained low"
	}
	if f.WorkerMem.P95_600 >= cfg.WorkerMemLow {
		return false, "worker mem not sustained low"
	}
	return true, ""
}

//
//
func workerCreateInfraOnly(s SystemState, cfg Cfg) (bool, string) {
	n := s.WorkerCount
	if s.WorkerVMCount > n {
		n = s.WorkerVMCount
	}
	if n >= cfg.MaxWorkers {
		return false, fmt.Sprintf("at max workers (vm=%d node=%d max=%d)",
			s.WorkerVMCount, s.WorkerCount, cfg.MaxWorkers)
	}
	if s.WorkerVMCount > s.ReadyWorkers {
		return false, fmt.Sprintf("a worker is still booting (vm=%d ready=%d)",
			s.WorkerVMCount, s.ReadyWorkers)
	}
	return true, ""
}

func workerDeleteInfraOnly(s SystemState, cfg Cfg) (bool, string) {
	if s.WorkerCount <= cfg.MinWorkers {
		return false, "at min workers"
	}
	if s.PodPendingCount > 0 {
		return false, "pods pending"
	}
	if s.NodePressure {
		return false, "node pressure"
	}
	if s.IdleWorker == "" {
		return false, "no idle worker"
	}
	return true, ""
}

func vyosDeleteInfraOnly(s SystemState, cfg Cfg) (bool, string) {
	if s.VyosCount <= cfg.MinVyos {
		return false, "at min VyOS"
	}
	if s.PodPendingCount > 0 {
		return false, "pods pending"
	}
	if s.NodePressure {
		return false, "node pressure active"
	}
	return true, ""
}

// VyosSafeToDelete gates VyOS deletion on VyOS-layer signals only (sustained
// low over the long window + no rising trend), not on the other layers.
func VyosSafeToDelete(s SystemState, f FeatureSet, p PressureSet, timers *Timers, cfg Cfg) (bool, string) {
	if s.VyosCount <= cfg.MinVyos {
		return false, "at min VyOS"
	}
	// v4.48: DECOUPLE VyOS scale-in from the UPF drop-safety. The generic
	// scaleInSafety() gates on the UPF drop RATIO (DropUP/PktRateUP) — a UPF-LAYER
	// signal. During ramp-down the UPF's own migration/rehome churn raises that
	// ratio, which then blocked VyOS deletion ("drop_up not safe (ratio)") even
	// though removing a VyOS is a seamless sender-route swap over REPLICATED DNAT
	// (loss≈0) that has nothing to do with UPF drops — run15's daemon log shows
	// VyOS rejected on "drop_up not safe" / lagging "C_vyos" every slow-tick, so
	// it stayed at 3 the whole run. VyOS scale-in needs only INFRA safety; its OWN
	// load is judged by the lowVyos + rising-slope guards below.
	if s.PodPendingCount > 0 {
		return false, "pods pending"
	}
	if s.NodePressure {
		return false, "node pressure active"
	}
	// v4.53 — PREDICTIVE, rebound-free scale-in. Deleting a VyOS redistributes its
	// load onto the N-1 survivors, so it is safe iff the BUSIEST node's load scaled
	// by N/(N-1) (what a survivor inherits after a rebalance) still lands BELOW the
	// scale-OUT line, with a safety margin. Then the removal cannot immediately
	// re-trip scale-out → NO deploy/delete flap by construction, and the trigger
	// point falls out of the load physics instead of a hand-tuned VyosLow.
	//   • busiest (CpuVyosReal), not pool-mean → a freshly-deployed idle node can't
	//     drag the signal down and trick us into deleting it (the v4.50 mean flap:
	//     run26 deploy/delete/deploy at ru3).
	//   • P90_60 → GAP-IMMUNE: a brief traffic gap (fill-capture / stage transition
	//     drops every node to ~0% for a few scrapes) sits in the bottom decile, so
	//     the 90th percentile ignores it → no gap-induced false "low" (the churn the
	//     old Avg30 + rising-slope patch were bolted on to fight).
	//   • projection vs VyosHigh → pressure/scale-out and scale-in share ONE basis
	//     and ONE threshold; the band is self-consistent.
	// A ramp-down's sustained drop pulls P90_60 down within ~60s, so the projection
	// crosses the line in pace (rd2 3→2, then cool 2→1) — exactly when the survivors
	// can absorb the load. DIRECTION_LOCK_VYOS + VyosScaleInCooldown remain backstops.
	// v4.62: project on the POOL MEAN, NOT the busiest node. The v4.53 busiest
	// (CpuVyosReal.P90_60) projection STUCK scale-in: during ramp-down one VyOS runs
	// hot from IMBALANCE (run36 rd2: busiest 46.6% while pool mean was 29.3%) → the
	// busiest projects high → reject → VyOS never released until cool (stuck at 3 the
	// whole run). But a hot busiest is a DISTRIBUTION problem (the rebalancer's job),
	// NOT a capacity one — whether the pool can drop a node depends on the TOTAL load,
	// i.e. the MEAN. mean × N/(N-1) = total/(N-1) is the post-removal per-node load if
	// the survivors rebalance (which they do). It is also REBOUND-FREE by construction:
	// total is conserved, so an idle just-added node can't drag it (no flap), and the
	// projection ≤ VyosHigh ensures the removal won't re-trip scale-out. Avg30 (not
	// P90_60) so it tracks the ramp-down drop in ~30s → 3→2 at rd2, 2→1 at rd3.
	if metricAvailable(f.PktRateUP) || metricAvailable(f.CpuVyosReal) {
		n := float64(s.VyosCount)
		if n < 2 {
			return false, "at min VyOS"
		}
		// v4.63: MEAN-dominant + LOW-weight MAX. Pure mean (v4.62) released the 2nd
		// VyOS too early (2→1 at rd2 not rd3): with N=2 the ×2 projection amplifies, so
		// the moment mean dips it cuts to 1. Adding 0.25·max (the busiest, which stays
		// elevated from ramp-down imbalance) adds just enough conservatism at the ×2
		// step to hold 2→1 until rd3, WITHOUT re-introducing the pure-max stuck problem
		// (mean still dominates at 0.75, so 3→2 at rd1 isn't blocked by one hot node).
		// v4.64: Robust60Raw (0.5·P90_60 + 0.3·Avg60 + 0.2·Now), NOT Avg30. A telegraf
		// SCRAPE GAP makes the VyOS CPU read 0 for a scrape or two (run39: C_vyos=0.00
		// mid-ramp-up during the deploy churn, when the real load was 1.2M); Avg30 fell
		// to ~0 on that → spurious DELETE right after a DEPLOY = the 2↔3 flap the user
		// saw. Robust60Raw is GAP-IMMUNE: the P90_60 term (weight 0.5) sits in the top
		// decile so it ignores the transient 0, while Now+Avg60 keep it responsive
		// enough to track a SUSTAINED ramp-down drop → scale in at rd2/rd3, not on a gap.
		// v4.71: project the THROUGHPUT-DOMINANT p.Vyos onto the N-1 survivors, so
		// scale-in and scale-out share one basis (no deploy/delete flap). The
		// throughput term is per-VyOS (PktRateUP/N); after one removal each survivor
		// forwards PktRateUP/(N-1) — recompute it at N-1. The cpu/loss terms (already
		// in p.Vyos) ride along as conservative corroborators (they don't drop in the
		// projection, so a hot busiest still adds caution at the ×N/(N-1) step that
		// holds 2→1 to rd3). Recomputing throughput at N-1 IS the rebound-free
		// projection: total pps is conserved, so an idle just-added node can't drag it.
		projThru := p.VyosThroughput
		if cfg.VyosThruCap > 0 && s.OfferedPPS > 0 {
			// v5.0.24 — demand-side projection: per-survivor combined (UL+DL)
			// load after removal = 2*offered/(n-1). Measured PktRateUP shrinks
			// when a delete blackholes traffic (smoke v2 chained 3->2->1 on
			// its own wake); sender-egress offered does not.
			projThru = norm(2*s.OfferedPPS/(n-1), cfg.VyosThruCap)
		} else if cfg.VyosThruCap > 0 && metricAvailable(f.PktRateUP) {
			// v4.88: BACK to the original Robust60Raw projection (the tuned VyOS scale-in
			// pacer). The v4.83-86 detours (max(Robust60Raw,Now)/P90_60/UEcount-demand)
			// were chasing the peak VyOS flap at the projection layer; the real cause was
			// the emergency override bypassing the direction lock (fixed above). Restoring
			// Robust60Raw restores the tuned 3→2→1 timing; the direction lock now blocks the
			// boundary/reload-dip rebound.
			projThru = norm(f.PktRateUP.Robust60Raw()/(n-1), cfg.VyosThruCap)
		}
		// v4.77: project the CPU term onto the N-1 survivors too (×N/(N-1)), exactly like
		// throughput — removing a node concentrates BOTH onto the survivors. Without this,
		// at PEAK 3 VyOS sat at ~50% CPU so p.Vyos≈0.38 and a delete looked safe, but the
		// 2 survivors then hit ~93% (p.Vyos≈0.63) → instant re-deploy = a 3→2→3 flap that
		// spiked peak p95 to 304ms (phaseF). Projecting CPU makes the guard SEE the
		// post-removal saturation and reject (peak projected 0.57 > 0.52). Ramp-down is
		// unaffected: at rd1 the genuinely-low CPU still projects below the line (0.435).
		// v4.79: ROBUST peak-rebound guard FIRST — throughput is vbash/scrape-immune, the
		// CPU term is NOT (phaseG peak: CPU read 10% vs real ~40% → projected stayed low →
		// spurious 3→2 → flap). If the survivors' per-node throughput alone would be high,
		// they'd re-saturate → reject regardless of CPU. Holds 3 at peak (projThru≈0.8),
		// allows ramp-down (rd1 projThru≈0.4).
		if cfg.VyosScaleInThruCeil > 0 && projThru > cfg.VyosScaleInThruCeil {
			return false, "delete would re-saturate survivors (throughput projects high)"
		}
		projCpu := clamp01(p.VyosCpu * n / (n - 1))
		projected := clamp01(0.5*projThru + 0.3*projCpu + 0.2*p.VyosLoss)
		if projected > cfg.VyosHigh*cfg.VyosInSafetyFrac {
			return false, "delete would re-trip scale-out (p.Vyos projects high)"
		}
	} else if metricAvailable(f.HhroVyosScore) {
		if f.HhroVyosScore.P95_300 > cfg.VyosLow {
			return false, "C_vyos not sustained low (fallback)"
		}
	} else if p.Vyos >= cfg.VyosLow {
		return false, "C_vyos not sustained low"
	}
	return true, ""
}
