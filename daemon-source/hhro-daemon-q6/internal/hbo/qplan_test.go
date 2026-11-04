package hbo

import (
	"encoding/json"
	"math"
	"os"
	"testing"
	"time"
)

func qInput(nup, nvy, nwk int, ue float64) PlanInput {
	return PlanInput{
		Cfg: V6Config{NUP: nup, NVY: nvy, NWK: nwk}, Offered: ue * 250000,
		Bounds:  V6Bounds{MinUP: 2, MaxUP: 8, MinVY: 1, MaxVY: 3, MinWK: 1, MaxWK: 4},
		Blocked: map[Action]bool{}, BaseCores: 8, BaseMemGi: 12,
	}
}

func TestDecideQuantileBasics(t *testing.T) {
	c0 := DefaultCalib()
	p := V6Params{Lambda: 0.002, MarginM: 0.93}
	c := PlanCalib(&c0, p)
	r := mustRise(t, 0.05)

	prev := QNeeds{}
	for ue := 4.0; ue <= 40; ue += 2 {
		q := qNeeds(qInput(2, 1, 1, ue), c, r)
		if q.NeedUP < prev.NeedUP || q.NeedVY < prev.NeedVY || q.NeedWK < prev.NeedWK {
			t.Fatalf("needs must be monotone in offered: %v UE %+v after %+v", ue, q, prev)
		}
		if q.NeedWK*slotsPerWorker < q.NeedUP {
			t.Fatalf("worker positions must cover the slot requirement: %+v", q)
		}
		prev = q
		t.Logf("%4.0f UE → need up/vy/wk = %d/%d/%d (margins %.1f/%.1f/%.1f UE)", ue, q.NeedUP, q.NeedVY, q.NeedWK, q.MarginUP/250000, q.MarginVY/250000, q.MarginWK/250000)
	}
	best, _ := decideQuantile(qInput(2, 1, 1, 40), c, p, r)
	for _, a := range []Action{ActDeployVyOS, ActCreateWorker, ActScaleOutUP} {
		if !hasMove(best.Moves, a) {
			t.Fatalf("40 UE on 2/1/1 must scale out every layer, got %q", best.Key)
		}
	}
	in := qInput(2, 1, 1, 40)
	in.Blocked[ActDeployVyOS] = true
	if best, _ := decideQuantile(in, c, p, r); hasMove(best.Moves, ActDeployVyOS) {
		t.Fatalf("blocked action dispatched: %q", best.Key)
	}
	in = qInput(7, 2, 4, 40)
	in.InFlight = []Move{{Act: ActScaleOutUP, TEffect: 10, deltaUP: +1}, {Act: ActDeployVyOS, TEffect: 60, deltaVY: +1}}
	if best, _ := decideQuantile(in, c, p, r); len(best.Moves) != 0 {
		t.Fatalf("in-flight capacity already covers the need, got %q", best.Key)
	}
	in = qInput(8, 3, 4, 6)
	in.IdleWK = false
	best, _ = decideQuantile(in, c, p, r)
	if !hasMove(best.Moves, ActScaleInUP) || !hasMove(best.Moves, ActDeleteVyOS) {
		t.Fatalf("6 UE on 8/3/4 must propose releases, got %q", best.Key)
	}
	if hasMove(best.Moves, ActDeleteWorker) {
		t.Fatalf("no idle worker → no worker delete: %q", best.Key)
	}
}

func TestHoldQuantile(t *testing.T) {
	c0 := DefaultCalib()
	p := V6Params{Lambda: 0.002, MarginM: 0.93}
	c := PlanCalib(&c0, p)
	r := mustRise(t, 0.05)
	if hold, why := holdQuantilePure(ActScaleInUP, V6Config{NUP: 6, NVY: 2, NWK: 3}, 25*250000, c, p, r); !hold {
		t.Fatalf("25 UE on 6 slots must hold the 6th slot")
	} else {
		t.Log(why)
	}
	if hold, why := holdQuantilePure(ActScaleInUP, V6Config{NUP: 6, NVY: 2, NWK: 3}, 8*250000, c, p, r); hold {
		t.Fatalf("8 UE on 6 slots must release: %s", why)
	}
	for _, a := range [][2]Action{{ActScaleInUP, ActScaleOutUP}, {ActDeleteVyOS, ActDeployVyOS}, {ActDeleteWorker, ActCreateWorker}} {
		cfg := V6Config{NUP: 6, NVY: 2, NWK: 3}
		if w, h := qCommitWindow(a[0], cfg, c), qOutHorizon(a[1], c); a[0] != ActScaleInUP && w < h {
			t.Fatalf("%s commit window %.0f < out horizon %.0f", a[0], w, h)
		}
		if d := qBreakEven(a[0], c, p); d <= 0 {
			t.Fatalf("break-even dwell must be positive for %s", a[0])
		}
	}
	t.Logf("break-even dwell: UP %.0fs VY %.0fs WK %.0fs", qBreakEven(ActScaleInUP, c, p), qBreakEven(ActDeleteVyOS, c, p), qBreakEven(ActDeleteWorker, c, p))
	full := V6Config{NUP: 8, NVY: 3, NWK: 4}
	t.Setenv("V6_REVERSIBLE_DRAIN", "true")
	if w := qCommitWindow(ActScaleInUP, full, c); w != c.Act[ActScaleOutUP].TReadySec+v6Grid {
		t.Fatalf("reversible drain: full-position window %.0f != T_out+grid", w)
	}
	t.Setenv("V6_REVERSIBLE_DRAIN", "false")
	if w := qCommitWindow(ActScaleInUP, full, c); w != c.Act[ActScaleInUP].TReadySec+c.Act[ActScaleOutUP].TReadySec+v6Grid {
		t.Fatalf("irreversible drain: full-position window %.0f != T_in+T_out+grid", w)
	}
}

