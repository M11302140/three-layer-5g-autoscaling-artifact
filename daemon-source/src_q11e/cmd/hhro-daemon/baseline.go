package main

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"net/http"
	"sort"
	"time"

	"github.com/anon/hhro-daemon/internal/envcfg"
	"github.com/anon/hhro-daemon/internal/hbo"
)

//
//

type baselineState struct {
	holtInit     bool
	holtL, holtT float64
	hpa      *hbo.HPAState
	b6       *b6State
	lastDisp map[hbo.Action]time.Time
	baseAt   map[hbo.Action]int
}

func baselineMode() string { return envcfg.Get("BASELINE_MODE", "") }

var (
	baselineNow      = time.Now
	baselineEnabled  = func(d *Daemon) bool { return d.hbo.IsEnabled() }
	baselineSessions = func(d *Daemon, ctx context.Context) (int, map[int]int, []int) { return d.collectSlotSessions(ctx) }
)

func (d *Daemon) baseline() *baselineState {
	if d.bl == nil {
		d.bl = &baselineState{
			hpa: &hbo.HPAState{
				Tol:        envcfg.Float("HPA_TOLERANCE", 0.10),
				Target:     envcfg.Float("HPA_TARGET_SESS", 4.65),
				Min:        envcfg.Int("HPA_MIN", 2),
				Max:        envcfg.Int("HPA_MAX", 8),
				DownWindow: envcfg.Dur("HPA_DOWN_WINDOW", 300*time.Second),
			},
			lastDisp: map[hbo.Action]time.Time{},
			baseAt:   map[hbo.Action]int{},
		}
	}
	return d.bl
}

func (d *Daemon) collectSlotSessions(ctx context.Context) (total int, per map[int]int, active []int) {
	per = map[int]int{}
	if d.eupfAct == nil {
		return
	}
	idxs, err := d.eupfAct.ActiveSlotIdxs(ctx)
	if err != nil {
		d.log.Warn("baseline: active slots failed", "err", err)
		return
	}
	hc := &http.Client{Timeout: 3 * time.Second}
	for _, sl := range d.eupfAct.Cfg.Slots {
		if !idxs[sl.Idx] {
			continue
		}
		active = append(active, sl.N3Octet)
		req, _ := http.NewRequestWithContext(ctx, http.MethodGet,
			fmt.Sprintf("http://10.0.1.%d:8080/api/v1/pfcp_sessions", sl.N3Octet), nil)
		resp, err := hc.Do(req)
		if err != nil {
			continue
		}
		b, _ := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
		resp.Body.Close()
		var arr []json.RawMessage
		if json.Unmarshal(b, &arr) == nil {
			per[sl.N3Octet] = len(arr)
			total += len(arr)
		}
	}
	sort.Ints(active)
	return
}

func (b *baselineState) inflight(a hbo.Action, cur int, maxAge time.Duration) bool {
	t, ok := b.lastDisp[a]
	if !ok {
		return false
	}
	if cur != b.baseAt[a] || baselineNow().Sub(t) > maxAge {
		delete(b.lastDisp, a)
		delete(b.baseAt, a)
		return false
	}
	return true
}

func (b *baselineState) note(a hbo.Action, cur int) { b.lastDisp[a] = baselineNow(); b.baseAt[a] = cur }

