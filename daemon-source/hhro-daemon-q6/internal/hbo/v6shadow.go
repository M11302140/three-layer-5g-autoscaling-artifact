package hbo

import (
	"fmt"
	"log/slog"
	"math"
	"sort"
	"sync"
	"time"

	"github.com/anon/hhro-daemon/internal/envcfg"
)

// v6shadow.go — P2: the v6 planner running in SHADOW alongside the v5.x
// pipeline. Same inputs (FeatureSet/SystemState/Timers), decisions are only
// LOGGED and EXPORTED, never actuated. Divergence between the shadow tuple and
// the v5 decision is the P2-gate dataset (agreement rate, boot-lead delta).

type V6Shadow struct {
	Enabled bool
	calib   Calib
	params  V6Params
	log     *slog.Logger

	// static base-pool usage outside the modeled layers (master VM, CP pods,
	// DN reflector share). [M] placeholder pending M0 inventory — shadow-grade.
	baseCores, baseMemGi float64

	mu    sync.Mutex
	resid Residuals

	emergMeasStreak int
	offeredEWMA     float64

	inflight []inflightMove
	recent           []inflightMove
	lastSlotChange   time.Time
	lastSlotIncrease time.Time

	offHist []offSample
	offFine []offSample

	episodeStart  time.Time
	posSlopeTicks int

	rise         *RiseModel
	riseFineLast time.Time
	LastQ        QNeeds

	// last tick snapshot (for /metrics and /state)
	Last struct {
		Valid     bool
		Best      TupleScore
		NoOpJ     float64
		In        PlanInput
		Emergency bool
		EmergWhy  string
		MeasE2E   float64
		Meas      SegLoss
	}
}

type inflightMove struct {
	Act  Action
	T0   time.Time
	Base V6Config // layer counts at dispatch
}

type offSample struct {
	T time.Time
	V float64
}

func NewV6Shadow(log *slog.Logger) *V6Shadow {
	v := &V6Shadow{
		Enabled:   envcfg.Get("V6_SHADOW", "true") == "true",
		calib:     DefaultCalib(),
		params:    DefaultV6Params(),
		log:       log,
		baseCores: envcfg.Float("V6_BASE_CORES", 8),
		baseMemGi: envcfg.Float("V6_BASE_MEM_GI", 12),
	}
	if demandModelQuantile() {
		rp, err := LoadRisePrior()
		if err != nil {
			log.Error("v7 rise prior unavailable — falling back to the batch demand model", "err", err)
		} else {
			v.rise = NewRiseModel(rp, qEps(), v.calib.PerUEBidir)
			pc := PlanCalib(&v.calib, v.params)
			v.rise.NeedFn = func(x float64) [3]int {
				up := slotsNeededUP(x, pc)
				return [3]int{up, vyNeeded(x, pc), (up + slotsPerWorker - 1) / slotsPerWorker}
			}
			log.Info("v7 HHRO-Q demand model ACTIVE", "eps", qEps(), "prior_traces", rp.NTraces, "horizons", len(rp.Horizons))
		}
	}
	return v
}

// Rise exposes the quantile demand model (nil in batch mode).
func (v *V6Shadow) Rise() *RiseModel {
	if v == nil {
		return nil
	}
	return v.rise
}

// QMode reports whether the v7 quantile pipeline is active.
func (v *V6Shadow) QMode() bool { return v != nil && v.rise != nil }

// NoteDispatched records a successfully dispatched v6 action as in-flight.
// Called by the daemon right after the actuator accepted the action.
func (v *V6Shadow) SlotLayerGrewWithin(d time.Duration) bool {
	if v == nil {
		return false
	}
	v.mu.Lock()
	defer v.mu.Unlock()
	return !v.lastSlotIncrease.IsZero() && time.Since(v.lastSlotIncrease) < d
}

func (v *V6Shadow) EpisodeAge() float64 {
	if v == nil {
		return 0
	}
	v.mu.Lock()
	defer v.mu.Unlock()
	if v.episodeStart.IsZero() {
		return 0
	}
	return time.Since(v.episodeStart).Seconds()
}

func (v *V6Shadow) slopeConfirmTicks() int {
	if n := envcfg.Int("V6_SLOPE_CONFIRM_TICKS", 0); n > 0 {
		return n
	}
	if v.calib.BatchIntervalSec <= 0 {
		return 2
	}
	n := int(math.Ceil(v.calib.BatchIntervalSec / v6Grid))
	if n < 2 {
		n = 2
	}
	return n
}

