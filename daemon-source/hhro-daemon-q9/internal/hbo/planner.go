package hbo

import (
	"math"
	"fmt"
	"sort"

	"github.com/anon/hhro-daemon/internal/envcfg"
)

func v6BarrierK() float64 { return envcfg.Float("V6_BARRIER_K", 50) }

// planner.go — v6 joint decision: receding-horizon argmin over enumerable
// action tuples with a threshold-greedy rollout continuation (spec §4-§5).
// Pure functions: feasibility context (cooldowns/locks/slots) is provided by
// the caller in PlanInput; nothing here touches prometheus, k8s or clocks.

const (
	v6Grid = 30.0  // decision tick, s (derived: mid-loop period)
	v6TH   = 300.0

	slotsPerWorker  = 2
	maxRolloutMoves = 6
)

// V6Bounds are the topology bounds (measured/config, not tunables).
type V6Bounds struct {
	MinUP, MaxUP int
	MinVY, MaxVY int
	MinWK, MaxWK int
}

// PlanInput is everything DecideV6 needs, precomputed by the caller.
type PlanInput struct {
	Cfg     V6Config
	Offered float64 // bidirectional aggregate pps entering the chain
	Slope   float64 // d(offered)/dt, pps/s (pre-clamp; planner clamps by params)
	Resid   Residuals

	Bounds  V6Bounds
	Blocked map[Action]bool
	InFlight []Move
	IdleWK   bool // an idle worker (zero slots) exists → deletable
	// host pool usage OUTSIDE the modeled layers (master, CP, system VMs):
	BaseCores, BaseMemGi float64
}

// Move is one dispatched action with its effect time on the horizon.
type Move struct {
	Act     Action
	TEffect float64 // s from now; dispatch is always "now" for tuple moves
	deltaUP int
	deltaVY int
	deltaWK int
}

// TupleScore is one evaluated candidate (exported for shadow logging).
type TupleScore struct {
	Key     string  // e.g. "UP+1,WK+1"
	J       float64 // loss-time + λ·core-time over [0,TH]
	Moves   []Move
	Rollout []Move // continuation appended by π₀ (not dispatched; diagnostic)
}

// DecideV6 evaluates all feasible tuples and returns the argmin plus the full
// score table. The returned moves are the IMMEDIATE dispatches; re-planning
// happens every tick (receding horizon).
// PlanCalib returns the calibration the PLANNER reasons with: capacities scaled
func PlanCalib(c *Calib, p V6Params) *Calib {
	m := p.MarginM
	if m <= 0 || m > 1 {
		return c
	}
	pc := *c
	pc.CapUP = c.CapUP * m
	pc.CapVY = c.CapVY * m
	return &pc
}

func DecideV6(in PlanInput, c *Calib, p V6Params) (best TupleScore, all []TupleScore) {
	c = PlanCalib(c, p)
	if plannerLayered() {
		best, all = decideLayered(in, c, p)
	} else {
		for _, τ := range enumerateTuples(in, c) {
			roll := rollout(τ, in, c, p)
			score := TupleScore{Key: tupleKey(τ), Moves: τ, Rollout: roll,
				J: evalJ(append(append([]Move{}, τ...), roll...), in, c, p)}
			all = append(all, score)
		}
		sort.Slice(all, func(i, j int) bool { return all[i].J < all[j].J })
		best = all[0]
	}
	// anti-dither: must beat NoOp by UMin
	for _, s := range all {
		if s.Key == "∅" {
			if best.J >= s.J-p.UMin {
				best = s
			}
			break
		}
	}
	if in.Slope > 0 {
		for _, m := range best.Rollout {
			long := m.Act == ActDeployVyOS || m.Act == ActCreateWorker
			first := m.TEffect <= v6Grid+c.Act[m.Act].TReadySec+0.1
			if long && first && !in.Blocked[m.Act] && !hasMove(best.Moves, m.Act) && !hasMove(best.Moves, reverseOf(m.Act)) {
				now := m
				now.TEffect = c.Act[m.Act].TReadySec
				best = TupleScore{Key: best.Key + "+" + string(m.Act) + "!π₀",
					Moves: append(append([]Move{}, best.Moves...), now), J: best.J,
					Rollout: best.Rollout}
				if best.Key[:2] == "∅+" {
					best.Key = best.Key[len("∅+"):]
				}
				break
			}
		}
	}
	return best, all
}

