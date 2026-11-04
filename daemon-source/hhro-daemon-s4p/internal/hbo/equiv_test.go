package hbo


import (
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"math"
	"os"
	"testing"
	"time"

	"github.com/anon/hhro-daemon/internal/state"
)

type eqEvent struct {
	T   float64 `json:"t"`
	Act string  `json:"act"`
}
type eqOpts struct {
	Name         string
	LamVM, LamUP float64
	DModel       string
	DrainSec     float64
	FailFirstOut bool
	ExecWorker   bool
	IdleMinSec   float64
	DropInOnOut  bool
}
type eqResult struct {
	Name   string    `json:"name"`
	Events []eqEvent `json:"events"`
	Alloc  float64   `json:"alloc"`
	SLO    int       `json:"slo"`
	Worst  float64   `json:"worst"`
	Traj   [][3]int  `json:"traj"`
	Ticks  []eqTick  `json:"ticks"`
}
type eqTick struct {
	T       float64 `json:"t"`
	D       float64 `json:"d"`
	NeedUP  int     `json:"need_up"`
	NeedVY  int     `json:"need_vy"`
	NeedWK  int     `json:"need_wk"`
	MUP     float64 `json:"m_up"`
	MVY     float64 `json:"m_vy"`
	MWK     float64 `json:"m_wk"`
	RepUP   int     `json:"rep_up"`
	ReadyUP int     `json:"ready_up"`
	VY      int     `json:"vy"`
	VYAdm   int     `json:"vy_adm"`
	WK      int     `json:"wk"`
	WKVM    int     `json:"wk_vm"`
	Idle    bool    `json:"idle"`
	Tuple   string  `json:"tuple"`
}
type eqUnit struct {
	dispatch, vm, ready, gone float64
	draining, deleting        bool
}

const eqInf = 1e18