func (v *V6Shadow) SlotLayerChangedWithin(d time.Duration) bool {
	if v == nil {
		return false
	}
	v.mu.Lock()
	defer v.mu.Unlock()
	return !v.lastSlotChange.IsZero() && time.Since(v.lastSlotChange) < d
}

func (v *V6Shadow) NoteDispatched(a Action) {
	if v == nil {
		return
	}
	v.mu.Lock()
	if a == ActScaleOutUP || a == ActScaleInUP {
		v.lastSlotChange = time.Now()
		if a == ActScaleOutUP {
			v.lastSlotIncrease = time.Now()
		}
	}
	defer v.mu.Unlock()
	v.inflight = append(v.inflight, inflightMove{Act: a, T0: time.Now(), Base: v.Last.In.Cfg})
}

func (v *V6Shadow) ResetEpisode() {
	if v == nil {
		return
	}
	v.mu.Lock()
	defer v.mu.Unlock()
	v.offHist = nil
	v.offFine = nil
	v.episodeStart = time.Now()
	v.inflight = nil
	v.recent = nil
	v.offeredEWMA = 0
	v.emergMeasStreak = 0
	v.posSlopeTicks = 0
	v.resid = Residuals{}
	if v.rise != nil {
		v.rise.ResetEpisode(v.episodeStart)
		v.riseFineLast = time.Time{}
	}
	v.log.Info("v6 episode reset (autoscale enabled): history/in-flight/residuals cleared")
}

func (v *V6Shadow) DropInFlight(a Action) {
	if v == nil {
		return
	}
	v.mu.Lock()
	defer v.mu.Unlock()
	keep := v.inflight[:0]
	for _, m := range v.inflight {
		if m.Act != a {
			keep = append(keep, m)
		}
	}
	v.inflight = keep
}

// InFlight returns a snapshot of in-flight actions (for /state).
func (v *V6Shadow) InFlight() []Action {
	if v == nil {
		return nil
	}
	v.mu.Lock()
	defer v.mu.Unlock()
	out := make([]Action, 0, len(v.inflight))
	for _, m := range v.inflight {
		out = append(out, m.Act)
	}
	return out
}

// PeakOfferedSince returns the max offered (bidirectional) observed within
// the last d, falling back to the given current value.
func (v *V6Shadow) PeakOfferedSince(d time.Duration, cur float64) float64 {
	v.mu.Lock()
	defer v.mu.Unlock()
	peak := cur
	cut := time.Now().Add(-d)
	for _, o := range v.offHist {
		if o.T.After(cut) && o.V > peak {
			peak = o.V
		}
	}
	for _, o := range v.offFine {
		if o.T.After(cut) && o.V > peak {
			peak = o.V
		}
	}
	return peak
}

//
//
func (v *V6Shadow) SustainedPeakSince(win, minDur time.Duration, cur, perUE float64) float64 {
	v.mu.Lock()
	defer v.mu.Unlock()
	if perUE <= 0 {
		return v.peakSinceLocked(win, cur)
	}
	now := time.Now()
	cut := now.Add(-win)
	samp := make([]offSample, 0, len(v.offHist)+len(v.offFine))
	samp = append(samp, v.offHist...)
	samp = append(samp, v.offFine...)
	sort.Slice(samp, func(i, j int) bool { return samp[i].T.Before(samp[j].T) })
	lvl := func(x float64) int { return int(math.Round(x / perUE)) }
	lcur := lvl(cur)
	seen := map[int]bool{}
	var cands []int
	for _, o := range samp {
		if o.T.After(cut) {
			if l := lvl(o.V); l > lcur && !seen[l] {
				seen[l] = true
				cands = append(cands, l)
			}
		}
	}
	sort.Sort(sort.Reverse(sort.IntSlice(cands)))
	const grid = v6Grid * float64(time.Second)
	const maxGap = 45 * time.Second
	sustain := minDur + time.Duration(grid)
	for _, L := range cands {
		var runStart, runEnd time.Time
		inRun := false
		nRun := 0
		counts := false
		flush := func() {
			if !inRun {
				return
			}
			pad := time.Duration(grid)
			if nRun >= 2 {
				pad = runEnd.Sub(runStart) / time.Duration(nRun-1)
			}
			dur := runEnd.Sub(runStart) + pad
			endAge := now.Sub(runEnd)
			if endAge <= win && (dur >= sustain || endAge < minDur) {
				counts = true
			}
			inRun = false
			nRun = 0
		}
		for _, o := range samp {
			if lvl(o.V) >= L {
				if inRun && o.T.Sub(runEnd) > maxGap {
					flush()
				}
				if !inRun {
					runStart, runEnd, inRun = o.T, o.T, true
					nRun = 1
				} else {
					runEnd = o.T
					nRun++
				}
			} else {
				flush()
			}
		}
		flush()
		if counts {
			return math.Max(cur, float64(L)*perUE)
		}
	}
	peak := cur
	for _, o := range samp {
		if o.T.After(cut) && lvl(o.V) <= lcur && o.V > peak {
			peak = o.V
		}
	}
	return peak
}

