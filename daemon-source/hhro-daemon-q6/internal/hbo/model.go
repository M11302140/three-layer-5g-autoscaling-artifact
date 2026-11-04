package hbo

import (
	"math"

	"github.com/anon/hhro-daemon/internal/envcfg"
)

// model.go — v6 chain loss model. Pure functions, no side effects, no I/O.
// Spec: docs/proposals/v6-model-based-pseudocode.md §1-§3.

// V6Config is the discrete system configuration the planner reasons over.
// CP is NOT part of the data chain (control plane) and keeps its trivial
// threshold rule outside the planner — the SFC chain is VY → UP.
type V6Config struct {
	NUP int // active eUPF slots
	NVY int // active VyOS instances
	NWK int // worker VMs (2 slots each; hosts NUP)
}

// Residuals are the online additive curve corrections (§3): one first-order
// offset per chain layer, EWMA-updated from measured per-segment loss.
// Key property (regression-tested): additive residuals CANCEL in marginal
// comparisons f̂@N − f̂@N±1, so drift/imbalance loss never fakes a capacity
// signal; residuals move only emergency levels and diagnostics.
type Residuals struct {
	UP float64
	VY float64
}

// SegLoss is the measured per-segment sustained loss ratio (same segmentation
// the loss ledger uses: eupf XDP drop ratio, VY drop/err ratio).
type SegLoss struct {
	UP float64
	VY float64
}

// fCNF is the CNF-type loss curve: kernel/softirq queueing knee.
func fCNF(u float64, c *Calib) float64 {
	if u <= c.CNF.UKnee {
		return 0
	}
	return math.Exp(c.CNF.K*(u-c.CNF.UKnee)) - 1
}

// fVNF is the VNF-type loss curve: deterministic-service-rate overflow cliff
// anchored at Cap (no free shape parameters) plus the measured pre-cliff term.
func fVNF(u float64, c *Calib) float64 {
	cliff := 0.0
	if u > 1 {
		cliff = 1 - 1/u
	}
	return cliff + preCliff(u, c.VNF.PreCliff)
}

// preCliff interpolates the measured pre-cliff points (piecewise linear,
// zero outside the measured span). Empty table = g≡0 (provisional until E1).
func preCliff(u float64, pts []CurvePoint) float64 {
	if len(pts) == 0 || u <= pts[0].U {
		return 0
	}
	for i := 1; i < len(pts); i++ {
		if u <= pts[i].U {
			span := pts[i].U - pts[i-1].U
			frac := (u - pts[i-1].U) / span
			return pts[i-1].Loss + frac*(pts[i].Loss-pts[i-1].Loss)
		}
	}
	return pts[len(pts)-1].Loss
}

// fhatUP / fhatVY apply the online residual: f̂ = max(0, f + resid).
func residFloor() float64 { return envcfg.Float("V6_RESID_FLOOR", 0) }

func applyResidFloor(r float64) float64 {
	if fl := residFloor(); fl > 0 && r < fl && r > -fl {
		return 0
	}
	return r
}

func fhatUP(u float64, r Residuals, c *Calib) float64 {
	return clampLoss(fCNF(u, c) + applyResidFloor(r.UP))
}

func fhatVY(u float64, r Residuals, c *Calib) float64 {
	return clampLoss(fVNF(u, c) + applyResidFloor(r.VY))
}

func clampLoss(v float64) float64 {
	if v < 0 {
		return 0
	}
	if v > 1 {
		return 1
	}
	return v
}

// VE2E is the chain model (§2): flow propagation — each layer's input is the
// upstream SURVIVING flow, so upstream loss attenuates downstream utilization
// and all actions are priced against one end-to-end quantity.
//
// offered is the BIDIRECTIONAL aggregate pps entering the chain (2× UL egress
// for the symmetric echo workload). Chain order VY→UP is the UL order; for the
// symmetric workload the aggregate serial approximation matches per-direction
// composition to first order, and evaluating VY first (undamped load) is the
// conservative choice for the upstream layer.
func vyQuant(x float64, c *Calib) float64 {
	if c.PerUEBidir <= 0 {
		return x
	}
	ues := math.Ceil(x/c.PerUEBidir - ueQuantTol())
	if ues < 1 {
		ues = 1
	}
	return ues * c.PerUEBidir
}