func plannerLayered() bool { return envcfg.Bool("V6_PLANNER_LAYERED", false) }

func tupleLayer(τ []Move, in PlanInput) (layer string, ok bool) {
	var up, vy, wk int
	for _, m := range τ {
		switch m.Act {
		case ActScaleOutUP, ActScaleInUP:
			up++
		case ActDeployVyOS, ActDeleteVyOS:
			vy++
		case ActCreateWorker, ActDeleteWorker:
			wk++
		}
	}
	switch {
	case up == 0 && vy == 0 && wk == 0:
		return "∅", true
	case up == 1 && vy == 0 && wk == 0:
		return "UP", true
	case vy == 1 && up == 0 && wk == 0:
		return "VY", true
	case wk == 1 && up == 0 && vy == 0:
		return "WK", true
	case up == 1 && wk == 1 && vy == 0 && hasMove(τ, ActScaleOutUP) && hasMove(τ, ActCreateWorker):
		cfg := configAt(in.Cfg, in.InFlight, 1e12)
		if cfg.NUP >= cfg.NWK*slotsPerWorker {
			return "UP", true
		}
	}
	return "", false
}

func evalJLayer(layer string, moves []Move, in PlanInput, c *Calib, p V6Params) float64 {
	moves = append(append([]Move{}, in.InFlight...), moves...)
	j := 0.0
	for t := 0.0; t < v6TH; t += v6Grid {
		cfg := configAt(in.Cfg, moves, t)
		var m, w, cores float64
		switch layer {
		case "UP":
			off := offeredAtUP(in, p, c, t)
			if off > 0 && cfg.NUP >= 1 {
				u := uUPQuant(off, cfg.NUP, c)
				m = fhatUP(u, Residuals{}, c)
				w = fhatUP(u, in.Resid, c)
			}
			cores = float64(cfg.NUP)*c.Act[ActScaleOutUP].Cores + float64(cfg.NWK)*c.Act[ActCreateWorker].Cores
		case "VY":
			off := offeredAt(in, p, c, t)
			if off > 0 && cfg.NVY >= 1 {
				u := vyQuant(off, c) / (float64(cfg.NVY) * c.CapVY)
				m = fhatVY(u, Residuals{}, c)
				w = fhatVY(u, in.Resid, c)
			}
			cores = float64(cfg.NVY) * c.Act[ActDeployVyOS].Cores
		default: // WK / ∅
			cores = float64(cfg.NWK) * c.Act[ActCreateWorker].Cores
		}
		residPart := w - m
		if m > c.EpsDesign {
			m = c.EpsDesign + v6BarrierK()*(m-c.EpsDesign)
		}
		j += (m+residPart)*v6Grid + p.Lambda*(in.BaseCores+cores)*v6Grid
	}
	for _, mv := range moves[len(in.InFlight):] {
		j += c.Act[mv.Act].DLoss
	}
	return j
}