func (v *V6Shadow) peakSinceLocked(d time.Duration, cur float64) float64 {
	peak := cur
	cut := time.Now().Add(-d)
	for _, o := range v.offHist {
		if o.T.After(cut) && o.V > peak {
			peak = o.V
		}
	}
	for _, o := range v.offFine {
		if o.T.After(cut) && o.V > peak {
			peak = o.V
		}
	}
	return peak
}

// mergeOfferedFine folds the agent's 5 s-bucket UL history (×2 = bidirectional) into
// offFine, de-duplicated by bucket time, keeping 15 minutes. caller holds v.mu.
func (v *V6Shadow) mergeOfferedFine(h []OfferedSample) {
	if len(h) == 0 {
		return
	}
	seen := make(map[int64]int, len(v.offFine))
	for i, o := range v.offFine {
		seen[o.T.Unix()] = i
	}
	for _, x := range h {
		if x.PPS <= 0 {
			continue
		}
		if i, ok := seen[x.T.Unix()]; ok {
			if 2*x.PPS > v.offFine[i].V {
				v.offFine[i].V = 2 * x.PPS
			}
			continue
		}
		v.offFine = append(v.offFine, offSample{T: x.T, V: 2 * x.PPS})
		seen[x.T.Unix()] = len(v.offFine) - 1
	}
	sort.Slice(v.offFine, func(i, j int) bool { return v.offFine[i].T.Before(v.offFine[j].T) })
	for len(v.offFine) > 0 && time.Since(v.offFine[0].T) > 15*time.Minute {
		v.offFine = v.offFine[1:]
	}
}

func vmScaleOutDwellSec() float64 { return envcfg.Float("V6_VM_SCALEOUT_DWELL_S", 2*v6TH) }

const riseMemory = 10 * time.Minute

// slopeWindowSec mirrors the collector's Slope120 regression window (WINDOW_SLOPE
// default "120s"): the planner slope bound extrapolates over the same span it was
// measured on.
const slopeWindowSec = 120.0

// MaxNewHighRise is MaxRiseOver restricted to start points that were the running
// maximum of the memory up to then: it measures how much the workload climbed
// ABOVE its previous high within span. A recovery from a dip back to the old peak
// contributes ~0 (r9 min31: 9.3→6.5→9.3M), a staircase ramp contributes each step.
func (v *V6Shadow) MaxNewHighRise(span, memory time.Duration) float64 {
	v.mu.Lock()
	defer v.mu.Unlock()
	return v.maxNewHighRise(span, memory)
}

func (v *V6Shadow) maxNewHighRise(span, memory time.Duration) float64 {
	cut := time.Now().Add(-memory)
	best, runMax := 0.0, -1.0
	for j := 0; j < len(v.offHist); j++ {
		if v.offHist[j].T.Before(cut) {
			continue
		}
		isHigh := v.offHist[j].V >= runMax
		if v.offHist[j].V > runMax {
			runMax = v.offHist[j].V
		}
		if !isHigh {
			continue
		}
		for i := j + 1; i < len(v.offHist) && v.offHist[i].T.Sub(v.offHist[j].T) <= span; i++ {
			if r := v.offHist[i].V - v.offHist[j].V; r > best {
				best = r
			}
		}
	}
	return best
}

