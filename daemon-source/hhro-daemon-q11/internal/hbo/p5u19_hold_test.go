package hbo

import (
	"strings"
	"testing"
	"time"
)

//
func seriesUE(now time.Time, agoStart float64, levels []int) [][2]float64 {
	var pts [][2]float64
	ago := agoStart
	for _, l := range levels {
		pts = append(pts, [2]float64{ago, float64(l) * 0.25})
		ago -= 30
	}
	return pts
}

func TestSustainedPeakForgetsShortEndedExcursion(t *testing.T) {
	sh, cal := prodHoldFixture()
	now := time.Now()
	win, mind := 300*time.Second, 120*time.Second
	levels := []int{23, 23, 23, 23, 23, 23, 21, 21, 21, 21, 21, 21, 19, 19, 19, 19, 19, 19, 19, 21, 21, 21, 21, 19, 19}
	sh.offHist = hist(now, seriesUE(now, 30*float64(len(levels)-1)+30, levels))
	if p := sh.SustainedPeakSince(win, mind, 4.75e6, cal.PerUEBidir); p < 5.2e6 {
		t.Fatalf("rebound ended <120 s ago must still hold the peak at 21 UE, got %.2fM", p/1e6)
	}
	s := SystemState{RepUP: 6, WorkerCount: 3, VyosCount: 2}
	if hold, why := irreversibilityHoldWindow(ActScaleInUP, s, 4.75e6, sh, cal, 300); !hold || !strings.Contains(why, "peak") {
		t.Fatalf("A: must hold 6→5 right after the rebound: hold=%v %s", hold, why)
	}
	levels = append(levels, 19, 19, 19)
	sh.offHist = hist(now, seriesUE(now, 30*float64(len(levels)-1)+30, levels))
	if p := sh.SustainedPeakSince(win, mind, 4.75e6, cal.PerUEBidir); p > 4.8e6 {
		t.Fatalf("2-minute rebound ended 150 s ago must be forgotten, got %.2fM", p/1e6)
	}
	if hold, why := irreversibilityHoldWindow(ActScaleInUP, s, 4.75e6, sh, cal, 300); hold {
		t.Fatalf("B: 19 UE + one batch fits 5 slots, must release: %s", why)
	}
	levels = []int{23, 23, 23, 23, 23, 23, 21, 21, 21, 21, 21, 21, 19, 19, 19, 19, 19, 19}
	sh.offHist = hist(now, seriesUE(now, 30*float64(len(levels)-1)+30, levels))
	if p := sh.SustainedPeakSince(win, mind, 4.75e6, cal.PerUEBidir); p < 5.2e6 {
		t.Fatalf("sustained 21 UE level ended 180 s ago is inside the window: must hold, got %.2fM", p/1e6)
	}
	if p := sh.PeakOfferedSince(win, 4.75e6); p < 5.2e6 {
		t.Fatalf("legacy max peak must still see 21 (sanity), got %.2fM", p/1e6)
	}
}

func TestSustainedPeakFineBucketsExactBatchRebound(t *testing.T) {
	sh, cal := prodHoldFixture()
	now := time.Now()
	win, mind := 300*time.Second, 120*time.Second
	var fine []offSample
	add := func(agoStart, agoEnd float64, ue int) {
		for ago := agoStart; ago >= agoEnd; ago -= 5 {
			fine = append(fine, offSample{T: now.Add(-time.Duration(ago * float64(time.Second))), V: float64(ue) * 250e3})
		}
	}
	add(600, 445, 23)
	add(440, 275, 19)
	add(270, 155, 21)
	add(150, 0, 19)
	sh.offFine = fine
	sh.offHist = nil
	if p := sh.SustainedPeakSince(win, mind, 4.75e6, cal.PerUEBidir); p > 4.8e6 {
		t.Fatalf("one-batch-long rebound in 5 s buckets, ended 155 s ago, must be forgotten: got %.2fM", p/1e6)
	}
	fine = nil
	add(280, 105, 23)
	add(100, 0, 19)
	sh.offFine = fine
	if p := sh.SustainedPeakSince(win, mind, 4.75e6, cal.PerUEBidir); p < 5.7e6 {
		t.Fatalf("3-minute level in 5 s buckets inside the window must hold: got %.2fM", p/1e6)
	}
}
