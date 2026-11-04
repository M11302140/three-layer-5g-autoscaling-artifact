package hbo

import (
	"encoding/json"
	"math"
	"os"
	"testing"
)

func mustSigma(t *testing.T, lvm, lup float64) *RiseModel {
	t.Helper()
	sp, err := LoadSigmaPrior()
	if err != nil {
		t.Fatal(err)
	}
	c0 := sigmaCalib()
	p := V6Params{Lambda: 0.002, MarginM: 0.93}
	c := PlanCalib(&c0, p)
	hs := map[float64]float64{qOutHorizon(ActScaleOutUP, c): lup, qOutHorizon(ActDeployVyOS, c): lvm, qOutHorizon(ActCreateWorker, c): lvm}
	return NewSigmaRiseModel(sp, lvm, lup, 250000, hs)
}

// sigmaCalib: the calibration the sigma mode actually runs with (measured p90 leads, v7.1.1).
func sigmaCalib() Calib {
	c := DefaultCalib()
	if sigmaUseMeasured() {
		c = applyMeasuredTReady(c)
	}
	return c
}

func TestSigmaPriorMatchesReference(t *testing.T) {
	raw, err := os.ReadFile("testdata/sigma_expect.json")
	if err != nil {
		t.Fatal(err)
	}
	var exp []struct {
		Kind    string  `json:"kind"`
		H       float64 `json:"h"`
		LevelUE float64 `json:"level_ue"`
		SigmaUE float64 `json:"sigma_ue"`
	}
	if err := json.Unmarshal(raw, &exp); err != nil {
		t.Fatal(err)
	}
	sp, err := LoadSigmaPrior()
	if err != nil {
		t.Fatal(err)
	}
	for _, e := range exp {
		got := sp.Sigma(e.Kind, e.H, e.LevelUE*250000) / 250000
		if math.Abs(got-e.SigmaUE) > 1e-6 {
			t.Fatalf("sigma(%s,%.0f,%.0f UE) = %.4f, reference %.4f", e.Kind, e.H, e.LevelUE, got, e.SigmaUE)
		}
	}
	if sp.Sigma("win", 46, 20*250000) != sp.Sigma("win", 50, 20*250000) || sp.Sigma("run", 9999, 20*250000) != sp.Sigma("run", 420, 20*250000) {
		t.Fatalf("horizon grid mapping")
	}
	t.Logf("sigma prior: %d traces, win(45,20UE)=%.2f UE run(145,20UE)=%.2f UE", sp.NTraces, sp.Sigma("win", 45, 20*250000)/250000, sp.Sigma("run", 145, 20*250000)/250000)
}