func decideLayered(in PlanInput, c *Calib, p V6Params) (best TupleScore, all []TupleScore) {
	type cand struct {
		s TupleScore
		l string
	}
	var cands []cand
	for _, τ := range enumerateTuples(in, c) {
		l, ok := tupleLayer(τ, in)
		if !ok {
			continue
		}
		roll := rollout(τ, in, c, p)
		s := TupleScore{Key: tupleKey(τ), Moves: τ, Rollout: roll}
		if l == "∅" {
			cands = append(cands, cand{s, l})
			continue
		}
		s.J = evalJLayer(l, append(append([]Move{}, τ...), roll...), in, c, p)
		cands = append(cands, cand{s, l})
	}
	var noop TupleScore
	for _, cd := range cands {
		if cd.l == "∅" {
			noop = cd.s
		}
	}
	var chosen []Move
	for _, layer := range []string{"UP", "VY", "WK"} {
		nj := evalJLayer(layer, append(append([]Move{}, noop.Moves...), noop.Rollout...), in, c, p)
		bestJ, bestIdx := nj, -1
		for i, cd := range cands {
			if cd.l != layer {
				continue
			}
			all = append(all, cd.s)
			if cd.s.J < bestJ-p.UMin {
				bestJ, bestIdx = cd.s.J, i
			}
		}
		if bestIdx < 0 {
			continue
		}
		for _, m := range cands[bestIdx].s.Moves {
			if hasMove(chosen, reverseOf(m.Act)) || hasMove(chosen, m.Act) {
				continue
			}
			chosen = append(chosen, m)
		}
	}
	noop.J = evalJ(append(append([]Move{}, noop.Moves...), noop.Rollout...), in, c, p)
	all = append(all, noop)
	if len(chosen) == 0 {
		return noop, all
	}
	roll := rollout(chosen, in, c, p)
	best = TupleScore{Key: tupleKey(chosen) + "|layered", Moves: chosen, Rollout: roll,
		J: evalJ(append(append([]Move{}, chosen...), roll...), in, c, p)}
	return best, all
}

// enumerateTuples builds the pruned {−1,0,+1}³ tuple space (≤27; CP is out of
// the data chain and keeps its trivial rule outside the planner).
func enumerateTuples(in PlanInput, c *Calib) [][]Move {
	var out [][]Move
	b, cfg := in.Bounds, configAt(in.Cfg, in.InFlight, 1e12)
	for _, dUP := range []int{0, +1, -1} {
		for _, dVY := range []int{0, +1, -1} {
			for _, dWK := range []int{0, +1, -1} {
				var τ []Move
				ok := true

				// worker
				switch dWK {
				case +1:
					if cfg.NWK+1 > b.MaxWK || in.Blocked[ActCreateWorker] {
						ok = false
						break
					}
					τ = append(τ, Move{Act: ActCreateWorker, TEffect: c.Act[ActCreateWorker].TReadySec, deltaWK: +1})
				case -1:
					// only an idle worker is deletable, and survivors must still host NUP
					if cfg.NWK-1 < b.MinWK || !in.IdleWK || in.Blocked[ActDeleteWorker] ||
						(cfg.NUP+dUP) > (cfg.NWK-1)*slotsPerWorker {
						ok = false
						break
					}
					τ = append(τ, Move{Act: ActDeleteWorker, TEffect: c.Act[ActDeleteWorker].TReadySec, deltaWK: -1})
				}
				if !ok {
					continue
				}

				// eUPF slots
				switch dUP {
				case +1:
					if cfg.NUP+1 > b.MaxUP || in.Blocked[ActScaleOutUP] {
						ok = false
						break
					}
					slotFree := cfg.NUP < cfg.NWK*slotsPerWorker
					t := c.Act[ActScaleOutUP].TReadySec
					if !slotFree {
						if dWK != +1 { // no slot and no worker coming → infeasible
							ok = false
							break
						}
						t = c.Act[ActCreateWorker].TReadySec + c.Act[ActScaleOutUP].TReadySec
					}
					τ = append(τ, Move{Act: ActScaleOutUP, TEffect: t, deltaUP: +1})
				case -1:
					if cfg.NUP-1 < b.MinUP || in.Blocked[ActScaleInUP] {
						ok = false
						break
					}
					τ = append(τ, Move{Act: ActScaleInUP, TEffect: c.Act[ActScaleInUP].TReadySec, deltaUP: -1})
				}
				if !ok {
					continue
				}

				// VyOS
				switch dVY {
				case +1:
					if cfg.NVY+1 > b.MaxVY || in.Blocked[ActDeployVyOS] {
						ok = false
						break
					}
					τ = append(τ, Move{Act: ActDeployVyOS, TEffect: c.Act[ActDeployVyOS].TReadySec, deltaVY: +1})
				case -1:
					if cfg.NVY-1 < b.MinVY || in.Blocked[ActDeleteVyOS] {
						ok = false
						break
					}
					τ = append(τ, Move{Act: ActDeleteVyOS, TEffect: c.Act[ActDeleteVyOS].TReadySec, deltaVY: -1})
				}
				if !ok {
					continue
				}

				if !poolOK(τ, in, c) {
					continue
				}
				out = append(out, τ)
			}
		}
	}
	return out
}

