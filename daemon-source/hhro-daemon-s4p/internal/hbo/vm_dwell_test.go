package hbo

import (
	"testing"
	"time"
)

func TestVmScaleOutDwellBlocksEarlyVyosDelete(t *testing.T) {
	cfg := DefaultCfg()
	f := FeatureSet{PktRateUP: WindowFeature{Now: 6.49e6, Avg30: 6.49e6, Avg60: 6.49e6, P90_60: 6.49e6, Slope120: 0}}
	s := SystemState{RepUP: 7, ReadyUP: 7, WorkerCount: 4, ReadyWorkers: 4, VyosCount: 3, VyosAdmitted: 3,
		OfferedPPS: 3.245e6, UECount: 26}
	mk := func(ago time.Duration) *V6Shadow {
		v := NewV6Shadow(testLogger())
		v.calib = DefaultCalib()
		v.Enabled = true
		now := time.Now()
		var flat [][2]float64
		for a := 600.0; a >= 30; a -= 30 {
			flat = append(flat, [2]float64{a, 6.49})
		}
		v.offHist = hist(now, flat)
		v.recent = []inflightMove{{Act: ActDeployVyOS, T0: now.Add(-ago), Base: V6Config{NUP: 5, NVY: 2, NWK: 4}}}
		return v
	}
	v1 := mk(330 * time.Second)
	v1.Tick(f, s, cfg)
	if !v1.Last.Valid || !v1.Last.In.Blocked[ActDeleteVyOS] {
		t.Fatalf("330 s after DeployVyOS: DELETE_VYOS must still be blocked by the 600 s VM dwell (valid=%v)", v1.Last.Valid)
	}
	v2 := mk(700 * time.Second)
	v2.Tick(f, s, cfg)
	if !v2.Last.Valid || v2.Last.In.Blocked[ActDeleteVyOS] {
		t.Fatalf("700 s after DeployVyOS: dwell must have expired (valid=%v)", v2.Last.Valid)
	}
	v3 := mk(330 * time.Second)
	v3.recent = []inflightMove{{Act: ActScaleOutUP, T0: time.Now().Add(-330 * time.Second), Base: V6Config{NUP: 6, NVY: 3, NWK: 4}}}
	v3.Tick(f, s, cfg)
	if v3.Last.In.Blocked[ActScaleInUP] {
		t.Fatalf("slot layer dwell must stay T_H (300 s)")
	}
}
