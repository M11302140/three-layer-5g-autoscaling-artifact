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
	timers  *Timers
	freeze  *state.Freeze
	log     *slog.Logger
	shadow  *V6Shadow // P2: v6 planner in shadow mode (logs, never actuates)

	mu           sync.Mutex
	lastDecision atomic.Pointer[Decision]

	lastEmergForce time.Time // E3-r6:emergency force +1 refractory

	// latest computed values (exported for /metrics and /state)
	lastFeatures  FeatureSet
	lastPressure  PressureSet
	lastRisk      RiskSet
	lastBN        Bottleneck
	lastUtilities []ActionUtility

	v6Active bool
	v6Moves, v6Overrides atomic.Int64
	vyDeployStreak int
}

func NewController(cfg Cfg, prom *promq.Prom, freeze *state.Freeze, log *slog.Logger) *Controller {
	c := &Controller{
		cfg:    cfg,
		wc:     NewWindowCollector(prom, cfg),
		timers: NewTimers(cfg),
		freeze: freeze,
		log:    log,
		shadow: NewV6Shadow(log),
	}
	c.enabled.Store(cfg.Enabled)
	c.v6Active = envcfg.Get("V6_ENABLED", "false") == "true"
	if c.v6Active {
		c.timers.EnableV6Derived(&c.shadow.calib)
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
	return map[string]any{"eps": c.shadow.Rise().Eps(), "needs": q, "coverage": c.shadow.Rise().Coverage()}
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
	f, p, risk, bn := c.lastFeatures, c.lastPressure, c.lastRisk, c.lastBN
	c.mu.Unlock()

	c.shadow.mu.Lock()
	offered := c.shadow.Last.In.Offered
	c.shadow.mu.Unlock()

	now := time.Now()
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
			Action: mv.Act, Bottleneck: bn, Pressure: p, Risk: risk,
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
		if !hasOut && time.Since(c.lastEmergForce) >
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
				c.lastEmergForce = time.Now()
				c.log.Info("v6 emergency force", "action", act,
					"meas_up", meas.UP, "meas_vy", meas.VY)
				out = append(out, Decision{
					Action: act, Bottleneck: bn, Pressure: p, Risk: risk,
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
func (c *Controller) Timers() *Timers         { return c.timers }
func (c *Controller) Shadow() *V6Shadow       { return c.shadow }

// Snapshot returns the latest computed state for /metrics export.
func (c *Controller) Snapshot() (FeatureSet, PressureSet, RiskSet, Bottleneck) {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.lastFeatures, c.lastPressure, c.lastRisk, c.lastBN
}

// Decide runs the full HBO-HHRO pipeline for the mid-control loop.
func (c *Controller) Decide(ctx context.Context, sysState SystemState) Decision {
	dec := c.decide(ctx, sysState)
	c.lastDecision.Store(&dec)
	return dec
}

func (c *Controller) decide(ctx context.Context, s SystemState) Decision {
	now := time.Now()

	// Always collect features and compute pressure/risk/bottleneck for
	// observability (/metrics), even when autoscale is disabled or frozen.
	f := c.wc.CollectFeatures(ctx)
	p := ComputePressure(f, c.cfg, s.VyosCount, s.RepUP)
	bn := ClassifyBottleneck(f, p, s, c.cfg)
	risk := EstimateRisk(p, f, c.cfg)

	c.mu.Lock()
	c.lastFeatures = f
	c.lastPressure = p
	c.lastRisk = risk
	c.lastBN = bn
	c.mu.Unlock()

	// P2: v6 shadow tick — same inputs, logged decision, never actuated.
	// Runs even when autoscale is disabled (pure-observation runs still
	// produce the comparison dataset).
	shadowFrozen, _ := c.freeze.Active()
	c.shadow.Tick(f, s, c.timers, c.cfg, shadowFrozen)

	// Step 1: disabled check — still return computed state for audit
	if !c.enabled.Load() {
		return Decision{Action: ActNone, Bottleneck: bn, Pressure: p, Risk: risk, Reason: "autoscale disabled", At: now}
	}

	if c.v6Active {
		return Decision{Action: ActNone, Bottleneck: bn, Pressure: p, Risk: risk, Reason: "v6 pipeline active", At: now}
	}

	// Step 2: transition freeze — v4.70/Phase B: freeze now only blocks scale-OUT,
	// not scale-IN. The throughput-dominant pressure is noise-robust (a UE migration
	// can't fake a scale-out — Robust60Raw P90 ignores the transient), and scale-IN is
	// rebound-free (survivor projection) + gap-immune (P90 ignores a migration's
	// throughput dip). So a scale-IN during a freeze is safe, and exempting it fixes
	// the freeze delaying ramp-down scale-in (sess3: VyOS 2→1 stuck to cool because the
	// slow tick kept landing in migration freeze windows). Predictive VM-layer
	// scale-OUT (VyOS deploy / worker create) and UPF scale-OUT stay suppressed while
	// frozen (turbulence-conservative — no spurious capacity adds during rehome).
	frozen, _ := c.freeze.Active()

	// Step 5-6: bottleneck + risk already computed above

	// Step 6.45: Predictive VyOS pre-deploy (v4.67). VyOS is a VM (slow-loop lifecycle),
	// but like the worker pre-create below it needs MID-loop ANTICIPATION because VM boot
	// takes ~2min: a reactive deploy (only after p.Vyos≥VyosHigh, then boots) leaves the
	// 87-99%, vyos_count=1).
	//
	// TWO ordering/timing lessons baked in here (both bit run40 AND my first v4.66 attempt):
	//  1) This MUST run BEFORE the worker pre-create (Step 6.5). During ramp-up a UPF almost
	//     always wants a worker (max_worker_free<1700m), so Step 6.5 returns CREATE_WORKER
	//     EVERY mid tick — any VyOS deploy placed after it is starved forever (v4.66: vy
	//     stuck at 1 @99.9% CPU while the loop kept making workers). VyOS saturation hurts
	//     latency on ALL traffic, so it outranks the Nth worker; the worker it preempts is
	//     only delayed one 30s tick (and UPF→worker is also covered by the guard redirect).
	//  2) Trigger on the INSTANTANEOUS CpuVyosReal.Now, NOT the Robust60Raw level. risk.Vyos
	//     is dead for lead (its slope is computed from the SR-IOV-blind kubevirt CpuVyos →
	//     ~0 → risk_vyos≈0), and Robust60Raw lags ~60s, so the v4.66 p.Vyos>0.7·VyosHigh gate
	//     only crossed at ~700k — too late, vyos-1 still booting through the 99% saturation.
	//     Now·0.5·VyosHigh ≈ 27% guest CPU ≈ ~430k (early ru2): with the steep VyOS CPU curve
	//     (43%@600k→99%@800k) this gives the ~2min boot the lead it needs to be Ready before
	//     saturation. The vyRising gate (Now≥0.85·Robust60Raw) confines it to RISING load so
	//     it never pre-deploys into a ramp-down; cooldown(120s)+210s direction-lock keep it
	//     flap-safe (an over-eager deploy can't be reversed within the lock while load climbs
	//     past the point that justifies the 2nd node).
	// v(sess): vyRising must be GENUINELY climbing (Now >5% above the smoothed
	// Robust60Raw), not merely "not sharply falling". The old Now≥0.85·Robust was
	// TRUE even on a FLAT load (Now≈Robust), so on ramp-down — once the post-delete
	// concentration spike aged out of the 60s window and CPU sat flat at ~30% — it
	// read "rising" and pre-deployed a VyOS back (ramp-down rebound). Also the
	// trigger level is raised from 0.5·VyosHigh (≈27%, fired with plenty headroom)
	// to 0.75·VyosHigh (≈41%) so a single under-loaded VyOS doesn't pull a 2nd one.
	// v4.76: THROUGHPUT-DOMINANT predictive deploy — back to the user's original design.
	// p.Vyos = 0.5·throughput + 0.3·cpu + 0.2·loss, where throughput = norm(PktRateUP/
	// vyos_count, VyosThruCap). This signal is RIGHT for VyOS scale-out for three reasons
	// the CPU-based attempts kept fighting:
	//  • vbash-IMMUNE: it's UPF packet counters, not VyOS guest CPU (whose .Now spikes
	//    every time the rebalancer runs vbash). No smoothing/slope gymnastics needed.
	//  • LEADING: offered pps rises before CPU saturates → natural boot-lead.
	//  • NODE-COUNT-AWARE: dividing by vyos_count is what separates the stages — 1 VyOS at
	//    16 UE reads ~1.0 (deploy), 2 VyOS at the SAME 16 UE read ~0.5 (don't), 2 VyOS at
	//    24 UE climb back to ~0.75 (deploy). No CPU "is it imbalance vs capacity" gate needed.
	// VyosThruCap=1.8M calibrated from real data: 1 VyOS saturates (CPU 85-99%) at 16 UE
	// where PktRateUP≈1.8M bidirectional. Predictive uses 0.85·VyosHigh (≈0.47) for boot
	// lead — 2-VyOS-steady p.Vyos≈0.38 sits clear below it, so no ru2 false 3rd. Throughput
	// not-falling (vbash-immune) blocks ramp-down rebound.
	vyThruNotFalling := !metricAvailable(f.PktRateUP) || f.PktRateUP.Now >= 0.85*f.PktRateUP.Robust60Raw()
	// v4.79: VyOS predictive deploy is EXEMPT from the Phase B freeze. The freeze blocks
	// scale-OUT during UE-migration turbulence because the OLD CPU-noisy pressure could be
	// faked by a migration. p.Vyos is now THROUGHPUT-DOMINANT (vbash/migration-immune: a
	// rehome only DIPS offered pps, never spikes it, and not-falling guards the dip), so
	// freezing it just DELAYS scale-out: phaseG 1→2 sat ready at p.Vyos=0.555 but frozen=true
	// held it ~60s until 0.691. The deploy cooldown still prevents an in-stage double-deploy.
	// v5.0.32: pre-deploy fraction 0.85 -> env (default 1.0). With the 2c
	// gate-measured VYOS_THRU_CAP (3.8M) the 0.85 boot-lead fired the 2nd
	// vyos at 7 UE / 56% real single-vyos utilization (run#8v4 min4); at
	// 1.0xHIGH it fires at ~10 UE (run#7-like timing) while the 3rd vyos
	// still lands well before the flash-crowd design point.
	if p.Vyos >= c.cfg.VyosHigh*envcfg.Float("VYOS_PREDEPLOY_FRAC", 1.0) && vyThruNotFalling &&
		s.VyosCount < c.cfg.MaxVyos &&
		!c.timers.CooldownActive(ActDeployVyOS) {
		if blocked, _ := c.timers.DirectionLockBlocks(ActDeployVyOS); !blocked {
			c.log.Info("predictive VyOS pre-deploy",
				"reason", "p.Vyos (throughput-dominant) rising toward high (boot-lead anticipation)",
				"p_vyos", p.Vyos, "vy_throughput", p.VyosThroughput, "vy_cpu", p.VyosCpu,
				"vyos_count", s.VyosCount)
			return Decision{
				Action: ActDeployVyOS, Bottleneck: BNVyos, Pressure: p, Risk: risk,
				Reason: fmt.Sprintf("predictive VyOS: p.Vyos=%.3f (thru=%.2f) ≥ %.3f → boot-lead deploy",
					p.Vyos, p.VyosThroughput, c.cfg.VyosHigh*0.85),
				At: now,
			}
		}
	}

	// Step 6.5: Predictive worker pre-creation.
	// If UPF pressure is rising AND the next CNF scale-out would exhaust
	// worker capacity, pre-create a worker NOW so the CNF has somewhere
	// to land when it fires next tick. Avoids the "worker created but
	// empty because CNF already landed on old worker" problem.
	// Gate on RepUP < MaxUP: a new worker is only useful if a UPF can land on
	// it (CP is pinned to worker-0). Without this, the daemon over-creates idle
	// workers once UPF is already at its replica ceiling.
	// v4.50: the p.UP LEVEL disjunct must be NOT-FALLING. p.UP is Robust60-based and
	// lags — during ramp-down it stays >UpHigh*0.7 for ~60s after load drops, so the
	// predictive create fired with risk_up=0.000 right after an idle-worker reclaim
	// (max_worker_free<1700m because the surviving workers repack) → re-created the
	// just-deleted worker = rebound (run24: wk 4→3→4 at rd2). Require the live mean
	// to confirm the lagging level (same not-falling gate as the UPF scale-out fix);
	// risk.UP (forecast) stays the rising-demand path and is unaffected.
	// v4.58: the worker rebound's REAL bug was that this mid-loop predictive create
	// never checked DirectionLockBlocks — so a CREATE could fire 2min after a DELETE
	// (run30: delete→create, 300s lock ignored). The minimal fix is the lock check
	// below; the trigger condition is restored to the run29-proven PROACTIVE form
	// (upRising = Now≥0.85·Robust60) so ramp-up pre-boots workers in time (the v4.56
	// risk-only and v4.57 ueRising gates fired too LATE → UPF stuck under-provisioned
	// → peak catch-up churn + UE rehome failures, run31/32). The 300s create↔delete
	// direction-lock now makes upRising safe in ramp-down: even though upRising stays
	// true in steady ramp-down, a CREATE is blocked for 300s after the idle-worker
	// reclaim's DELETE → no rebound. Proactive on ramp-up, locked-out on ramp-down.
	upRising := f.MeanCpuUP.Now >= 0.85*f.MeanCpuUP.Robust60()
	if !frozen && // Phase B: predictive worker pre-create (scale-OUT) stays frozen during turbulence
		(risk.UP > c.cfg.RiskHigh || (p.UP > c.cfg.UpHigh*0.7 && upRising)) &&
		s.RepUP < c.cfg.MaxUP &&
		// v4.78: pre-create one slot EARLY — fire when the emptiest worker can fit only
		// ~1 more UPF (free < WorkerPrecreateFreeCpuM ≈ MinFreeCpuM+1 UPF), not at full
		// exhaustion. phaseF: the 4th worker was created reactively when the 8th UPF was
		// already wanted, but VM boot took ~3min → 7→8 stalled on BN_INFRA until peak.
		// Firing a slot early lets the worker boot while the current one fills its last slot.
		s.MaxWorkerFreeCpuM < float64(c.cfg.WorkerPrecreateFreeCpuM) &&
		s.WorkerCount < c.cfg.MaxWorkers &&
		s.WorkerCount <= s.ReadyWorkers && // node joined but not Ready yet
		s.WorkerVMCount <= s.ReadyWorkers && // VM created but not yet joined k8s (the worker-3 blind window)
		!c.timers.CooldownActive(ActCreateWorker) {
		if blocked, _ := c.timers.DirectionLockBlocks(ActCreateWorker); !blocked {
			c.log.Info("predictive worker pre-create",
				"reason", "UPF demand forecast rising + next CNF scale-out would exhaust worker",
				"risk_up", risk.UP, "max_worker_free_cpu_m", s.MaxWorkerFreeCpuM)
			return Decision{
				Action: ActCreateWorker, Bottleneck: BNInfra, Pressure: p, Risk: risk,
				Reason: fmt.Sprintf("predictive: risk_up=%.3f, max_worker_free=%.0fm < %dm (no worker can fit a UPF)",
					risk.UP, s.MaxWorkerFreeCpuM, c.cfg.MinFreeCpuM),
				At: now,
			}
		}
	}

	// Step 6.6: fast idle-worker reclaim (v4.19). An empty scaled worker (zero
	// UPF pods, Ready, age>idle) is non-disruptive to delete — but the only
	// reclaim path used to be the 300s SLOW loop, one worker per tick, so after
	// a ramp-down emptied 3 workers it took 900s+ and the run ended with them
	// still up (v4.18: UPF/VyOS reached baseline, workers stuck at 3). Reclaim
	// here in the 30s MID loop instead — but ONLY when load is NOT growing
	// (risk low, bn not a growth bottleneck) so we never delete a worker a
	// scale-out is about to use; the create→delete direction-lock (300s) also
	// guards a just-created worker, and IdleWorker requires zero UPF pods.
	// v4.61: also refuse to reclaim when UPF pressure is HIGH (p.UP ≥ UpHigh) — i.e.
	// at/near peak, where a worker is needed to host the UPF scale-out that is still
	// in progress. The bn!=BNUPF/INFRA/MIXED guard MISSED the bn==BN_VYOS case: when
	// VyOS was the dominant bottleneck (run35, after CTRL_SHARE↑ loaded test-vyos) the
	// reclaim fired AT PEAK and deleted a worker → the lagging UPF scale-out lost its
	// slot → stuck under-provisioned + worker rebound (delete→re-create). p.UP<UpHigh
	// is bottleneck-agnostic: high UPF load ⇒ keep every worker, period.
	if s.IdleWorker != "" && s.WorkerCount > c.cfg.MinWorkers &&
		risk.UP < c.cfg.RiskHigh && p.UP < c.cfg.UpHigh &&
		bn != BNUPF && bn != BNInfra && bn != BNMixed &&
		!c.timers.CooldownActive(ActDeleteWorker) {
		if blocked, _ := c.timers.DirectionLockBlocks(ActDeleteWorker); !blocked {
			return Decision{
				Action: ActDeleteWorker, Bottleneck: bn, Pressure: p, Risk: risk,
				Reason: fmt.Sprintf("mid loop: idle worker reclaim (%s, no UPF pods, load not growing)", s.IdleWorker),
				At:     now,
			}
		}
	}

	// Step 7: enumerate feasible actions
	actions := EnumerateFeasibleActions(s, c.timers, c.cfg)

	// Step 8: select by utility
	bestAction, bestUtil := SelectActionByUtility(actions, bn, risk, s, f, p, c.cfg)

	// Update low-dwell counter based on current state
	if bn == BNNone && p.CP < c.cfg.CpLow && p.UP < c.cfg.UpLow && p.Vyos < c.cfg.VyosLow {
		c.timers.IncrementLowDwell()
	} else {
		c.timers.ResetLowDwell()
	}

	// Step 9: stability guards
	guardedAction, guardReason := ApplyStabilityGuards(bestAction, bn, risk, s, f, p, c.timers, c.cfg)

	// Phase B: during a transition freeze, only scale-IN may proceed. Suppress any
	// scale-OUT the utility selected — the throughput-robust pressure won't spuriously
	// scale out, and staying conservative through rehome turbulence costs nothing (a
	// genuine capacity need re-fires the instant the freeze lifts). Scale-IN is exempt
	// (rebound-free projection + gap-immune P90) — the point of the exemption.
	if frozen && guardedAction != ActNone && !guardedAction.IsScaleIn() {
		guardReason = "transition freeze: scale-out suppressed (scale-in exempt)"
		guardedAction = ActNone
	}

	// Build decision
	dec := Decision{
		Action:     guardedAction,
		Bottleneck: bn,
		Pressure:   p,
		Risk:       risk,
		At:         now,
	}

	if guardedAction == ActNone {
		if guardReason != "" {
			dec.Reason = guardReason
			dec.BlockedBy = guardReason
		} else if bestAction == ActNone {
			dec.Reason = fmt.Sprintf("no beneficial action (bn=%s, utility=%.4f)", bn, bestUtil.Utility)
		} else {
			dec.Reason = "utility below threshold"
		}
	} else {
		dec.Reason = fmt.Sprintf("bn=%s risk=(cp=%.4f up=%.4f vy=%.4f) utility=%.4f gain=%.4f",
			bn, risk.CP, risk.UP, risk.Vyos, bestUtil.Utility, bestUtil.SLOGain)
	}

	return dec
}

// DecideSlow runs the slow-control loop logic for the VM layers (VyOS + worker).
// Called every SLOW_INTERVAL. It returns INDEPENDENT per-layer decisions (a VyOS
// action AND a worker action may both be returned in the same tick) so the two
// VM layers never starve each other — the old single-Decision form returned on
// the first eligible action, so a VyOS deploy/delete every tick kept the worker
// layer (and vice-versa) from ever acting. CNF (UPF/CP) scale-in is NOT done here
// — it is the mid loop's job (utility-based), so the slow loop is purely the
// VM-layer controller. One unified controller, multiple cadences, no cross-layer
// starvation. VyOS-deploy and VyOS-delete are mutually exclusive (high vs low
// pressure), as are worker-create and worker-delete, so at most one action per
// layer is ever appended.
func (c *Controller) DecideSlow(ctx context.Context, s SystemState) []Decision {
	now := time.Now()
	var decisions []Decision
	workerActed := false // at most one worker action per tick (create XOR delete XOR reclaim)

	if !c.enabled.Load() {
		return nil
	}
	// Phase B: freeze only blocks VM-layer scale-OUT (VyOS deploy / worker create),
	// not scale-IN (VyOS delete / worker delete / idle reclaim). Scale-IN is rebound-
	// free + gap-immune, so exempting it lets ramp-down scale-in proceed even while a
	// migration freeze is active — directly fixing the sess3 VyOS 2→1 stuck-to-cool
	// (every slow tick had landed in a freeze window and returned nil).
	frozen, _ := c.freeze.Active()

	f := c.wc.CollectFeatures(ctx)
	p := ComputePressure(f, c.cfg, s.VyosCount, s.RepUP)
	bn := ClassifyBottleneck(f, p, s, c.cfg)
	risk := EstimateRisk(p, f, c.cfg)

	// 1. VyOS sustained high → deploy VyOS.
	// v4.66: VyOS deploy is checked BEFORE worker-create. It used to be 2nd, but the
	// worker-create block returns on bn==BN_INFRA — and during ramp-up a UPF almost
	// always wants a worker (max_worker_free < 1700m) → bn=BN_INFRA every slow tick →
	// the VyOS deploy below was NEVER reached, so VyOS sat at 1 node at 87-98% CPU
	// the transport layer carrying ALL UPF traffic; its saturation hurts latency more
	// than the Nth UPF's missing home, and worker-create is ALSO reachable via the mid
	// loop (predictive pre-create + the ScaleOutUP→CreateWorker guard redirect), so it
	// is not starved by losing slow-loop priority. Deploy stays gated by its own high
	// signal + cooldown + 210s direction-lock (flap-safe).
	// v4.64: also honour the direction-lock (mirror the delete path) so a DEPLOY
	// cannot reverse a just-done DELETE within DIRECTION_LOCK_VYOS → no deploy↔delete
	// flap from the deploy side either.
	// v4.76: slow loop's REACTIVE VyOS scale-out (the main path; VyOS is a slow-loop
	// resource). Driven by the THROUGHPUT-DOMINANT p.Vyos — same basis as the predictive
	// (mid) deploy and the scale-in guard. The node-count-aware throughput term separates
	// the stages (2 VyOS@ru2 reads p.Vyos≈0.38, won't fire; 2 VyOS@ru3 climbs back ≥0.55),
	// so NO separate CPU gate is needed — that was the v4.71-75 detour. Throughput
	// not-falling (vbash-immune UPF pps) blocks ramp-down rebound; cooldown + 210s
	// direction-lock keep deploy↔delete flap-safe.
	vyThruNotFalling := !metricAvailable(f.PktRateUP) || f.PktRateUP.Now >= 0.85*f.PktRateUP.Robust60Raw()
	// v4.79: freeze-EXEMPT (see the predictive deploy note) — throughput-dominant p.Vyos is
	// migration-immune, so freezing only delays the reactive scale-out.
	if p.Vyos >= c.cfg.VyosHigh && vyThruNotFalling {
		blockedDeploy, _ := c.timers.DirectionLockBlocks(ActDeployVyOS)
		if s.VyosCount < c.cfg.MaxVyos && !c.timers.CooldownActive(ActDeployVyOS) && !blockedDeploy {
			decisions = append(decisions, Decision{
				Action:     ActDeployVyOS,
				Bottleneck: bn,
				Pressure:   p,
				Risk:       risk,
				Reason:     "slow loop: VyOS sustained high pressure",
				At:         now,
			})
		}
	}

	// 2. Infra bottleneck → create worker (only if a UPF can still use it)
	if !frozen && bn == BNInfra {
		if s.RepUP < c.cfg.MaxUP && s.WorkerCount < c.cfg.MaxWorkers &&
			s.WorkerCount <= s.ReadyWorkers && // node joined but not Ready yet
			s.WorkerVMCount <= s.ReadyWorkers && // VM created but not yet joined k8s (the worker-3 blind window)
			!c.timers.CooldownActive(ActCreateWorker) {
			decisions = append(decisions, Decision{
				Action:     ActCreateWorker,
				Bottleneck: bn,
				Pressure:   p,
				Risk:       risk,
				Reason:     "slow loop: infra bottleneck → create worker",
				At:         now,
			})
			workerActed = true
		}
	}

	// 3. Scale-in sequence: UPF → CP → VyOS → Worker. Each layer is gated by
	// ITS OWN sustained-low signals (per-layer guards) so an over-provisioned
	// layer shrinks during ramp-down even while another layer is still warm —
	// the old all-layers gate kept UPFs at max until everything was idle.
	//
	// Rejection reasons are logged: v43 post-mortem could not explain why
	// ramp-down scale-in never fired because the guard verdicts were invisible.
	// v4.50: VyOS scale-in is checked FIRST in the slow-loop sequence. It used to
	// be 3rd (after UPF, CP) and the loop returns on the first eligible action —
	// so during ramp-down UPF scale-in returned every tick and VyOS was never
	// reached until UPF finished (cool). VyOS is the SLOW loop's own VM-layer job;
	// UPF/CP scale-in are ALSO covered by the fast loop (utility), so giving VyOS
	// priority here de-starves it without losing UPF/CP scale-in. (run21-24: VyOS
	// stuck at 3→2, released only in cool — slow-loop starvation, not the signal.)
	{
		okDel, _ := VyosSafeToDelete(s, f, p, c.timers, c.cfg)
		if okDel && !c.timers.CooldownActive(ActDeleteVyOS) {
			if dlDel, _ := c.timers.DirectionLockBlocks(ActDeleteVyOS); !dlDel {
				decisions = append(decisions, Decision{
					Action: ActDeleteVyOS, Bottleneck: bn, Pressure: p, Risk: risk,
					Reason: "slow loop: VyOS sustained low → delete VyOS", At: now,
				})
			}
		}
	}
	// CNF (UPF/CP) scale-in is the MID loop's job (utility-based) — NOT done here.
	// The slow loop is purely the VM-layer (VyOS + worker) controller.
	if ok, _ := WorkerSafeToDelete(s, f, p, c.timers, c.cfg); ok && !workerActed {
		if !c.timers.CooldownActive(ActDeleteWorker) {
			if blocked, _ := c.timers.DirectionLockBlocks(ActDeleteWorker); !blocked {
				decisions = append(decisions, Decision{
					Action: ActDeleteWorker, Bottleneck: bn, Pressure: p, Risk: risk,
					Reason: "slow loop: worker idle/low → delete worker", At: now,
				})
				workerActed = true
			}
		}
	}

	// 4. Idle worker reclaim — PER-WORKER, not aggregate. The old condition
	// (aggregate worker CPU p95 low) never fired while other workers were busy,
	// so a redundant worker survived entire runs. IdleWorker is a Ready,
	// >10-min-old scaled worker hosting ZERO UPF pods: reclaimable by
	// definition even at full load on the rest of the pool.
	if s.IdleWorker != "" && !workerActed &&
		s.WorkerCount > c.cfg.MinWorkers &&
		p.UP < c.cfg.UpHigh && // v4.61: not at peak — a lagging UPF scale-out may still need it
		!c.timers.CooldownActive(ActDeleteWorker) {
		if blocked, _ := c.timers.DirectionLockBlocks(ActDeleteWorker); !blocked {
			decisions = append(decisions, Decision{
				Action: ActDeleteWorker, Bottleneck: bn, Pressure: p, Risk: risk,
				Reason: fmt.Sprintf("slow loop: idle worker reclaim (%s Ready >10min with no UPF pods)", s.IdleWorker),
				At:     now,
			})
			workerActed = true
		}
	}

	return decisions
}

//
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