type qsimResult struct {
	SLO          int
	Worst, Alloc float64
	Acts, Flaps  int
	Traj         []V6Config
}

func qsimRun(t *testing.T, ue []float64, eps float64) qsimResult {
	t.Helper()
	t.Setenv("V6_RISE_WARM_S", "0")
	c0 := DefaultCalib()
	p := V6Params{Lambda: 0.002, MarginM: 0.93}
	c := PlanCalib(&c0, p)
	r := mustRise(t, eps)
	r.NeedFn = func(x float64) [3]int {
		up := slotsNeededUP(x, c)
		return [3]int{up, vyNeeded(x, c), (up + slotsPerWorker - 1) / slotsPerWorker}
	}
	b := V6Bounds{MinUP: 2, MaxUP: 8, MinVY: 1, MaxVY: 3, MinWK: 1, MaxWK: 4}
	const dt = 5.0
	d := make([]float64, 0, len(ue)*12)
	for _, u := range ue {
		for k := 0; k < 12; k++ {
			d = append(d, u*250000)
		}
	}
	t0 := time.Date(2026, 9, 29, 0, 0, 0, 0, time.UTC)
	r.ResetEpisode(t0)
	q0 := qNeeds(PlanInput{Offered: d[0], Bounds: b}, c, r)
	cur := V6Config{NUP: q0.NeedUP, NVY: q0.NeedVY, NWK: q0.NeedWK}
	type fl struct {
		m   Move
		eff float64
	}
	var infl []fl
	type dying struct {
		act Action
		end float64
	}
	var dy []dying
	burn := cur
	lastOut := map[Action]float64{}
	lastDir := map[string][2]float64{}
	res := qsimResult{}
	lossMin := make([]float64, 60)
	offMin := make([]float64, 60)
	capVY := c.CapVY * ThetaDesignVY(c)
	for i := range d {
		now := float64(i) * dt
		keep := infl[:0]
		for _, f := range infl {
			if f.eff <= now {
				cur.NUP += f.m.deltaUP
				cur.NVY += f.m.deltaVY
				cur.NWK += f.m.deltaWK
			} else {
				keep = append(keep, f)
			}
		}
		infl = keep
		kd := dy[:0]
		for _, x := range dy {
			if x.end <= now {
				switch x.act {
				case ActScaleInUP:
					burn.NUP--
				case ActDeleteVyOS:
					burn.NVY--
				case ActDeleteWorker:
					burn.NWK--
				}
			} else {
				kd = append(kd, x)
			}
		}
		dy = kd
		l := 0.0
		if cv := float64(cur.NVY) * capVY; d[i] > cv {
			l = 1 - cv/d[i]
		}
		x := d[i] * (1 - l)
		if cu := float64(cur.NUP) * 5 * 250000; x > cu+1 {
			l = 1 - (1-l)*cu/x
		}
		mi := int(now) / 60
		lossMin[mi] += l * d[i] * dt
		offMin[mi] += d[i] * dt
		res.Alloc += (3*float64(burn.NWK) + 2*float64(burn.NVY) + 0.8*float64(burn.NUP)) * dt / 60
		if math.Mod(now, v6Grid) != 0 {
			continue
		}
		res.Traj = append(res.Traj, cur)
		r.Observe(t0.Add(time.Duration(now)*time.Second), d[i], nil)
		in := PlanInput{Cfg: cur, Offered: d[i], Bounds: b, Blocked: map[Action]bool{}, BaseCores: 8, BaseMemGi: 12}
		for _, f := range infl {
			m := f.m
			m.TEffect = f.eff - now
			in.InFlight = append(in.InFlight, m)
			in.Blocked[reverseOf(m.Act)] = true
		}
		for a, tt := range lastOut {
			if now-tt < qBreakEven(reverseOf(a), c, p)*qDwellK() {
				in.Blocked[reverseOf(a)] = true
			}
		}
		eff := configAt(cur, in.InFlight, 1e12)
		in.IdleWK = eff.NUP <= (eff.NWK-1)*slotsPerWorker
		best, _ := decideQuantile(in, c, p, r)
		for _, m := range best.Moves {
			layer := map[Action]string{ActScaleOutUP: "up", ActScaleInUP: "up", ActDeployVyOS: "vy", ActDeleteVyOS: "vy", ActCreateWorker: "wk", ActDeleteWorker: "wk"}[m.Act]
			if m.Act.IsScaleIn() {
				delta := qBreakEven(m.Act, c, p) * qDwellK()
				if now < delta {
					continue
				}
				peak := d[i]
				for j := i; j >= 0 && float64(i-j)*dt <= delta; j-- {
					if d[j] > peak {
						peak = d[j]
					}
				}
				if hold, _ := holdQuantilePure(m.Act, cur, peak, c, p, r); hold {
					continue
				}
				cur.NUP += m.deltaUP
				cur.NVY += m.deltaVY
				cur.NWK += m.deltaWK
				dy = append(dy, dying{m.Act, now + c.Act[m.Act].TReadySec})
				if ld, ok := lastDir[layer]; ok && ld[0] > 0 && now-ld[1] <= 600 {
					res.Flaps++
				}
				lastDir[layer] = [2]float64{-1, now}
			} else {
				infl = append(infl, fl{m, now + m.TEffect})
				burn.NUP += m.deltaUP
				burn.NVY += m.deltaVY
				burn.NWK += m.deltaWK
				lastOut[m.Act] = now
				if ld, ok := lastDir[layer]; ok && ld[0] < 0 && now-ld[1] <= 600 {
					res.Flaps++
				}
				lastDir[layer] = [2]float64{+1, now}
			}
			res.Acts++
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

func loadUE(t *testing.T, path string) []float64 {
	t.Helper()
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	var tr struct {
		UE []float64 `json:"ue"`
	}
	if err := json.Unmarshal(raw, &tr); err != nil {
		t.Fatal(err)
	}
	return tr.UE[:60]
}

func TestQSimDevTraces(t *testing.T) {
	for _, rule := range []string{"r0", "r1"} {
		t.Setenv("V6_RELEASE_RULE", rule)
		qsimDev(t, rule)
	}
}

func TestReleaseRuleR1ReducesFlaps(t *testing.T) {
	for _, name := range []string{"t1", "t2"} {
		ue := loadUE(t, "testdata/trace_"+name+".json")
		for _, eps := range []float64{0.2, 0.1, 0.05} {
			t.Setenv("V6_RELEASE_RULE", "r0")
			a := qsimRun(t, ue, eps)
			t.Setenv("V6_RELEASE_RULE", "r1")
			b := qsimRun(t, ue, eps)
			if b.Flaps > a.Flaps {
				t.Fatalf("%s eps=%.2f: r1 flaps %d > r0 flaps %d", name, eps, b.Flaps, a.Flaps)
			}
			if b.SLO < a.SLO-1 {
				t.Fatalf("%s eps=%.2f: r1 SLO %d materially below r0 %d", name, eps, b.SLO, a.SLO)
			}
		}
	}
}

func qsimDev(t *testing.T, rule string) {
	for _, name := range []string{"t1", "t2"} {
		ue := loadUE(t, "testdata/trace_"+name+".json")
		prevAlloc := 0.0
		for _, eps := range []float64{0.2, 0.1, 0.05, 0.02} {
			r := qsimRun(t, ue, eps)
			t.Logf("%s %s eps=%.2f  SLO %d/60  worst %.2f%%  alloc %.0f core-min  acts %d  flaps %d", rule, name, eps, r.SLO, r.Worst, r.Alloc, r.Acts, r.Flaps)
			if eps <= 0.05 && r.SLO < 57 {
				t.Fatalf("%s eps=%.2f: SLO %d/60 — model under-provisions the dev trace", name, eps, r.SLO)
			}
			if r.Alloc+30 < prevAlloc {
				t.Fatalf("%s: allocation must not drop materially as eps tightens (%.0f → %.0f)", name, prevAlloc, r.Alloc)
			}
			prevAlloc = r.Alloc
		}
	}
}


func TestQSimRhoSweep(t *testing.T) {
	t.Setenv("V6_RELEASE_RULE", "r1")
	for _, name := range []string{"t1", "t2"} {
		ue := loadUE(t, "testdata/trace_"+name+".json")
		for _, cfg := range [][3]string{{"0.05", "0.30", "1"}, {"0.05", "0.50", "1"}, {"0.10", "0.10", "1"}, {"0.10", "0.30", "1"}, {"0.10", "0.30", "2"}, {"0.10", "0.50", "2"}, {"0.10", "0.30", "4"}, {"0.05", "0.30", "2"}, {"0.05", "0.30", "4"}} {
			t.Setenv("V6_RHO", cfg[1])
			t.Setenv("V6_DWELL_K", cfg[2])
			eps := 0.10
			if cfg[0] == "0.05" {
				eps = 0.05
			}
			r := qsimRun(t, ue, eps)
			t.Logf("%s eps=%s rho=%s k=%s  SLO %d/60  worst %.2f%%  alloc %.0f  acts %d  flaps %d", name, cfg[0], cfg[1], cfg[2], r.SLO, r.Worst, r.Alloc, r.Acts, r.Flaps)
		}
	}
}