func (d *Daemon) decideBaseline(ctx context.Context, mode string, s hbo.SystemState) []hbo.Decision {
	if !baselineEnabled(d) || mode == "b1" {
		return nil
	}
	b := d.baseline()
	now := baselineNow()
	total, per, active := baselineSessions(d, ctx)
	var out []hbo.Decision
	scaledOut := false

	if mode == "b6" {
		return d.decideB6(ctx, b, s, now, total, per, active)
	}

	pred := func(ticks int) float64 { return float64(total) }
	if mode == "b5" {
		a, be := envcfg.Float("HOLT_ALPHA", 0.3), envcfg.Float("HOLT_BETA", 0.05)
		x := float64(total)
		if !b.holtInit {
			b.holtL, b.holtT, b.holtInit = x, 0, true
		} else {
			lp := b.holtL
			b.holtL = a*x + (1-a)*(b.holtL+b.holtT)
			b.holtT = be*(b.holtL-lp) + (1-be)*b.holtT
		}
		pred = func(ticks int) float64 {
			f := b.holtL + float64(ticks)*b.holtT
			if f < x {
				f = x
			}
			return f
		}
		d.log.Info("baseline holt", "sessions", total, "level", b.holtL, "trend", b.holtT,
			"f_up", pred(envcfg.Int("B5_LEAD_TICKS_UP", 2)), "f_vy", pred(envcfg.Int("B5_LEAD_TICKS_VY", 4)), "f_wk", pred(envcfg.Int("B5_LEAD_TICKS_WK", 5)))
		mode = "b4p"
	}
	predictive := mode == "b4p"
	if predictive {
		mode = "b4"
	}

	if mode == "b2" || mode == "b4" {
		mu := envcfg.Float("DASA_MU_SESS", 16.5)
		n0 := envcfg.Int("DASA_N0", 1)
		kMax := envcfg.Int("DASA_K_MAX", 2)
		margin := envcfg.Float("DASA_SCALEIN_MARGIN", 0.9)
		cur := s.VyosCount
		sessVY := pred(envcfg.Int("B5_LEAD_TICKS_VY", 4))
		desired := n0
		if mu > 0 {
			desired = int(math.Ceil(sessVY/mu - 1e-9))
		}
		if desired < n0 {
			desired = n0
		}
		if desired > n0+kMax {
			desired = n0 + kMax
		}
		reason := fmt.Sprintf("DASA sess=%d mu=%.1f cur=%d desired=%d", total, mu, cur, desired)
		switch {
		case desired > cur && !b.inflight(hbo.ActDeployVyOS, cur, 240*time.Second):
			out = append(out, hbo.Decision{Action: hbo.ActDeployVyOS, Reason: reason, At: now})
			b.note(hbo.ActDeployVyOS, cur)
		case desired < cur && cur > n0 && sessVY <= float64(cur-1)*mu*margin &&
			!b.inflight(hbo.ActDeleteVyOS, cur, 240*time.Second):
			out = append(out, hbo.Decision{Action: hbo.ActDeleteVyOS, Reason: reason, At: now})
			b.note(hbo.ActDeleteVyOS, cur)
		}
		d.log.Info("baseline dasa", "sessions", total, "vyos", cur, "desired", desired, "reason", reason)
	}

	curW := s.WorkerCount
	if s.WorkerVMCount > curW {
		curW = s.WorkerVMCount
	}
	positions := curW * envcfg.Int("B6_SLOTS_PER_WORKER", 2)
	needWorker := false
	if mode == "b3" || mode == "b4" {
		cur := len(active)
		if cur > 0 {
			avg := pred(envcfg.Int("B5_LEAD_TICKS_UP", 2)) / float64(cur)
			eff, reason := b.hpa.Step(now, cur, avg)
			d.log.Info("baseline hpa", "sessions", total, "per", fmt.Sprintf("%v", per), "cur", cur, "desired", eff, "reason", reason)
			if eff > cur && !b.inflight(hbo.ActScaleOutUP, cur, 90*time.Second) {
				n := eff - cur
				if n > envcfg.Int("HPA_MAX_BATCH", 3) {
					n = envcfg.Int("HPA_MAX_BATCH", 3)
				}
				if predictive && !envcfg.Bool("B5_LEGACY_WORKER", false) {
					if eff > positions {
						needWorker = true
					}
					if free := s.WorkerCount*envcfg.Int("B6_SLOTS_PER_WORKER", 2) - cur; n > free {
						n = free
					}
				}
				if n > 0 {
					for i := 0; i < n; i++ {
						out = append(out, hbo.Decision{Action: hbo.ActScaleOutUP, Reason: reason, At: now})
					}
					b.note(hbo.ActScaleOutUP, cur)
					scaledOut = true
				} else if predictive {
					d.log.Info("baseline b5: slot scale-out waits for worker", "desired", eff, "cur", cur, "positions", positions, "workers", curW)
				}
			} else if eff < cur && !b.inflight(hbo.ActScaleInUP, cur, 300*time.Second) {
				out = append(out, hbo.Decision{Action: hbo.ActScaleInUP, Reason: reason, At: now})
				b.note(hbo.ActScaleInUP, cur)
			}
		}
	}

	if envcfg.Bool("B5_LEGACY_WORKER", false) {
		curW = s.WorkerCount
		positions = s.WorkerCount * 2
		needWorker = false
	}
	if predictive && curW < envcfg.Int("MAX_WORKERS", 4) && !b.inflight(hbo.ActCreateWorker, curW, 240*time.Second) {
		needSlots := int(math.Ceil(pred(envcfg.Int("B5_LEAD_TICKS_WK", 5))/envcfg.Float("HPA_TARGET_SESS", 4.65) - 1e-9))
		if max := envcfg.Int("HPA_MAX", 8); needSlots > max {
			needSlots = max
		}
		if needWorker || needSlots > positions {
			out = append(out, hbo.Decision{Action: hbo.ActCreateWorker,
				Reason: fmt.Sprintf("b5 predictive worker: forecast needs %d slots > %d positions (ready %d, vms %d)", needSlots, positions, s.WorkerCount, s.WorkerVMCount), At: now})
			b.note(hbo.ActCreateWorker, curW)
			scaledOut = true
		}
	}

	if (mode == "b3" || mode == "b4") && !scaledOut && s.IdleWorker != "" &&
		s.WorkerCount > envcfg.Int("MIN_WORKERS", 1) && !b.inflight(hbo.ActDeleteWorker, s.WorkerCount, 180*time.Second) {
		out = append(out, hbo.Decision{Action: hbo.ActDeleteWorker,
			Reason: fmt.Sprintf("baseline idle worker reclaim (%s)", s.IdleWorker), At: now})
		b.note(hbo.ActDeleteWorker, s.WorkerCount)
	}
	return out
}
