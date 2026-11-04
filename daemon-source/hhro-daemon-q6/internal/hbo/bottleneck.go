package hbo

// ClassifyBottleneck determines the dominant system bottleneck using NF
// pressure scores, trend evidence, and infrastructure state.
func ClassifyBottleneck(f FeatureSet, p PressureSet, s SystemState, cfg Cfg) Bottleneck {
	highCP := p.CP >= cfg.CpHigh
	// v4.17 — scale-out fires on POOL-wide load (mean per-pod), NOT a single hot
	// pod. The old `CpuUP.P90_60 >= UpCpuHigh` (hottest pod ≥90% of a core) fired
	// scale-out for an IMBALANCE the daemon can't fix by scaling (it can't move
	// existing UEs): right after a scale-in rehome concentrated sessions on one
	// pod, that pod spiked → scale-out → scale-in→out limit cycle at the
	// direction-lock period (v4.16). Mean ≥ UpMeanHigh means EVERY pod is loaded
	// → no idle peer to absorb → genuine capacity need → scale out. One hot pod
	// + low mean → NONE (the experiment redistributes UEs after real scale
	// events). C_up is now mean-dominant too, so p.UP itself tracks the pool.
	// v4.41 — a composite p.UP ≥ UpHigh must be backed by actual CPU load to count
	// as a UPF scale-out trigger. Otherwise a migration/rehome packet-DROP spike
	// (dropUP term) alone pushes p.UP past UpHigh while the pods are CPU-idle
	// (cpu < idle_floor) → spurious ramp-down rebound scale-out (run14f: up_cpu=0.42,
	// drop=1608 → p.UP=0.57 → scale-out 7→8). Drop still counts (sustained drops with
	// load = real congestion), it just can't trigger scale-out on its own when idle.
	// v4.48: NOT-FALLING gate — fixes the ramp-down rebound (run15: UPF 7→8, and
	// the VyOS layer would re-expand while load was dropping). The scale-out
	// triggers read a LAGGING Robust60 (0.5·P90_60 + …) that keeps reading high
	// for ~60s after load starts falling; on its own it fired a spurious rebound
	// scale-out at a ramp-down stage transition (tx still 518k→400k, falling).
	// Require the INSTANTANEOUS reading (Now) to confirm the lagging window —
	// i.e. Now within ~15% of Robust60. RISING load: Now ≥ Robust60 → ratio ≥1 →
	// passes with NO delay (when Robust60 finally crosses the level, Now already
	// has). FALLING load: Now drops below the lagging window → ratio <0.85 →
	// scale-out suppressed → bn falls to BN_NONE sooner, which also un-blocks
	// scale-in. Ratio form is UNIT-ROBUST: PromQL deriv is per-second, so ramp
	// slopes (~0.0015/s) never clear the 0.005 slope threshold — a slope gate
	// would silently never trip. Missing metric ⇒ Robust60≈0 ⇒ ratio guard moot.
	// v4.70: not-falling gate on THROUGHPUT (the new dominant pressure signal), not
	// CPU. p.UP is now throughput-dominant + noise-robust (SUSTAINED drop, Robust60Raw
	// throughput), so the old cpuActiveUP floor and the MeanCpuUP≥UpMeanHigh CPU bypass
	// are removed — scale-out keys off p.UP alone. Falling THROUGHPUT (ramp-down) pulls
	// Now below the lagging window → suppresses rebound scale-out (same anti-rebound
	// role the CPU not-falling gate had, on the cleaner signal).
	// v4.89: gate on Avg30, NOT Now. The single-scrape Now is fooled by a TRANSIENT
	// PktRateUP spike during ramp-down/cool churn (a scale-in's rehome/TRex reload
	// recovery briefly bursts pps) → Now≥0.85·Robust60Raw reads not-falling for one
	// tick → BN_UPF → a spurious 2→3 scale-out near cool (then 3→2→1 = the rebound),
	// and the drop-spike from that same churn flips emergency=true so it even slips the
	// 300s direction lock. Avg30 (30s mean) ignores a one-scrape burst but still rises
	// within 30s on a real ramp-UP, so ramp-up scale-out is unaffected; on ramp-down
	// Avg30 sits below the lagging Robust60Raw → not-falling=false → no rebound.
	upNotFalling := !metricAvailable(f.PktRateUP) || f.PktRateUP.Avg30 >= 0.85*f.PktRateUP.Robust60Raw()
	highUP := p.UP >= cfg.UpHigh && upNotFalling
	// v4.76: VyOS scale-out keys off the THROUGHPUT-DOMINANT p.Vyos alone (the user's
	// design). The node-count-aware throughput term self-separates the stages, so no
	// CPU-confirm gate is needed (the v4.71-75 detour). NOT-falling uses the THROUGHPUT
	// (UPF pps, vbash-immune) — falling offered load (ramp-down) suppresses rebound,
	// exactly like highUP. (CPU is the 0.3 corroborator INSIDE p.Vyos, not a gate here.)
	vyNotFalling := !metricAvailable(f.PktRateUP) || f.PktRateUP.Avg30 >= 0.85*f.PktRateUP.Robust60Raw() // v4.89: Avg30 not Now (transient-spike-immune, see upNotFalling)
	highVyos := p.Vyos >= cfg.VyosHigh && vyNotFalling

	risingCP := f.CpuCP.Slope120 > cfg.CpSlopeHigh

	// Step 1: Infra bottleneck — highest priority.
	// infraLack = "cannot PLACE another UPF", a SCHEDULABILITY question, not a
	// busy-ness one: per-worker request headroom (emptiest schedulable worker
	// can't fit a 1500m UPF) or pods already pending. Node CPU UTILIZATION is
	// deliberately NOT here — a worker at 90% CPU (3 hot single-thread UPFs)
	// still has request-room by k8s, and including it made bn=INFRA dominate
	// the whole loaded run (v4.13), masking UPF/VyOS and poisoning ScaleOutUP's
	// utility. The 3-UPF/node physical cap is enforced by request sizing
	// (1500m × 4 > 6-core, and MIN_FREE_CPU_M=1700 rejects the 4th), not here.
	infraLack := s.MaxWorkerFreeCpuM < float64(cfg.MinFreeCpuM) ||
		s.WorkerFreeMemMiB < float64(cfg.MinFreeMemMiB) ||
		s.PodPendingCount >= cfg.PodPendingHigh

	if infraLack && (highCP || highUP) {
		return BNInfra
	}

	// Step 2: VyOS bottleneck — transport layer checked before CNFs.
	// p.Vyos is throughput-dominant (v4.76+): crossing VyosHigh IS the evidence,
	// no separate iface/drop corroboration needed (the old evidence disjunct was
	// short-circuited by `|| highVyos` anyway — removed as dead code).
	if highVyos {
		if highUP || highCP {
			return BNMixed
		}
		return BNVyos
	}

	// Step 3: UPF bottleneck.
	// v4.70: highUP keys off the throughput-dominant p.UP (pool-wide by
	// construction — a single hot pod can't raise it), so crossing UpHigh is
	// sufficient evidence on its own.
	if highUP {
		if highVyos || highCP {
			return BNMixed
		}
		return BNUPF
	}

	// Step 4: CP bottleneck
	if highCP {
		cpuCPNorm := cpuCPNormalized(f.CpuCP, cfg.CpCpuNorm)
		cpEvidence := risingCP ||
			(metricAvailable(f.ReadyCP) && f.ReadyCP.Now < cfg.ReadyMin) ||
			cpuCPNorm.P90_60 >= cfg.CpHigh

		if cpEvidence {
			if highUP || highVyos {
				return BNMixed
			}
			return BNCP
		}
	}

	// Step 5: Multiple NFs near-high → BN_MIXED as early risk
	nearHighCount := 0
	if p.CP >= 0.90*cfg.CpHigh {
		nearHighCount++
	}
	if p.UP >= 0.90*cfg.UpHigh {
		nearHighCount++
	}
	if p.Vyos >= 0.90*cfg.VyosHigh {
		nearHighCount++
	}
	if nearHighCount >= 2 {
		return BNMixed
	}

	return BNNone
}
