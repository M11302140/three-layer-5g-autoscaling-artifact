package hbo

import (
	"testing"
	"time"
)

func r7History(now time.Time) []offSample {
	pts := []struct {
		ago float64
		v   float64
	}{
		{330, 6.40e6}, {300, 6.87e6}, {270, 7.77e6},
		{240, 7.22e6}, {210, 7.22e6}, {180, 7.23e6},
		{150, 7.77e6}, // 09:15:38
		{120, 8.11e6}, // 09:16:08
		{90, 6.97e6}, {60, 6.97e6}, {30, 6.59e6},
		{0, 6.56e6},
	}
	out := make([]offSample, 0, len(pts))
	for _, p := range pts {
		out = append(out, offSample{T: now.Add(-time.Duration(p.ago * float64(time.Second))), V: p.v})
	}
	return out
}

func TestIrreversibilityWindowIncludesScaleInLead(t *testing.T) {
	cal := calibV2()
	s := SystemState{RepUP: 8, WorkerCount: 4, VyosCount: 2}
	if w := irreversibilityWindow(ActScaleInUP, s, &cal); w != v6TH {
		t.Fatalf("ScaleInUP window=%v want max(T_in+T_out=135, T_H=300)=300", w)
	}
	if w := irreversibilityWindow(ActDeleteVyOS, s, &cal); w != cal.Act[ActDeployVyOS].TReadySec {
		t.Fatalf("DeleteVyOS window=%v want T_deploy=%v", w, cal.Act[ActDeployVyOS].TReadySec)
	}
	if w := irreversibilityWindow(ActDeleteWorker, s, &cal); w != 60+100+15 {
		t.Fatalf("DeleteWorker window=%v want 175", w)
	}
	s2 := SystemState{RepUP: 8, WorkerCount: 2}
	if w := irreversibilityWindow(ActScaleInUP, s2, &cal); w != v6TH {
		t.Fatalf("ScaleInUP window (no free slot)=%v want max(235, T_H=300)=300", w)
	}
	t.Setenv("V6_UP_SCALEIN_HOLD_S", "0")
	if w := irreversibilityWindow(ActScaleInUP, s2, &cal); w != 120+15+100 {
		t.Fatalf("hold off: ScaleInUP window (no free slot)=%v want 235", w)
	}
}

func TestIrreversibilityHoldR7Replay(t *testing.T) {
	sh := NewV6Shadow(testLogger())
	sh.calib = calibV2()
	base := calibV2()
	cal := PlanCalib(&base, params())
	s := SystemState{RepUP: 8, WorkerCount: 4, VyosCount: 2}
	now := time.Now()
	sh.offHist = r7History(now)
	if hold, why := irreversibilityHoldWindow(ActScaleInUP, s, 6.56e6, sh, cal, 15); hold {
		t.Fatalf("old 15s window should have passed (that is the r7 defect): %s", why)
	}
	hold, why := irreversibilityHold(ActScaleInUP, s, 6.56e6, sh, cal)
	if !hold {
		t.Fatalf("r7 09:18:08 tick must hold (peak 8.1M+step within 165s) — got pass")
	}
	t.Log(why)
	sh.offHist = append(r7History(now.Add(-30*time.Second)), offSample{T: now, V: 6.56e6})
	if hold, _ := irreversibilityHold(ActScaleInUP, s, 6.56e6, sh, cal); !hold {
		t.Fatalf("r7 09:18:38 tick must hold (8.11M within 165s)")
	}
}

func TestIrreversibilityHoldTroughStillScalesIn(t *testing.T) {
	sh := NewV6Shadow(testLogger())
	sh.calib = calibV2()
	base := calibV2()
	cal := PlanCalib(&base, params())
	s := SystemState{RepUP: 8, WorkerCount: 4, VyosCount: 2}
	now := time.Now()
	for ago := 600.0; ago >= 0; ago -= 30 {
		sh.offHist = append(sh.offHist, offSample{T: now.Add(-time.Duration(ago * float64(time.Second))), V: 3.0e6})
	}
	if hold, why := irreversibilityHold(ActScaleInUP, s, 3.0e6, sh, cal); hold {
		t.Fatalf("flat trough 3.0M must not hold: %s", why)
	}
}

// ---------------------------------------------------------------------------
// ---------------------------------------------------------------------------