func TestSigmaMarginsAndDecide(t *testing.T) {
	t.Setenv("V6_DEMAND_MODEL", "sigma")
	t.Setenv("V6_RELEASE_RULE", "r1")
	c0 := sigmaCalib()
	p := V6Params{Lambda: 0.002, MarginM: 0.93}
	c := PlanCalib(&c0, p)
	r := mustSigma(t, 1.5, 3.5)
	if !r.SigmaMode() {
		t.Fatal("sigma mode")
	}
	sp := r.sig
	prev := QNeeds{}
	for ue := 4.0; ue <= 40; ue += 2 {
		q := qNeeds(qInput(2, 1, 1, ue), c, r)
		lvl := ue * 250000
		if w := 3.5 * sp.Sigma("win", qOutHorizon(ActScaleOutUP, c), lvl); math.Abs(q.MarginUP-w) > 1 {
			t.Fatalf("UP margin %.0f != λ_UP·σ %.0f", q.MarginUP, w)
		}
		if w := 1.5 * sp.Sigma("win", qOutHorizon(ActDeployVyOS, c), lvl); math.Abs(q.MarginVY-w) > 1 {
			t.Fatalf("VY margin %.0f != λ_VM·σ %.0f", q.MarginVY, w)
		}
		if w := 1.5 * sp.Sigma("win", qOutHorizon(ActCreateWorker, c), lvl); math.Abs(q.MarginWK-w) > 1 {
			t.Fatalf("WK margin %.0f != λ_VM·σ %.0f", q.MarginWK, w)
		}
		if int(ue/10) == int((ue-2)/10) && (q.NeedUP < prev.NeedUP || q.NeedVY < prev.NeedVY || q.NeedWK < prev.NeedWK) {
			t.Fatalf("needs must be monotone in offered within a σ bucket: %v UE %+v after %+v", ue, q, prev)
		}
		if int(ue/10) != int((ue-2)/10) && (q.NeedUP < prev.NeedUP || q.NeedVY < prev.NeedVY || q.NeedWK < prev.NeedWK) {
			t.Logf("bucket boundary at %.0f UE: needs %d/%d/%d after %d/%d/%d (σ bucket change)", ue, q.NeedUP, q.NeedVY, q.NeedWK, prev.NeedUP, prev.NeedVY, prev.NeedWK)
		}
		p1 := clampInt(slotsNeededUP(lvl+q.MarginWK, c), 2, 8)
		p2 := clampInt(slotsNeededUP(lvl+3.5*sp.Sigma("win", qOutHorizon(ActCreateWorker, c), lvl), c), 2, 8)
		if p2 > p1 {
			p1 = p2
		}
		if want := (p1 + slotsPerWorker - 1) / slotsPerWorker; q.NeedWK != clampInt(want, 1, 4) {
			t.Fatalf("NeedWK %d != ceil(max(own, slot-target@H_WK)/spw) %d", q.NeedWK, want)
		}
		if q.NeedWK*slotsPerWorker < q.NeedUP {
			t.Fatalf("invariant: positions %d < slot need %d at %.0f UE", q.NeedWK*slotsPerWorker, q.NeedUP, ue)
		}
		prev = q
		if int(ue)%8 == 0 {
			t.Logf("%4.0f UE → need up/vy/wk = %d/%d/%d (λσ margins %.2f/%.2f/%.2f UE)", ue, q.NeedUP, q.NeedVY, q.NeedWK, q.MarginUP/250000, q.MarginVY/250000, q.MarginWK/250000)
		}
	}
	best, _ := decideQuantile(qInput(2, 1, 1, 40), c, p, r)
	for _, a := range []Action{ActDeployVyOS, ActCreateWorker, ActScaleOutUP} {
		if !hasMove(best.Moves, a) {
			t.Fatalf("40 UE on 2/1/1 must scale out every layer, got %q", best.Key)
		}
	}
	in := qInput(8, 3, 4, 6)
	in.IdleWK = false
	if best, _ = decideQuantile(in, c, p, r); !hasMove(best.Moves, ActScaleInUP) || !hasMove(best.Moves, ActDeleteVyOS) {
		t.Fatalf("6 UE on 8/3/4 must propose releases, got %q", best.Key)
	}
	in = qInput(2, 1, 1, 7)
	if q := qNeeds(in, c, r); q.NeedUP > 2 {
		if q.NeedWK*slotsPerWorker < q.NeedUP {
			t.Fatalf("invariant violated at 7 UE: %+v", q)
		}
		if best, _ = decideQuantile(in, c, p, r); !hasMove(best.Moves, ActCreateWorker) {
			t.Fatalf("worker layer must order the position for the slot target: %q (needs %+v)", best.Key, q)
		}
	}
	if hold, why := holdQuantilePure(ActDeleteWorker, V6Config{NUP: 6, NVY: 2, NWK: 4}, 24*250000, c, p, r); !hold {
		t.Fatalf("worker release must respect the slot layer's order-up-to (24 UE peak, 6 slots on 4 workers)")
	} else {
		t.Log(why)
	}
	cfg := V6Config{NUP: 6, NVY: 2, NWK: 3}
	w := qCommitWindow(ActScaleInUP, cfg, c)
	x, h := qReleaseDemand(ActScaleInUP, cfg, 20*250000, c, p, r)
	if h != w || math.Abs(x-(20*250000+3.5*sp.Sigma("run", w, 20*250000))) > 1 {
		t.Fatalf("release demand must be peak + λ_UP·σ_run(W): got x=%.0f h=%.0f, W=%.0f", x, h, w)
	}
	if ww := qCommitWindow(ActDeleteWorker, cfg, c); ww != c.Act[ActCreateWorker].TReadySec+c.Act[ActScaleOutUP].TReadySec+v6Grid {
		t.Fatalf("sigma-mode WK exposure window %.0f != h_WK + h_UP + g", ww)
	}
	if hold, why := holdQuantilePure(ActScaleInUP, cfg, 25*250000, c, p, r); !hold {
		t.Fatalf("25 UE peak on 6 slots must hold the 6th slot")
	} else {
		t.Log(why)
	}
	if hold, why := holdQuantilePure(ActScaleInUP, cfg, 8*250000, c, p, r); hold {
		t.Fatalf("8 UE on 6 slots must release: %s", why)
	}
	if sigmaLockSec(ActScaleOutUP) != 300 || sigmaLockSec(ActDeployVyOS) != 600 || sigmaLockSec(ActCreateWorker) != 600 {
		t.Fatalf("inherited locks must be 300 s (slot) / 600 s (VM)")
	}
	t.Logf("W: UP %.0f VY %.0f WK %.0f s; H: UP %.0f VY %.0f WK %.0f s", w, qCommitWindow(ActDeleteVyOS, cfg, c), qCommitWindow(ActDeleteWorker, cfg, c), qOutHorizon(ActScaleOutUP, c), qOutHorizon(ActDeployVyOS, c), qOutHorizon(ActCreateWorker, c))
}

