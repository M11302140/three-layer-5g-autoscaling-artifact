package main

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"regexp"
	"sort"
	"strings"
	"sync"
	"sync/atomic"
	"time"

	"github.com/anon/hhro-daemon/internal/actuate"
	"github.com/anon/hhro-daemon/internal/collect"
	"github.com/anon/hhro-daemon/internal/envcfg"
	"github.com/anon/hhro-daemon/internal/hbo"
	"github.com/anon/hhro-daemon/internal/sshexec"
	"github.com/anon/hhro-daemon/internal/state"
)

// Daemon ties the collect/decide/actuate loops together.
type Daemon struct {
	mu        sync.RWMutex
	lastMid   state.State
	lastSlow  state.State
	lastScore state.Scores

	weights state.Weights
	norms   state.Norms
	col     *collect.Collector
	act     *actuate.Actuator
	eupfAct *actuate.EupfActuator // v5.0: eUPF slot activation
	freeze  *state.Freeze
	steady  *state.SteadyGate
	ueProbe *sshexec.UeProbe

	offeredMu   sync.Mutex
	offeredVal  float64
	offeredHist []hbo.OfferedSample
	admittedAt  time.Time
	admittedVal int
	offeredAt   time.Time
	lastRelief  time.Time
	bl          *baselineState
	hotBusy     atomic.Bool

	// workers created FOR a pending eupf slot are reserved: the idle-worker
	// reclaim must not eat them before the slot lands (run#1: worker-1
	// created 20:44 for slot-1, reclaimed 20:50 with zero pods, re-created
	// 20:52 — pure churn).
	reservedMu      sync.Mutex
	reservedWorkers map[string]time.Time

	// two-phase VyOS drain in flight (data IP). Only one at a time: a second
	// DELETE_VYOS tick must not pick a victim whose drain has not landed.
	vyDrainMu sync.Mutex
	vyDrainIP string

	// HBO-HHRO controller (replaces the old Decisioner for autoscale decisions)
	hbo *hbo.Controller

	transitionDefault time.Duration
	log               *slog.Logger
}

// buildSystemState constructs the SystemState that HBO needs from the
// collected state + live Prom queries.
func (d *Daemon) buildSystemState(st state.State) hbo.SystemState {
	return hbo.SystemState{
		WorkerCount:       st.W.N,
		ReadyWorkers:      st.W.Ready,
		WorkerVMCount:     st.W.VMCount,
		IdleWorker:        st.W.IdleWorker,
		WorkerFreeCpuM:    st.W.AllocCpu,
		MaxWorkerFreeCpuM: st.W.MaxFreeCpu,
		WorkerFreeMemMiB:  st.W.AllocMem / (1024 * 1024),
		WorkerCpu:         st.W.Cpu,
		PodPendingCount:   st.Up.PendingPods,
		NodePressure:      false,
		RepCP:             st.Cp.Rep,
		RepUP:             st.Up.Rep,
		ReadyCP:           st.Cp.Ready,
		ReadyUP:           st.Up.Ready,
		VyosCount:         st.V.Count,
		VyosAdmitted:      d.vyosAdmitted(),
		UECount:           st.Q.UeCount,
		OfferedPPS:        d.offeredPPS(),
		OfferedHist:       d.offeredHistCopy(),
	}
}

// vyosAdmitted returns the number of VyOS the sender's UL streams are built on
// (agent /ulpool, cached ≤30s); -1 when unavailable or stale (>120s).
func (d *Daemon) vyosAdmitted() int {
	d.offeredMu.Lock()
	defer d.offeredMu.Unlock()
	if time.Since(d.admittedAt) < 30*time.Second {
		return d.admittedVal
	}
	d.admittedAt = time.Now()
	d.admittedVal = -1
	if d.eupfAct != nil && d.eupfAct.Rehome != nil && d.eupfAct.Rehome.Enabled {
		ctx, cancel := context.WithTimeout(context.Background(), 8*time.Second)
		defer cancel()
		if pool, age, err := d.eupfAct.Rehome.ULPool(ctx); err == nil && age >= 0 && age < 120 {
			d.admittedVal = len(pool)
		}
	}
	return d.admittedVal
}