func hist(now time.Time, pts [][2]float64) []offSample {
	out := make([]offSample, 0, len(pts))
	for _, p := range pts {
		out = append(out, offSample{T: now.Add(-time.Duration(p[0] * float64(time.Second))), V: p[1] * 1e6})
	}
	return out
}

func holdFixture() (*V6Shadow, *Calib) {
	sh := NewV6Shadow(testLogger())
	sh.calib = calibV2()
	base := calibV2()
	return sh, PlanCalib(&base, params())
}

func TestHoldR9TroughReleasesAfterOneStep(t *testing.T) {
	sh, cal := holdFixture()
	now := time.Now()
	sh.offHist = hist(now, [][2]float64{
		{600, 1.50}, {570, 1.50}, {540, 1.50}, {510, 1.50}, {480, 1.50}, {450, 1.50}, {420, 1.50}, {390, 1.50},
		{360, 1.50}, {330, 2.41}, {300, 2.41}, {270, 1.50}, {240, 1.80}, {210, 2.10}, {180, 2.10}, {150, 2.11},
		{120, 2.11}, {90, 2.10}, {60, 2.11}, {30, 2.11}, {0, 2.11},
	})
	s := SystemState{RepUP: 4, WorkerCount: 2, VyosCount: 1}
	if hold, why := irreversibilityHold(ActScaleInUP, s, 2.11e6, sh, cal); hold {
		t.Fatalf("r9 19:13:38 4→3 slots must release (7 UE on 3 slots): %s", why)
	}
}

func TestHoldR9PeakEdgeStillHolds(t *testing.T) {
	sh, cal := holdFixture()
	now := time.Now()
	sh.offHist = hist(now, [][2]float64{
		{600, 7.23}, {570, 8.03}, {540, 8.03}, {510, 9.00}, {480, 9.00}, {450, 9.00}, {420, 9.0}, {390, 9.3},
		{360, 9.31}, {330, 6.48}, {300, 9.32}, {270, 9.32}, {240, 9.34}, {210, 9.31}, {180, 9.31}, {150, 9.31},
		{120, 9.28}, {90, 9.28}, {60, 9.31}, {30, 9.26}, {0, 8.72},
	})
	s := SystemState{RepUP: 8, WorkerCount: 4, VyosCount: 3}
	hold, why := irreversibilityHold(ActScaleInUP, s, 8.72e6, sh, cal)
	if !hold {
		t.Fatalf("r9 19:40:38 8→7 slots must hold (9.31M within window)")
	}
	t.Log(why)
}

func TestHoldR9DescentReleases(t *testing.T) {
	sh, cal := holdFixture()
	now := time.Now()
	sh.offHist = hist(now, [][2]float64{
		{630, 6.48}, {600, 9.32}, {570, 9.32}, {540, 9.34}, {510, 9.31}, {480, 9.31}, {450, 9.31}, {420, 9.28},
		{390, 9.28}, {360, 9.31}, {330, 9.26}, {300, 8.72}, {270, 8.41}, {240, 8.74}, {210, 9.11}, {180, 7.52},
		{150, 6.61}, {120, 6.61}, {90, 6.61}, {60, 6.61}, {30, 6.55}, {0, 5.31},
	})
	s := SystemState{RepUP: 8, WorkerCount: 4, VyosCount: 3}
	if hold, why := irreversibilityHoldWindow(ActScaleInUP, s, 5.31e6, sh, cal, 135); hold {
		t.Fatalf("r9 19:45:38 8→7 slots must release (dip left the 10 min memory): %s", why)
	}
}

func TestHoldR9TailReleasesVyos(t *testing.T) {
	sh, cal := holdFixture()
	now := time.Now()
	sh.offHist = hist(now, [][2]float64{
		{600, 6.62}, {570, 6.62}, {540, 6.62}, {510, 6.62}, {480, 6.61}, {450, 5.50}, {420, 4.50}, {390, 4.50},
		{360, 4.50}, {330, 4.49}, {300, 4.49}, {270, 4.49}, {240, 4.50}, {210, 4.50}, {180, 3.90}, {150, 3.90},
		{120, 2.72}, {90, 2.72}, {60, 2.71}, {30, 3.60}, {0, 3.60},
	})
	s := SystemState{RepUP: 6, WorkerCount: 4, VyosCount: 2}
	if hold, why := irreversibilityHold(ActDeleteVyOS, s, 3.60e6, sh, cal); hold {
		t.Fatalf("r9 19:53:08 vyos 2→1 must release (8-12 UE): %s", why)
	}
}

