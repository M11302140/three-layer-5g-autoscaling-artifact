package hbo

import (
	"encoding/json"
	"os"
	"testing"
)

func TestR2MatchesPython(t *testing.T) {
	raw, err := os.ReadFile("testdata/r2_cases.json")
	if err != nil {
		t.Fatal(err)
	}
	var cases [][5]any
	if err := json.Unmarshal(raw, &cases); err != nil {
		t.Fatal(err)
	}
	bad := 0
	for _, c := range cases {
		D, nu, nw, w, want := c[0].(float64), int(c[1].(float64)), int(c[2].(float64)), c[3].(float64), c[4].(bool)
		if got := r2OK(D, nu, nw, w); got != want {
			bad++
			if bad < 10 {
				t.Errorf("D=%v nUP=%d nWK=%d w=%v: got %v want %v", D, nu, nw, w, got, want)
			}
		}
	}
	t.Logf("%d cases, %d mismatches", len(cases), bad)
}

func TestS4pFlagsDefaultOff(t *testing.T) {
	if s4pIndepWK() {
		t.Fatal("V6_S4P_INDEP_WK default must be false")
	}
	if _, on := s4pR2W(); on {
		t.Fatal("V6_S4P_R2_W default must be off")
	}
}