// newHighRiseNow: how far the current window's maximum sits above the running
// maximum of the memory BEFORE the window (0 if it does not exceed it). A recovery to
// an old peak contributes 0; each step of a live ramp contributes its height.
// caller holds v.mu.
func (v *V6Shadow) newHighRiseNow(span, memory time.Duration) float64 {
	if len(v.offHist) == 0 {
		return 0
	}
	now := v.offHist[len(v.offHist)-1].T
	cut, winStart := now.Add(-memory), now.Add(-span-time.Second)
	runMax := -1.0
	for _, o := range v.offHist {
		if o.T.Before(cut) || !o.T.Before(winStart) {
			continue
		}
		if o.V > runMax {
			runMax = o.V
		}
	}
	cur := -1.0 // max over the current window (incl. the latest sample)
	for _, o := range v.offHist {
		if !o.T.Before(winStart) && o.V > cur {
			cur = o.V
		}
	}
	if runMax < 0 {
		// no sample before the window: treat the window's own start as the reference
		first := -1.0
		for _, o := range v.offHist {
			if !o.T.Before(winStart) {
				first = o.V
				break
			}
		}
		if first < 0 {
			return 0
		}
		runMax = first
	}
	if r := cur - runMax; r > 0 {
		return r
	}
	return 0
}

// MaxRiseOver returns the largest increase offered(t₂)−offered(t₁) over any pair
// of samples with 0 < t₂−t₁ ≤ span, both within the last memory. It is the
// self-consistent "how much can demand rise within a horizon of this length"
// statistic: a single staircase step counts once however short it was, and a
// sustained ramp counts by its observed amplitude over the same span.
// (MaxStepSince is the span=one-grid special case; MaxSlopeSince×span would
// instead extrapolate one 30 s step across the whole span — r9 printed peaks
// of 24-28M against a 9.3M workload from exactly that.)
func (v *V6Shadow) ConfirmedSlope() float64 {
	if v == nil {
		return 0
	}
	v.mu.Lock()
	defer v.mu.Unlock()
	if !v.Last.Valid {
		return 0
	}
	return v.Last.In.Slope
}

func (v *V6Shadow) OfferedNonIncreasingFor(d time.Duration, tol float64) bool {
	if v == nil {
		return false
	}
	v.mu.Lock()
	defer v.mu.Unlock()
	cut := time.Now().Add(-d)
	var prev *offSample
	covered := false
	for i := range v.offHist {
		o := &v.offHist[i]
		if o.T.Before(cut) {
			covered = true
			continue
		}
		if prev != nil && o.V > prev.V+tol {
			return false
		}
		prev = o
	}
	return covered && prev != nil
}

func (v *V6Shadow) MaxRiseOver(span, memory time.Duration) float64 {
	v.mu.Lock()
	defer v.mu.Unlock()
	return v.maxRiseOver(span, memory)
}

func (v *V6Shadow) maxRiseOver(span, memory time.Duration) float64 {
	cut := time.Now().Add(-memory)
	best := 0.0
	for i := 1; i < len(v.offHist); i++ {
		if v.offHist[i].T.Before(cut) {
			continue
		}
		for j := i - 1; j >= 0; j-- {
			if v.offHist[j].T.Before(cut) || v.offHist[i].T.Sub(v.offHist[j].T) > span {
				break
			}
			if r := v.offHist[i].V - v.offHist[j].V; r > best {
				best = r
			}
		}
	}
	return best
}

// MaxStepSince returns the largest positive jump between consecutive offered
// samples within the last d (staircase-workload step size, measured).
func (v *V6Shadow) MaxStepSince(d time.Duration) float64 {
	v.mu.Lock()
	defer v.mu.Unlock()
	cut := time.Now().Add(-d)
	best := 0.0
	for i := 1; i < len(v.offHist); i++ {
		if v.offHist[i].T.Before(cut) {
			continue
		}
		if st := v.offHist[i].V - v.offHist[i-1].V; st > best {
			best = st
		}
	}
	return best
}

// reverseOf returns the same-layer opposite action.
func reverseOf(a Action) Action {
	switch a {
	case ActDeployVyOS:
		return ActDeleteVyOS
	case ActDeleteVyOS:
		return ActDeployVyOS
	case ActCreateWorker:
		return ActDeleteWorker
	case ActDeleteWorker:
		return ActCreateWorker
	case ActScaleOutUP:
		return ActScaleInUP
	case ActScaleInUP:
		return ActScaleOutUP
	}
	return ""
}

