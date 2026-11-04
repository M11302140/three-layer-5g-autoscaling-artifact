package hbo

import "testing"

func TestRecentKeepCoversReverseGuard(t *testing.T) {
	cal := DefaultCalib()
	if need := cal.Act[ActDeployVyOS].TReadySec + cal.Act[ActDeleteVyOS].TReadySec + v6Grid; recentKeepSecScaleIn(&cal, ActDeleteVyOS) < need {
		t.Fatalf("DeleteVyOS keep=%v < %v", recentKeepSecScaleIn(&cal, ActDeleteVyOS), need)
	}
	if w := recentKeepSecScaleIn(&cal, ActScaleInUP); w < cal.Act[ActScaleOutUP].TReadySec+cal.Act[ActScaleInUP].TReadySec {
		t.Fatalf("ScaleInUP keep=%v too short", w)
	}
	if w := recentKeepSecScaleIn(&cal, ActDeployVyOS); w != 0 {
		t.Fatalf("scale-out must be untouched, got %v", w)
	}
}