func TestSigmaQSimDevTraces(t *testing.T) {
	t.Setenv("V6_DEMAND_MODEL", "sigma")
	t.Setenv("V6_RISE_WARM_S", "0")
	c0 := sigmaCalib()
	p := V6Params{Lambda: 0.002, MarginM: 0.93}
	c := PlanCalib(&c0, p)
	t.Logf("sigma calib (measured=%v): T_ready out UP/VY/WK %.0f/%.0f/%.0f, in %.0f/%.0f/%.0f", sigmaUseMeasured(), c.Act[ActScaleOutUP].TReadySec, c.Act[ActDeployVyOS].TReadySec, c.Act[ActCreateWorker].TReadySec, c.Act[ActScaleInUP].TReadySec, c.Act[ActDeleteVyOS].TReadySec, c.Act[ActDeleteWorker].TReadySec)
	for _, name := range []string{"t1", "t2"} {
		ue := loadUE(t, "testdata/trace_"+name+".json")
		for _, lam := range [][2]float64{{1.5, 3.5}, {1.0, 2.5}, {2.0, 4.5}} {
			r := mustSigma(t, lam[0], lam[1])
			res := qsimRunWith(t, ue, r, c, p, func(out Action) float64 { return sigmaLockSec(out) }, func(in Action, cfg V6Config) float64 { return qCommitWindow(in, cfg, c) })
			t.Logf("%s sigma λ %.1f/%.1f: SLO %d/60 worst %.3f%% alloc %.0f core-min acts %d flaps %d", name, lam[0], lam[1], res.SLO, res.Worst, res.Alloc, res.Acts, res.Flaps)
			if lam[0] == 1.5 && res.SLO < 55 {
				t.Fatalf("%s sigma λ 1.5/3.5: SLO %d/60 too low", name, res.SLO)
			}
		}
		t.Setenv("V6_DEMAND_MODEL", "quantile")
		q := qsimRun(t, ue, 0.05)
		t.Setenv("V6_DEMAND_MODEL", "sigma")
		t.Logf("%s quantile ε=0.05 (r1): SLO %d/60 worst %.3f%% alloc %.0f acts %d flaps %d", name, q.SLO, q.Worst, q.Alloc, q.Acts, q.Flaps)
	}
}