// offeredPPS returns a <=30s-cached sender-egress pps reading from the agent;
// 0 (= unavailable, fall back to measured PktRateUP) on any error.
func (d *Daemon) offeredPPS() float64 {
	d.offeredMu.Lock()
	defer d.offeredMu.Unlock()
	if time.Since(d.offeredAt) < 3*time.Second {
		return d.offeredVal
	}
	d.offeredAt = time.Now()
	d.offeredVal = 0
	if d.eupfAct != nil && d.eupfAct.Rehome != nil && d.eupfAct.Rehome.Enabled {
		ctx, cancel := context.WithTimeout(context.Background(), 8*time.Second)
		defer cancel()
		if v, h, err := d.eupfAct.Rehome.Offered(ctx); err == nil {
			d.offeredVal = v
			d.offeredHist = make([]hbo.OfferedSample, 0, len(h))
			for _, x := range h {
				d.offeredHist = append(d.offeredHist, hbo.OfferedSample{T: x.T, PPS: x.PPS})
			}
		}
	}
	return d.offeredVal
}

// offeredHistCopy returns the cached sender-egress peak history (see offeredPPS).
func (d *Daemon) offeredHistCopy() []hbo.OfferedSample {
	d.offeredMu.Lock()
	defer d.offeredMu.Unlock()
	return append([]hbo.OfferedSample(nil), d.offeredHist...)
}

func (d *Daemon) tickMid(ctx context.Context) {
	c, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()
	st := d.col.Collect(c)

	// UE count via SSH probe
	if d.ueProbe != nil {
		probeCtx, probeCancel := context.WithTimeout(ctx, 5*time.Second)
		if n, err := d.ueProbe.Count(probeCtx); err == nil {
			st.Q.UeCount = n
		} else {
			d.log.Debug("ue probe failed", "err", err)
		}
		probeCancel()
	}

	// Legacy score (still exported for backwards compat)
	sc := state.Compute(st, d.weights, d.norms)

	d.mu.Lock()
	d.lastMid = st
	d.lastScore = sc
	d.mu.Unlock()

	// HBO-HHRO decision
	if d.act != nil && d.hbo != nil {
		sysState := d.buildSystemState(st)
		decision := d.hbo.Decide(ctx, sysState)

		if d.hbo.V6Active() {
			var decs []hbo.Decision
			if mode := baselineMode(); mode != "" {
				decs = d.decideBaseline(ctx, mode, sysState)
				if envcfg.Bool("BASELINE_EMERGENCY", false) {
					decs = d.hbo.BaselineEmergencyForce(sysState, decs, &baselineEmergLast)
				}
			} else {
				decs = d.hbo.V6Decisions(sysState)
			}
			if len(decs) > 0 {
				go func() {
					disruptiveDone := false
					for _, dec := range decs {
						disruptive := dec.Action.IsScaleIn()
						if disruptive && disruptiveDone {
							d.log.Info("v6 decision deferred (one disruptive per tick)",
								"action", dec.Action)
							continue
						}
						mv, ov := d.hbo.V6GuardStats()
						d.log.Info("v6 decision", "action", dec.Action, "reason", dec.Reason,
							"guard_overrides", ov, "moves_total", mv)
						d.executeHBODecisionFrom(dec, true)
						if disruptive {
							disruptiveDone = true
						}
					}
				}()
			}
			if frozen, _ := d.freeze.Active(); d.hbo.IsEnabled() && !frozen && len(decs) == 0 && d.eupfAct != nil &&
				time.Since(d.lastRelief) > time.Duration(envcfg.Int("V6_RELIEF_PERIOD", 150))*time.Second {
				d.lastRelief = time.Now()
				go func() {
					rctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
					defer cancel()
					n, cnt, err := d.eupfAct.PoolRelief(rctx,
						envcfg.Int("UP_REBALANCE_DONOR_MIN", 4), envcfg.Int("V6_RELIEF_MAX_MOVES", 2))
					if err != nil {
						d.log.Warn("v6 pool relief failed", "err", err)
					} else {
						d.log.Info("v6 pool relief", "moves", n, "dist", fmt.Sprintf("%v", cnt))
					}
				}()
			}
			if frozen, _ := d.freeze.Active(); d.hbo.IsEnabled() && !frozen && d.eupfAct != nil &&
				envcfg.Bool("V6_HOT_SLOT_RELIEF", true) && d.hotBusy.CompareAndSwap(false, true) {
				go func() {
					defer d.hotBusy.Store(false)
					hctx, cancel := context.WithTimeout(context.Background(), 90*time.Second)
					defer cancel()
					rates := d.eupfAct.SampleVFOob(hctx, envcfg.Int("V6_HOT_SLOT_WORKERS", 4))
					for _, oct := range d.eupfAct.HotSlotCandidates() {
						n, cnt, err := d.eupfAct.HotSlotRelief(hctx, oct, envcfg.Int("UP_REBALANCE_RECV_MAX", 5))
						if err != nil {
							d.log.Warn("v6 hot slot relief failed", "slot", oct, "err", err)
						} else {
							d.log.Info("v6 hot slot relief", "slot", oct, "oob_pps", int(rates[oct]), "moves", n, "dist", fmt.Sprintf("%v", cnt))
						}
						break // one move per tick
					}
				}()
			}
		} else if decision.Action != hbo.ActNone {
			d.log.Info("hbo decision", "action", decision.Action, "reason", decision.Reason)
			go d.executeHBODecision(decision)
		} else {
			d.log.Debug("hbo decision none", "reason", decision.Reason)
		}
	}

	frozen, freezeRem := d.freeze.Active()
	f := d.hboSnapshot()
	d.log.Info("mid",
		"cp_cpu", envcfg.Round3(st.Cp.Cpu),
		"up_cpu", envcfg.Round3(st.Up.Cpu), "up_rep", st.Up.Rep,
		"up_drop_pps", envcfg.Round3(st.Up.Drop),
		// v4.53: REAL telegraf VyOS CPU (busiest node) — max.Now / max.P90_60 (the
		// scale-in signal) / pool-mean — replaces the always-0 kubevirt st.V.Cpu so
		// the scale thresholds can be read straight off the run.
		"vy_cpu_max", envcfg.Round3(f.CpuVyosReal.Now),
		"vy_cpu_max_p90", envcfg.Round3(f.CpuVyosReal.P90_60),
		"vy_cpu_mean", envcfg.Round3(f.MeanCpuVyosReal.Now),
		"vyos_count", st.V.Count,
		"ue", st.Q.UeCount,
		"frozen", frozen, "freeze_left_s", envcfg.Round3(freezeRem.Seconds()),
	)
}

