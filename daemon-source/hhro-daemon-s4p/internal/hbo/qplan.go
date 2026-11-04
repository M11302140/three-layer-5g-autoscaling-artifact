package hbo

import (
	"fmt"
	"math"
	"time"

	"github.com/anon/hhro-daemon/internal/envcfg"
)

//
//

func demandModelQuantile() bool { return envcfg.Get("V6_DEMAND_MODEL", "batch") == "quantile" }

func demandModelSigma() bool { return envcfg.Get("V6_DEMAND_MODEL", "batch") == "sigma" }

func qEps() float64 { return envcfg.Float("V6_EPS", 0.05) }

//
//
func qReleaseRule() string     { return envcfg.Get("V6_RELEASE_RULE", "r1") }
func qReversibleDrain() bool   { return envcfg.Bool("V6_REVERSIBLE_DRAIN", true) }
func qRho(eps float64) float64 { return envcfg.Float("V6_RHO", eps) }
func qDwellK() float64         { return envcfg.Float("V6_DWELL_K", 1) }

// qReleaseDemand returns the demand level the post-release configuration must carry
// (the larger of the safety and economy tests) and the horizon that bound it.
func qReleaseDemand(act Action, cfg V6Config, base float64, c *Calib, p V6Params, rise *RiseModel) (x, horizon float64) {
	w := qCommitWindow(act, cfg, c)
	if rise.SigmaMode() {
		return base + rise.MarginRelease(act, w, base), w
	}
	x, horizon = base+rise.Margin(w, base), w
	if qReleaseRule() != "r1" {
		return
	}
	h := qBreakEven(act, c, p)*qDwellK() + w + qOutHorizon(reverseOf(act), c)
	if xe := base + rise.MarginAt(h, base, qRho(rise.Eps())); xe > x {
		x, horizon = xe, h
	}
	return
}

func qOutHorizon(act Action, c *Calib) float64 {
	switch act {
	case ActScaleOutUP:
		return c.Act[ActScaleOutUP].TReadySec + v6Grid
	case ActDeployVyOS:
		return c.Act[ActDeployVyOS].TReadySec + v6Grid
	case ActCreateWorker:
		return c.Act[ActCreateWorker].TReadySec + c.Act[ActScaleOutUP].TReadySec + v6Grid
	}
	return v6Grid
}

func qCommitWindow(act Action, cfg V6Config, c *Calib) float64 {
	switch act {
	case ActScaleInUP:
		w := c.Act[ActScaleOutUP].TReadySec
		if cfg.NUP >= cfg.NWK*slotsPerWorker && !qReversibleDrain() {
			w = c.Act[ActScaleInUP].TReadySec + c.Act[ActScaleOutUP].TReadySec
			if cfg.NUP-1 >= cfg.NWK*slotsPerWorker {
				w += c.Act[ActCreateWorker].TReadySec
			}
		}
		return w + v6Grid
	case ActDeleteVyOS:
		return c.Act[ActDeployVyOS].TReadySec + v6Grid
	case ActDeleteWorker:
		if demandModelSigma() {
			return c.Act[ActCreateWorker].TReadySec + c.Act[ActScaleOutUP].TReadySec + v6Grid
		}
		return c.Act[ActDeleteWorker].TReadySec + c.Act[ActCreateWorker].TReadySec + c.Act[ActScaleOutUP].TReadySec + v6Grid
	}
	return v6Grid
}

func qBreakEven(scaleIn Action, c *Calib, p V6Params) float64 {
	out := reverseOf(scaleIn)
	if out == "" {
		return 0
	}
	d := c.Act[scaleIn].TReadySec + c.Act[out].TReadySec
	if cores := c.Act[out].Cores; p.Lambda > 0 && cores > 0 {
		d += (c.Act[scaleIn].DLoss + c.Act[out].DLoss) / (p.Lambda * cores)
	}
	return d
}

func vyNeeded(x float64, c *Calib) int {
	th := ThetaDesignVY(c)
	for n := 1; n < 64; n++ {
		if vyQuant(x, c)/(float64(n)*c.CapVY) <= th {
			return n
		}
	}
	return 64
}

func clampInt(v, lo, hi int) int {
	if v < lo {
		return lo
	}
	if v > hi {
		return hi
	}
	return v
}

// QNeeds is the per-layer requirement at the current tick (diagnostics + decision).
type QNeeds struct {
	Offered                      float64
	MarginUP, MarginVY, MarginWK float64
	NeedUP, NeedVY, NeedWK       int
}