func TestHoldR9EpisodeStartAssumesOneBatch(t *testing.T) {
	sh, cal := holdFixture()
	now := time.Now()
	sh.offHist = hist(now, [][2]float64{{180, 1.50}, {150, 1.50}, {120, 1.50}, {90, 1.50}, {60, 1.50}, {30, 1.50}, {0, 1.50}})
	if hold, why := irreversibilityHold(ActScaleInUP, SystemState{RepUP: 4, WorkerCount: 2, VyosCount: 1}, 1.5e6, sh, cal); hold {
		t.Fatalf("4→3 slots at 5 UE must release: %s", why)
	}
	hold, why := irreversibilityHold(ActScaleInUP, SystemState{RepUP: 3, WorkerCount: 2, VyosCount: 1}, 1.5e6, sh, cal)
	if !hold {
		t.Fatalf("3→2 slots at 5 UE must hold (one more batch of 4 UE would put 5 on a slot)")
	}
	t.Log(why)
}

func TestPlannerR9DipRecoverySlopeDeploysVyosUnbounded(t *testing.T) {
	cfg := V6Config{NUP: 8, NVY: 2, NWK: 4}
	best, _ := DecideV6(input(cfg, 9.34e6, 33830), DefaultCalibPtr(), params())
	if !hasAct(best.Moves, ActDeployVyOS) && !hasAct(best.Rollout, ActDeployVyOS) {
		t.Fatalf("unbounded +33.8k/s slope should reproduce r9's DEPLOY_VYOS, got %s", best.Key)
	}
	best, _ = DecideV6(input(cfg, 9.34e6, 1.2e6/v6TH), DefaultCalibPtr(), params())
	if hasAct(best.Moves, ActDeployVyOS) {
		t.Fatalf("bounded slope (10k/s → +3M at T_H → u_VY 0.95 at 2 vyos) must not deploy, got %s", best.Key)
	}
}

func DefaultCalibPtr() *Calib { c := calibV2(); return &c }

func TestTickBoundsSlopeByObservedRise(t *testing.T) {
	v := NewV6Shadow(testLogger())
	v.calib = calibV2()
	v.Enabled = true
	now := time.Now()
	v.offHist = hist(now, [][2]float64{
		{330, 9.31}, {300, 9.31}, {270, 9.31}, {240, 9.31}, {210, 9.31}, {180, 9.31}, {150, 9.31},
		{120, 9.31}, {90, 6.48}, {60, 9.32}, {30, 9.34},
	})
	f := FeatureSet{PktRateUP: WindowFeature{Now: 9.34e6, Avg30: 9.3e6, Avg60: 9.0e6, P90_60: 9.34e6, Slope120: 33830}}
	s := SystemState{RepUP: 8, ReadyUP: 8, WorkerCount: 4, ReadyWorkers: 4, VyosCount: 2, VyosAdmitted: 2,
		OfferedPPS: 4.67e6, UECount: 31}
	cfg := DefaultCfg()
	v.Tick(f, s, cfg)
	if !v.Last.Valid {
		t.Fatal("tick did not plan")
	}
	if lim := 1.2e6 / v6TH; v.Last.In.Slope > lim+1 {
		t.Fatalf("slope not bounded: got %.0f pps/s, want ≤ %.0f", v.Last.In.Slope, lim)
	}
	if hasAct(v.Last.Best.Moves, ActDeployVyOS) {
		t.Fatalf("bounded tick must not deploy vyos: %s", v.Last.Best.Key)
	}
	v2 := NewV6Shadow(testLogger())
	v2.calib = calibV2()
	v2.Enabled = true
	var ramp [][2]float64
	for ago := 330.0; ago >= 30; ago -= 30 {
		ramp = append(ramp, [2]float64{ago, 2.0 + (330-ago)/30*0.5})
	}
	v2.offHist = hist(now, ramp)
	t.Setenv("V6_SLOPE_CONFIRM_TICKS", "1")
	f2 := FeatureSet{PktRateUP: WindowFeature{Now: 6.5e6, Avg30: 6.3e6, Avg60: 6.0e6, P90_60: 6.5e6, Slope120: 15000}}
	s2 := SystemState{RepUP: 6, ReadyUP: 6, WorkerCount: 3, ReadyWorkers: 3, VyosCount: 2, VyosAdmitted: 2,
		OfferedPPS: 3.25e6, UECount: 22}
	v2.Tick(f2, s2, cfg)
	if v2.Last.In.Slope < 14999 {
		t.Fatalf("genuine ramp slope must pass through, got %.0f", v2.Last.In.Slope)
	}
}