func runDaemonEquiv(t *testing.T, ue []float64, o eqOpts) eqResult {
	t.Helper()
	t.Setenv("V6_DEMAND_MODEL", "sigma")
	t.Setenv("V6_LAMBDA_VM", fmt.Sprint(o.LamVM))
	t.Setenv("V6_LAMBDA_UP", fmt.Sprint(o.LamUP))
	t.Setenv("V6_TREADY_MEASURED", "true")
	t.Setenv("V6_ENABLED", "true")
	t.Setenv("V6_SHADOW", "true")
	t.Setenv("V6_RISE_WARM_S", "0")
	cfg := Cfg{Enabled: true, MinUP: 2, MaxUP: 8, MinVyos: 1, MaxVyos: 3, MinWorkers: 1, MaxWorkers: 4, EupfMode: true}
	var lw io.Writer = io.Discard
	if os.Getenv("EQUIV_DEBUG") != "" {
		lw = os.Stderr
	}
	ctrl := NewController(cfg, nil, state.NewFreeze(), slog.New(slog.NewTextHandler(lw, nil)))
	if ctrl.shadow.rise == nil || !ctrl.shadow.rise.SigmaMode() {
		t.Fatal("sigma prior not loaded")
	}
	t0 := time.Date(2026, 10, 5, 0, 0, 0, 0, time.UTC)
	sim := 0.0
	nowFn = func() time.Time { return t0.Add(time.Duration(sim * float64(time.Second))) }
	defer func() { nowFn = time.Now }()
	ctrl.V6ResetEpisode()
	cal := ctrl.shadow.calib
	pc := PlanCalib(&cal, ctrl.shadow.params)
	hUP, hVY, hWK := cal.Act[ActScaleOutUP].TReadySec, cal.Act[ActDeployVyOS].TReadySec, cal.Act[ActCreateWorker].TReadySec
	dVY, dWK := cal.Act[ActDeleteVyOS].TReadySec, cal.Act[ActDeleteWorker].TReadySec
	perUE := 250000.0
	const dt = 5.0
	// demand per step
	d := make([]float64, 0, len(ue)*12)
	for _, u := range ue {
		x := u
		if o.DModel == "pps" {
			x = u * 0.993
		}
		for k := 0; k < 12; k++ {
			d = append(d, x)
		}
	}
	// converged start(= qsim)
	b := V6Bounds{MinUP: 2, MaxUP: 8, MinVY: 1, MaxVY: 3, MinWK: 1, MaxWK: 4}
	q0 := qNeeds(PlanInput{Offered: d[0] * perUE, Bounds: b}, pc, ctrl.shadow.rise)
	var pods, vys, wks []*eqUnit
	for i := 0; i < q0.NeedUP; i++ {
		pods = append(pods, &eqUnit{dispatch: -1e6, vm: -1e6, ready: -1e6, gone: eqInf})
	}
	for i := 0; i < q0.NeedVY; i++ {
		vys = append(vys, &eqUnit{dispatch: -1e6, vm: -1e6, ready: -1e6, gone: eqInf})
	}
	for i := 0; i < q0.NeedWK; i++ {
		wks = append(wks, &eqUnit{dispatch: -1e6, vm: -1e6, ready: -1e6, gone: eqInf})
	}
	res := eqResult{Name: o.Name}
	ev := func(a string) { res.Events = append(res.Events, eqEvent{T: sim, Act: a}) }
	lossMin := make([]float64, 60)
	offMin := make([]float64, 60)
	capVY := 4.45e6 * 0.93 / perUE // UE per VyOS(qsim cap_vy)
	failedOnce := false
	count := func(us []*eqUnit, f func(*eqUnit) bool) int {
		n := 0
		for _, u := range us {
			if u.gone > sim && f(u) {
				n++
			}
		}
		return n
	}
	for i := range d {
		sim = float64(i) * dt
		D := d[i]
		nUP := count(pods, func(u *eqUnit) bool { return u.ready <= sim && !u.draining })
		nVY := count(vys, func(u *eqUnit) bool { return u.ready <= sim && !u.deleting })
		nWK := count(wks, func(u *eqUnit) bool { return u.ready <= sim && !u.deleting })
		l := 0.0
		if cv := float64(nVY) * capVY; D > cv {
			l = 1 - cv/D
		}
		x := D * (1 - l)
		if cu := float64(nUP) * 5; x > cu {
			l = 1 - (1-l)*cu/x
		}
		mi := i * int(dt) / 60
		lossMin[mi] += l * D * dt
		offMin[mi] += D * dt
		bUP := count(pods, func(u *eqUnit) bool { return u.dispatch <= sim })
		bVY := count(vys, func(u *eqUnit) bool { return u.dispatch <= sim })
		bWK := count(wks, func(u *eqUnit) bool { return u.dispatch <= sim })
		res.Alloc += (3*float64(bWK) + 2*float64(bVY) + 0.8*float64(bUP)) * dt / 60
		if math.Mod(sim, 60) == 0 {
			res.Traj = append(res.Traj, [3]int{nUP, nVY, nWK})
		}
		if math.Mod(sim, v6Grid) != 0 {
			continue
		}
		repUP := count(pods, func(u *eqUnit) bool { return u.dispatch <= sim })
		readyUP := count(pods, func(u *eqUnit) bool { return u.ready <= sim })
		vyCount := count(vys, func(u *eqUnit) bool { return u.vm <= sim })
		vyAdm := count(vys, func(u *eqUnit) bool { return u.ready <= sim && !u.deleting })
		wkReady := count(wks, func(u *eqUnit) bool { return u.ready <= sim })
		wkVM := count(wks, func(u *eqUnit) bool { return u.vm <= sim })
		idle := ""
		if wkReady > 1 && repUP <= (wkReady-1)*slotsPerWorker {
			for _, w := range wks {
				if w.gone > sim && w.ready <= sim-o.IdleMinSec && !w.deleting {
					idle = "worker-x"
					break
				}
			}
		}
		s := SystemState{OfferedPPS: D * perUE / 2, UECount: int(math.Round(D)), RepUP: repUP, ReadyUP: readyUP,
			VyosCount: vyCount, VyosAdmitted: vyAdm, WorkerCount: wkReady, ReadyWorkers: wkReady, WorkerVMCount: wkVM, IdleWorker: idle}
		for k := 48; k >= 0; k-- {
			j := i - k
			if j < 0 {
				continue
			}
			s.OfferedHist = append(s.OfferedHist, OfferedSample{T: nowFn().Add(-time.Duration(k*5) * time.Second), PPS: d[j] * perUE / 2})
		}
		miss := WindowFeature{Missing: true}
		f := FeatureSet{CpuCP: miss, CpuUP: miss, MeanCpuUP: miss, CpuVyos: miss, CpuVyosReal: miss, MeanCpuVyosReal: miss, ReadyCP: miss, DropUP: miss, PktRateUP: miss, BwUP: miss, UECount: miss, VyosDropErr: miss, VyosLossRatio: miss, VyosImbalance: miss}
		if os.Getenv("EQUIV_DEBUG") != "" {
			fmt.Fprintf(os.Stderr, "## t=%.0f min=%d D=%.2f rep=%d ready=%d vy=%d/%d wk=%d/%d idle=%q\n", sim, int(sim)/60, D, repUP, readyUP, vyCount, vyAdm, wkReady, wkVM, idle)
		}
		ctrl.shadow.Tick(f, s, cfg)
		ctrl.mu.Lock()
		ctrl.lastFeatures = f
		ctrl.mu.Unlock()
		lq := ctrl.shadow.LastQ
		res.Ticks = append(res.Ticks, eqTick{T: sim, D: D, NeedUP: lq.NeedUP, NeedVY: lq.NeedVY, NeedWK: lq.NeedWK, MUP: lq.MarginUP / perUE, MVY: lq.MarginVY / perUE, MWK: lq.MarginWK / perUE, RepUP: repUP, ReadyUP: readyUP, VY: vyCount, VYAdm: vyAdm, WK: wkReady, WKVM: wkVM, Idle: idle != "", Tuple: ctrl.shadow.Last.Best.Key})
		for _, dec := range ctrl.V6Decisions(s) {
			switch dec.Action {
			case ActScaleOutUP:
				var dr *eqUnit
				for _, p := range pods {
					if p.draining && p.gone > sim {
						dr = p
					}
				}
				if dr != nil {
					dr.draining = false
					dr.gone = eqInf
					ctrl.V6DropInFlight(ActScaleInUP)
					ev("CANCEL_DRAIN")
					continue
				}
				if o.FailFirstOut && !failedOnce {
					failedOnce = true
					ev("SCALE_OUT_UP_FAIL")
					continue
				}
				if repUP < wkReady*slotsPerWorker {
					pods = append(pods, &eqUnit{dispatch: sim, vm: sim, ready: sim + hUP, gone: eqInf})
					ctrl.V6NoteDispatched(ActScaleOutUP)
					if o.DropInOnOut {
						ctrl.V6DropInFlight(ActScaleInUP)
					}
					ev("SCALE_OUT_UP")
				} else if o.ExecWorker {
					if wkVM > wkReady {
						ev("SLOT_WORKER_BOOTING")
						continue
					}
					if wkVM >= cfg.MaxWorkers {
						ev("SCALE_OUT_UP_NOPOS")
						continue
					}
					wks = append(wks, &eqUnit{dispatch: sim, vm: sim + 5, ready: sim + hWK, gone: eqInf})
					ctrl.V6NoteDispatched(ActCreateWorker)
					ev("CREATE_WORKER*exec")
				} else {
					ev("SCALE_OUT_UP_NOPOS")
				}
			case ActScaleInUP:
				var victim *eqUnit
				for _, p := range pods {
					if p.gone > sim && !p.draining && p.ready <= sim {
						victim = p
					}
				}
				if victim == nil {
					ev("SCALE_IN_UP_NONE")
					continue
				}
				victim.draining = true
				victim.gone = sim + o.DrainSec
				ctrl.V6NoteDispatched(ActScaleInUP)
				ev("SCALE_IN_UP")
			case ActDeployVyOS:
				vys = append(vys, &eqUnit{dispatch: sim, vm: sim + 29, ready: sim + hVY, gone: eqInf})
				ctrl.V6NoteDispatched(ActDeployVyOS)
				ev("DEPLOY_VYOS")
			case ActDeleteVyOS:
				var victim *eqUnit
				for _, v := range vys {
					if v.gone > sim && !v.deleting && v.ready <= sim {
						victim = v
					}
				}
				if victim == nil {
					ev("DELETE_VYOS_NONE")
					continue
				}
				victim.deleting = true
				victim.gone = sim + dVY
				ctrl.V6NoteDispatched(ActDeleteVyOS)
				ev("DELETE_VYOS")
			case ActCreateWorker:
				wks = append(wks, &eqUnit{dispatch: sim, vm: sim + 5, ready: sim + hWK, gone: eqInf})
				ctrl.V6NoteDispatched(ActCreateWorker)
				ev("CREATE_WORKER")
			case ActDeleteWorker:
				var victim *eqUnit
				for _, w := range wks {
					if w.gone > sim && !w.deleting && w.ready <= sim-o.IdleMinSec {
						victim = w
					}
				}
				if victim == nil {
					ev("DELETE_WORKER_NONE")
					continue
				}
				victim.deleting = true
				victim.gone = sim + dWK
				ctrl.V6NoteDispatched(ActDeleteWorker)
				ev("DELETE_WORKER")
			}
		}
	}
	for m := 0; m < 60; m++ {
		pct := 100 * lossMin[m] / math.Max(offMin[m], 1)
		if pct <= 0.1 {
			res.SLO++
		}
		if pct > res.Worst {
			res.Worst = pct
		}
	}
	return res
}

