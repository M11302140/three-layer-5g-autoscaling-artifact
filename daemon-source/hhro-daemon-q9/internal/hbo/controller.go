package hbo

import (
	"context"
	"fmt"
	"log/slog"
	"math"
	"sync"
	"sync/atomic"
	"time"

	"github.com/anon/hhro-daemon/internal/envcfg"
	"github.com/anon/hhro-daemon/internal/promq"
	"github.com/anon/hhro-daemon/internal/state"
)

// Controller is the HBO-HHRO decision engine. It replaces the old Decisioner.
type Controller struct {
	cfg     Cfg
	enabled atomic.Bool
	wc      *WindowCollector
	freeze  *state.Freeze
	log     *slog.Logger
	shadow  *V6Shadow // P2: v6 planner in shadow mode (logs, never actuates)

	mu           sync.Mutex
	lastDecision atomic.Pointer[Decision]

	lastEmergForce time.Time // E3-r6:emergency force +1 refractory

	// latest computed values (exported for /metrics and /state)
	lastFeatures FeatureSet

	v6Active bool
	v6Moves, v6Overrides atomic.Int64
	vyDeployStreak int
}

func NewController(cfg Cfg, prom *promq.Prom, freeze *state.Freeze, log *slog.Logger) *Controller {
	c := &Controller{
		cfg:    cfg,
		wc:     NewWindowCollector(prom, cfg),
		freeze: freeze,
		log:    log,
		shadow: NewV6Shadow(log),
	}
	c.enabled.Store(cfg.Enabled)
	c.v6Active = envcfg.Get("V6_ENABLED", "false") == "true"
	if c.v6Active {
		log.Info("v6 pipeline ACTIVE (P3)", "note", "v5 policy chain + slow-loop VM decisions disabled")
	}
	return c
}

func (c *Controller) V6Active() bool { return c.v6Active }

// V6NoteDispatched records a successfully actuated v6 action as in-flight
func (c *Controller) V6NoteDispatched(a Action) { c.shadow.NoteDispatched(a) }

// V6DropInFlight removes in-flight records of one action (reversible drain cancelled).
func (c *Controller) V6DropInFlight(a Action) { c.shadow.DropInFlight(a) }

// V6InFlight exposes the in-flight set for /state.
func (c *Controller) V6InFlight() []Action { return c.shadow.InFlight() }

// V6QState exposes the v7 quantile model state (nil in batch mode) for /state.
func (c *Controller) V6QState() map[string]any {
	if !c.shadow.QMode() {
		return nil
	}
	c.shadow.mu.Lock()
	q := c.shadow.LastQ
	c.shadow.mu.Unlock()
	lvm, lup := c.shadow.Rise().Lambdas()
	model := "quantile"
	if c.shadow.Rise().SigmaMode() {
		model = "sigma"
	}
	return map[string]any{"model": model, "eps": c.shadow.Rise().Eps(), "lam_vm": lvm, "lam_up": lup, "needs": q, "coverage": c.shadow.Rise().Coverage()}
}

// V6ResetEpisode clears planner history at the start of a closed-loop episode.
func (c *Controller) V6ResetEpisode() { c.shadow.ResetEpisode() }

func (c *Controller) V6GuardStats() (int64, int64) {
	return c.v6Moves.Load(), c.v6Overrides.Load()
}

