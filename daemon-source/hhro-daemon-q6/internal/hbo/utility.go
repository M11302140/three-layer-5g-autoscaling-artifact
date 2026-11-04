package hbo

// SelectActionByUtility scores every feasible action and returns the best one.
// Returns ActNone if no action exceeds MinActionGain.
func SelectActionByUtility(actions []Action, bn Bottleneck, risk RiskSet, s SystemState, f FeatureSet, p PressureSet, cfg Cfg) (Action, ActionUtility) {
	var bestAct Action = ActNone
	var bestUtil ActionUtility

	for _, a := range actions {
		u := scoreAction(a, bn, risk, s, f, p, cfg)
		if u.Utility > bestUtil.Utility {
			bestUtil = u
			bestAct = a
		}
	}

	if bestUtil.Utility < cfg.MinActionGain {
		return ActNone, ActionUtility{Action: ActNone}
	}
	return bestAct, bestUtil
}

func scoreAction(a Action, bn Bottleneck, risk RiskSet, s SystemState, f FeatureSet, p PressureSet, cfg Cfg) ActionUtility {
	sloGain := estimateSLOGain(a, bn, risk, s, f, p, cfg)
	infraCost := estimateInfraCost(a, s, cfg)
	churnCost := estimateChurnCost(a, s, cfg)
	mismatch := bottleneckMismatchCost(a, bn, cfg)
	disruption := estimateDisruptionCost(a, s, cfg)

	u := sloGain -
		cfg.LambdaCost*infraCost -
		cfg.LambdaChurn*churnCost -
		cfg.LambdaWrong*mismatch -
		cfg.LambdaDisrupt*disruption

	return ActionUtility{
		Action:         a,
		Utility:        u,
		SLOGain:        sloGain,
		InfraCost:      infraCost,
		ChurnCost:      churnCost,
		MismatchCost:   mismatch,
		DisruptionCost: disruption,
	}
}

func estimateSLOGain(a Action, bn Bottleneck, risk RiskSet, s SystemState, f FeatureSet, p PressureSet, cfg Cfg) float64 {
	switch a {
	case ActScaleOutCP:
		if bn == BNCP || bn == BNMixed {
			// gain = current severity (reactive) + forecast risk (proactive).
			// Severity ensures a sustained-high-but-stable bottleneck still
			// fires even when slope (→risk) is near zero.
			sev := clamp01(p.CP - cfg.CpHigh)
			return (sev + risk.CP) * cfg.EtaCP
		}
		return 0

	case ActScaleOutUP:
		if bn == BNUPF || bn == BNMixed {
			sev := clamp01(p.UP - cfg.UpHigh)
			// Single-thread saturation: the composite C_up plateaus ≈0.5 below
			// UpHigh while the hottest pod is pinned at its effective cap, so
			// composite severity reads 0 and the flat-gain REBALANCE_UPF wins
			// every tick (a no-op livelock that starves scale-out). Mirror the
			// bottleneck cpu trigger: severity is also how far sustained
			// per-pod cpu sits past UpCpuHigh, normalized to the remaining
			// headroom (pinned pod → 1.0).
			if cfg.UpCpuHigh < 1 {
				cpuSev := clamp01((f.CpuUP.P90_60 - cfg.UpCpuHigh) / (1 - cfg.UpCpuHigh))
				if cpuSev > sev {
					sev = cpuSev
				}
			}
			return (sev + risk.UP) * cfg.EtaUP
		}
		return 0

	case ActDeployVyOS:
		if bn == BNVyos || bn == BNMixed {
			sev := clamp01(p.Vyos - cfg.VyosHigh)
			return (sev + risk.Vyos) * cfg.EtaVyos
		}
		return 0

	case ActCreateWorker:
		if bn == BNInfra {
			return cfg.EtaWorker
		}
		if (risk.CP > cfg.RiskHigh || risk.UP > cfg.RiskHigh) &&
			s.WorkerFreeCpuM < float64(cfg.MinFreeCpuM) {
			return cfg.EtaWorkerPrepare
		}
		return 0

	case ActRebalanceUPF:
		if (bn == BNUPF || bn == BNMixed) && s.RepUP > 1 {
			// v4.82: gain PROPORTIONAL to real pool imbalance (hottest pod above the
			// mean), not a flat constant. The flat EtaRebalance won EVERY tick whenever
			// bn==BN_UPF — including a BALANCED ramp-down, where it starved the
			// progressive SCALE_IN_UP (the daemon kept "rebalancing" an already-even
			// pool instead of shedding a UPF → stuck at 8 until full idle). CpuUP=max-pod,
			// MeanCpuUP=pool-mean → their gap IS the imbalance; even pool → gain→0 so
			// scale-in (below) wins. A genuine hot pod still earns the rebalance.
			imbal := float64(1)
			if cfg.UpfImbalanceHigh > 0 {
				imbal = clamp01((f.CpuUP.Robust60() - f.MeanCpuUP.Robust60()) / cfg.UpfImbalanceHigh)
			}
			return cfg.EtaRebalance * imbal
		}
		return 0

	case ActRebalanceVy:
		if (bn == BNVyos || bn == BNMixed) && s.VyosCount > 1 {
			imbal := float64(1)
			if metricAvailable(f.VyosImbalance) && cfg.VyosImbalanceHigh > 0 {
				imbal = clamp01(f.VyosImbalance.Avg60 / cfg.VyosImbalanceHigh)
			}
			return cfg.EtaRebalance * imbal
		}
		return 0

	case ActScaleInCP, ActDeleteVyOS, ActDeleteWorker:
		if bn == BNNone {
			return cfg.EtaCostSaving
		}
		return 0

	case ActScaleInUP:
		// v4.82: earn cost-saving gain during RAMP-DOWN too, not only at full idle
		// (bn==BNNone). During ramp-down bn stays BN_UPF (load still moderate), so the
		// old BNNone-only gate let the flat-gain REBALANCE_UPF win every tick → the UPF
		// pool was stuck at 8 through rd1/rd2 and only collapsed all-at-once at idle,
		// instead of pacing down rd1→7, rd2→4, rd3→2. The ShouldScaleInUP guard (applied
		// AFTER selection in ApplyStabilityGuards) is the real safety net: it blocks the
		// scale-in unless the load genuinely fits on N-1 (max(Avg60,Now)/(N-1) < cap), so
		// allowing the gain at BN_UPF CANNOT cause a peak rebound — at peak the guard
		// fails on the high instantaneous load. Pairs with the imbalance-scaled
		// REBALANCE_UPF gain above so a balanced pool yields to scale-in.
		if bn == BNNone || bn == BNUPF {
			return cfg.EtaCostSaving
		}
		return 0

	case ActNone:
		return 0
	}
	return 0
}