// MaxSlopeSince returns the largest positive 30s-sample slope (pps/s) within d.
func (v *V6Shadow) MaxSlopeSince(d time.Duration) float64 {
	v.mu.Lock()
	defer v.mu.Unlock()
	cut := time.Now().Add(-d)
	best := 0.0
	for i := 1; i < len(v.offHist); i++ {
		if v.offHist[i].T.Before(cut) {
			continue
		}
		dt := v.offHist[i].T.Sub(v.offHist[i-1].T).Seconds()
		if dt <= 0 {
			continue
		}
		if sl := (v.offHist[i].V - v.offHist[i-1].V) / dt; sl > best {
			best = sl
		}
	}
	return best
}

// layerDelta: expected change of the layer count when the action takes effect.
func layerDelta(a Action) (up, vy, wk int) {
	switch a {
	case ActScaleOutUP:
		return +1, 0, 0
	case ActScaleInUP:
		return -1, 0, 0
	case ActDeployVyOS:
		return 0, +1, 0
	case ActDeleteVyOS:
		return 0, -1, 0
	case ActCreateWorker:
		return 0, 0, +1
	case ActDeleteWorker:
		return 0, 0, -1
	}
	return 0, 0, 0
}

// reconcileInflight drops in-flight moves whose effect is now observed in
// the live counts (or that timed out), and returns the rest as planner Moves
// with their REMAINING lead time.
func (v *V6Shadow) reconcileInflight(cur V6Config) []Move {
	now := time.Now()
	var keep []inflightMove
	var moves []Move
	claimed := map[string]int{}
	pending := map[string]bool{}
	for _, m := range v.inflight {
		up, vy, wk := layerDelta(m.Act)
		bc := m.Base.NWK
		if up != 0 {
			bc = m.Base.NUP
		} else if vy != 0 {
			bc = m.Base.NVY
		}
		key := fmt.Sprintf("%s@%d", m.Act, bc)
		n := claimed[key] + 1
		done := !pending[key] && ((up > 0 && cur.NUP >= m.Base.NUP+up*n) || (up < 0 && cur.NUP <= m.Base.NUP+up*n) ||
			(vy > 0 && cur.NVY >= m.Base.NVY+vy*n) || (vy < 0 && cur.NVY <= m.Base.NVY+vy*n) ||
			(wk > 0 && cur.NWK >= m.Base.NWK+wk*n) || (wk < 0 && cur.NWK <= m.Base.NWK+wk*n))
		if done {
			claimed[key]++
		} else {
			pending[key] = true
		}
		tr := v.calib.Act[m.Act].TReadySec
		el := now.Sub(m.T0).Seconds()
		if done && el >= tr {
			v.log.Info("v6 inflight done", "action", m.Act, "elapsed_s", int(el))
			v.recent = append(v.recent, inflightMove{Act: m.Act, T0: m.T0, Base: m.Base})
			continue
		}
		if done {
			keep = append(keep, m)
			moves = append(moves, Move{Act: m.Act, TEffect: v6Grid, deltaUP: 0, deltaVY: 0, deltaWK: 0})
			continue
		}
		if el > tr+2*v6Grid {
			v.log.Warn("v6 inflight expired (effect never observed)", "action", m.Act, "elapsed_s", int(el))
			continue
		}
		keep = append(keep, m)
		rem := tr - el
		if rem < v6Grid {
			rem = v6Grid // imminent but not yet observed: one grid
		}
		moves = append(moves, Move{Act: m.Act, TEffect: rem, deltaUP: up, deltaVY: vy, deltaWK: wk})
	}
	v.inflight = keep
	return moves
}

