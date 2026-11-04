package actuate

import "testing"

// v6.0.56:survivor-first packing — victims go to the earliest survivor with room,
// never to the emptiest (= next victim) slot.
func TestPlanScaleInPacksSurvivorsFirst(t *testing.T) {
	ues := map[int]ueInfo{}
	for i := 0; i < 5; i++ {
		ues[i] = ueInfo{Dnn: "internet"}
	}
	for i := 5; i < 8; i++ {
		ues[i] = ueInfo{Dnn: "internet4"}
	}
	ues[20] = ueInfo{Dnn: "internet8"}
	ues[21] = ueInfo{Dnn: "internet8"}
	ues[22] = ueInfo{Dnn: "internet8"}
	rem := []string{"internet", "internet4", "internet2"}
	mv := planScaleInCap(ues, rem, "internet8", 5)
	if len(mv) != 3 {
		t.Fatalf("moves=%v", mv)
	}
	want := []string{"internet4", "internet4", "internet2"} // internet at cap, internet4 3→5, then internet2
	for i, m := range mv {
		if m.Dnn != want[i] {
			t.Fatalf("move %d: got %s want %s (all=%v)", i, m.Dnn, want[i], mv)
		}
	}
	old := planScaleInCap(ues, rem, "internet8", 0)
	if old[0].Dnn != "internet2" {
		t.Fatalf("cap=0 must keep least-loaded: %v", old)
	}
}