func estimateInfraCost(a Action, s SystemState, cfg Cfg) float64 {
	switch a {
	case ActScaleOutCP, ActScaleOutUP:
		return 0.1
	case ActDeployVyOS:
		return 0.3
	case ActCreateWorker:
		return 0.5
	case ActScaleInCP, ActScaleInUP:
		return -0.1
	case ActDeleteVyOS:
		return -0.3
	case ActDeleteWorker:
		return -0.5
	case ActRebalanceUPF, ActRebalanceVy:
		return 0.0
	}
	return 0
}

func estimateChurnCost(a Action, s SystemState, cfg Cfg) float64 {
	switch a {
	// Scale-OUT churn is low — reacting to SLO pressure should be cheap.
	// Scale-IN churn is higher — releasing resources must be conservative.
	case ActScaleOutCP:
		return 0.05
	case ActScaleOutUP:
		return 0.05
	case ActDeployVyOS:
		return 0.10
	case ActScaleInCP:
		return 0.2
	case ActScaleInUP:
		return 0.3
	case ActDeleteVyOS:
		return 0.5
	case ActCreateWorker, ActDeleteWorker:
		return 0.7
	case ActRebalanceUPF:
		return 0.4
	case ActRebalanceVy:
		return 0.2
	}
	return 0
}

func bottleneckMismatchCost(a Action, bn Bottleneck, cfg Cfg) float64 {
	switch bn {
	case BNCP:
		switch a {
		case ActScaleOutCP:
			return 0
		case ActCreateWorker:
			return 0.2
		default:
			if a.IsScaleIn() {
				return 0.1
			}
			return 1.0
		}

	case BNUPF:
		switch a {
		case ActScaleOutUP, ActRebalanceUPF:
			return 0
		case ActCreateWorker:
			return 0.2
		default:
			if a.IsScaleIn() {
				return 0.1
			}
			return 1.0
		}

	case BNVyos:
		switch a {
		case ActDeployVyOS, ActRebalanceVy:
			return 0
		default:
			if a.IsScaleIn() {
				return 0.1
			}
			return 1.0
		}

	case BNInfra:
		switch a {
		case ActCreateWorker:
			return 0
		default:
			if a.IsScaleIn() {
				return 0.1
			}
			return 1.0
		}

	case BNMixed:
		return 0.2

	case BNNone:
		switch {
		case a == ActNone:
			return 0
		case a.IsScaleIn():
			return 0.1
		default:
			return 0.8
		}
	}
	return 0
}

func estimateDisruptionCost(a Action, s SystemState, cfg Cfg) float64 {
	switch a {
	case ActScaleOutCP, ActScaleOutUP:
		return 0.0
	case ActDeployVyOS:
		return 0.1
	case ActCreateWorker:
		return 0.1
	case ActScaleInCP:
		return 0.2
	case ActScaleInUP:
		return 0.3
	case ActDeleteVyOS:
		return 0.5
	case ActDeleteWorker:
		return 0.8
	case ActRebalanceUPF:
		return 0.4
	case ActRebalanceVy:
		return 0.1
	}
	return 0
}