// worker-N with N>=1 (scaled UPF-hosting workers; worker-0 is baseline).
var workerScaledRe = regexp.MustCompile(`^worker-([1-9][0-9]*)$`)

func (d *Daemon) hboSnapshot() hbo.FeatureSet {
	if d.hbo == nil {
		return hbo.FeatureSet{}
	}
	return d.hbo.Snapshot()
}

// executeHBODecision maps HBO actions to the existing actuator calls.
func (d *Daemon) executeHBODecision(dec hbo.Decision) {
	d.executeHBODecisionFrom(dec, false)
}

func (d *Daemon) executeHBODecisionFrom(dec hbo.Decision, fromV6 bool) {
	ctx, cancel := context.WithTimeout(context.Background(), 120*time.Second)
	defer cancel()

	if !fromV6 {
		// v8: cooldown/direction-lock timers deleted; only the relief transition freeze remains.
		if dec.Action.IsScaleOut() || dec.Action.IsScaleIn() {
			d.freeze.Set(d.transitionDefault)
		}
	}
	noteV6 := func(a hbo.Action) {
		if fromV6 {
			d.hbo.V6NoteDispatched(a)
		}
	}

	switch dec.Action {
	case hbo.ActScaleOutCP:
		n, err := d.act.ScaleGroup(ctx, "cp", +1, true)
		d.logScaleResult("scale_out_cp", n, err)

	case hbo.ActScaleInCP:
		n, err := d.act.ScaleGroup(ctx, "cp", -1, true)
		d.logScaleResult("scale_in_cp", n, err)

	case hbo.ActScaleOutUP:
		if d.eupfAct != nil {
			if fromV6 && d.hbo.Shadow().QMode() && envcfg.Bool("V6_REVERSIBLE_DRAIN", true) {
				if pod, ok := d.eupfAct.DrainInFlight(); ok && d.eupfAct.CancelDrain(pod) {
					d.log.Info("hbo scale_out_up (eupf): cancelled in-flight drain, slot retained", "slot", pod)
					d.hbo.V6DropInFlight(hbo.ActScaleInUP)
					return
				}
			}
			// v8: the v5 demand-side veto and demand-sized batch (UP_SCALEOUT_*) are deleted; v6 tuples size themselves.
			addN := 1
			for i := 0; i < addN; i++ {
				name, err := d.eupfAct.DeployUPF(ctx, true)
				var wnr *actuate.WorkerNotReadyError
				if errors.As(err, &wnr) {
					if sh := d.hbo.Shadow(); fromV6 && sh.QMode() && sh.Rise().SigmaMode() {
						d.log.Info("hbo scale_out_up (eupf): no free slot position; worker layer owns creation (sigma)", "worker", wnr.Node)
						return
					}
					wname, created, werr := d.act.CreateWorkerNamed(ctx, wnr.Node)
					if werr != nil {
						d.log.Warn("hbo scale_out_up (eupf): worker create for slot failed", "err", werr)
						return
					}
					if !created {
						d.log.Info("hbo scale_out_up (eupf): slot worker still booting", "worker", wname)
						return
					}
					d.log.Info("hbo scale_out_up (eupf): creating slot worker first", "worker", wname)
					noteV6(hbo.ActCreateWorker)
					d.reserveWorker(wname, 12*time.Minute)
					go func(node string) {
						pctx, cancel := context.WithTimeout(context.Background(), 15*time.Minute)
						defer cancel()
						if perr := d.eupfAct.ProvisionWorkerVFs(pctx, node, 12*time.Minute); perr != nil {
							d.log.Warn("eupf worker provisioning failed", "node", node, "err", perr)
							return
						}
						d.log.Info("eupf worker provisioned", "node", node)
					}(wname)
					return
				}
				if err != nil {
					d.log.Warn("hbo scale_out_up (eupf) rejected", "err", err)
					return
				}
				d.log.Info("hbo scale_out_up (eupf)", "slot", name, "batch", fmt.Sprintf("%d/%d", i+1, addN))
				noteV6(hbo.ActScaleOutUP)
				if fromV6 {
					d.hbo.V6DropInFlight(hbo.ActScaleInUP)
				}
				go d.vfioPinLater("after slot "+name, 20, 75)
				// v5.0.30: UP_SCALEOUT_REBALANCE = relief (default) | full | off.
				// "relief" moves ONLY UEs on donors above the per-slot design
				// capacity (>UP_REBALANCE_DONOR_MIN) — the full even-spread's
				// in-move outages dominated run#7's remaining ramp loss, while
				// arrival steering converges balance for free. "off" risks
				// SUSTAINED AMBR overload on early-filled slots; keep relief.
				if mode := envcfg.Get("UP_SCALEOUT_REBALANCE", "relief"); mode != "off" {
					go func(slot string, full bool) {
						rctx, cancel := context.WithTimeout(context.Background(), 12*time.Minute)
						defer cancel()
						if rerr := d.eupfAct.RebalanceInto(rctx, slot, full); rerr != nil {
							d.log.Warn("eupf rehome (scale-out) failed", "slot", slot, "err", rerr)
							return
						}
						d.log.Info("eupf rehome (scale-out) done", "slot", slot)
					}(name, mode == "full")
				}
			}
		}

	case hbo.ActScaleInUP:
		if d.eupfAct != nil {
			target, err := d.eupfAct.PickScaleInTarget(ctx)
			if err != nil {
				d.log.Warn("hbo pick eupf target failed", "err", err)
				return
			}
			// drain-then-delete (async): UEs leave the slot before its capacity
			// does — zero-loss scale-in. PickScaleInTarget skips slots whose
			// drain is still in flight, so ticks can't double-fire.
			noteV6(hbo.ActScaleInUP)
			go func(slot string) {
				rctx, cancel := context.WithTimeout(context.Background(), 12*time.Minute)
				defer cancel()
				if rerr := d.eupfAct.DrainAndDelete(rctx, slot); rerr != nil {
					if errors.Is(rerr, actuate.ErrDrainCancelled) {
						d.log.Info("hbo scale_in_up (eupf) cancelled: slot retained (reversible scale-in)", "slot", slot)
						return
					}
					d.log.Warn("hbo scale_in_up (eupf) failed", "slot", slot, "err", rerr)
					return
				}
				d.log.Info("hbo scale_in_up (eupf)", "slot", slot)
				d.vfioPinLater("after slot delete "+slot, 10, 60)
			}(target)
		}

	case hbo.ActCreateWorker:
		name, err := d.act.CreateWorker(ctx, true)
		if err != nil {
			d.log.Warn("hbo create_worker rejected", "err", err)
			return
		}
		d.log.Info("hbo create_worker", "name", name)
		noteV6(hbo.ActCreateWorker)
		go d.hostPinKicks(name)
		// v5.0.29: predictive pre-creates get the same 12-min reserve as
		// slot-dispatch creates — run#4 idle-reclaimed a predictive worker
		// 6min after boot (created 06:49, deleted 06:55), pure churn.
		d.reserveWorker(name, 12*time.Minute)
		if d.eupfAct != nil {
			// v5.0: a fresh worker's eUPF VF state is ALL runtime (MAC, N3 IP,
			// MTU, queue, policy routing, DN neighbor, IRQ pin) — provision it
			// as soon as SSH answers so its slots become activatable.
			go func(node string) {
				pctx, cancel := context.WithTimeout(context.Background(), 15*time.Minute)
				defer cancel()
				if err := d.eupfAct.ProvisionWorkerVFs(pctx, node, 12*time.Minute); err != nil {
					d.log.Warn("eupf worker provisioning failed", "node", node, "err", err)
					return
				}
				d.log.Info("eupf worker provisioned", "node", node)
			}(name)
		}

	case hbo.ActDeleteWorker:
		// Prefer the idle worker (zero UPF pods) — deleting it is non-disruptive
		// by definition. PickReleaseTarget (highest index) could hit a worker
		// that still hosts UPFs while an empty one survives.
		// v4.19: read lastMID (refreshed every 30s) not lastSlow (every 300s) —
		// the mid-loop reclaim path needs the CURRENT idle worker, not a target
		// that may be 5 min stale (already deleted / no longer empty).
		d.mu.RLock()
		target := d.lastMid.W.IdleWorker
		if target == "" {
			target = d.lastSlow.W.IdleWorker
		}
		d.mu.RUnlock()
		if target != "" && d.workerReserved(target) {
			d.log.Info("hbo delete_worker skipped: worker reserved for a pending eupf slot", "name", target)
			return
		}
		if target == "" {
			var err error
			target, err = actuate.PickReleaseTarget(ctx, d.act.H, d.act.Cfg.NamePrefix)
			if err != nil {
				d.log.Warn("hbo pick worker target failed", "err", err)
				return
			}
		}
		if err := d.act.DeleteWorker(ctx, target, true); err != nil {
			d.log.Warn("hbo delete_worker rejected", "name", target, "err", err)
			return
		}
		go d.vfioPinLater("after delete "+target, 60, 150)
		d.log.Info("hbo delete_worker", "name", target)
		noteV6(hbo.ActDeleteWorker)

	case hbo.ActDeployVyOS:
		name, err := d.act.DeployVyOS(ctx, true)
		if err != nil {
			d.log.Warn("hbo deploy_vyos rejected", "err", err)
			return
		}
		d.log.Info("hbo deploy_vyos", "name", name)
		noteV6(hbo.ActDeployVyOS)
		go d.hostPinKicks(name)

	case hbo.ActDeleteVyOS:
		target, err := actuate.PickReleaseVyosTarget(ctx, d.act.H, d.act.VyosCfg.NamePrefix)
		if err != nil {
			d.log.Warn("hbo pick vyos target failed", "err", err)
			return
		}
		d.vyDrainMu.Lock()
		if d.vyDrainIP != "" {
			inflight := d.vyDrainIP
			d.vyDrainMu.Unlock()
			d.log.Info("hbo delete_vyos skipped: drain in flight", "inflight", inflight, "want", target)
			return
		}
		d.vyDrainIP = target
		d.vyDrainMu.Unlock()
		noteV6(hbo.ActDeleteVyOS)

		// v6.0.24 — TWO-PHASE DRAIN (r29 min32/min39 root cause).
		// v5.0.21's repath-before-delete only moved the DL affinity (the
		// agent's worker_repoint); the sender's UPLINK stream steering is
		// owned by the measurement harness and was only rebuilt when the
		// harness NOTICED the deletion — by failing to ping the victim's
		// mgmt IP twice. A deleted KubeVirt VM answers mgmt pings for tens
		// of seconds, so the notice came 33s late on one delete and never
		// (within the window) on the other: 9/26 and 5/11 UEs dark for
		// 30-63s = the 4.5%/45.4% minutes, i.e. 100% of r29's >2% mass.
		// Now: publish "draining" -> move DL -> WAIT for the sender to
		// acknowledge its UL has left the victim -> only then destroy.
		go d.drainAndDeleteVyos(target)
		go d.vfioPinLater("after delete vyos "+target, 90, 180)

	case hbo.ActRebalanceUPF:
		d.log.Info("hbo rebalance_upf (delegated to rebalancer)")

	case hbo.ActRebalanceVy:
		d.log.Info("hbo rebalance_vyos (delegated to rebalancer)")
	}
}