// V6Decisions converts the freshest shadow tuple (computed in this tick's
// decide()) into dispatchable Decisions, applying the SAFETY guards that v6's
// model does not subsume (drop-ratio/pending/node-pressure/min-floors;
// policy-level v5 heuristics are the model's job now). Call AFTER Decide().
func (c *Controller) V6Decisions(s SystemState) []Decision {
	if !c.v6Active || !c.enabled.Load() {
		return nil
	}
	c.shadow.mu.Lock()
	valid := c.shadow.Last.Valid
	best := c.shadow.Last.Best
	noopJ := c.shadow.Last.NoOpJ
	emerg := c.shadow.Last.Emergency
	meas := c.shadow.Last.Meas
	c.shadow.mu.Unlock()
	if !valid {
		return nil
	}
	c.mu.Lock()
	f := c.lastFeatures
	c.mu.Unlock()

	c.shadow.mu.Lock()
	offered := c.shadow.Last.In.Offered
	c.shadow.mu.Unlock()

	now := nowFn()
	var out []Decision
	wantVy := false
	for _, mv := range best.Moves {
		if mv.Act == ActDeployVyOS {
			wantVy = true
		}
	}
	if wantVy {
		c.vyDeployStreak++
	} else {
		c.vyDeployStreak = 0
	}
	vyConfirm := envcfg.Int("V6_VY_DEPLOY_CONFIRM_TICKS", 1)
	qmode := c.shadow.QMode()
	if qmode {
		vyConfirm = 1
	}
	for _, mv := range best.Moves {
		c.v6Moves.Add(1)
		ok, why := true, ""
		switch mv.Act {
		case ActScaleInUP:
			ok, why = scaleInSafety(f, s, c.cfg)
		case ActCreateWorker:
			ok, why = workerCreateInfraOnly(s, c.cfg)
		case ActDeleteWorker:
			ok, why = workerDeleteInfraOnly(s, c.cfg)
			if ok && !qmode && workerDeleteLocksSlotLayer(best.Moves, s, PlanCalib(&c.shadow.calib, c.shadow.params)) {
				ok, why = false, fmt.Sprintf("worker delete deferred: planner still wants SCALE_IN_UP and deletion leaves no free slot position (rep %d, workers %d)", s.RepUP, s.WorkerCount)
			}
			if ok && !qmode && envcfg.Bool("V6_WK_DELETE_KEEP_SPARE", true) {
				cal := PlanCalib(&c.shadow.calib, c.shadow.params)
				if need, pos, nb, fits := workerDeleteHeadroomOK(offered, s, cal); !fits {
					ok, why = false, fmt.Sprintf("worker delete deferred: slot layer may need %d slots within worker lead time (%d batches, offered %.2fM) > %d positions after deletion (rep %d, workers %d)", need, nb, offered/1e6, pos, s.RepUP, s.WorkerCount)
				}
			}
			if ok && !qmode {
				if dw := time.Duration(envcfg.Float("V6_WK_DELETE_SLOT_DWELL_S", 120)) * time.Second; dw > 0 && c.shadow.SlotLayerChangedWithin(dw) {
					ok, why = false, fmt.Sprintf("worker delete deferred: slot layer changed within %.0fs (VM-layer scale-in waits one horizon)", dw.Seconds())
				}
			}
		case ActDeployVyOS:
			if !emerg && c.vyDeployStreak < vyConfirm {
				ok, why = false, fmt.Sprintf("vyos deploy confirm %d/%d ticks (p5u23: single-tick knife crossing is not a ramp)", c.vyDeployStreak, vyConfirm)
			}
		case ActDeleteVyOS:
			ok, why = vyosDeleteInfraOnly(s, c.cfg)
		}
		if ok && mv.Act.IsScaleIn() {
			cal := PlanCalib(&c.shadow.calib, c.shadow.params)
			if qmode {
				if hold, hwhy := holdQuantile(mv.Act, s, offered, c.shadow, cal); hold {
					ok, why = false, hwhy
				}
			} else if hold, hwhy := irreversibilityHold(mv.Act, s, offered, c.shadow, cal); hold {
				ok, why = false, hwhy
			}
		}
		if ok && !qmode && mv.Act == ActScaleInUP {
			if hold, hwhy := scaleInMarginHold(best.J, noopJ, emerg, scaleInMarginJ()); hold {
				ok, why = false, hwhy
			}
		}
		if !ok {
			c.v6Overrides.Add(1)
			c.log.Info("v6 move guard-overridden", "action", mv.Act, "why", why)
			continue
		}
		out = append(out, Decision{
			Action: mv.Act,
			Reason: fmt.Sprintf("v6 tuple %s J=%.4f noopJ=%.4f emerg=%v", best.Key, best.J, noopJ, emerg),
			At:     now,
		})
	}

	if kept, dropped := slotDrainBeforeWorkerDelete(out); dropped {
		c.log.Info("v6 move deferred: worker delete waits for slot drain dispatched this tick", "action", ActDeleteWorker)
		out = kept
	}

	if emerg {
		hasOut := false
		for _, d := range out {
			if d.Action.IsScaleOut() {
				hasOut = true
			}
		}
		if !hasOut && sinceFn(c.lastEmergForce) >
			time.Duration(envcfg.Int("V6_EMERG_REFRACTORY_SEC", 90))*time.Second {
			var act Action
			if meas.VY >= meas.UP && s.VyosCount < c.cfg.MaxVyos {
				act = ActDeployVyOS
			} else if s.RepUP < c.cfg.MaxUP && s.PodPendingCount == 0 && s.ReadyUP >= s.RepUP {
				act = ActScaleOutUP
			}
			if act != "" {
				var rev Action
				switch act {
				case ActDeployVyOS:
					rev = ActDeleteVyOS
				case ActScaleOutUP:
					rev = ActScaleInUP
				}
				if rev != "" {
					win := time.Duration((c.shadow.calib.Act[rev].TReadySec + c.shadow.calib.Act[act].TReadySec + v6Grid) * float64(time.Second))
					if c.shadow.RecentlyDispatched(rev, win) {
						c.log.Info("v6 emergency force suppressed: reverse of recent scale-in", "action", act, "recent", rev, "window_s", win.Seconds())
						act = ""
					}
				}
			}
			if act != "" {
				c.lastEmergForce = nowFn()
				c.log.Info("v6 emergency force", "action", act,
					"meas_up", meas.UP, "meas_vy", meas.VY)
				out = append(out, Decision{
					Action: act,
					Reason: fmt.Sprintf("v6 emergency force +1 (meas UP=%.4f VY=%.4f)", meas.UP, meas.VY),
					At:     now,
				})
			}
		}
	}
	return out
}

