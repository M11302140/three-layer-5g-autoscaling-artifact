package hbo

import "math"

// ComputePressure calculates independent NF pressure scores C_cp, C_up, C_vyos
// using robust window values. Falls back to simplified formulas when optional
// metrics are missing.
func ComputePressure(f FeatureSet, cfg Cfg, vyosCount, repUP int) PressureSet {
	var p PressureSet

	// --- C_cp ---
	// AMF has no resource limits, so CpuCP is in raw cores.
	// Normalize to [0,1] using CpCpuNorm.
	cpuCPNorm := cpuCPNormalized(f.CpuCP, cfg.CpCpuNorm)
	cpuCP := cpuCPNorm.Robust60()

	readyCPLoss := clamp01(1 - f.ReadyCP.Now)
	if f.ReadyCP.Missing {
		readyCPLoss = 0
	}

	// Simplified formula: 0.75 * cpu + 0.25 * (1 - ready)
	// PDU session rate/latency not available in Open5GS.
	p.CP = clamp01(0.75*cpuCP + 0.25*readyCPLoss)

	// --- C_up ---
	// v4.17 — MEAN-dominant blend. C_up is the POOL pressure level: it should
	// reflect whether the whole UPF pool is loaded, NOT whether one pod is hot.
	// A single hot pod with idle peers is an IMBALANCE (fixed by redistributing
	// UEs), not a capacity shortage (fixed by scale-out) — and scaling out on a
	// transient single-pod spike (e.g. right after a scale-in's rehome
	// concentrates sessions) drove a scale-in→out limit cycle at the
	// direction-lock period (v4.16). Weighting mean catches "pool full" while
	// de-emphasising the lone-hot-pod transient. The hottest pod still carries
	// 0.30 so genuine pool-wide saturation isn't under-read. Scale-OUT now keys
	// off MeanCpuUP (UpMeanHigh in bottleneck), so this no longer hides capacity
	// need — it removes the false one-pod trigger that caused the rebound.
	// v4.70 — THROUGHPUT-DOMINANT, noise-robust pressure (replaces the v4.63 6-term
	// CPU+trend blend). Goal: let the FREEZE retire. The old blend leaned on CPU
	// (noisy during UE migration: P_up swung 0.31↔0.85 at 8-16 UE) so the daemon had
	// to be frozen during migration to avoid spurious scale-out. The new score is:
	//   p.UP = 0.5·throughput + 0.3·cpu + 0.2·drop_score
	// • throughput = max(pps_util, bw_util), per-UPF, Robust60Raw (P90-blend) → a
	//   migration's transient RX dip sits in the bottom decile and is ignored. This
	//   smooth offered-load signal DOMINATES, so CPU noise (w2) can't flip the call.
	//   UPF is pps-bound at small frames; bw_util binds only if the packet mix grows.
	// • cpu = the existing mean-dominant CPU blend (corroborating, lower weight).
	// • drop_score = exp(K·SUSTAINED_drop_ratio)-1. SUSTAINED (P90_60 ratio), NOT
	//   instantaneous — a migration's brief drop spike can't detonate it; only real
	//   persistent congestion does, and then the exponential dominates the sum →
	//   emergency scale-out even though w3 is the smallest weight.
	cpuUP := 0.3*f.CpuUP.Robust60() + 0.7*f.MeanCpuUP.Robust60()
	if f.MeanCpuUP.Missing {
		cpuUP = f.CpuUP.Robust60()
	}

	// v4.70: throughput per-UPF, Robust60Raw (the metric is already a rate[1m] so a
	// 30s window adds little). Cap is BIDIRECTIONAL (PktRateUP = rx+tx ≈ 2.2× offered),
	// so UpPressurePpsCap is the per-UPF rx+tx saturation, NOT the unidirectional 200k.
	ppsUtil := float64(0)
	if metricAvailable(f.PktRateUP) && repUP > 0 && cfg.UpPressurePpsCap > 0 {
		ppsUtil = norm(f.PktRateUP.Robust60Raw()/float64(repUP), cfg.UpPressurePpsCap)
	}
	bwUtil := float64(0)
	if metricAvailable(f.BwUP) && repUP > 0 && cfg.UpPressureBwCap > 0 {
		bwUtil = norm(f.BwUP.Robust60Raw()/float64(repUP), cfg.UpPressureBwCap)
	}
	throughput := ppsUtil
	if bwUtil > throughput {
		throughput = bwUtil
	}

	// sustained drop RATIO = drops / (drops + received); robust windows on both.
	dropRatio := float64(0)
	if cfg.EupfMode {
		// eupf mode: DropUP is already a prometheus-side ratio in [0,1]
		// (see eupfQuerySet) — counter-reset epochs never mix in the window.
		if metricAvailable(f.DropUP) {
			dropRatio = clamp01(f.DropUP.P90_60)
		}
	} else if metricAvailable(f.DropUP) && metricAvailable(f.PktRateUP) {
		rx := f.PktRateUP.Robust60Raw()
		dr := f.DropUP.P90_60
		if rx+dr > 0 {
			dropRatio = dr / (rx + dr)
		}
	}
	dropScore := math.Exp(cfg.UpDropExpK*dropRatio) - 1
	// v4.70 ⑥ BALANCE-FIRST: drops only drive scale-OUT when the POOL is genuinely
	// saturated (throughput high). When throughput is only moderate yet drops exist,
	// the congestion is an IMBALANCE (one hot UPF with idle peers) — adding a UPF
	// won't help; the rebalancer (experiment: migrate ≤2 sessions, re-judge) fixes it.
	// Gate the drop term on throughput so an imbalance can't spuriously trigger a
	// scale-out. At genuine under-provision throughput is clamped to 1.0 → gate=1.0,
	// so the drop emergency still fires full when really needed.
	dropGate := clamp01((throughput - 0.7) / 0.3)
	dropScore *= dropGate

	if metricAvailable(f.PktRateUP) {
		p.UP = clamp01(0.5*throughput + 0.3*cpuUP + 0.2*dropScore)
	} else {
		// no throughput metric available — fall back to CPU-dominant (+ drop emergency).
		p.UP = clamp01(0.8*cpuUP + 0.2*dropScore)
	}
	p.UpThroughput = throughput
	p.UpCpu = cpuUP
	p.UpDrop = dropScore

	// --- C_vyos ---
	// VyOS forwards ALL UPF data-plane traffic, but its own NIC counter is the
	// SR-IOV VF (passthrough) which KubeVirt's vmi_network metric can't see
	// (reads ~0 at any load). So derive the per-VyOS load from the aggregate
	// UPF packet rate (container_network metrics ARE visible) divided by the
	// VyOS pool size — the sender distributes UPF externalIP routes across the
	// pool, so total UPF pps / vyos_count ≈ what each VyOS forwards.
	if vyosCount < 1 {
		vyosCount = 1
	}
	imbalance := float64(0)
	if metricAvailable(f.VyosImbalance) {
		imbalance = norm(f.VyosImbalance.Now, cfg.VyosImbalanceNorm)
	}

	// v4.76 — THROUGHPUT-DOMINANT VyOS pressure, mirroring the UPF score EXACTLY
	// (per the user's design): p.Vyos = 0.5·throughput + 0.3·cpu + 0.2·loss_score.
	// THROUGHPUT is the primary, leading, vbash-immune, node-count-aware signal; CPU and
	// loss are the 2nd/3rd lines of insurance (same role as in p.UP).
	// • throughput = per-VyOS forwarded pps (PktRateUP/vyos_count), Robust60Raw, norm by
	//   VyosThruCap. Dividing by vyos_count is what separates the stages (1 VyOS@16UE→~1.0
	//   deploy; 2 VyOS@16UE→~0.5 hold; 2 VyOS@24UE→~0.75 deploy). VyosThruCap=1.8M from
	//   real data: 1 VyOS saturates (CPU 85-99%) at 16 UE where PktRateUP≈1.8M bidirectional.
	// • cpu = pool-MEAN real telegraf CPU via AVG60 (NOT Robust60Raw): the VyOS guest CPU
	//   spikes instantaneously when the route rebalancer runs vbash, and Robust60Raw's
	//   P90_60 term (weight 0.5) would re-admit those spikes. Avg60 (pure 60s mean) averages
	//   vbash out. Pool-MEAN (not busiest) so a lone hot node = rebalancer's job, not a +node.
	// • loss_score = exp(K·SUSTAINED_loss_ratio)-1, ratio on P90_60 (robust) so a MIGRATION
	//   transient drop can't detonate it — only sustained congestion. Gated balance-first
	//   (dropGate): drops only count once throughput is genuinely high, else a low-load drop
	//   is an imbalance the rebalancer fixes, not a capacity add. Mirrors p.UP's dropScore.
	// p.Vyos drives scale-out (predictive + slow reactive) AND scale-in (VyosSafeToDelete
	// projection) — one basis, flap-free.
	vyThru := float64(0)
	if metricAvailable(f.PktRateUP) && cfg.VyosThruCap > 0 {
		// v4.80: use .Now, NOT Robust60Raw. PktRateUP is ALREADY a rate[1m] (1-min smoothed),
		// so a 60s robust window stacks ANOTHER ~60s on top → double-lag (~60-90s): phaseH
		// 1→2 fired 30s+ AFTER 16 UE arrived → single VyOS saturated → ru2 p95 198ms.
		// VERIFIED against prom: a 30s robust window (Robust30) only leads Robust60 by 1-5%
		// (the rate[1m] dominates), but .Now leads by 10-24% — and .Now here is the CURRENT
		// value of a 1-min-smoothed rate (NOT a spiky instantaneous gauge), so it's safe;
		// throughput is UPF packet counters (vbash-IMMUNE). Leads the ramp so the 2nd VyOS
		// boots before saturation. Scale-IN keeps its own Robust60Raw projection (guards.go).
		vyThru = norm(f.PktRateUP.Now/float64(vyosCount), cfg.VyosThruCap)
	}
	vyCpu := float64(0)
	if metricAvailable(f.MeanCpuVyosReal) {
		vyCpu = norm(f.MeanCpuVyosReal.Avg60, cfg.VyosCpuNorm)
	} else if metricAvailable(f.CpuVyosReal) {
		vyCpu = norm(f.CpuVyosReal.Avg60, cfg.VyosCpuNorm)
	}
	vyDropRatio := float64(0)
	if metricAvailable(f.VyosDropErr) && metricAvailable(f.PktRateUP) {
		rx := f.PktRateUP.Robust60Raw() / float64(vyosCount)
		dr := f.VyosDropErr.P90_60
		if rx+dr > 0 {
			vyDropRatio = dr / (rx + dr)
		}
	}
	vyLoss := math.Exp(cfg.VyosDropExpK*vyDropRatio) - 1
	// balance-first gate (mirror p.UP): loss only drives scale-out when the pool is
	// genuinely saturated (throughput high); a low-throughput drop is an imbalance.
	vyLoss *= clamp01((vyThru - 0.7) / 0.3)

	if cfg.EupfEnabled {
		// v5.0 — the telegraf CPU signal is DEAD under the 1-worker VPP config:
		// DPDK poll mode pins the worker core at 100% regardless of load
		// (measured: cpu-total busy identical at idle and at 4.8M). Keeping the
		// CPU term would add a CONSTANT ~0.26 floor to p.Vyos (34.7/40 × 0.3)
		// and break both the scale-out level and the scale-in projection.
		// Throughput (now sourced from Σ upf_xdp_tx = combined UL+DL) carries
		// the score; the loss term stays as the emergency corroborator.
		vyCpu = 0
		p.Vyos = clamp01(0.8*vyThru + 0.2*vyLoss)
	} else if metricAvailable(f.PktRateUP) || metricAvailable(f.CpuVyosReal) {
		p.Vyos = clamp01(0.5*vyThru + 0.3*vyCpu + 0.2*vyLoss)
	} else {
		// Last resort: kubevirt vCPU (undercounts SR-IOV forwarding).
		p.Vyos = clamp01(0.85*f.CpuVyos.Robust60() + 0.15*imbalance)
	}
	p.VyosThroughput = vyThru
	p.VyosCpu = vyCpu
	p.VyosLoss = vyLoss

	return p
}
