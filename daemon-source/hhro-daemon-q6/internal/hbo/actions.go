package hbo

// EnumerateFeasibleActions returns all actions that pass cooldown, resource
// bounds, and capacity checks.
func EnumerateFeasibleActions(s SystemState, timers *Timers, cfg Cfg) []Action {
	actions := []Action{ActNone}

	// Capacity must be PER-WORKER on a UPF-schedulable node (MaxWorkerFreeCpuM
	// excludes the infra node): the aggregate WorkerFreeCpuM counts worker-0's
	// free CPU, where UPF clones can never schedule, so scale-out passed the
	// capacity check and stranded upf-5/6 Pending for an hour (v44 attempt 3).
	hasCapacity := s.MaxWorkerFreeCpuM >= float64(cfg.MinFreeCpuM) &&
		s.WorkerFreeMemMiB >= float64(cfg.MinFreeMemMiB) &&
		s.PodPendingCount == 0 &&
		!s.NodePressure

	// CP
	if !timers.CooldownActive(ActScaleOutCP) {
		if s.RepCP < cfg.MaxCP && hasCapacity {
			actions = append(actions, ActScaleOutCP)
		}
	}
	if !timers.CooldownActive(ActScaleInCP) {
		if s.RepCP > cfg.MinCP {
			actions = append(actions, ActScaleInCP)
		}
	}

	// UPF
	// v4.64: scale-OUT must honour the direction-lock too. It only checked the
	// cooldown, so after a ramp-down scale-IN it could re-trip ~60s later → flap
	// (run38 8↔7 every ~60s): removing a UPF raises the survivors' per-UPF
	// throughput → the v4.63 throughput-inclusive C_up rises → BN_UPF → scale-out,
	// undoing the scale-in. The 300s create↔delete lock (already enforced on
	// scale-IN) now also gates scale-OUT, so a just-done scale-in can't be reversed.
	if !timers.CooldownActive(ActScaleOutUP) {
		if blocked, _ := timers.DirectionLockBlocks(ActScaleOutUP); !blocked {
			if s.RepUP < cfg.MaxUP && hasCapacity {
				actions = append(actions, ActScaleOutUP)
			}
		}
	}
	if !timers.CooldownActive(ActScaleInUP) {
		if s.RepUP > cfg.MinUP {
			actions = append(actions, ActScaleInUP)
		}
	}

	// VyOS — NOT a mid-loop (utility) action. v4.55: VyOS is a VM, not a CNF pod;
	// its whole lifecycle (deploy AND delete) belongs to the SLOW loop alongside the
	// other VM layer (workers), so it is decided ONLY in DecideSlow (deploy at
	// p.Vyos≥VyosHigh, delete via VyosSafeToDelete). Leaving DeployVyOS in the
	// mid-loop feasible set let it fire every 30s (gated only by the 120s cooldown,
	// not the 180s slow tick) → two deploys could land in one ramp stage (run28
	// 1→2→3 both at ru2). VM boot takes minutes, so the mid-loop "responsiveness"
	// was illusory anyway; slow-loop-only gives clean 180s spacing (ru2 then ru3).

	// Worker. CREATE_WORKER is only FEASIBLE when a new worker would actually
	// be USED: a UPF replica can still be added (RepUP<MaxUP) AND no existing
	// worker can host it (per-worker headroom, not aggregate) AND nothing is
	// already booting (VM-level: a created-but-not-yet-joined VM is invisible
	// to k8s node counts). This path previously checked only cooldown, which
	// re-created a worker every ~5min while the Harvester disk could not fit
	// it (worker-3..7 ErrorUnschedulable cascade, 2026-06-11).
	if !timers.CooldownActive(ActCreateWorker) {
		// A new worker is useful when another UPF could still be added OR when
		// UPF pods are already stranded Pending (deploys at MaxUP with nowhere
		// to schedule — requiring RepUP<MaxUP here deadlocked that recovery:
		// rep counts deployments, not running pods).
		needsHome := s.RepUP < cfg.MaxUP || s.PodPendingCount > 0
		if s.WorkerCount < cfg.MaxWorkers &&
			needsHome &&
			s.MaxWorkerFreeCpuM < float64(cfg.MinFreeCpuM) &&
			s.WorkerCount <= s.ReadyWorkers &&
			s.WorkerVMCount <= s.ReadyWorkers {
			actions = append(actions, ActCreateWorker)
		}
	}
	if !timers.CooldownActive(ActDeleteWorker) {
		if s.WorkerCount > cfg.MinWorkers {
			actions = append(actions, ActDeleteWorker)
		}
	}

	// Rebalance
	if cfg.RebalanceEnabled {
		if !timers.CooldownActive(ActRebalanceUPF) {
			actions = append(actions, ActRebalanceUPF)
		}
		if !timers.CooldownActive(ActRebalanceVy) {
			actions = append(actions, ActRebalanceVy)
		}
	}

	return actions
}

// HasWorkerCapacity checks if a UPF-schedulable worker can fit a new CNF pod
// (per-worker headroom, infra node excluded — see hasCapacity above).
func HasWorkerCapacity(s SystemState, cfg Cfg) bool {
	return s.MaxWorkerFreeCpuM >= float64(cfg.MinFreeCpuM) &&
		s.WorkerFreeMemMiB >= float64(cfg.MinFreeMemMiB) &&
		s.PodPendingCount == 0 &&
		!s.NodePressure
}