// poolOK enforces the shared host pool (§4) on vCPU/memory ALLOCATION: peak
// usage during the horizon (all additions applied, deletions credited only
// after effect) must fit. λ pricing uses burned cores instead (layerCores).
func poolOK(moves []Move, in PlanInput, c *Calib) bool {
	cores := in.BaseCores + poolCores(in.Cfg, c)
	mem := in.BaseMemGi + poolMemGi(in.Cfg, c)
	for _, m := range append(append([]Move{}, in.InFlight...), moves...) {
		spec := c.Act[m.Act]
		if spec.PoolCores > 0 {
			cores += spec.PoolCores
		}
		if spec.MemGi > 0 {
			mem += spec.MemGi
		}
	}
	return cores <= c.HostCores && mem <= c.HostMemGi-c.HostReserveGi
}

// poolCores/poolMemGi: host-pool ALLOCATION of the modeled layers.
func poolCores(cfg V6Config, c *Calib) float64 {
	return float64(cfg.NWK)*c.Act[ActCreateWorker].PoolCores +
		float64(cfg.NVY)*c.Act[ActDeployVyOS].PoolCores
}

func poolMemGi(cfg V6Config, c *Calib) float64 {
	return float64(cfg.NWK)*c.Act[ActCreateWorker].MemGi + float64(cfg.NVY)*c.Act[ActDeployVyOS].MemGi
}

// layerCores: λ-priced BURNED compute — VM allocations burn regardless of
// load (DPDK poll / reservation), active slots burn their measured softirq
// share inside the worker.
func layerCores(cfg V6Config, c *Calib) float64 {
	return float64(cfg.NWK)*c.Act[ActCreateWorker].Cores +
		float64(cfg.NVY)*c.Act[ActDeployVyOS].Cores +
		float64(cfg.NUP)*c.Act[ActScaleOutUP].Cores
}

