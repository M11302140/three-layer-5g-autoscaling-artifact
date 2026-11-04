package hbo

import (
	"fmt"
	"testing"
	"time"
)

// r70 (2026-09-16) replay: why 8 slots at 28 UE (min4.8) and 5→7 at 21 UE (min51.8/52.3).
func TestReplayR70Ticks(t *testing.T) {
	c := DefaultCalib()
	p := V6Params{Lambda: 0.002, MarginM: 0.93, SlopeMax: 0.05, UMin: 0}
	b := V6Bounds{MinUP: 1, MaxUP: 8, MinVY: 1, MaxVY: 3, MinWK: 1, MaxWK: 4}
	for _, tc := range []struct {
		name          string
		nup, nvy, nwk int
		off, slope    float64
	}{
		{"min4.8 28UE 7slots", 7, 2, 4, 7009216, 0},
		{"min0 25UE 7slots", 7, 2, 4, 6.25e6, 0},
		{"min51.8 21UE 5slots", 5, 2, 4, 5238120, 0},
		{"min52.3 21UE 6slots", 6, 2, 4, 5240336, 119.8},
		{"min50.8 19UE 6slots", 6, 2, 4, 4750382, 0},
		{"ramp 28UE 7slots +3UE/min", 7, 2, 4, 7009216, 12500},
		{"jitter 21UE 6slots +2UE/2min", 6, 2, 4, 5240336, 4170},
	} {
		in := input(V6Config{NUP: tc.nup, NVY: tc.nvy, NWK: tc.nwk}, tc.off, tc.slope)
		in.Bounds = b
		best, all := DecideV6(in, &c, p)
		t.Logf("%-24s -> %-28s J=%.2f noopJ=%.2f", tc.name, best.Key, best.J, noopJ(all))
		switch tc.name {
		case "min4.8 28UE 7slots", "min52.3 21UE 6slots":
			if hasAct(best.Moves, ActScaleOutUP) {
				t.Fatalf("p5u: %s must not add a slot (only +1 batch visible to the slot layer): %q", tc.name, best.Key)
			}
		case "ramp 28UE 7slots +3UE/min":
			if !hasAct(best.Moves, ActScaleOutUP) {
				t.Fatalf("p5u2: a sustained +3 UE/min rise at 28 UE must buy the spare (8th) slot: %q", best.Key)
			}
		case "jitter 21UE 6slots +2UE/2min":
			if hasAct(best.Moves, ActScaleOutUP) {
				t.Fatalf("p5u2: 2-UE jitter slope must not add a 7th slot at 21 UE: %q", best.Key)
			}
		case "min51.8 21UE 5slots":
			if !hasAct(best.Moves, ActScaleOutUP) {
				t.Fatalf("p5u: 21 UE on 5 slots needs a 6th for the next batch: %q", best.Key)
			}
		}
		// per-grid model loss for the noop config
		s := ""
		for tt := 0.0; tt < v6TH; tt += v6Grid {
			off := offeredAt(in, p, &c, tt)
			m := VE2E(in.Cfg, off, Residuals{}, &c)
			s += fmt.Sprintf(" t%3.0f:ue%.1f/f%.4f", tt, off/2.5e5, m*100)
		}
		t.Logf("   noop per-grid (ue / model loss %%):%s", s)
	}
	t.Logf("EpsDesign=%.5f  fCNF(u=0.85)=%.5f fCNF(0.94)=%.5f fCNF(0.996)=%.5f fCNF(1.03)=%.5f", c.EpsDesign, fCNF(0.85, &c), fCNF(0.94, &c), fCNF(0.996, &c), fCNF(1.03, &c))
}

func TestUPScaleInHoldWindowAtLeastHorizon(t *testing.T) {
	c := DefaultCalib()
	w := irreversibilityWindow(ActScaleInUP, SystemState{RepUP: 6, WorkerCount: 4}, &c)
	if w < v6TH {
		t.Fatalf("p5u: slot scale-in commitment window must be >= planning horizon: %.0f", w)
	}
	if nb := upLookaheadBatches(&c); nb != 1 {
		t.Fatalf("slot lookahead batches: want 1, got %d", nb)
	}
}

// r71 (p5u2) min48-55: 7 slots at 19 UE, 300 s peak 21 UE → 7→6 must be allowed (21+1 batch=26 on 6
// slots = 5/slot); 6→5 must be held (26 on 5 = 6/slot). Old rise floor (2 batches) held 7→6 forever.
func TestUPScaleInHoldUsesOneBatchRise(t *testing.T) {
	sh, cal := holdFixture()
	now := time.Now()
	pts := [][2]float64{}
	for ago := 600.0; ago >= 0; ago -= 30 { // 21 UE plateau for the last 10 min (5.25M bidir)
		pts = append(pts, [2]float64{ago, 5.25})
	}
	sh.offHist = hist(now, pts)
	s := SystemState{RepUP: 7, WorkerCount: 4, VyosCount: 2}
	if hold, why := irreversibilityHold(ActScaleInUP, s, 4.75e6, sh, cal); hold {
		t.Fatalf("p5u3: 7→6 at 19 UE with 300 s peak 21 UE must release: %s", why)
	}
	s6 := SystemState{RepUP: 6, WorkerCount: 4, VyosCount: 2}
	if hold, _ := irreversibilityHold(ActScaleInUP, s6, 4.75e6, sh, cal); !hold {
		t.Fatalf("p5u3: 6→5 at 19 UE with 300 s peak 21 UE must hold (26 UE on 5 slots)")
	}
}