func TestPlannerR10RampStartScalesOutOnRawSlope(t *testing.T) {
	t.Setenv("V6_SLOPE_CONFIRM_TICKS", "1")
	cfg := V6Config{NUP: 3, NVY: 1, NWK: 2}
	best, _ := DecideV6(input(cfg, 3.31e6, 6172), DefaultCalibPtr(), params())
	if !hasAct(best.Moves, ActScaleOutUP) && !hasAct(best.Moves, ActCreateWorker) {
		t.Fatalf("raw regression slope 6172 must scale out at 11 UE on 3 slots (r9 did), got %s", best.Key)
	}
	v := NewV6Shadow(testLogger())
	v.calib = calibV2()
	v.Enabled = true
	now := time.Now()
	v.offHist = hist(now, [][2]float64{{330, 2.10}, {300, 2.10}, {270, 2.10}, {240, 2.10}, {210, 2.10}, {180, 2.10},
		{150, 2.10}, {120, 2.10}, {90, 2.63}, {60, 2.63}, {30, 3.31}})
	f := FeatureSet{PktRateUP: WindowFeature{Now: 3.31e6, Avg30: 3.3e6, Avg60: 3.0e6, P90_60: 3.31e6, Slope120: 6172}}
	s := SystemState{RepUP: 3, ReadyUP: 3, WorkerCount: 2, ReadyWorkers: 2, VyosCount: 1, VyosAdmitted: 1,
		OfferedPPS: 1.655e6, UECount: 11}
	c := DefaultCfg()
	v.Tick(f, s, c)
	if v.Last.In.Slope < 6171 {
		t.Fatalf("ramp-start slope must pass unbounded, got %.0f", v.Last.In.Slope)
	}
	if !hasAct(v.Last.Best.Moves, ActScaleOutUP) && !hasAct(v.Last.Best.Moves, ActCreateWorker) {
		t.Fatalf("tick at ramp start must scale out, got %s", v.Last.Best.Key)
	}
}

func TestMaxNewHighRiseIgnoresDipRecovery(t *testing.T) {
	v := NewV6Shadow(testLogger())
	v.calib = calibV2()
	now := time.Now()
	v.offHist = hist(now, [][2]float64{{150, 9.31}, {120, 9.31}, {90, 6.48}, {60, 9.32}, {30, 9.34}, {0, 9.31}})
	if r := v.MaxNewHighRise(120*time.Second, riseMemory); r > 0.05e6 {
		t.Fatalf("dip recovery must not count as new-high rise, got %.2fM", r/1e6)
	}
	if r := v.MaxRiseOver(120*time.Second, riseMemory); r < 2.8e6 {
		t.Fatalf("plain rise must still see the recovery (hold uses it), got %.2fM", r/1e6)
	}
	v.offHist = hist(now, [][2]float64{{150, 2.10}, {120, 2.10}, {90, 2.63}, {60, 2.63}, {30, 3.31}, {0, 3.31}})
	if r := v.MaxNewHighRise(120*time.Second, riseMemory); r < 1.2e6 {
		t.Fatalf("staircase must count each new high, got %.2fM", r/1e6)
	}
}

func TestHoldAccountsForInFlightSlotDrain(t *testing.T) {
	sh, cal := holdFixture()
	now := time.Now()
	sh.offHist = hist(now, [][2]float64{{240, 2.25}, {210, 2.25}, {180, 2.25}, {150, 2.25}, {120, 2.25}, {90, 2.25}, {60, 2.25}, {30, 2.25}, {0, 2.25}})
	s := SystemState{RepUP: 4, WorkerCount: 2, VyosCount: 2}
	if hold, why := irreversibilityHold(ActScaleInUP, s, 2.25e6, sh, cal); hold {
		t.Fatalf("first drain 4→3 at 9 UE must be allowed: %s", why)
	}
	sh.NoteDispatched(ActScaleInUP)
	hold, why := irreversibilityHold(ActScaleInUP, s, 2.25e6, sh, cal)
	if !hold {
		t.Fatalf("second drain while one is in flight (→2 slots for 9+4 UE) must hold")
	}
	t.Log(why)
}

