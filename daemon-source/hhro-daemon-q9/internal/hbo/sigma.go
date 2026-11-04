package hbo

import (
	_ "embed"
	"encoding/json"
	"fmt"
	"math"
	"os"
	"sort"
	"strconv"

	"github.com/anon/hhro-daemon/internal/envcfg"
)

//
//
//

//go:embed prior_sigma.json
var embeddedSigmaPrior []byte

type sigmaTable struct {
	All float64    `json:"all"`
	N   int        `json:"n"`
	B   []*float64 `json:"b"`
}

// SigmaPrior is the rise standard-deviation library (units: library UE; ue_pps converts to pps).
type SigmaPrior struct {
	UEPPS    float64               `json:"ue_pps"`
	BucketUE float64               `json:"bucket_ue"`
	GridSec  float64               `json:"grid_sec"`
	GSec     float64               `json:"g_sec"`
	NTraces  int                   `json:"n_traces"`
	Source   string                `json:"source"`
	Win      map[string]sigmaTable `json:"win"`
	Run      map[string]sigmaTable `json:"run"`
	hs       []float64
}

// LoadSigmaPrior reads V6_SIGMA_PRIOR_PATH if set, else the embedded table.
func LoadSigmaPrior() (*SigmaPrior, error) {
	raw := embeddedSigmaPrior
	if p := envcfg.Get("V6_SIGMA_PRIOR_PATH", ""); p != "" {
		b, err := os.ReadFile(p)
		if err != nil {
			return nil, fmt.Errorf("sigma prior %s: %w", p, err)
		}
		raw = b
	}
	var sp SigmaPrior
	if err := json.Unmarshal(raw, &sp); err != nil {
		return nil, fmt.Errorf("sigma prior parse: %w", err)
	}
	if len(sp.Win) == 0 || len(sp.Run) == 0 || sp.UEPPS <= 0 || sp.BucketUE <= 0 {
		return nil, fmt.Errorf("sigma prior: empty or malformed")
	}
	for k := range sp.Win {
		if f, err := strconv.ParseFloat(k, 64); err == nil {
			sp.hs = append(sp.hs, f)
		}
	}
	sort.Float64s(sp.hs)
	return &sp, nil
}

// gridH: smallest library horizon ≥ h (cap at max).
func (sp *SigmaPrior) gridH(h float64) float64 {
	for _, x := range sp.hs {
		if x >= h-1e-9 {
			return x
		}
	}
	return sp.hs[len(sp.hs)-1]
}

// Sigma returns σ̂ (pps) of the rise over horizon h at offered level (pps).
// kind: "win" (arrival window [H−g, H]) for replenishment, "run" (exposure window (0, W]) for release.
func (sp *SigmaPrior) Sigma(kind string, h, level float64) float64 {
	if sp == nil || h <= 0 {
		return 0
	}
	tab := sp.Win
	if kind == "run" {
		tab = sp.Run
	}
	t, ok := tab[strconv.Itoa(int(sp.gridH(h)))]
	if !ok {
		return 0
	}
	val := func(b int) float64 {
		if b >= 0 && b < len(t.B) && t.B[b] != nil {
			return *t.B[b]
		}
		return t.All
	}
	x := level/(sp.BucketUE*sp.UEPPS) - 0.5
	n := len(t.B)
	var s float64
	switch {
	case n == 0:
		s = t.All
	case x <= 0:
		s = val(0)
	case x >= float64(n-1):
		s = val(n - 1)
	default:
		b0 := int(math.Floor(x))
		fr := x - float64(b0)
		s = (1-fr)*val(b0) + fr*val(b0+1)
	}
	return s * sp.UEPPS
}

var measuredTReady = map[Action]float64{
	ActScaleOutUP: 30, ActScaleInUP: 150, ActDeployVyOS: 150, ActDeleteVyOS: 60, ActCreateWorker: 120, ActDeleteWorker: 90,
}

func sigmaUseMeasured() bool { return envcfg.Bool("V6_TREADY_MEASURED", true) }

// applyMeasuredTReady returns a copy of c with Act TReadySec replaced by the measured p90 values.
func applyMeasuredTReady(c Calib) Calib {
	acts := map[Action]ActionSpec{}
	for a, sp := range c.Act {
		if t, ok := measuredTReady[a]; ok {
			sp.TReadySec = t
		}
		acts[a] = sp
	}
	c.Act = acts
	return c
}

func lamVM() float64 { return envcfg.Float("V6_LAMBDA_VM", 1.42) }
func lamUP() float64 { return envcfg.Float("V6_LAMBDA_UP", 2.25) }

// lamFor: λ by layer of the action.
func lamFor(act Action, lvm, lup float64) float64 {
	if act == ActScaleOutUP || act == ActScaleInUP {
		return lup
	}
	return lvm
}

// sigmaLockSec: post-scale-out reverse lock per layer — inherited v6 hand values (300 s slot / 600 s VM).
func sigmaLockSec(out Action) float64 {
	if out == ActScaleOutUP {
		return envcfg.Float("V6_SIGMA_LOCK_UP_S", v6TH)
	}
	return envcfg.Float("V6_SIGMA_LOCK_VM_S", 2*v6TH)
}

// NewSigmaRiseModel builds a RiseModel in sigma mode. hs maps each scale-out horizon (s) to its λ
// (used only for the coverage diagnostics of Observe); margins are computed from sp directly.
func NewSigmaRiseModel(sp *SigmaPrior, lvm, lup, perUE float64, hs map[float64]float64) *RiseModel {
	r := &RiseModel{
		eps:     0,
		aci:     false,
		lmin:    0,
		grid:    sp.GridSec,
		prior:   map[float64]riseHist{},
		online:  map[float64][]float64{},
		alpha:   map[float64]float64{},
		pend:    map[float64][]risePend{},
		cov:     map[float64]*RiseCov{},
		warmSec: envcfg.Float("V6_RISE_WARM_S", 120),
		minPPS:  envcfg.Float("V6_MEAS_MIN_PPS", 200000),
		sig:     sp,
		lamVM:   lvm,
		lamUP:   lup,
		sigLam:  map[float64]float64{},
	}
	_ = perUE // levels are pps; the library's own ue_pps converts σ
	for h, l := range hs {
		r.hs = append(r.hs, h)
		r.sigLam[h] = l
		r.cov[h] = &RiseCov{}
	}
	sort.Float64s(r.hs)
	return r
}

// SigmaMode reports whether margins come from λ·σ̂ (true) or the quantile model (false).
func (r *RiseModel) SigmaMode() bool { return r != nil && r.sig != nil }

// Lambdas returns (λ_VM, λ_UP) in sigma mode (0,0 otherwise).
func (r *RiseModel) Lambdas() (float64, float64) {
	if !r.SigmaMode() {
		return 0, 0
	}
	return r.lamVM, r.lamUP
}

// MarginFor is the replenishment margin (pps) of the layer of act over horizon h at level.
func (r *RiseModel) MarginFor(act Action, h, level float64) float64 {
	if r == nil || h <= 0 {
		return 0
	}
	if r.sig != nil {
		return lamFor(act, r.lamVM, r.lamUP) * r.sig.Sigma("win", h, level)
	}
	return r.Margin(h, level)
}

// MarginRelease is the release (exposure-window) margin of the layer of act over window w at level.
func (r *RiseModel) MarginRelease(act Action, w, level float64) float64 {
	if r == nil || w <= 0 {
		return 0
	}
	if r.sig != nil {
		return lamFor(act, r.lamVM, r.lamUP) * r.sig.Sigma("run", w, level)
	}
	return r.Margin(w, level)
}
