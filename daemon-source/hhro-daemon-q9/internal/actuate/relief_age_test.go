package actuate

import "testing"

// r8 2026-09-06 min49: a UE that arrived seconds ago must never be a relief
// victim (its NAS is still busy; cli_move fails; the fallback blacked it out).
func TestPlanReliefSkipsFreshUEs(t *testing.T) {
	ues := map[int]ueInfo{
		1: {Dnn: "internet5", AgeS: 600}, 2: {Dnn: "internet5", AgeS: 500},
		3: {Dnn: "internet5", AgeS: 400}, 4: {Dnn: "internet5", AgeS: 300},
		5: {Dnn: "internet5", AgeS: 5}, // fresh arrival on the hot slot
		6: {Dnn: "internet2", AgeS: 900},
	}
	moves := planRelief(ues, "internet7", 4, 5)
	if len(moves) != 1 {
		t.Fatalf("want 1 move (5 on donor, donorMin 4), got %v", moves)
	}
	if moves[0].UE == 5 {
		t.Fatalf("fresh UE-5 must not be moved: %v", moves)
	}
	// oldest anchor first
	if moves[0].UE != 1 {
		t.Fatalf("expected oldest UE-1 to be relieved, got %v", moves)
	}
	// agent without age_s (0) stays eligible (backward compatible)
	ues[5] = ueInfo{Dnn: "internet5"}
	if !eligibleForMove(ues[5]) {
		t.Fatal("AgeS=0 (old agent) must remain eligible")
	}
}