func TestPlateauAfterVyosDeleteDoesNotRedeploy(t *testing.T) {
	v := NewV6Shadow(testLogger())
	v.calib = calibV2()
	now := time.Now()
	var pts [][2]float64
	for ago := 600.0; ago >= 0; ago -= 30 {
		pts = append(pts, [2]float64{ago, 4.75})
	}
	pts[len(pts)-3][1] = 4.2
	v.offHist = hist(now, pts)
	f := FeatureSet{PktRateUP: WindowFeature{Now: 4.75e6, Avg30: 4.7e6, Avg60: 4.6e6, P90_60: 4.75e6, Slope120: 9000}}
	s := SystemState{RepUP: 5, ReadyUP: 5, WorkerCount: 3, ReadyWorkers: 3, VyosCount: 2, VyosAdmitted: 2,
		OfferedPPS: 2.375e6, UECount: 19}
	c := DefaultCfg()
	v.Tick(f, s, c)
	if v.Last.In.Slope > 1.2e6/v6TH+1 {
		t.Fatalf("plateau slope must be floored at one batch per horizon, got %.0f", v.Last.In.Slope)
	}
	if hasAct(v.Last.Best.Moves, ActDeployVyOS) {
		t.Fatalf("plateau at 2 vyos (u 0.95 with one batch) must not redeploy: %s", v.Last.Best.Key)
	}
}

func TestPlateauDeploysSecondVyosAhead(t *testing.T) {
	c := DefaultCalib()
	cfg := V6Config{NUP: 3, NVY: 1, NWK: 2}
	plateau := 2.8e6
	in := input(cfg, plateau, 0)
	in.Bounds = V6Bounds{MinUP: 1, MaxUP: 8, MinVY: 1, MaxVY: 3, MinWK: 1, MaxWK: 4}
	best, _ := DecideV6(in, &c, DefaultV6Params())
	plan := append(append([]Move{}, best.Moves...), best.Rollout...)
	if !hasAct(plan, ActDeployVyOS) {
		t.Fatalf("plateau on 1 vyos must deploy the 2nd vyos ahead (2 batches within 140 s), got %s", best.Key)
	}
	for _, m := range plan {
		if m.Act == ActDeployVyOS && m.TEffect > 150 {
			t.Fatalf("2nd vyos must land before the 2nd batch (150 s), plan lands at %.0f s", m.TEffect)
		}
	}
	cfg2 := V6Config{NUP: 4, NVY: 2, NWK: 2}
	in2 := input(cfg2, plateau, 0)
	in2.Bounds = in.Bounds
	best2, _ := DecideV6(in2, &c, DefaultV6Params())
	if hasAct(best2.Moves, ActDeployVyOS) {
		t.Fatalf("2 vyos at 8 UE must not deploy a third: %s", best2.Key)
	}
}

func TestSlotWindowShortWhenFreeSlotExists(t *testing.T) {
	cal := DefaultCalib()
	if w := irreversibilityWindow(ActScaleInUP, SystemState{RepUP: 3, WorkerCount: 2}, &cal); w != v6TH {
		t.Fatalf("free slot exists → window must be T_H=300 under p5u, got %v", w)
	}
	t.Setenv("V6_UP_SCALEIN_HOLD_S", "0")
	if w := irreversibilityWindow(ActScaleInUP, SystemState{RepUP: 3, WorkerCount: 2}, &cal); w != 15 {
		t.Fatalf("hold off: free slot exists → window must be T_out=15, got %v", w)
	}
	if w := irreversibilityWindow(ActScaleInUP, SystemState{RepUP: 4, WorkerCount: 2}, &cal); w != 120+15 {
		t.Fatalf("hold off: all slots active on 2 workers → drain+out, got %v", w)
	}
}

func TestRecentlyDispatchedTracksInflightAndRecent(t *testing.T) {
	v := NewV6Shadow(testLogger())
	v.calib = calibV2()
	if v.RecentlyDispatched(ActDeleteVyOS, time.Minute) {
		t.Fatal("empty shadow must report nothing recent")
	}
	v.NoteDispatched(ActDeleteVyOS)
	if !v.RecentlyDispatched(ActDeleteVyOS, time.Minute) {
		t.Fatal("just-dispatched DeleteVyOS must be recent (in-flight)")
	}
	if v.RecentlyDispatched(ActDeployVyOS, time.Minute) {
		t.Fatal("DeployVyOS was never dispatched")
	}
}