func VE2ELayered(cfg V6Config, offVY, offUP float64, r Residuals, c *Calib) float64 {
	if offVY <= 0 || offUP <= 0 || cfg.NVY < 1 || cfg.NUP < 1 {
		return 0
	}
	fvy := fhatVY(vyQuant(offVY, c)/(float64(cfg.NVY)*c.CapVY), r, c)
	fup := fhatUP(uUPQuant(offUP*(1-fvy), cfg.NUP, c), r, c)
	return 1 - (1-fvy)*(1-fup)
}

func VE2E(cfg V6Config, offered float64, r Residuals, c *Calib) float64 {
	if offered <= 0 || cfg.NVY < 1 || cfg.NUP < 1 {
		return 0
	}
	x := offered
	x *= 1 - fhatVY(x/(float64(cfg.NVY)*c.CapVY), r, c)
	x *= 1 - fhatUP(uUPQuant(x, cfg.NUP, c), r, c)
	return 1 - x/offered
}

func ueQuantTol() float64 { return envcfg.Float("V6_UE_QUANT_TOL", 0.25) }

func uUPQuant(x float64, nup int, c *Calib) float64 {
	agg := x / (float64(nup) * c.CapUP)
	if c.PerUEBidir <= 0 {
		return agg
	}
	ues := math.Ceil(x/c.PerUEBidir - ueQuantTol())
	if ues < 1 {
		ues = 1
	}
	perSlot := math.Ceil(ues/float64(nup)) * c.PerUEBidir
	if q := perSlot / c.CapUP; q > agg {
		return q
	}
	return agg
}

// LayerUtils returns the per-layer utilizations under flow propagation —
// diagnostics and emergency levels (§6) read these.
func LayerUtils(cfg V6Config, offered float64, r Residuals, c *Calib) (uVY, uUP float64) {
	if offered <= 0 || cfg.NVY < 1 || cfg.NUP < 1 {
		return 0, 0
	}
	uVY = offered / (float64(cfg.NVY) * c.CapVY)
	x := offered * (1 - fhatVY(uVY, r, c))
	uUP = uUPQuant(x, cfg.NUP, c)
	return uVY, uUP
}

// UpdateResiduals EWMA-updates the additive corrections from measured
// per-segment loss at the CURRENT operating point (§3). alpha is derived:
// dt/W_settle (e.g. 30s tick / 60s window = 0.5) — not a free parameter.
// The residual is measured locally and applied as a curve offset; its
// extrapolation to N±1 configs is first-order (documented risk, guards below).
func UpdateResiduals(r *Residuals, meas SegLoss, cfg V6Config, offered float64, alpha float64, c *Calib) {
	if offered <= 0 || cfg.NVY < 1 || cfg.NUP < 1 {
		return
	}
	uVY := offered / (float64(cfg.NVY) * c.CapVY)
	errVY := meas.VY - fVNF(uVY, c)
	x := offered * (1 - clampLoss(meas.VY)) // propagate MEASURED survival downstream
	uUP := uUPQuant(x, cfg.NUP, c)
	errUP := meas.UP - fCNF(uUP, c)
	r.VY += alpha * (errVY - r.VY)
	r.UP += alpha * (errUP - r.UP)
}

// ThetaCrit returns the layer's emergency utilization level: f_L(u) = EpsSLO
// solved on the CALIBRATED curve (residual-free — emergency compares measured
// levels, model drift is already in the measurement).
func ThetaCritUP(c *Calib) float64 {
	// invert f_CNF: u = uKnee + ln(1+eps)/K
	return c.CNF.UKnee + math.Log(1+c.EpsSLO)/c.CNF.K
}

func ThetaCritVY(c *Calib) float64 {
	// invert the cliff+precliff numerically over the operating range
	return invertMono(func(u float64) float64 { return fVNF(u, c) }, c.EpsSLO, 0.5, 3.0)
}

// ThetaDesign: f_L(u) = EpsDesign — the planning/attribution level.
func ThetaDesignUP(c *Calib) float64 {
	return c.CNF.UKnee + math.Log(1+c.EpsDesign)/c.CNF.K
}

func ThetaDesignVY(c *Calib) float64 {
	return invertMono(func(u float64) float64 { return fVNF(u, c) }, c.EpsDesign, 0.5, 3.0)
}

// invertMono finds u in [lo,hi] with f(u)=target for nondecreasing f (bisection).
func invertMono(f func(float64) float64, target, lo, hi float64) float64 {
	if f(hi) < target {
		return hi
	}
	for i := 0; i < 60; i++ {
		mid := (lo + hi) / 2
		if f(mid) < target {
			lo = mid
		} else {
			hi = mid
		}
	}
	return (lo + hi) / 2
}
