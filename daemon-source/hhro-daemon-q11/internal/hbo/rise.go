package hbo

import (
	_ "embed"
	"encoding/json"
	"fmt"
	"math"
	"os"
	"sort"
	"strconv"
	"sync"
	"time"

	"github.com/anon/hhro-daemon/internal/envcfg"
)

//
//

//go:embed prior_rise.json
var embeddedRisePrior []byte

type riseHist struct {
	V []float64 `json:"v"`
	C []float64 `json:"c"`
}

// RisePrior is the offline rise-score library (relative units).
type RisePrior struct {
	LminUE   float64             `json:"lmin_ue"`
	GridSec  float64             `json:"grid_sec"`
	Quant    float64             `json:"quant"`
	NTraces  int                 `json:"n_traces"`
	Source   string              `json:"source"`
	Horizons map[string]riseHist `json:"horizons"`
}

// LoadRisePrior reads V6_PRIOR_PATH if set, else the embedded library.
func LoadRisePrior() (*RisePrior, error) {
	raw := embeddedRisePrior
	if p := envcfg.Get("V6_PRIOR_PATH", ""); p != "" {
		b, err := os.ReadFile(p)
		if err != nil {
			return nil, fmt.Errorf("rise prior %s: %w", p, err)
		}
		raw = b
	}
	var rp RisePrior
	if err := json.Unmarshal(raw, &rp); err != nil {
		return nil, fmt.Errorf("rise prior parse: %w", err)
	}
	if len(rp.Horizons) == 0 || rp.GridSec <= 0 {
		return nil, fmt.Errorf("rise prior: empty or no grid")
	}
	return &rp, nil
}

type risePend struct {
	T      time.Time
	Base   float64 // offered at issue time (pps)
	Margin float64 // margin issued (pps)
}

// RiseCov is the online coverage record of one horizon.
type RiseCov struct {
	N     int     `json:"n"`
	Miss  int     `json:"miss"`
	Alpha float64 `json:"alpha"`
}

// RiseModel is the online quantile model. Safe for concurrent use.
type RiseModel struct {
	mu sync.Mutex

	eps, gamma, amin float64
	aci              bool
	twoSided         bool
	lmin             float64 // pps
	grid             float64 // horizon grid, s
	hs               []float64
	prior            map[float64]riseHist
	online           map[float64][]float64 // sorted relative rises realized online
	alpha            map[float64]float64
	pend             map[float64][]risePend
	cov              map[float64]*RiseCov

	samples []offSample // offered series for realization
	NeedFn  func(x float64) [3]int
	epStart time.Time
	warmSec float64
	minPPS  float64

	sig    *SigmaPrior
	lamVM  float64
	lamUP  float64
	sigLam map[float64]float64
}

// NewRiseModel builds the model. perUE converts the prior's UE floor to pps.
func NewRiseModel(rp *RisePrior, eps, perUE float64) *RiseModel {
	r := &RiseModel{
		eps:      eps,
		gamma:    envcfg.Float("V6_ACI_GAMMA", math.Max(0.005, eps/5)),
		amin:     envcfg.Float("V6_ACI_ALPHA_MIN", eps/2),
		aci:      envcfg.Bool("V6_ACI", true),
		twoSided: envcfg.Bool("V6_ACI_TWO_SIDED", false),
		lmin:     rp.LminUE * perUE,
		grid:     rp.GridSec,
		prior:    map[float64]riseHist{},
		online:   map[float64][]float64{},
		alpha:    map[float64]float64{},
		pend:     map[float64][]risePend{},
		cov:      map[float64]*RiseCov{},
		warmSec:  envcfg.Float("V6_RISE_WARM_S", 120),
		minPPS:   envcfg.Float("V6_MEAS_MIN_PPS", 200000),
	}
	for k, h := range rp.Horizons {
		f, err := strconv.ParseFloat(k, 64)
		if err != nil || len(h.V) == 0 || len(h.V) != len(h.C) {
			continue
		}
		r.hs = append(r.hs, f)
		r.prior[f] = h
		r.alpha[f] = eps
		r.cov[f] = &RiseCov{Alpha: eps}
	}
	sort.Float64s(r.hs)
	return r
}

// Eps returns the target miscoverage.
func (r *RiseModel) Eps() float64 { return r.eps }

// gridH maps an arbitrary horizon to the smallest library horizon ≥ h (cap at max).
func (r *RiseModel) gridH(h float64) float64 {
	if len(r.hs) == 0 {
		return 0
	}
	for _, x := range r.hs {
		if x >= h-1e-9 {
			return x
		}
	}
	return r.hs[len(r.hs)-1]
}