// Tick runs one shadow decision. frozen mirrors the v5 transition-freeze
// verdict so the shadow faces the same feasibility the live controller would.
func (v *V6Shadow) Tick(f FeatureSet, s SystemState, timers *Timers, cfg Cfg, frozen bool) {
	if v == nil || !v.Enabled {
		return
	}
	v.mu.Lock()
	defer v.mu.Unlock()

	// --- offered load (bidirectional aggregate entering the chain) ---
	offered := 2 * s.OfferedPPS // agent sender-egress is unidirectional UL
	slope := 0.0
	if metricAvailable(f.PktRateUP) {
		slope = f.PktRateUP.Slope120 // bidirectional (Σ upf_xdp_tx)
		if offered <= 0 {
			offered = f.PktRateUP.Robust60Raw() // fallback: measured through-UP
		}
		if slope > 0 && !v.episodeStart.IsZero() && time.Since(v.episodeStart) < time.Duration(2*slopeWindowSec)*time.Second {
			slope = 0
		}
	}
	if offered <= 0 {
		return // nothing meaningful to plan against
	}

	nvy := s.VyosCount
	if s.VyosAdmitted > 0 && s.VyosAdmitted < nvy {
		nvy = s.VyosAdmitted
	}
	v6cfg := V6Config{NUP: s.RepUP, NVY: nvy, NWK: s.WorkerCount}
	if v6cfg.NUP < 1 || v6cfg.NVY < 1 || v6cfg.NWK < 1 {
		return
	}
	v.offHist = append(v.offHist, offSample{T: time.Now(), V: offered})
	for len(v.offHist) > 0 && time.Since(v.offHist[0].T) > 15*time.Minute {
		v.offHist = v.offHist[1:]
	}
	v.mergeOfferedFine(s.OfferedHist)
	if v.rise != nil {
		var fine []offSample
		for _, x := range s.OfferedHist {
			if x.T.After(v.riseFineLast) {
				fine = append(fine, offSample{T: x.T, V: 2 * x.PPS})
			}
		}
		for _, x := range fine {
			if x.T.After(v.riseFineLast) {
				v.riseFineLast = x.T
			}
		}
		v.rise.Observe(time.Now(), offered, fine)
	}
	if slope > 0 {
		rise := v.newHighRiseNow(time.Duration(slopeWindowSec*float64(time.Second)), riseMemory)
		lim := rise / slopeWindowSec
		if v.calib.BatchIntervalSec <= 0 {
			if f := v.calib.StepFloor / v6TH; lim < f {
				lim = f
			}
		}
		if slope > lim {
			slope = lim
		}
	}
	if slope > 0 {
		v.posSlopeTicks++
	} else {
		v.posSlopeTicks = 0
	}
	if n := v.slopeConfirmTicks(); slope > 0 && v.posSlopeTicks < n {
		slope = 0
	}
	inflight := v.reconcileInflight(v6cfg)

	// --- measured per-segment loss → residuals (§3) ---
	meas := SegLoss{}
	measValid := offered >= envcfg.Float("V6_MEAS_MIN_PPS", 200000)
	if measValid && metricAvailable(f.DropUP) {
		meas.UP = clamp01(f.DropUP.P90_60)
	}
	if !measValid {
		// no update
	} else if metricAvailable(f.VyosLossRatio) {
		meas.VY = clamp01(f.VyosLossRatio.P90_60)
	} else if metricAvailable(f.VyosDropErr) && metricAvailable(f.PktRateUP) {
		rx := f.PktRateUP.Robust60Raw() / float64(v6cfg.NVY)
		dr := f.VyosDropErr.P90_60
		if rx+dr > 0 {
			meas.VY = dr / (rx + dr)
		}
	}
	if measValid {
		UpdateResiduals(&v.resid, meas, v6cfg, offered, 0.5 /* GRID/W_settle */, &v.calib)
	}

	measE2E := 1 - (1-meas.VY)*(1-meas.UP)
	if v.offeredEWMA == 0 {
		v.offeredEWMA = offered
	} else {
		v.offeredEWMA = 0.7*v.offeredEWMA + 0.3*offered
	}
	emerg, why := EmergencyV6(measE2E, v6cfg, v.offeredEWMA, &v.calib)
	if emerg {
		v.emergMeasStreak++
		if v.emergMeasStreak < 2 {
			emerg, why = false, ""
		}
	} else {
		v.emergMeasStreak = 0
	}

	blocked := map[Action]bool{}
	var keepRecent []inflightMove
	for _, m := range v.recent {
		tr := v.calib.Act[m.Act].TReadySec
		dw := 2 * tr
		if m.Act.IsScaleOut() && dw < v6TH {
			dw = v6TH
		}
		if m.Act == ActDeployVyOS || m.Act == ActCreateWorker {
			if d := vmScaleOutDwellSec(); dw < d {
				dw = d
			}
		}
		if v.rise != nil && m.Act.IsScaleOut() {
			dw = qBreakEven(reverseOf(m.Act), &v.calib, v.params) * qDwellK()
		}
		if m.Act.IsScaleIn() {
			if w := recentKeepSecScaleIn(&v.calib, m.Act); w > dw {
				dw = w
			}
		}
		if time.Since(m.T0).Seconds() < dw {
			keepRecent = append(keepRecent, m)
			if m.Act.IsScaleOut() {
				blocked[reverseOf(m.Act)] = true
			}
		}
	}
	v.recent = keepRecent
	for _, m := range inflight {
		switch m.Act {
		case ActDeployVyOS:
			blocked[ActDeleteVyOS] = true
		case ActCreateWorker:
			blocked[ActDeleteWorker] = true
		case ActScaleOutUP:
			blocked[ActScaleInUP] = true
		case ActScaleInUP:
			blocked[ActDeleteWorker] = true
		}
	}
	if emerg {
		blocked[ActScaleInUP] = true
		blocked[ActDeleteVyOS] = true
		blocked[ActDeleteWorker] = true
	}
	if s.ReadyUP < s.RepUP || s.PodPendingCount > 0 {
		blocked[ActScaleOutUP] = true
	}
	_ = timers
	_ = frozen

	in := PlanInput{
		Cfg: v6cfg, Offered: offered, Slope: slope, Resid: v.resid,
		Bounds: V6Bounds{
			MinUP: cfg.MinUP, MaxUP: cfg.MaxUP,
			MinVY: cfg.MinVyos, MaxVY: cfg.MaxVyos,
			MinWK: cfg.MinWorkers, MaxWK: cfg.MaxWorkers,
		},
		Blocked:   blocked,
		InFlight:  inflight,
		IdleWK:    s.IdleWorker != "",
		BaseCores: v.baseCores, BaseMemGi: v.baseMemGi,
	}

	var best TupleScore
	var all []TupleScore
	if v.rise != nil {
		best, v.LastQ = decideQuantile(in, PlanCalib(&v.calib, v.params), v.params, v.rise)
	} else {
		best, all = DecideV6(in, &v.calib, v.params)
	}
	v.Last.Valid = true
	v.Last.Best = best
	v.Last.In = in
	v.Last.Emergency = emerg
	v.Last.EmergWhy = why
	v.Last.MeasE2E = measE2E
	v.Last.Meas = meas
	for _, sc := range all {
		if sc.Key == "∅" {
			v.Last.NoOpJ = sc.J
			break
		}
	}

	// one structured line per tick — the P2 comparison dataset
	v.log.Info("v6shadow",
		"tuple", best.Key, "j", best.J, "j_noop", v.Last.NoOpJ,
		"offered", offered, "slope", slope,
		"nup", v6cfg.NUP, "nvy", v6cfg.NVY, "nwk", v6cfg.NWK,
		"resid_up", v.resid.UP, "resid_vy", v.resid.VY,
		"meas_up", meas.UP, "meas_vy", meas.VY, "meas_e2e", measE2E,
		"emergency", emerg, "rollout", len(best.Rollout), "inflight", len(inflight),
	)
	if v.rise != nil {
		q := v.LastQ
		v.log.Info("v7q",
			"eps", v.rise.Eps(), "offered", q.Offered,
			"m_up", q.MarginUP, "m_vy", q.MarginVY, "m_wk", q.MarginWK,
			"need_up", q.NeedUP, "need_vy", q.NeedVY, "need_wk", q.NeedWK,
			"nup", v6cfg.NUP, "nvy", v6cfg.NVY, "nwk", v6cfg.NWK, "tuple", best.Key,
		)
	}
}

