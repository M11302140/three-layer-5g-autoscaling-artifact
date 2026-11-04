package hbo

import (
	"os"
	"testing"
)

func TestLayeredNeverJointVoluntary(t *testing.T) {
	c := DefaultCalib()
	for _, cfg := range []V6Config{{NUP: 6, NVY: 2, NWK: 3}, {NUP: 3, NVY: 1, NWK: 2}, {NUP: 8, NVY: 3, NWK: 4}} {
		for _, off := range []float64{2.5e6, 4.5e6, 6.5e6, 8.0e6} {
			in := input(cfg, off, 20)
			os.Setenv("V6_PLANNER_LAYERED", "true")
			best, all := DecideV6(in, &c, tailParams())
			os.Unsetenv("V6_PLANNER_LAYERED")
			if len(all) == 0 {
				t.Fatalf("cfg %+v off %.0f: no candidates", cfg, off)
			}
			for _, m := range best.Moves {
				if _, ok := tupleLayer([]Move{m}, in); !ok {
					t.Fatalf("cfg %+v off %.0f: layered best has non-single-layer move %v", cfg, off, m.Act)
				}
			}
			bj, _ := DecideV6(in, &c, tailParams())
			if bj.Key == "" {
				t.Fatalf("joint decide returned empty key")
			}
		}
	}
}

func TestIrrevHoldFlagOff(t *testing.T) {
	os.Setenv("V6_IRREV_HOLD", "false")
	defer os.Unsetenv("V6_IRREV_HOLD")
	c := DefaultCalib()
	sh := NewV6Shadow(nil)
	if hold, _ := irreversibilityHold(ActScaleInUP, SystemState{RepUP: 6, VyosCount: 2}, 6.5e6, sh, &c); hold {
		t.Fatal("hold should be off")
	}
}