func workerLeadBatches(cal *Calib) int {
	if n := envcfg.Int("V6_WK_LEAD_BATCHES", 0); n > 0 {
		return n
	}
	if cal.BatchIntervalSec <= 0 {
		return 1
	}
	lead := cal.Act[ActCreateWorker].TReadySec + cal.Act[ActScaleOutUP].TReadySec + v6Grid
	nb := int(math.Ceil(lead / cal.BatchIntervalSec))
	if nb < 1 {
		nb = 1
	}
	return nb
}

func slotsNeededUP(x float64, cal *Calib) int {
	for n := 1; n < 64; n++ {
		if uUPQuant(x, n, cal) <= ThetaDesignUP(cal) {
			return n
		}
	}
	return 64
}

func workerDeleteHeadroomOK(offered float64, s SystemState, cal *Calib) (need, pos, nb int, fits bool) {
	nb = workerLeadBatches(cal)
	need = slotsNeededUP(offered+float64(nb)*cal.StepFloor, cal)
	if need < s.RepUP {
		need = s.RepUP
	}
	pos = (s.WorkerCount - 1) * slotsPerWorker
	return need, pos, nb, need <= pos
}

func workerDeleteLocksSlotLayer(moves []Move, s SystemState, cal *Calib) bool {
	if !hasMove(moves, ActScaleInUP) || s.WorkerCount <= 1 {
		return false
	}
	after := s
	after.WorkerCount--
	return irreversibilityWindow(ActScaleInUP, after, cal) > irreversibilityWindow(ActScaleInUP, s, cal)
}

// slotDrainBeforeWorkerDelete drops DELETE_WORKER from a tick's dispatch list when a
func slotDrainBeforeWorkerDelete(out []Decision) (kept []Decision, dropped bool) {
	hasSlot := false
	for _, d := range out {
		if d.Action == ActScaleInUP {
			hasSlot = true
		}
	}
	if !hasSlot {
		return out, false
	}
	for _, d := range out {
		if d.Action == ActDeleteWorker {
			dropped = true
			continue
		}
		kept = append(kept, d)
	}
	return kept, dropped
}

func (c *Controller) SetEnabled(v bool)       { c.enabled.Store(v) }
func (c *Controller) IsEnabled() bool         { return c.enabled.Load() }
func (c *Controller) LastDecision() *Decision { return c.lastDecision.Load() }
func (c *Controller) Shadow() *V6Shadow       { return c.shadow }

