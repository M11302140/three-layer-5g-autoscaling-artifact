package hbo

import (
	"encoding/json"
	"math"
	"os"
	"testing"
	"time"
)

func mustRise(t *testing.T, eps float64) *RiseModel {
	t.Helper()
	rp, err := LoadRisePrior()
	if err != nil {
		t.Fatal(err)
	}
	return NewRiseModel(rp, eps, 250000)
}

func TestRiseMarginMatchesReference(t *testing.T) {
	raw, err := os.ReadFile("testdata/rise_expect.json")
	if err != nil {
		t.Fatal(err)
	}
	var exp []struct {
		H        float64 `json:"h"`
		Eps      float64 `json:"eps"`
		LevelUE  float64 `json:"level_ue"`
		MarginUE float64 `json:"margin_ue"`
	}
	if err := json.Unmarshal(raw, &exp); err != nil {
		t.Fatal(err)
	}
	if len(exp) == 0 {
		t.Fatal("no reference values")
	}
	for _, e := range exp {
		r := mustRise(t, e.Eps)
		got := r.Margin(e.H, e.LevelUE*250000) / 250000
		if math.Abs(got-e.MarginUE) > 1e-6 {
			t.Fatalf("h=%.0f eps=%.2f level=%.0f UE: margin %.4f UE, reference %.4f", e.H, e.Eps, e.LevelUE, got, e.MarginUE)
		}
	}
}

func TestRiseMarginMonotone(t *testing.T) {
	lvl := 20 * 250000.0
	prev := -1.0
	r := mustRise(t, 0.05)
	for h := 15.0; h <= 330; h += 15 {
		m := r.Margin(h, lvl)
		if m+1e-9 < prev {
			t.Fatalf("margin not monotone in horizon: h=%.0f m=%.0f prev=%.0f", h, m, prev)
		}
		prev = m
	}
	prev = -1
	for _, e := range []float64{0.2, 0.1, 0.05, 0.02, 0.01} {
		m := mustRise(t, e).Margin(120, lvl)
		if m+1e-9 < prev {
			t.Fatalf("margin not monotone in eps: eps=%.2f m=%.0f prev=%.0f", e, m, prev)
		}
		prev = m
	}
}

func TestRiseACI(t *testing.T) {
	t.Setenv("V6_RISE_WARM_S", "0")
	r := mustRise(t, 0.1)
	t0 := time.Date(2026, 9, 29, 0, 0, 0, 0, time.UTC)
	r.ResetEpisode(t0)
	off := 20 * 250000.0
	m0 := r.Margin(45, off)
	for i := 1; i <= 12; i++ {
		off += 8 * 250000
		r.Observe(t0.Add(time.Duration(i*30)*time.Second), off, nil)
	}
	c := r.Coverage()["45"]
	if c.Miss == 0 || c.Alpha >= 0.1 {
		t.Fatalf("ramp must register misses and lower alpha: %+v", c)
	}
	if m1 := r.Margin(45, 20*250000.0); m1 < m0 {
		t.Fatalf("margin must not shrink after misses: %.0f → %.0f", m0, m1)
	}
	for i := 13; i <= 132; i++ {
		r.Observe(t0.Add(time.Duration(i*30)*time.Second), off, nil)
	}
	c2 := r.Coverage()["45"]
	if c2.Alpha <= c.Alpha || c2.Alpha > 0.1+1e-9 {
		t.Fatalf("alpha must recover on a plateau but never exceed eps (one-sided): %.3f → %.3f", c.Alpha, c2.Alpha)
	}
	if m := r.Margin(45, 20*250000.0); m+1e-6 < mustRise(t, 0.1).Margin(45, 20*250000.0) {
		t.Fatalf("one-sided ACI: margin %.0f fell below the prior quantile", m)
	}
}

func TestRiseWarmGuard(t *testing.T) {
	r := mustRise(t, 0.05)
	t0 := time.Date(2026, 9, 29, 0, 0, 0, 0, time.UTC)
	r.ResetEpisode(t0)
	r.Observe(t0.Add(30*time.Second), 0.1e6, nil)
	r.Observe(t0.Add(60*time.Second), 5e6, nil)
	r.Observe(t0.Add(90*time.Second), 5e6, nil)
	for _, c := range r.Coverage() {
		if c.N != 0 {
			t.Fatalf("no realization expected inside the warm window: %+v", c)
		}
	}
	for i := 4; i <= 20; i++ {
		r.Observe(t0.Add(time.Duration(i*30)*time.Second), 5e6, nil)
	}
	if c := r.Coverage()["45"]; c.N == 0 || c.Miss != 0 {
		t.Fatalf("plateau after warm-up must realize with zero misses: %+v", c)
	}
}