func qNeeds(in PlanInput, c *Calib, rise *RiseModel) QNeeds {
	d := in.Offered
	q := QNeeds{Offered: d,
		MarginUP: rise.MarginFor(ActScaleOutUP, qOutHorizon(ActScaleOutUP, c), d),
		MarginVY: rise.MarginFor(ActDeployVyOS, qOutHorizon(ActDeployVyOS, c), d),
		MarginWK: rise.MarginFor(ActCreateWorker, qOutHorizon(ActCreateWorker, c), d),
	}
	b := in.Bounds
	q.NeedUP = clampInt(slotsNeededUP(d+q.MarginUP, c), b.MinUP, b.MaxUP)
	q.NeedVY = clampInt(vyNeeded(d+q.MarginVY, c), b.MinVY, b.MaxVY)
	pos := clampInt(slotsNeededUP(d+q.MarginWK, c), b.MinUP, b.MaxUP)
	if rise.SigmaMode() && !s4pIndepWK() {
		if p2 := clampInt(slotsNeededUP(d+rise.MarginFor(ActScaleOutUP, qOutHorizon(ActCreateWorker, c), d), c), b.MinUP, b.MaxUP); p2 > pos {
			pos = p2
		}
	}
	q.NeedWK = clampInt(int(math.Ceil(float64(pos)/slotsPerWorker)), b.MinWK, b.MaxWK)
	return q
}

// decideQuantile returns this tick's moves (at most one per layer and direction).
// c must already be the planning calibration (PlanCalib: capacities × MarginM).
func decideQuantile(in PlanInput, c *Calib, p V6Params, rise *RiseModel) (TupleScore, QNeeds) {
	eff := configAt(in.Cfg, in.InFlight, 1e12)
	q := qNeeds(in, c, rise)
	var moves []Move
	add := func(m Move) bool {
		if in.Blocked[m.Act] || !poolOK(append(append([]Move{}, moves...), m), in, c) {
			return false
		}
		moves = append(moves, m)
		return true
	}

	outVY, outWK, outUP := false, false, false
	if q.NeedVY > eff.NVY && eff.NVY < in.Bounds.MaxVY {
		outVY = add(Move{Act: ActDeployVyOS, TEffect: c.Act[ActDeployVyOS].TReadySec, deltaVY: +1})
	}
	if q.NeedWK > eff.NWK && eff.NWK < in.Bounds.MaxWK {
		outWK = add(Move{Act: ActCreateWorker, TEffect: c.Act[ActCreateWorker].TReadySec, deltaWK: +1})
	}
	if q.NeedUP > eff.NUP && eff.NUP < in.Bounds.MaxUP {
		nwk := eff.NWK
		if outWK {
			nwk++
		}
		t := c.Act[ActScaleOutUP].TReadySec
		switch {
		case eff.NUP < eff.NWK*slotsPerWorker:
			outUP = add(Move{Act: ActScaleOutUP, TEffect: t, deltaUP: +1})
		case eff.NUP < nwk*slotsPerWorker:
			outUP = add(Move{Act: ActScaleOutUP, TEffect: c.Act[ActCreateWorker].TReadySec + t, deltaUP: +1})
		case eff.NWK < in.Bounds.MaxWK && !in.Blocked[ActCreateWorker] && !rise.SigmaMode():
			if add(Move{Act: ActCreateWorker, TEffect: c.Act[ActCreateWorker].TReadySec, deltaWK: +1}) {
				outWK = true
				outUP = add(Move{Act: ActScaleOutUP, TEffect: c.Act[ActCreateWorker].TReadySec + t, deltaUP: +1})
			}
		}
	}

	d := in.Offered
	if !outUP && eff.NUP > in.Bounds.MinUP && eff.NUP == in.Cfg.NUP {
		if x, _ := qReleaseDemand(ActScaleInUP, eff, d, c, p, rise); slotsNeededUP(x, c) <= eff.NUP-1 {
			if w, on := s4pR2W(); !on || c.PerUEBidir <= 0 || r2OK(math.Round(d/c.PerUEBidir), eff.NUP, eff.NWK, w) {
				add(Move{Act: ActScaleInUP, TEffect: c.Act[ActScaleInUP].TReadySec, deltaUP: -1})
			}
		}
	}
	if !outVY && eff.NVY > in.Bounds.MinVY && eff.NVY == in.Cfg.NVY {
		if x, _ := qReleaseDemand(ActDeleteVyOS, eff, d, c, p, rise); vyNeeded(x, c) <= eff.NVY-1 {
			add(Move{Act: ActDeleteVyOS, TEffect: c.Act[ActDeleteVyOS].TReadySec, deltaVY: -1})
		}
	}
	if !outWK && in.IdleWK && eff.NWK > in.Bounds.MinWK && eff.NWK == in.Cfg.NWK {
		x, _ := qReleaseDemand(ActDeleteWorker, eff, d, c, p, rise)
		pos := (eff.NWK - 1) * slotsPerWorker
		need := slotsNeededUP(x, c)
		if need < eff.NUP {
			need = eff.NUP
		}
		if rise.SigmaMode() && !s4pIndepWK() {
			if n2 := slotsNeededUP(d+rise.MarginRelease(ActScaleInUP, qCommitWindow(ActDeleteWorker, eff, c), d), c); n2 > need {
				need = n2
			}
		}
		if need <= pos {
			add(Move{Act: ActDeleteWorker, TEffect: c.Act[ActDeleteWorker].TReadySec, deltaWK: -1})
		}
	}
	key := tupleKey(moves)
	return TupleScore{Key: key + "|q", Moves: moves}, q
}

