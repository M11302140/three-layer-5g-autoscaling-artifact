package actuate

import "testing"

// r67 warm-in 2026-09-16 00:57: 25 UEs had arrived in 4 min onto the two base
// slots (8 on internet, 8 on internet4, 3 on internet2 fresh); eupf-5
// (internet6) came up → relief moved ALL 8 over-donorMin UEs onto it (cap ~5)
// → 7% sustained loss. The receiver must be capped at recvMax.
func TestPlanReliefCapsReceiver(t *testing.T) {
	ues := map[int]ueInfo{}
	for i := 0; i < 8; i++ {
		ues[i] = ueInfo{Dnn: "internet", AgeS: float64(300 - i)}
	}
	for i := 8; i < 16; i++ {
		ues[i] = ueInfo{Dnn: "internet4", AgeS: float64(300 - i)}
	}
	for i := 16; i < 19; i++ {
		ues[i] = ueInfo{Dnn: "internet2", AgeS: 20} // fresh, not eligible
	}
	moves := planRelief(ues, "internet6", 4, 5)
	if len(moves) != 5 {
		t.Fatalf("receiver cap 5: want 5 moves, got %d %v", len(moves), moves)
	}
	for _, m := range moves {
		if m.Dnn != "internet6" {
			t.Fatalf("bad target %v", m)
		}
	}
	// uncapped legacy behaviour (recvMax 0) still drains every donor to donorMin
	if n := len(planRelief(ues, "internet6", 4, 0)); n != 8 {
		t.Fatalf("recvMax 0 must be uncapped: want 8, got %d", n)
	}
	// UEs already sitting on the receiver count against the cap
	ues[30] = ueInfo{Dnn: "internet6", AgeS: 10}
	ues[31] = ueInfo{Dnn: "internet6", AgeS: 10}
	if n := len(planRelief(ues, "internet6", 4, 5)); n != 3 {
		t.Fatalf("2 already on receiver: want 3 moves, got %d", n)
	}
	// receiver already at cap → no moves at all
	for i := 32; i < 35; i++ {
		ues[i] = ueInfo{Dnn: "internet6", AgeS: 10}
	}
	if n := len(planRelief(ues, "internet6", 4, 5)); n != 0 {
		t.Fatalf("receiver full: want 0 moves, got %d", n)
	}
}
