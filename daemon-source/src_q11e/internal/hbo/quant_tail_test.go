package hbo

import "testing"


func tailParams() V6Params {
	return V6Params{Lambda: 0.002, MarginM: 0.93, SlopeMax: 0.05, UMin: 0}
}

func r49TailTick1() PlanInput {
	c := DefaultCalib()
	in := input(V6Config{NUP: 4, NVY: 2, NWK: 2}, 2500014, -8.3)
	in.Resid = Residuals{UP: 8.1e-5, VY: 4.0e-6}
	in.InFlight = []Move{{Act: ActDeleteWorker, TEffect: v6Grid}}
	in.IdleWK = false
	_ = c
	return in
}

func r49TailTick2() PlanInput {
	in := input(V6Config{NUP: 3, NVY: 2, NWK: 3}, 2500062, 1.1)
	in.Resid = Residuals{UP: 8.1e-5, VY: 3.5e-6}
	in.InFlight = []Move{{Act: ActScaleInUP, TEffect: v6Grid}, {Act: ActCreateWorker, TEffect: v6Grid}}
	in.Blocked[ActDeleteWorker] = true
	return in
}

func noopJ(all []TupleScore) float64 {
	for _, s := range all {
		if s.Key == "∅" {
			return s.J
		}
	}
	return -1
}

func TestTailQuantizationNoRebound(t *testing.T) {
	c := DefaultCalib()
	for name, in := range map[string]PlanInput{"tick1": r49TailTick1(), "tick2": r49TailTick2()} {
		best, all := DecideV6(in, &c, tailParams())
		if hasAct(best.Moves, ActCreateWorker) || hasAct(best.Moves, ActScaleOutUP) {
			t.Fatalf("%s: 10 UE plateau must not scale out, got %q (noop J %.2f)", name, best.Key, noopJ(all))
		}
		if j := noopJ(all); j > 20 {
			t.Fatalf("%s: noop J %.2f — barrier fired on a 10 UE plateau", name, j)
		}
	}
}

func TestTailQuantizationOldCeilReproducesRebound(t *testing.T) {
	t.Setenv("V6_UE_QUANT_TOL", "0")
	t.Setenv("V6_UP_LOOKAHEAD_BATCHES", "0")
	c := DefaultCalib()
	best, all := DecideV6(r49TailTick1(), &c, tailParams())
	if !hasAct(best.Moves, ActCreateWorker) || noopJ(all) < 50 {
		t.Fatalf("old ceil semantics should reproduce r49 tick1 rebound (CREATE_WORKER, noop J≈81), got %q J_noop %.2f", best.Key, noopJ(all))
	}
}

func TestUEQuantTolerance(t *testing.T) {
	c := DefaultCalib()
	pc := PlanCalib(&c, tailParams())
	u20 := uUPQuant(20*pc.PerUEBidir+28, 4, pc)
	u21 := uUPQuant(20.5*pc.PerUEBidir, 4, pc)
	if u20 > 1.0 || u21 < 1.1 {
		t.Fatalf("quantization: u(20 UE+28pps)=%.3f (want <1.0), u(20.5 UE)=%.3f (want >1.1)", u20, u21)
	}
}