func TestDecisionEquivalenceDump(t *testing.T) {
	lams := map[string][2]float64{"S3a": {2.50, 3.25}, "S3b": {1.42, 2.25}, "S4a": {2.83, 3.08}, "S4b": {1.83, 2.00}}
	for _, tn := range []string{"t1", "t2"} {
		ue := loadUE(t, "testdata/trace_"+tn+".json")
		for _, grp := range []string{"S3a", "S3b", "S4a", "S4b"} {
			for _, sc := range []struct {
				tag   string
				dm    string
				drain float64
				fail  bool
				exec  bool
				drop  bool
			}{
				{"v712_exact_d150", "exact", 150, false, true, false},
				{"v712_exact_d30", "exact", 30, false, true, false},
				{"exact_d150", "exact", 150, false, false, true},
				{"pps_d150", "pps", 150, false, false, true},
				{"exact_d30", "exact", 30, false, false, true},
				{"exact_d150_fail", "exact", 150, true, false, true},
			} {
				name := fmt.Sprintf("%s_%s_%s", grp, tn, sc.tag)
				if only := os.Getenv("EQUIV_ONLY"); only != "" && only != name {
					continue
				}
				r := runDaemonEquiv(t, ue, eqOpts{Name: name, LamVM: lams[grp][0], LamUP: lams[grp][1], DModel: sc.dm, DrainSec: sc.drain, FailFirstOut: sc.fail, ExecWorker: sc.exec, IdleMinSec: 600, DropInOnOut: sc.drop})
				raw, _ := json.Marshal(r)
				if err := os.WriteFile("testdata/equiv/"+name+".json", raw, 0o644); err != nil {
					t.Fatal(err)
				}
				t.Logf("%-28s SLO %d/60 worst %.3f%% alloc %.0f events %d", name, r.SLO, r.Worst, r.Alloc, len(r.Events))
			}
		}
	}
}
