package hbo

import (
	"fmt"
	"math"
	"time"
)

// HPAState implements the Kubernetes HPA control law exactly as analyzed in
// Nguyen et al., "Properties of Horizontal Pod Autoscaling Algorithms and
// Application for Scaling Cloud-Native Network Functions" — applied to the
// eUPF (CNF) slot pool. Baseline B3 (VNF static) / B4 (VNF via DASA).
//
//	desired = ceil(cur * currentMetric / targetMetric)
//
// with the stock algorithm properties the paper studies:
//   - tolerance band: no action while |ratio-1| <= tol (default 0.10)
//   - sync period:    caller ticks Step() every HPA_SYNC (default 15s)
//   - scale-down stabilization: the effective desired is the MAX of the raw
//     desired values seen over the trailing window (default 300s) — scale-up
//     applies immediately, scale-down waits out the window (K8s default
//     behaviour: stabilizationWindowSeconds=300 down / 0 up)
//
// The metric is per-slot active PDU sessions (custom metric — the paper's
// algorithm is metric-agnostic; sessions are the natural CNF load unit and
// the same signal class HHRO's CNF layer consumes: a best-case, no-strawman
// baseline). Actuation is delegated to the caller and uses the SAME graceful
// primitives as HHRO (relief on out, drain-verify on in): all baselines share
// the actuation layer and differ ONLY in the scaling decision.
type HPAState struct {
	Tol        float64       // tolerance band, default 0.10
	Target     float64       // target sessions per slot (utilization target)
	Min, Max   int           // replica clamp
	DownWindow time.Duration // scale-down stabilization window

	hist []hpaSample // raw desired history for the stabilization window
}

type hpaSample struct {
	at  time.Time
	des int
}

// Step consumes the current replica count and the average metric per ACTIVE
// replica, and returns the effective desired replica count plus a log line.
func (h *HPAState) Step(now time.Time, cur int, avgSess float64) (int, string) {
	if cur < 1 {
		cur = 1
	}
	raw := cur
	ratio := 0.0
	if h.Target > 0 {
		ratio = avgSess / h.Target
	}
	// tolerance band: inside it the raw desired is the current count
	if math.Abs(ratio-1) > h.Tol {
		raw = int(math.Ceil(float64(cur) * ratio))
	}
	if raw < h.Min {
		raw = h.Min
	}
	if raw > h.Max {
		raw = h.Max
	}

	// record raw desired; effective scale-down = max over trailing window
	h.hist = append(h.hist, hpaSample{at: now, des: raw})
	cut := now.Add(-h.DownWindow)
	i := 0
	for ; i < len(h.hist) && h.hist[i].at.Before(cut); i++ {
	}
	h.hist = h.hist[i:]

	eff := raw
	if raw < cur { // scale-down: stabilize
		for _, s := range h.hist {
			if s.des > eff {
				eff = s.des
			}
		}
		if eff > cur {
			eff = cur // stabilization never causes an up-move
		}
	}
	reason := fmt.Sprintf("HPA avg=%.2f target=%.2f ratio=%.2f cur=%d raw=%d eff=%d (tol=%.2f win=%s)",
		avgSess, h.Target, ratio, cur, raw, eff, h.Tol, h.DownWindow)
	return eff, reason
}