// holdQuantilePure is the commitment-aware release criterion.
func holdQuantilePure(act Action, cfg V6Config, peak float64, c *Calib, p V6Params, rise *RiseModel) (bool, string) {
	x, w := qReleaseDemand(act, cfg, peak, c, p, rise)
	m := x - peak
	switch act {
	case ActScaleInUP:
		if cfg.NUP-1 < 1 {
			return true, "commitment hold: slot layer at minimum"
		}
		if need := slotsNeededUP(x, c); need > cfg.NUP-1 {
			return true, fmt.Sprintf("commitment hold: peak %.2fM + margin(%.0fs) %.2fM needs %d slots > %d after release", peak/1e6, w, m/1e6, need, cfg.NUP-1)
		}
	case ActDeleteVyOS:
		if cfg.NVY-1 < 1 {
			return true, "commitment hold: vyos layer at minimum"
		}
		if need := vyNeeded(x, c); need > cfg.NVY-1 {
			return true, fmt.Sprintf("commitment hold: peak %.2fM + margin(%.0fs) %.2fM needs %d vyos > %d after release", peak/1e6, w, m/1e6, need, cfg.NVY-1)
		}
	case ActDeleteWorker:
		pos := (cfg.NWK - 1) * slotsPerWorker
		need := slotsNeededUP(x, c)
		if need < cfg.NUP {
			need = cfg.NUP
		}
		if rise.SigmaMode() && !s4pIndepWK() {
			if n2 := slotsNeededUP(peak+rise.MarginRelease(ActScaleInUP, qCommitWindow(ActDeleteWorker, cfg, c), peak), c); n2 > need {
				need = n2
			}
		}
		if need > pos {
			return true, fmt.Sprintf("commitment hold: peak %.2fM + margin(%.0fs) %.2fM needs %d slot positions > %d after release", peak/1e6, w, m/1e6, need, pos)
		}
	}
	return false, ""
}

// holdQuantile binds holdQuantilePure to the live shadow state.
func holdQuantile(act Action, s SystemState, offered float64, sh *V6Shadow, cal *Calib) (bool, string) {
	delta := qBreakEven(act, cal, sh.params) * qDwellK()
	if sh.Rise().SigmaMode() {
		nvyS := s.VyosCount
		if s.VyosAdmitted > 0 && s.VyosAdmitted < nvyS {
			nvyS = s.VyosAdmitted
		}
		delta = qCommitWindow(act, V6Config{NUP: s.RepUP, NVY: nvyS, NWK: s.WorkerCount}, cal)
	}
	nvy0 := s.VyosCount
	if s.VyosAdmitted > 0 && s.VyosAdmitted < nvy0 {
		nvy0 = s.VyosAdmitted
	}
	need := delta + qCommitWindow(act, V6Config{NUP: s.RepUP, NVY: nvy0, NWK: s.WorkerCount}, cal)
	if age := sh.EpisodeAge(); age > 0 && age < need {
		return true, fmt.Sprintf("commitment hold: episode age %.0fs < dwell+window %.0fs (no history yet)", age, need)
	}
	peak := sh.PeakOfferedSince(time.Duration(delta*float64(time.Second)), offered)
	inUP, inVY, inWK := 0, 0, 0
	for _, a := range sh.InFlight() {
		switch a {
		case ActScaleInUP:
			inUP++
		case ActDeleteVyOS:
			inVY++
		case ActDeleteWorker:
			inWK++
		}
	}
	nvy := s.VyosCount
	if s.VyosAdmitted > 0 && s.VyosAdmitted < nvy {
		nvy = s.VyosAdmitted
	}
	cfg := V6Config{NUP: s.RepUP - inUP, NVY: nvy - inVY, NWK: s.WorkerCount - inWK}
	return holdQuantilePure(act, cfg, peak, cal, sh.params, sh.Rise())
}
