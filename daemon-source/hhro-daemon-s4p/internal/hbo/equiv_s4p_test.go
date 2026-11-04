package hbo


import (
	"encoding/json"
	"fmt"
	"os"
	"testing"
)

func TestDecisionEquivalenceDumpS4p(t *testing.T) {
	if os.Getenv("EQUIV_S4P") == "" {
		t.Skip("EQUIV_S4P not set")
	}
	grps := []struct {
		name     string
		vm, up   float64
		s4p      bool
	}{{"S4b", 1.83, 2.00, false}, {"S4a", 2.83, 3.08, false}, {"S4p2", 1.5, 1.92, true}, {"S4p05", 2.33, 3.33, true}}
	for i := 1; i <= 12; i++ {
		tn := fmt.Sprintf("t%d", i)
		ue := loadUE(t, "testdata/s4ptraces/"+tn+".json")
		for _, g := range grps {
			for _, sc := range []struct {
				tag   string
				dm    string
				drain float64
				fail  bool
			}{{"exact_d150", "exact", 150, false}, {"pps_d150", "pps", 150, false}, {"exact_d30", "exact", 30, false}, {"exact_d150_fail", "exact", 150, true}} {
				name := fmt.Sprintf("%s_%s_%s", g.name, tn, sc.tag)
				if g.s4p {
					t.Setenv("V6_S4P_INDEP_WK", "true")
					t.Setenv("V6_S4P_R2_W", "1600")
				} else {
					t.Setenv("V6_S4P_INDEP_WK", "false")
					t.Setenv("V6_S4P_R2_W", "")
				}
				r := runDaemonEquiv(t, ue, eqOpts{Name: name, LamVM: g.vm, LamUP: g.up, DModel: sc.dm, DrainSec: sc.drain, FailFirstOut: sc.fail, ExecWorker: false, IdleMinSec: 600, DropInOnOut: true})
				raw, _ := json.Marshal(r)
				if err := os.WriteFile("testdata/equiv_s4p/"+name+".json", raw, 0o644); err != nil {
					t.Fatal(err)
				}
			}
		}
	}
}