func (d *Daemon) drainAndDeleteVyos(target string) {
	rctx, cancel := context.WithTimeout(context.Background(), 4*time.Minute)
	defer cancel()
	victimIP := ""
	var vidx int
	if _, serr := fmt.Sscanf(target, d.act.VyosCfg.NamePrefix+"%d", &vidx); serr == nil {
		victimIP = fmt.Sprintf("%s%d", d.act.VyosCfg.DataPrefix, d.act.VyosCfg.DataBase+vidx)
	}
	var rh *actuate.RehomeClient
	if d.eupfAct != nil && d.eupfAct.Rehome != nil && d.eupfAct.Rehome.Enabled {
		rh = d.eupfAct.Rehome
	}
	waited := 0.0
	if rh != nil && victimIP != "" {
		// phase 1 — publish. The harness polls /tmp/vy_drain.json
		// every ~2s and rebuilds its UL streams off the victim.
		if derr := rh.SetDrain(rctx, victimIP, true); derr != nil {
			d.log.Warn("hbo delete_vyos: drain publish failed", "name", target, "err", derr)
		}
		// phase 2 — DL affinity (unchanged v5.0.21 behaviour).
		if ues, uerr := rh.UEs(rctx); uerr == nil {
			remaining := map[string]bool{}
			for _, u := range ues {
				if u.Vyos != victimIP && u.Vyos != "" {
					remaining[u.Vyos] = true
				}
			}
			var rem []string
			for v := range remaining {
				rem = append(rem, v)
			}
			sort.Strings(rem)
			moves := actuate.PlanVyosDrain(ues, rem, victimIP)
			if rerr := rh.Repath(rctx, moves); rerr != nil {
				d.log.Warn("hbo delete_vyos: repath failed", "name", target, "err", rerr)
			} else {
				d.log.Info("hbo delete_vyos: repathed UEs off victim", "name", target, "moves", len(moves))
			}
		} else {
			d.log.Warn("hbo delete_vyos: agent unreachable, proceeding without repath", "err", uerr)
		}
		// phase 3 — wait for the UL acknowledgement. Bounded: a dead
		// or wedged harness must not park a VyOS forever.
		budget := float64(envcfg.Int("VYOS_DRAIN_WAIT_S", 30))
		budgetAlive := float64(envcfg.Int("VYOS_DRAIN_WAIT_ALIVE_S", 150))
		alive := false
		for {
			pool, age, perr := rh.ULPool(rctx)
			alive = perr == nil && age >= 0 && age < 20
			if alive && !pool[victimIP] {
				break
			}
			if (alive && waited >= budgetAlive) || (!alive && waited >= budget) {
				break
			}
			time.Sleep(time.Second)
			waited++
		}
		timedOut := (alive && waited >= budgetAlive) || (!alive && waited >= budget)
		d.log.Info("hbo delete_vyos: ul drain confirmed", "name", target,
			"victim_ip", victimIP, "waited_s", waited, "timeout", timedOut, "harness_alive", alive)
	}
	if derr := d.act.DeleteVyOS(rctx, target, true); derr != nil {
		d.log.Warn("hbo delete_vyos rejected", "name", target, "err", derr)
	} else {
		d.log.Info("hbo delete_vyos", "name", target, "drain_wait_s", waited)
	}
	// Keep the victim published as draining for a while after the VM
	// is gone: it keeps answering mgmt pings during teardown, and the
	// harness re-admits anything that pings. The harness also drops
	// its first-seen stamp for a draining IP, so re-entry costs a
	// full fresh quarantine either way.
	if rh != nil && victimIP != "" {
		time.Sleep(90 * time.Second)
		var cerr error
		for i := 0; i < 5; i++ {
			cctx, ccancel := context.WithTimeout(context.Background(), 25*time.Second)
			cerr = rh.SetDrain(cctx, victimIP, false)
			ccancel()
			if cerr == nil {
				break
			}
			time.Sleep(10 * time.Second)
		}
		if cerr != nil {
			d.log.Warn("hbo delete_vyos: drain clear failed after retries", "ip", victimIP, "err", cerr)
		}
	}
	d.vyDrainMu.Lock()
	d.vyDrainIP = ""
	d.vyDrainMu.Unlock()
}

