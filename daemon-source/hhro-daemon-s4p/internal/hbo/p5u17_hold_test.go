package hbo

import (
	"strings"
	"testing"
	"time"
)

func prodHoldFixture() (*V6Shadow, *Calib) {
	sh := NewV6Shadow(testLogger())
	sh.calib = DefaultCalib()
	sh.episodeStart = time.Now().Add(-30 * time.Minute)
	base := DefaultCalib()
	return sh, PlanCalib(&base, V6Params{Lambda: 0.002, MarginM: 0.93, SlopeMax: 0.05, UMin: 0})
}

func TestHoldRiseFollowsConfirmedSlopeNotMemory(t *testing.T) {
	sh, cal := prodHoldFixture()
	now := time.Now()
	var pts [][2]float64
	for ago := 660.0; ago > 360; ago -= 30 {
		pts = append(pts, [2]float64{ago, 9.75})
	}
	for ago := 360.0; ago > 180; ago -= 30 {
		pts = append(pts, [2]float64{ago, 7.0})
	}
	for ago := 180.0; ago >= 30; ago -= 30 {
		pts = append(pts, [2]float64{ago, 4.72})
	}
	sh.offHist = hist(now, pts)
	s := SystemState{RepUP: 8, WorkerCount: 4, VyosCount: 2}
	if hold, why := irreversibilityHoldWindow(ActScaleInUP, s, 4.72e6, sh, cal, 300); hold {
		t.Fatalf("falling load: the old ramp's rise memory must not hold 8 slots: %s", why)
	}
	sh.Last.Valid = true
	sh.Last.In.Slope = 8000
	if hold, _ := irreversibilityHoldWindow(ActScaleInUP, s, 4.72e6, sh, cal, 300); !hold {
		t.Fatal("confirmed positive slope must keep the capacity (rise = slope projection)")
	}
}

func TestAdaptiveHoldWindowOnMonotoneRampDown(t *testing.T) {
	t.Setenv("V6_UP_HOLD_ADAPTIVE", "true")
	sh, cal := prodHoldFixture()
	now := time.Now()
	var pts [][2]float64
	for ago := 660.0; ago > 300; ago -= 30 {
		pts = append(pts, [2]float64{ago, 3.75})
	}
	for ago := 300.0; ago > 120; ago -= 30 {
		pts = append(pts, [2]float64{ago, 3.25})
	}
	for ago := 120.0; ago >= 30; ago -= 30 {
		pts = append(pts, [2]float64{ago, 2.5})
	}
	sh.offHist = hist(now, pts)
	s := SystemState{RepUP: 4, WorkerCount: 4, VyosCount: 1}
	if w := holdWindowFor(ActScaleInUP, s, sh, cal); w != 120 {
		t.Fatalf("monotone ramp-down: window must shrink to one batch interval, got %.0f", w)
	}
	if hold, why := irreversibilityHold(ActScaleInUP, s, 2.5e6, sh, cal); hold {
		t.Fatalf("10 UE for 120 s on a clean ramp-down: 4→3 must be allowed: %s", why)
	}
	var pts2 [][2]float64
	for ago := 660.0; ago > 150; ago -= 30 {
		pts2 = append(pts2, [2]float64{ago, 4.75})
	}
	for ago := 150.0; ago > 60; ago -= 30 {
		pts2 = append(pts2, [2]float64{ago, 5.25})
	}
	for ago := 60.0; ago >= 30; ago -= 30 {
		pts2 = append(pts2, [2]float64{ago, 4.75})
	}
	sh.offHist = hist(now, pts2)
	s2 := SystemState{RepUP: 6, WorkerCount: 4, VyosCount: 2}
	if w := holdWindowFor(ActScaleInUP, s2, sh, cal); w != 300 {
		t.Fatalf("rebound inside the window: keep the 300 s window, got %.0f", w)
	}
	if hold, why := irreversibilityHold(ActScaleInUP, s2, 4.75e6, sh, cal); !hold || !strings.Contains(why, "peak") {
		t.Fatalf("21 UE within 300 s must hold 6→5 (no 6→5→6 flap): hold=%v %s", hold, why)
	}
}

func TestOfferedNonIncreasingFor(t *testing.T) {
	sh, _ := prodHoldFixture()
	now := time.Now()
	sh.offHist = hist(now, [][2]float64{{400, 5}, {300, 5}, {200, 4.9}, {100, 4.85}, {30, 4.8}})
	if !sh.OfferedNonIncreasingFor(300*time.Second, 62500) {
		t.Fatal("monotone within tolerance must be true")
	}
	sh.offHist = hist(now, [][2]float64{{400, 5}, {300, 5}, {200, 4.9}, {100, 5.2}, {30, 4.8}})
	if sh.OfferedNonIncreasingFor(300*time.Second, 62500) {
		t.Fatal("a +0.3M rebound inside the window must be false")
	}
	sh.offHist = hist(now, [][2]float64{{100, 5}, {30, 4.8}})
	if sh.OfferedNonIncreasingFor(300*time.Second, 62500) {
		t.Fatal("window not covered by history must be false")
	}
}

func TestHoldWindowDefaultStays300(t *testing.T) {
	sh, cal := prodHoldFixture()
	now := time.Now()
	var pts [][2]float64
	for ago := 660.0; ago >= 30; ago -= 30 {
		pts = append(pts, [2]float64{ago, 4.75})
	}
	sh.offHist = hist(now, pts)
	if w := holdWindowFor(ActScaleInUP, SystemState{RepUP: 6, WorkerCount: 3, VyosCount: 2}, sh, cal); w != 300 {
		t.Fatalf("default window must stay 300 s even on a monotone past, got %.0f", w)
	}
}
