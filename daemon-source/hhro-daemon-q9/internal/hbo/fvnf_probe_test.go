package hbo

import "testing"

func TestProbeFVNF(t *testing.T) {
	c := DefaultCalib()
	for _, u := range []float64{0.85, 0.90, 0.93, 0.95, 0.97, 0.98, 1.00, 1.02, 1.03, 1.05, 1.07, 1.10} {
		t.Logf("u=%.2f fVNF=%.5f (EpsDesign %.5f) 2VyOS-UE=%.1f", u, fVNF(u, &c), c.EpsDesign, u*2*c.CapVY/2.5e5)
	}
}