func (d *Daemon) logScaleResult(act string, replicas int, err error) {
	if err != nil {
		d.log.Warn("hbo "+act+" rejected", "err", err)
		return
	}
	d.log.Info("hbo "+act, "replicas", replicas)
}

func (d *Daemon) tickSlow(ctx context.Context) {
	c, cancel := context.WithTimeout(ctx, 15*time.Second)
	defer cancel()
	st := d.col.Collect(c)
	d.mu.Lock()
	d.lastSlow = st
	d.mu.Unlock()
	d.log.Info("slow",
		"n_w", st.W.N, "ready_w", st.W.Ready,
		"cpu_w", envcfg.Round3(st.W.Cpu), "mem_w", envcfg.Round3(st.W.Mem),
		"alloc_cpu_m", envcfg.Round3(st.W.AllocCpu),
		"alloc_mem_gib", envcfg.Round3(st.W.AllocMem/(1<<30)),
		"vyos_exist", st.V.Exist,
	)

	// Reap stuck VMs
	if d.act != nil {
		stuck := envcfg.Dur("VM_STUCK_REAP_AFTER", 5*time.Minute)
		reaped, err := d.act.ReapStuckVMs(c, stuck)
		if err != nil {
			d.log.Warn("reap stuck VMs failed", "err", err)
		} else if len(reaped) > 0 {
			d.log.Warn("reaped stuck VMs", "names", reaped)
		}
	}

	// v8: the v5 slow VM loop (DecideSlow) is deleted; VM-layer decisions come from the v6 planner tuples.
}

