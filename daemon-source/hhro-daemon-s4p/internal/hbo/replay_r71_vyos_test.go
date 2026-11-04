package hbo

import (
	"strings"
	"fmt"
	"testing"
	"time"
)

func TestReplayVyosKnife(t *testing.T) {
	c := DefaultCalib()
	p := V6Params{Lambda: 0.002, MarginM: 0.93, SlopeMax: 0.05, UMin: 0}
	b := V6Bounds{MinUP: 1, MaxUP: 8, MinVY: 1, MaxVY: 3, MinWK: 1, MaxWK: 4}
	for _, tc := range []struct {
		name          string
		nup, nvy, nwk int
		off, slope    float64
	}{
		{"r71p5u3 min5.8 28.2UE", 7, 2, 4, 7.05e6, 343},
		{"r70 min4.8 28.0UE", 8, 2, 4, 7009216, 0},
		{"r70 min5.3 28.0UE nup8", 8, 2, 4, 7.0e6, 0},
		{"28.0UE nup7", 7, 2, 4, 7.0e6, 0},
		{"28.2UE nup8", 8, 2, 4, 7.05e6, 0},
		{"r72 min8.0 9UE slope7556", 3, 1, 2, 9.02 * 2.5e5, 7556},
		{"r72 min8.0 9UE slope0", 3, 1, 2, 9.02 * 2.5e5, 0},
	} {
		in := input(V6Config{NUP: tc.nup, NVY: tc.nvy, NWK: tc.nwk}, tc.off, tc.slope)
		in.Bounds = b
		best, all := DecideV6(in, &c, p)
		s := ""
		for tt := 0.0; tt < v6TH; tt += v6Grid {
			off := offeredAt(in, p, &c, tt)
			uvy := off / (float64(tc.nvy) * c.CapVY)
			s += fmt.Sprintf(" t%.0f:%.1fUE/u%.2f", tt, off/2.5e5, uvy)
		}
		t.Logf("%-28s -> %-26s J=%.2f noopJ=%.2f |%s", tc.name, best.Key, best.J, noopJ(all), s)
		switch tc.name {
		case "r71p5u3 min5.8 28.2UE", "28.2UE nup8":
			if hasAct(best.Moves, ActDeployVyOS) {
				t.Fatalf("p5u4: 28.2 UE quantizes to 28 → 33 UE on 2 VyOS must not deploy: %q", best.Key)
			}
		}
	}
}

func TestVyosDeploysAt29UE(t *testing.T) {
	c := DefaultCalib()
	p := V6Params{Lambda: 0.002, MarginM: 0.93, SlopeMax: 0.05, UMin: 0}
	in := input(V6Config{NUP: 7, NVY: 2, NWK: 4}, 29 * 2.5e5, 0)
	in.Bounds = V6Bounds{MinUP: 1, MaxUP: 8, MinVY: 1, MaxVY: 3, MinWK: 1, MaxWK: 4}
	best, _ := DecideV6(in, &c, p)
	if !hasAct(best.Moves, ActDeployVyOS) {
		t.Fatalf("29 UE + 1 batch = 34 > 33.1 must deploy the 3rd VyOS: %q", best.Key)
	}
}

// r72 (trace 1) min8.0: 6,6,10(30 s blip),6,6,9,9 → the 9 is not a new high → rise 0.
// r10 ramp: 9,9,9,14 → rise 5 (current window vs running max before it).
func TestNewHighRiseNowIgnoresOldBlip(t *testing.T) {
	sh, _ := holdFixture()
	now := time.Now()
	sh.offHist = hist(now, [][2]float64{{240, 1.5}, {210, 1.5}, {180, 2.5}, {150, 1.5}, {120, 1.5}, {90, 1.5}, {60, 2.25}, {30, 2.25}, {0, 2.25}})
	if r := sh.newHighRiseNow(120*time.Second, 10*time.Minute); r != 0 {
		t.Fatalf("recovery to below the old blip peak must give rise 0, got %.2f", r/1e6)
	}
	sh.offHist = hist(now, [][2]float64{{240, 2.25}, {210, 2.25}, {180, 2.25}, {150, 2.25}, {120, 2.25}, {90, 2.25}, {60, 3.5}, {30, 3.5}, {0, 3.5}})
	if r := sh.newHighRiseNow(120*time.Second, 10*time.Minute); r < 1.2e6 {
		t.Fatalf("ramp step 9→14 UE must give rise ≈1.25M, got %.2f", r/1e6)
	}
}

func TestSlotLayerChangedWithin(t *testing.T) {
	v := NewV6Shadow(testLogger())
	if v.SlotLayerChangedWithin(300 * time.Second) {
		t.Fatal("fresh shadow must report no slot change")
	}
	v.NoteDispatched(ActScaleInUP)
	if !v.SlotLayerChangedWithin(300 * time.Second) {
		t.Fatal("slot scale-in just dispatched must be reported")
	}
	v.lastSlotChange = time.Now().Add(-301 * time.Second)
	if v.SlotLayerChangedWithin(300 * time.Second) {
		t.Fatal("301 s old slot change must not be reported")
	}
}

func TestSlotLayerGrewWithin(t *testing.T) {
	v := NewV6Shadow(testLogger())
	v.NoteDispatched(ActScaleInUP)
	if v.SlotLayerGrewWithin(600 * time.Second) {
		t.Fatal("scale-in must not count as growth")
	}
	v.NoteDispatched(ActScaleOutUP)
	if !v.SlotLayerGrewWithin(600 * time.Second) {
		t.Fatal("scale-out just dispatched must count as growth")
	}
}

func TestHoldUntilHistory(t *testing.T) {
	sh, cal := holdFixture()
	sh.episodeStart = time.Now().Add(-60 * time.Second)
	now := time.Now()
	sh.offHist = hist(now, [][2]float64{{30, 0.1}, {0, 0.1}})
	s := SystemState{RepUP: 2, WorkerCount: 1, VyosCount: 1}
	if hold, why := irreversibilityHold(ActScaleInUP, s, 0.1e6, sh, cal); !hold {
		t.Fatalf("p5u9: 60 s into the episode no scale-in may release capacity: %s", why)
	}
	sh.episodeStart = time.Now().Add(-400 * time.Second)
	if _, why := irreversibilityHold(ActScaleInUP, s, 0.1e6, sh, cal); strings.Contains(why, "no history yet") {
		t.Fatalf("p5u9: with a full window of history the history hold must not fire: %s", why)
	}
}
