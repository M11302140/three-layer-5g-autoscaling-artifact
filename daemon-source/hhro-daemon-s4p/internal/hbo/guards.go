package hbo

import "fmt"

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

//
//
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
