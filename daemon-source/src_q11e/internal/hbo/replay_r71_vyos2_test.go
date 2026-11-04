package hbo

import (
	"fmt"
	"testing"
)

func TestReplayVyosKnifeDetail(t *testing.T) {
	c := DefaultCalib()
	p := V6Params{Lambda: 0.002, MarginM: 0.93, SlopeMax: 0.05, UMin: 0}
	b := V6Bounds{MinUP: 1, MaxUP: 8, MinVY: 1, MaxVY: 3, MinWK: 1, MaxWK: 4}
	for _, off := range []float64{7.0e6, 7.05e6} {
		in := input(V6Config{NUP: 7, NVY: 2, NWK: 4}, off, 0)
		in.Bounds = b
		_, all := DecideV6(in, &c, p)
		for _, ts := range all {
			if ts.Key == "∅" || ts.Key == "DEPLOY_VYOS" {
				r := ""
				for _, m := range ts.Rollout {
					r += fmt.Sprintf(" %s@%.0f", m.Act, m.TEffect)
				}
				t.Logf("off=%.2fUE tuple %-12s J=%.2f rollout:%s", off/2.5e5, ts.Key, ts.J, r)
			}
		}
		// per-grid layered loss for the noop config with the noop rollout applied
		var noop TupleScore
		for _, ts := range all {
			if ts.Key == "∅" {
				noop = ts
			}
		}
		moves := append(append([]Move{}, in.InFlight...), noop.Rollout...)
		s := ""
		for tt := 0.0; tt < v6TH; tt += v6Grid {
			cfg := configAt(in.Cfg, moves, tt)
			offVY := offeredAt(in, p, &c, tt)
			offUP := offeredAtUP(in, p, &c, tt)
			m := VE2ELayered(cfg, offVY, offUP, Residuals{}, &c)
			s += fmt.Sprintf(" t%.0f:vy%d/up%d/%.3f%%", tt, cfg.NVY, cfg.NUP, m*100)
		}
		t.Logf("   noop+rollout per-grid:%s", s)
	}
}