// Snapshot returns the latest computed state for /metrics export.
func (c *Controller) Snapshot() FeatureSet {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.lastFeatures
}

// Decide runs the full HBO-HHRO pipeline for the mid-control loop.
func (c *Controller) Decide(ctx context.Context, sysState SystemState) Decision {
	dec := c.decide(ctx, sysState)
	c.lastDecision.Store(&dec)
	return dec
}

func (c *Controller) decide(ctx context.Context, s SystemState) Decision {
	now := nowFn()
	// v8: features only (the v5 pressure/risk/bottleneck chain is deleted).
	f := c.wc.CollectFeatures(ctx)
	c.mu.Lock()
	c.lastFeatures = f
	c.mu.Unlock()
	// v6/v8 planner tick — logged decision; tuples are dispatched by the daemon via V6Decisions().
	c.shadow.Tick(f, s, c.cfg)
	if !c.enabled.Load() {
		return Decision{Action: ActNone, Reason: "autoscale disabled", At: now}
	}
	return Decision{Action: ActNone, Reason: "v6 pipeline active", At: now}
}

func irreversibilityWindowRaw(act Action, s SystemState, cal *Calib) float64 {
	if act != ActScaleInUP {
		return irreversibilityWindow(act, s, cal)
	}
	w := cal.Act[ActScaleOutUP].TReadySec
	if s.RepUP >= s.WorkerCount*slotsPerWorker {
		w = cal.Act[ActScaleInUP].TReadySec + cal.Act[ActScaleOutUP].TReadySec
		if s.RepUP-1 >= s.WorkerCount*slotsPerWorker {
			w += cal.Act[ActCreateWorker].TReadySec
		}
	}
	return w
}

func irreversibilityWindow(act Action, s SystemState, cal *Calib) float64 {
	switch act {
	case ActScaleInUP:
		w := cal.Act[ActScaleOutUP].TReadySec
		if s.RepUP >= s.WorkerCount*slotsPerWorker {
			w = cal.Act[ActScaleInUP].TReadySec + cal.Act[ActScaleOutUP].TReadySec
			if s.RepUP-1 >= s.WorkerCount*slotsPerWorker {
				w += cal.Act[ActCreateWorker].TReadySec
			}
		}
		if h := envcfg.Float("V6_UP_SCALEIN_HOLD_S", v6TH); h > w {
			w = h
		}
		return w
	case ActDeleteVyOS:
		return cal.Act[ActDeployVyOS].TReadySec
	case ActDeleteWorker:
		return cal.Act[ActDeleteWorker].TReadySec + cal.Act[ActCreateWorker].TReadySec + cal.Act[ActScaleOutUP].TReadySec
	}
	return 0
}

//
func irreversibilityHold(act Action, s SystemState, offered float64, sh *V6Shadow, cal *Calib) (bool, string) {
	if !envcfg.Bool("V6_IRREV_HOLD", true) {
		return false, ""
	}
	return irreversibilityHoldWindow(act, s, offered, sh, cal, holdWindowFor(act, s, sh, cal))
}

func holdWindowFor(act Action, s SystemState, sh *V6Shadow, cal *Calib) float64 {
	w := irreversibilityWindow(act, s, cal)
	if act != ActScaleInUP || sh == nil || cal.BatchIntervalSec <= 0 || !envcfg.Bool("V6_UP_HOLD_ADAPTIVE", false) {
		return w
	}
	long := envcfg.Float("V6_UP_SCALEIN_HOLD_S", v6TH)
	short := cal.BatchIntervalSec
	if short >= w {
		return w
	}
	tol := ueQuantTol() * cal.PerUEBidir
	if sh.OfferedNonIncreasingFor(time.Duration(long*float64(time.Second)), tol) {
		if w > long {
			return w
		}
		if wo := irreversibilityWindowRaw(act, s, cal); wo > short {
			return wo
		}
		return short
	}
	return w
}