// rollout is the base policy π₀ (§5): threshold-greedy, OUT-only completion.
// Walking the grid, whenever a layer's predicted loss at its own lead time
// still exceeds EpsDesign given every in-flight move, append the cheapest +1.
// Scale-in opportunities are NOT rolled out — they reappear as tuple
// candidates at every re-plan tick (receding horizon), while capacity
// adequacy in the tail must be modeled to price slow moves fairly.
//
// Continuation starts at t = v6Grid, NOT t = 0: a rolled-out move can be
// dispatched no earlier than the NEXT re-plan tick. This is what makes
// "act now" strictly beat procrastination (the ∅ tuple's rollout lands one
// grid later → one grid of extra tail loss), so the argmin actually dispatches
// instead of deferring forever.
func rollout(τ []Move, in PlanInput, c *Calib, p V6Params) []Move {
	moves := append(append([]Move{}, in.InFlight...), τ...)
	var added []Move
	for t := v6Grid; t <= v6TH && len(added) < maxRolloutMoves; t += v6Grid {
		// VY: check at its own lead time
		tv := t + c.Act[ActDeployVyOS].TReadySec
		cfgV := configAt(in.Cfg, moves, tv)
		if cfgV.NVY < in.Bounds.MaxVY {
			uVY := vyQuant(offeredAt(in, p, c, tv), c) / (float64(cfgV.NVY) * c.CapVY)
			if fVNF(uVY, c) >= c.EpsDesign {
				m := Move{Act: ActDeployVyOS, TEffect: tv, deltaVY: +1}
				if poolOK(append(moves, m), in, c) {
					moves = append(moves, m)
					added = append(added, m)
				}
			}
		}
		// UP: may need a worker first
		tu := t + c.Act[ActScaleOutUP].TReadySec
		cfgU := configAt(in.Cfg, moves, tu)
		if cfgU.NUP < in.Bounds.MaxUP {
			x := offeredAtUP(in, p, c, tu)
			uVY := x / (float64(cfgU.NVY) * c.CapVY)
			x *= 1 - fhatVY(uVY, in.Resid, c)
			uUP := uUPQuant(x, cfgU.NUP, c)
			if fCNF(uUP, c) >= c.EpsDesign {
				var m Move
				if cfgU.NUP < cfgU.NWK*slotsPerWorker {
					m = Move{Act: ActScaleOutUP, TEffect: tu, deltaUP: +1}
				} else {
					// no slot: worker first, slot lands later
					tw := t + c.Act[ActCreateWorker].TReadySec
					wk := Move{Act: ActCreateWorker, TEffect: tw, deltaWK: +1}
					if poolOK(append(moves, wk), in, c) && configAt(in.Cfg, moves, tw).NWK < in.Bounds.MaxWK {
						moves = append(moves, wk)
						added = append(added, wk)
					}
					m = Move{Act: ActScaleOutUP, TEffect: tw + c.Act[ActScaleOutUP].TReadySec, deltaUP: +1}
				}
				if poolOK(append(moves, m), in, c) {
					moves = append(moves, m)
					added = append(added, m)
				}
			}
		}
	}
	return added
}

// evalJ integrates predicted e2e loss + λ·cores over [0,TH] (left-point sum)
// and adds transition damages (§5).
func evalJ(moves []Move, in PlanInput, c *Calib, p V6Params) float64 {
	moves = append(append([]Move{}, in.InFlight...), moves...)
	j := 0.0
	for t := 0.0; t < v6TH; t += v6Grid {
		cfg := configAt(in.Cfg, moves, t)
		off := offeredAt(in, p, c, t)
		offUP := offeredAtUP(in, p, c, t) // p5u2
		m := VE2ELayered(cfg, off, offUP, Residuals{}, c)
		w := VE2ELayered(cfg, off, offUP, in.Resid, c)
		residPart := w - m
		if m > c.EpsDesign {
			m = c.EpsDesign + v6BarrierK()*(m-c.EpsDesign)
		}
		j += (m + residPart) * v6Grid
		j += p.Lambda * (in.BaseCores + layerCores(cfg, c)) * v6Grid
	}
	for _, m := range moves[len(in.InFlight):] {
		j += c.Act[m.Act].DLoss
	}
	return j
}

// configAt applies every move whose effect time has passed.
func configAt(base V6Config, moves []Move, t float64) V6Config {
	cfg := base
	for _, m := range moves {
		if m.TEffect <= t {
			cfg.NUP += m.deltaUP
			cfg.NVY += m.deltaVY
			cfg.NWK += m.deltaWK
		}
	}
	if cfg.NUP < 1 {
		cfg.NUP = 1
	}
	if cfg.NVY < 1 {
		cfg.NVY = 1
	}
	if cfg.NWK < 1 {
		cfg.NWK = 1
	}
	return cfg
}