func (d *Daemon) reserveWorker(name string, ttl time.Duration) {
	d.reservedMu.Lock()
	defer d.reservedMu.Unlock()
	if d.reservedWorkers == nil {
		d.reservedWorkers = map[string]time.Time{}
	}
	d.reservedWorkers[name] = time.Now().Add(ttl)
}

func (d *Daemon) workerReserved(name string) bool {
	d.reservedMu.Lock()
	defer d.reservedMu.Unlock()
	t, ok := d.reservedWorkers[name]
	if !ok {
		return false
	}
	if time.Now().After(t) {
		delete(d.reservedWorkers, name)
		return false
	}
	return true
}

func (d *Daemon) hostPinKicks(name string) {
	if !envcfg.Bool("HOST_PIN_KICK", true) || d.act == nil || d.act.Host == nil {
		return
	}
	addr := envcfg.Get("HOST_MGMT", "10.0.0.193:22")
	user := envcfg.Get("HOST_USER", "rancher")
	pass := envcfg.Get("HOST_PASS", "")
	kick0 := fmt.Sprintf(hostPinKick0Script, name)
	ctx0, cancel0 := context.WithTimeout(context.Background(), 150*time.Second)
	out, err := d.act.Host.ExecOnAddrAs(ctx0, addr, user, pass, "sudo -S -p '' bash -c "+shellQuote(kick0))
	cancel0()
	if err != nil {
		d.log.Warn("host pin kick0 failed", "vm", name, "err", err)
	} else {
		d.log.Info("host pin kick0", "vm", name, "out", strings.TrimSpace(out))
	}
	cmd := "sudo -S -p '' systemctl start --no-block vcpu-pin.service"
	for _, at := range []int{10, 30} {
		time.Sleep(time.Duration(at) * time.Second)
		ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
		_, err := d.act.Host.ExecOnAddrAs(ctx, addr, user, pass, cmd)
		cancel()
		if err != nil {
			d.log.Warn("host pin kick failed", "vm", name, "t", at, "err", err)
			return
		}
	}
	d.log.Info("host pin kicks done", "vm", name)
	for _, at := range []int{5, 40} {
		time.Sleep(time.Duration(at) * time.Second)
		d.hostVfioIrqPin("after " + name)
	}
}