// Snapshot returns a copy of the last shadow state for /metrics and /state.
func (v *V6Shadow) Snapshot() (last TupleScore, noopJ float64, resid Residuals, emerg bool, valid bool) {
	if v == nil {
		return
	}
	v.mu.Lock()
	defer v.mu.Unlock()
	return v.Last.Best, v.Last.NoOpJ, v.resid, v.Last.Emergency, v.Last.Valid
}

func (v *V6Shadow) RecentlyDispatched(a Action, within time.Duration) bool {
	if v == nil {
		return false
	}
	v.mu.Lock()
	defer v.mu.Unlock()
	cut := time.Now().Add(-within)
	for _, m := range v.inflight {
		if m.Act == a && m.T0.After(cut) {
			return true
		}
	}
	for _, m := range v.recent {
		if m.Act == a && m.T0.After(cut) {
			return true
		}
	}
	return false
}

// recentKeepSecScaleIn: how long a finished scale-in must stay visible to RecentlyDispatched —
// the emergency reverse-guard window T_ready(reverse)+T_ready(self)+grid.
func recentKeepSecScaleIn(cal *Calib, a Action) float64 {
	if !a.IsScaleIn() {
		return 0
	}
	rev := reverseOf(a)
	if rev == "" {
		return 0
	}
	return cal.Act[rev].TReadySec + cal.Act[a].TReadySec + v6Grid
}
