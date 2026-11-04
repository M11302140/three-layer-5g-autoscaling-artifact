package hbo

import (
	"testing"
	"time"
)

func TestBlipSlopeDoesNotDeployVyos(t *testing.T) {
	c := DefaultCalib()
	p := V6Params{Lambda: 0.002, MarginM: 0.93, SlopeMax: 0.05, UMin: 0}
	in := input(V6Config{NUP: 3, NVY: 1, NWK: 2}, 1.5e6, 9919)
	in.Bounds = V6Bounds{MinUP: 1, MaxUP: 8, MinVY: 1, MaxVY: 3, MinWK: 1, MaxWK: 4}
	best, all := DecideV6(in, &c, p)
	if hasAct(best.Moves, ActDeployVyOS) {
		t.Fatalf("a one-minute blip slope must not deploy a VyOS at 6 UE: %q (noop J %.1f)", best.Key, noopJ(all))
	}
	in2 := input(V6Config{NUP: 4, NVY: 1, NWK: 3}, 3.5e6, 8000)
	in2.Bounds = in.Bounds
	best2, _ := DecideV6(in2, &c, p)
	if !hasAct(best2.Moves, ActDeployVyOS) {
		t.Fatalf("14 UE with one more batch in lead time must deploy: %q", best2.Key)
	}
}

func TestSlopeNeedsOneBatchInterval(t *testing.T) {
	v := NewV6Shadow(testLogger())
	v.calib = DefaultCalib()
	v.Enabled = true
	v.episodeStart = time.Now().Add(-600 * time.Second)
	now := time.Now()
	var plateau [][2]float64
	for ago := 330.0; ago >= 60; ago -= 30 {
		plateau = append(plateau, [2]float64{ago, 1.5})
	}
	plateau = append(plateau, [2]float64{30, 2.5})
	v.offHist = hist(now, plateau)
	f := FeatureSet{PktRateUP: WindowFeature{Now: 2.5e6, Avg30: 2.5e6, Avg60: 2.0e6, P90_60: 2.5e6, Slope120: 5046}}
	s := SystemState{RepUP: 3, ReadyUP: 3, WorkerCount: 2, ReadyWorkers: 2, VyosCount: 1, VyosAdmitted: 1,
		OfferedPPS: 1.25e6, UECount: 10}
	cfg := DefaultCfg()
	v.Tick(f, s, cfg)
	if !v.Last.Valid {
		t.Fatal("tick did not plan")
	}
	if v.Last.In.Slope != 0 {
		t.Fatalf("first positive-slope tick must not extrapolate: In.Slope=%.0f", v.Last.In.Slope)
	}
	if hasAct(v.Last.Best.Moves, ActScaleOutUP) {
		t.Fatalf("10 UE + one batch fits 3 slots; a one-tick step must not add the 4th: %s", v.Last.Best.Key)
	}
	for i := 0; i < 2; i++ {
		v.Tick(f, s, cfg)
		if v.Last.In.Slope != 0 || hasAct(v.Last.Best.Moves, ActScaleOutUP) {
			t.Fatalf("tick %d of a 60 s bump must not extrapolate yet: In.Slope=%.0f %s", i+2, v.Last.In.Slope, v.Last.Best.Key)
		}
	}
	v.Tick(f, s, cfg)
	if v.Last.In.Slope <= 0 {
		t.Fatalf("fourth consecutive positive-slope tick (one batch interval) is a confirmed ramp: In.Slope=%.0f", v.Last.In.Slope)
	}
}