const hostPinKick0Script = `name=%s
CG=/sys/fs/cgroup
eval "$(sed -n '/^declare -A VMSET=(/,/^)/p;/^qemu_pid()/,/^}/p;/^pod_slice()/,/^}/p;/^confine_vm()/,/^}/p;/^unquota_vm()/,/^}/p' /oem/vcpu-pin.sh)"
pins=$(grep -E "^pin_one +$name +\"CPU [0-9]+/KVM\" +[0-9]+" /oem/vcpu-pin.sh | sed -E 's/^pin_one +[^ ]+ +"(CPU [0-9]+\/KVM)" +([0-9]+).*/\1:\2/' | tr ' ' '_')
[ -z "$pins" ] && { echo "kick0: no pin table for $name"; exit 0; }
pid=""; i=0
while [ $i -lt 120 ]; do
  i=$((i+1))
  pid=$(qemu_pid "$name")
  if [ -n "$pid" ]; then
    ok=1
    for pc in $pins; do comm=$(echo "${pc%%:*}" | tr '_' ' '); grep -qxF "$comm" /proc/$pid/task/*/comm 2>/dev/null || ok=0; done
    [ $ok = 1 ] && break
  fi
  sleep 1
done
[ -z "$pid" ] && { echo "kick0: qemu for $name not seen in ${i}s"; exit 0; }
confine_vm "$pid" "${VMSET[$name]}"
unquota_vm "$pid"
for pc in $pins; do
  comm=$(echo "${pc%%:*}" | tr '_' ' '); core=${pc##*:}
  for t in /proc/$pid/task/*; do [ "$(cat $t/comm 2>/dev/null)" = "$comm" ] && taskset -pc "$core" "$(basename $t)" >/dev/null 2>&1; done
done
echo "kick0: $name pid=$pid pinned at +${i}s cpuset=$(cat $(pod_slice $pid)/cpuset.cpus 2>/dev/null) pins=$pins"
`