// offeredAt extrapolates offered load with the clamped slope. SlopeMax is a
// fraction of the CURRENT offered per second (scale-free clamp).
func offeredAt(in PlanInput, p V6Params, c *Calib, t float64) float64 {
	nb := 0
	if c != nil {
		nb = c.MaxBatches
	}
	return offeredAtCapped(in, p, c, t, nb, nb)
}

func offeredAtUP(in PlanInput, p V6Params, c *Calib, t float64) float64 {
	nb := 0
	if c != nil {
		nb = c.MaxBatches
	}
	return offeredAtCapped(in, p, c, t, nb, upLookaheadBatches(c))
}

func upLookaheadBatches(c *Calib) int {
	if c == nil || c.BatchIntervalSec <= 0 {
		return 0
	}
	if v := envcfg.Int("V6_UP_LOOKAHEAD_BATCHES", -1); v >= 0 {
		if v == 0 {
			return c.MaxBatches
		}
		return v
	}
	nb := int(math.Ceil((c.Act[ActScaleOutUP].TReadySec + v6Grid) / c.BatchIntervalSec))
	if nb < 1 {
		nb = 1
	}
	if c.MaxBatches > 0 && nb > c.MaxBatches {
		nb = c.MaxBatches
	}
	return nb
}

// offeredAtCapped is offeredAt with an explicit cap on the number of arrival batches
// the projection may contain (linear term and step floor alike).
func offeredAtCapped(in PlanInput, p V6Params, c *Calib, t float64, nbLin, nbFloor int) float64 {
	s := in.Slope
	lim := p.SlopeMax * in.Offered
	if s > lim {
		s = lim
	}
	if s < -lim {
		s = -lim
	}
	o := in.Offered + s*t
	if c != nil && c.BatchIntervalSec > 0 && nbLin > 0 && c.StepFloor > 0 {
		if capLin := in.Offered + float64(nbLin)*c.StepFloor; o > capLin {
			o = capLin
		}
	}
	if c != nil && c.BatchIntervalSec > 0 && c.StepFloor > 0 {
		nb := math.Ceil(t / c.BatchIntervalSec)
		if nbFloor > 0 && nb > float64(nbFloor) {
			nb = float64(nbFloor)
		}
		if fl := in.Offered + nb*c.StepFloor; fl > o {
			o = fl
		}
	}
	if o < 0 {
		return 0
	}
	return o
}

func hasMove(ms []Move, a Action) bool {
	for _, m := range ms {
		if m.Act == a {
			return true
		}
	}
	return false
}

func tupleKey(τ []Move) string {
	if len(τ) == 0 {
		return "∅"
	}
	k := ""
	for i, m := range τ {
		if i > 0 {
			k += ","
		}
		k += string(m.Act)
	}
	return k
}

// EmergencyV6 is the measured-level emergency gate (§6): real e2e loss at SLO,
// or any layer's measured utilization past its critical level.
func EmergencyV6(measE2E float64, cfg V6Config, offered float64, c *Calib) (bool, string) {
	uVY := offered / (float64(cfg.NVY) * c.CapVY)
	uUPraw := offered / (float64(cfg.NUP) * c.CapUP)
	if measE2E >= c.EpsSLO && (uVY >= emergUMin() || uUPraw >= emergUMin()) {
		return true, fmt.Sprintf("measured e2e loss %.3f ≥ SLO %.3f (uVY %.2f uUP %.2f)", measE2E, c.EpsSLO, uVY, uUPraw)
	}
	if uVY >= ThetaCritVY(c) {
		return true, fmt.Sprintf("VY util %.2f ≥ crit %.2f", uVY, ThetaCritVY(c))
	}
	uUP := offered / (float64(cfg.NUP) * c.CapUP)
	if uUP >= ThetaCritUP(c) {
		return true, fmt.Sprintf("UP util %.2f ≥ crit %.2f", uUP, ThetaCritUP(c))
	}
	return false, ""
}

func emergUMin() float64 { return envcfg.Float("V6_EMERG_UMIN", 0.5) }