// irreversibilityHoldWindow is the judgement with an explicit commitment window
// (seconds) — split out so the r7 replay test can contrast the old 15 s window
// against the corrected T_in+T_out one.
func irreversibilityHoldWindow(act Action, s SystemState, offered float64, sh *V6Shadow, cal *Calib, outT float64) (bool, string) {
	win := time.Duration((outT + v6Grid) * float64(time.Second))
	if age := sh.EpisodeAge(); envcfg.Bool("V6_HOLD_UNTIL_HISTORY", true) && age > 0 && age < win.Seconds() {
		return true, fmt.Sprintf("irreversibility hold: episode age %.0fs < commitment window %.0fs (no history yet)", age, win.Seconds())
	}
	peak := sh.PeakOfferedSince(win, offered)
	if act == ActScaleInUP && cal.BatchIntervalSec > 0 && envcfg.Bool("V6_UP_HOLD_SUSTAINED", true) {
		peak = sh.SustainedPeakSince(win, time.Duration(cal.BatchIntervalSec*float64(time.Second)), offered, cal.PerUEBidir)
	}
	rise := sh.MaxRiseOver(win, riseMemory)
	if act == ActScaleInUP && envcfg.Bool("V6_UP_HOLD_RISE_SLOPE", true) {
		rise = 0
		if sl := sh.ConfirmedSlope(); sl > 0 {
			rise = sl * win.Seconds()
			if cap := float64(cal.MaxBatches) * cal.StepFloor; cal.MaxBatches > 0 && rise > cap {
				rise = cap
			}
		}
	}
	floor := cal.StepFloor
	if cal.BatchIntervalSec > 0 {
		nb := math.Ceil((outT + v6Grid) / cal.BatchIntervalSec)
		if cal.MaxBatches > 0 && nb > float64(cal.MaxBatches) {
			nb = float64(cal.MaxBatches)
		}
		if act == ActScaleInUP {
			if ub := upLookaheadBatches(cal); ub > 0 && float64(ub) < nb {
				nb = float64(ub)
			}
		}
		floor = nb * cal.StepFloor
	}
	if rise < floor {
		rise = floor
	}
	peak += rise
	inUP, inVY := 0, 0
	for _, a := range sh.InFlight() {
		switch a {
		case ActScaleInUP:
			inUP++
		case ActDeleteVyOS:
			inVY++
		}
	}
	switch act {
	case ActScaleInUP:
		rep := s.RepUP - inUP
		if rep-1 < 1 {
			return true, fmt.Sprintf("irreversibility hold: %d slot drain(s) already in flight (rep %d)", inUP, s.RepUP)
		}
		if uA := uUPQuant(peak, rep-1, cal); uA > ThetaDesignUP(cal) {
			return true, fmt.Sprintf("irreversibility hold: peak(%.0fs)=%.2fM → u_UP after=%.2f > θ=%.2f (in-flight drains %d)", outT, peak/1e6, uA, ThetaDesignUP(cal), inUP)
		}
	case ActDeleteVyOS:
		vy := s.VyosCount - inVY
		if vy-1 < 1 {
			return true, fmt.Sprintf("irreversibility hold: %d vyos delete(s) already in flight (count %d)", inVY, s.VyosCount)
		}
		if uA := peak / (float64(vy-1) * cal.CapVY); uA > ThetaDesignVY(cal) {
			return true, fmt.Sprintf("irreversibility hold: peak(%.0fs)=%.2fM → u_VY after=%.2f > θ=%.2f (in-flight deletes %d)", outT, peak/1e6, uA, ThetaDesignVY(cal), inVY)
		}
	}
	return false, ""
}

func scaleInMarginHold(bestJ, noopJ float64, emerg bool, margin float64) (bool, string) {
	if emerg || margin <= 0 {
		return false, ""
	}
	if adv := noopJ - bestJ; adv < margin {
		return true, fmt.Sprintf("scale-in margin hold: J advantage %.3f < %.2f (noop %.3f, tuple %.3f)", adv, margin, noopJ, bestJ)
	}
	return false, ""
}

func scaleInMarginJ() float64 { return envcfg.Float("V6_SCALEIN_MARGIN_J", 0.15) }