const hostVfioIrqPinScript = `HK="%s"
for p in $(pgrep -f 'qemu-kvm|qemu-system'); do
  n=$(tr '\0' ' ' < /proc/$p/cmdline | grep -oE 'guest=[^, ]+' | head -1 | cut -d= -f2)
  [ -z "$n" ] && continue
  dp=""
  for t in /proc/$p/task/*; do
    c=$(cat $t/comm 2>/dev/null); case "$c" in CPU*) ;; *) continue;; esac
    idx=${c#CPU }; idx=${idx%%%%/*}
    al=$(grep Cpus_allowed_list $t/status | awk '{print $2}')
    case "$al" in *-*|*,*) continue;; esac
    case " $HK " in *" $al "*) continue;; esac
    dp="$dp $idx:$al"
  done
  dp=$(echo $dp | tr ' ' '\n' | sort -t: -k1 -n -r | cut -d: -f2)
  vfs=$(for g in $(ls -l /proc/$p/fd 2>/dev/null | grep -oE '/dev/vfio/[0-9]+' | grep -oE '[0-9]+$' | sort -u); do ls /sys/kernel/iommu_groups/$g/devices/ 2>/dev/null; done | sort)
  i=0
  for vf in $vfs; do
    core=$(echo "$dp" | sed -n "$((i+1))p"); [ -z "$core" ] && core=$(echo $HK | tr ' ' ',')
    for irq in $(grep -E "vfio-msix\[[0-9]+\]\($vf\)" /proc/interrupts | awk -F: '{print $1}' | tr -d ' '); do
      echo "$core" > /proc/irq/$irq/smp_affinity_list 2>/dev/null
    done
    echo "$n $vf -> $core"
    i=$((i+1))
  done
done`

// hostVfioIrqPin runs hostVfioIrqPinScript on the Harvester host (sudo). Idempotent; safe to
func (d *Daemon) hostVfioIrqPin(why string) {
	if !envcfg.Bool("HOST_VFIO_PIN", true) || d.act == nil || d.act.Host == nil {
		return
	}
	addr := envcfg.Get("HOST_MGMT", "10.0.0.193:22")
	user := envcfg.Get("HOST_USER", "rancher")
	pass := envcfg.Get("HOST_PASS", "")
	hk := envcfg.Get("HOST_HK_CORES", "0 1 2 3 16 17 18 19 29 30 31")
	script := fmt.Sprintf(hostVfioIrqPinScript, hk)
	cmd := "sudo -S -p '' bash -c " + shellQuote(script)
	ctx, cancel := context.WithTimeout(context.Background(), 40*time.Second)
	defer cancel()
	out, err := d.act.Host.ExecOnAddrAs(ctx, addr, user, pass, cmd)
	if err != nil {
		d.log.Warn("host vfio irq pin failed", "why", why, "err", err)
		return
	}
	d.log.Info("host vfio irq pin", "why", why, "map", strings.ReplaceAll(strings.TrimSpace(out), "\n", "; "))
}

func shellQuote(s string) string { return "'" + strings.ReplaceAll(s, "'", "'\\''") + "'" }

func (d *Daemon) vfioPinLater(why string, delaysSec ...int) {
	prev := 0
	for _, at := range delaysSec {
		time.Sleep(time.Duration(at-prev) * time.Second)
		prev = at
		d.hostVfioIrqPin(why + fmt.Sprintf(" +%ds", at))
	}
}