// ResetEpisode drops pending margins, the realization series and the online
// samples, and restores α to ε. Called at autoscale enable / resume: the step
// from idle to the first load is a harness artifact, not workload.
func (r *RiseModel) ResetEpisode(now time.Time) {
	if r == nil {
		return
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	r.epStart = now
	r.samples = nil
	for _, h := range r.hs {
		r.pend[h] = nil
		r.online[h] = nil
		r.alpha[h] = r.eps
		r.cov[h] = &RiseCov{Alpha: r.eps}
	}
}

// quantileLocked returns the (1−a) quantile of prior ∪ online for horizon h (relative units).
func (r *RiseModel) quantileLocked(h, a float64) float64 {
	p := r.prior[h]
	on := r.online[h]
	if len(p.C) == 0 {
		return 0
	}
	n := p.C[len(p.C)-1] + float64(len(on))
	k := math.Ceil((1 - a) * n)
	if k < 1 {
		k = 1
	}
	i, j, cum := 0, 0, 0.0
	last := 0.0
	for i < len(p.V) || j < len(on) {
		takePrior := j >= len(on) || (i < len(p.V) && p.V[i] <= on[j])
		if takePrior {
			prev := 0.0
			if i > 0 {
				prev = p.C[i-1]
			}
			cum += p.C[i] - prev
			last = p.V[i]
			i++
		} else {
			cum++
			last = on[j]
			j++
		}
		if cum >= k {
			return last
		}
	}
	return last
}

// Margin returns the demand margin (pps) to hold for horizon h seconds at the
// given offered level (pps): with probability ≥ 1−ε the offered load stays
// below level+Margin throughout the next h seconds.
func (r *RiseModel) Margin(h, level float64) float64 {
	if r == nil || h <= 0 {
		return 0
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	return r.marginLocked(r.gridH(h), level)
}

func (r *RiseModel) marginLocked(gh, level float64) float64 {
	if gh <= 0 {
		return 0
	}
	if r.sig != nil {
		return r.sigLam[gh] * r.sig.Sigma("win", gh, level)
	}
	a := r.alpha[gh]
	if a < r.amin {
		a = r.amin
	}
	hi := r.eps
	if r.twoSided {
		hi = 1
	}
	if a > hi {
		a = hi
	}
	q := r.quantileLocked(gh, a)
	if q < 0 {
		q = 0
	}
	return q * math.Max(level, r.lmin)
}

// Observe feeds one offered sample (and optional finer samples), realizes the
// margins whose horizon has elapsed (ACI update + online sample), and issues
// the margins of this tick. Call once per decision tick.
func (r *RiseModel) Observe(now time.Time, offered float64, fine []offSample) {
	if r == nil {
		return
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	if r.epStart.IsZero() {
		r.epStart = now
	}
	for _, f := range fine {
		if f.T.After(r.epStart) && !f.T.After(now) {
			r.samples = append(r.samples, f)
		}
	}
	r.samples = append(r.samples, offSample{T: now, V: offered})
	sort.SliceStable(r.samples, func(i, j int) bool { return r.samples[i].T.Before(r.samples[j].T) })
	maxH := r.hs[len(r.hs)-1]
	cut := now.Add(-time.Duration((maxH + 60) * float64(time.Second)))
	for len(r.samples) > 0 && r.samples[0].T.Before(cut) {
		r.samples = r.samples[1:]
	}
	for _, h := range r.hs {
		hd := time.Duration(h * float64(time.Second))
		for len(r.pend[h]) > 0 && !r.pend[h][0].T.Add(hd).After(now) {
			p := r.pend[h][0]
			r.pend[h] = r.pend[h][1:]
			peak := p.Base
			end := p.T.Add(hd)
			ws := p.T
			if r.sig != nil {
				if w := end.Add(-time.Duration(r.sig.GSec * float64(time.Second))); w.After(ws) {
					ws = w
				}
			}
			for _, s := range r.samples {
				if s.T.After(ws) && !s.T.After(end) && s.V > peak {
					peak = s.V
				}
			}
			real := peak - p.Base
			miss := real > p.Margin+1e-6
			if miss && r.NeedFn != nil {
				miss = r.NeedFn(p.Base+real) != r.NeedFn(p.Base+p.Margin)
			}
			c := r.cov[h]
			c.N++
			e := 0.0
			if miss {
				c.Miss++
				e = 1
			}
			if r.aci {
				a := r.alpha[h] + r.gamma*(r.eps-e)
				if !r.twoSided && a > r.eps {
					a = r.eps
				}
				if a > 1 {
					a = 1
				}
				if a < -0.5 {
					a = -0.5
				}
				r.alpha[h] = a
			}
			c.Alpha = r.alpha[h]
			rel := real / math.Max(p.Base, r.lmin)
			on := r.online[h]
			k := sort.SearchFloat64s(on, rel)
			on = append(on, 0)
			copy(on[k+1:], on[k:])
			on[k] = rel
			r.online[h] = on
		}
	}
	if now.Sub(r.epStart).Seconds() < r.warmSec || offered < r.minPPS {
		return
	}
	for _, h := range r.hs {
		r.pend[h] = append(r.pend[h], risePend{T: now, Base: offered, Margin: r.marginLocked(h, offered)})
	}
}

// MarginAt is Margin at an explicit miscoverage level a (no ACI), e.g. the release
// confidence ρ of the economy test.
func (r *RiseModel) MarginAt(h, level, a float64) float64 {
	if r == nil || h <= 0 {
		return 0
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	gh := r.gridH(h)
	if gh <= 0 {
		return 0
	}
	if a < 0.001 {
		a = 0.001
	}
	if a > 1 {
		a = 1
	}
	q := r.quantileLocked(gh, a)
	if q < 0 {
		q = 0
	}
	return q * math.Max(level, r.lmin)
}

// Coverage returns the online coverage record per horizon (diagnostics, /state).
func (r *RiseModel) Coverage() map[string]RiseCov {
	out := map[string]RiseCov{}
	if r == nil {
		return out
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	for _, h := range r.hs {
		out[strconv.Itoa(int(h))] = *r.cov[h]
	}
	return out
}
