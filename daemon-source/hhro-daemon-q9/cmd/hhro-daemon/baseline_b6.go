package main

//

import (
	"context"
	"encoding/json"
	"fmt"
	"math"
	"os"
	"sort"
	"time"

	"github.com/anon/hhro-daemon/internal/envcfg"
	"github.com/anon/hhro-daemon/internal/hbo"
)

type b6MLP struct {
	W1 [][]float64 `json:"W1"`
	B1 []float64   `json:"b1"`
	W2 [][]float64 `json:"W2"`
	B2 []float64   `json:"b2"`
}

type b6Models struct {
	AR   []float64 `json:"ar"`
	Holt []float64 `json:"holt"`
	MLP  *b6MLP    `json:"mlp"`
}

type b6State struct {
	models   b6Models
	names    []string
	hist     []float64
	tick     int
	holtL    float64
	holtT    float64
	holtInit bool
	predLog  map[string]map[[2]int]float64
	lastOut  map[string]time.Time
	lastIn   map[string]time.Time
	chosen   map[string]map[string]int
}

var b6Horizon = map[string]string{"up": "B5_LEAD_TICKS_UP", "vy": "B5_LEAD_TICKS_VY", "wk": "B5_LEAD_TICKS_WK"}
var b6HorizonDef = map[string]int{"up": 2, "vy": 5, "wk": 5}

func loadB6Models(log interface {
	Warn(string, ...any)
	Info(string, ...any)
}) (b6Models, []string) {
	var m b6Models
	var raw []byte
	var err error
	if p := envcfg.Get("B6_MODELS_FILE", ""); p != "" {
		raw, err = os.ReadFile(p)
	} else if s := envcfg.Get("B6_MODELS", ""); s != "" {
		raw = []byte(s)
	} else {
		err = fmt.Errorf("neither B6_MODELS_FILE nor B6_MODELS set")
	}
	if err == nil {
		err = json.Unmarshal(raw, &m)
	}
	names := []string{"holt"}
	if err != nil {
		log.Warn("baseline b6: models not loaded, holt only", "err", err)
		m.Holt = []float64{0.3, 0.05}
		return m, names
	}
	if len(m.Holt) != 2 {
		m.Holt = []float64{0.3, 0.05}
	}
	if len(m.AR) > 0 {
		names = append(names, "ar")
	}
	if m.MLP != nil && len(m.MLP.W1) == 8 && len(m.MLP.B1) == len(m.MLP.W1[0]) && len(m.MLP.W2) == len(m.MLP.B1) && len(m.MLP.B2) == 3 {
		names = append(names, "mlp")
	}
	sort.Strings(names)
	log.Info("baseline b6: models loaded", "forecasters", names, "ar", m.AR, "holt", m.Holt)
	return m, names
}

func (d *Daemon) b6() *b6State {
	b := d.baseline()
	if b.b6 == nil {
		m, names := loadB6Models(d.log)
		b.b6 = &b6State{models: m, names: names, predLog: map[string]map[[2]int]float64{},
			lastOut: map[string]time.Time{}, lastIn: map[string]time.Time{}, chosen: map[string]map[string]int{}}
		for _, n := range names {
			b.b6.predLog[n] = map[[2]int]float64{}
		}
		for _, k := range []string{"up", "vy", "wk"} {
			b.b6.chosen[k] = map[string]int{}
		}
	}
	return b.b6
}

func (s *b6State) fcHolt(h int) float64 { return s.holtL + float64(h)*s.holtT }

func (s *b6State) fcAR(h int) float64 {
	c := s.models.AR
	p := len(c)
	x := append([]float64(nil), s.hist...)
	if len(x) < p+1 {
		return x[len(x)-1]
	}
	for i := 0; i < h; i++ {
		n := len(x)
		var acc float64
		for j := 0; j < p; j++ {
			acc += c[j] * (x[n-1-j] - x[n-2-j])
		}
		x = append(x, x[n-1]+acc)
	}
	return x[len(x)-1]
}

func (s *b6State) fcMLP(h int) float64 {
	m := s.models.MLP
	n := len(s.hist)
	var x [8]float64
	for i := 0; i < 8; i++ {
		j := n - 8 + i
		if j < 0 {
			j = 0
		}
		x[i] = s.hist[j]
	}
	lvl := math.Max(x[7], 1.0)
	var f [8]float64
	for i := range x {
		f[i] = x[i]/lvl - 1.0
	}
	hid := len(m.B1)
	z := make([]float64, hid)
	for k := 0; k < hid; k++ {
		acc := m.B1[k]
		for i := 0; i < 8; i++ {
			acc += f[i] * m.W1[i][k]
		}
		z[k] = math.Tanh(acc)
	}
	var out [3]float64
	for o := 0; o < 3; o++ {
		acc := m.B2[o]
		for k := 0; k < hid; k++ {
			acc += z[k] * m.W2[k][o]
		}
		out[o] = acc
	}
	hs := [3]int{2, 4, 5}
	best := 0
	for i := range hs {
		if abs(hs[i]-h) < abs(hs[best]-h) {
			best = i
		}
	}
	return s.hist[n-1] + out[best]*lvl
}

func abs(a int) int {
	if a < 0 {
		return -a
	}
	return a
}

func (s *b6State) fc(name string, h int) float64 {
	switch name {
	case "ar":
		return s.fcAR(h)
	case "mlp":
		return s.fcMLP(h)
	default:
		return s.fcHolt(h)
	}
}

func (s *b6State) observe(x float64) {
	s.hist = append(s.hist, x)
	if len(s.hist) > 600 {
		s.hist = s.hist[len(s.hist)-600:]
		s.tick = len(s.hist) - 1
		for n := range s.predLog {
			s.predLog[n] = map[[2]int]float64{}
		}
	}
	a, be := s.models.Holt[0], s.models.Holt[1]
	if !s.holtInit {
		s.holtL, s.holtT, s.holtInit = x, 0, true
	} else {
		lp := s.holtL
		s.holtL = a*x + (1-a)*(s.holtL+s.holtT)
		s.holtT = be*(s.holtL-lp) + (1-be)*s.holtT
	}
}

func (s *b6State) selectAndForecast(layer string, h, W int) (string, float64) {
	ti := s.tick
	best, bestErr := "", math.Inf(1)
	for _, n := range s.names {
		var sum float64
		cnt := 0
		for j := max0(ti - W); j < ti; j++ {
			if j >= len(s.hist) {
				break
			}
			p, ok := s.predLog[n][[2]int{j, h}]
			if !ok {
				p = s.hist[j]
			}
			sum += math.Abs(p - s.hist[j])
			cnt++
		}
		e := 0.0
		if cnt > 0 {
			e = sum / float64(cnt)
		}
		if e < bestErr {
			best, bestErr = n, e
		}
	}
	f := s.fc(best, h)
	if f < 0 {
		f = 0
	}
	for _, n := range s.names {
		s.predLog[n][[2]int{ti + h, h}] = s.fc(n, h)
	}
	for _, n := range s.names {
		for k := range s.predLog[n] {
			if k[0] < ti-W-1 {
				delete(s.predLog[n], k)
			}
		}
	}
	s.chosen[layer][best]++
	return best, f
}

func max0(a int) int {
	if a < 0 {
		return 0
	}
	return a
}

func ceilDiv(x, cap float64) int {
	if cap <= 0 {
		return 0
	}
	return int(math.Ceil(x/cap - 1e-9))
}

func clampInt(v, lo, hi int) int {
	if v < lo {
		return lo
	}
	if v > hi {
		return hi
	}
	return v
}

func (d *Daemon) decideB6(ctx context.Context, b *baselineState, s hbo.SystemState, now time.Time, total int, per map[int]int, active []int) []hbo.Decision {
	st := d.b6()
	x := float64(total)
	st.observe(x)
	W := envcfg.Int("B6_BACKTEST_W", 10)
	uDef := envcfg.Float("B6_U", 0.93)
	u := map[string]float64{"up": envcfg.Float("B6_U_UP", uDef), "vy": envcfg.Float("B6_U_VY", uDef), "wk": envcfg.Float("B6_U_WK", uDef)}
	capVY := envcfg.Float("B6_CAP_VY_SESS", 17.8)
	capUP := envcfg.Float("B6_CAP_UP_SESS", 5.0)
	spw := envcfg.Int("B6_SLOTS_PER_WORKER", 2)
	n0, kMax := envcfg.Int("DASA_N0", 1), envcfg.Int("DASA_K_MAX", 2)
	upMin, upMax := envcfg.Int("HPA_MIN", 2), envcfg.Int("HPA_MAX", 8)
	wkMin, wkMax := envcfg.Int("MIN_WORKERS", 1), envcfg.Int("MAX_WORKERS", 4)
	dwellUP := envcfg.Dur("B6_DWELL_UP", 300*time.Second)
	dwellVM := envcfg.Dur("B6_DWELL_VM", 600*time.Second)

	needVY := func(v float64) int { return clampInt(ceilDiv(v, capVY*u["vy"]), n0, n0+kMax) }
	needUP := func(v float64) int { return clampInt(ceilDiv(v, capUP*u["up"]), upMin, upMax) }
	needWK := func(v float64) int { return clampInt(ceilDiv(float64(ceilDiv(v, capUP*u["wk"])), float64(spw)), wkMin, wkMax) }

	j0 := max0(st.tick - W)
	winMax := 0.0
	for j := j0; j <= st.tick && j < len(st.hist); j++ {
		winMax = math.Max(winMax, st.hist[j])
	}
	fc := map[string]float64{}
	who := map[string]string{}
	for _, k := range []string{"up", "vy", "wk"} {
		h := envcfg.Int(b6Horizon[k], b6HorizonDef[k])
		who[k], fc[k] = st.selectAndForecast(k, h, W)
	}
	st.tick++
	d.log.Info("baseline b6", "sessions", total, "per", fmt.Sprintf("%v", per), "winmax", winMax,
		"f_up", fmt.Sprintf("%.1f/%s", fc["up"], who["up"]), "f_vy", fmt.Sprintf("%.1f/%s", fc["vy"], who["vy"]), "f_wk", fmt.Sprintf("%.1f/%s", fc["wk"], who["wk"]),
		"holt", fmt.Sprintf("L=%.1f T=%.2f", st.holtL, st.holtT), "chosen_up", fmt.Sprintf("%v", st.chosen["up"]))

	var out []hbo.Decision
	scaledOut := false
	dwellOK := func(k string, dw time.Duration) bool {
		return now.Sub(st.lastOut[k]) >= dw && now.Sub(st.lastIn[k]) >= dw
	}
	curW := s.WorkerCount
	if s.WorkerVMCount > curW {
		curW = s.WorkerVMCount
	}
	positions := curW * spw
	needWorker := false

	{
		cur := s.VyosCount
		want := needVY(fc["vy"])
		if n := needVY(x); n > want {
			want = n
		}
		reason := fmt.Sprintf("B6 vy sess=%d fc=%.1f(%s) cur=%d want=%d", total, fc["vy"], who["vy"], cur, want)
		switch {
		case want > cur && !b.inflight(hbo.ActDeployVyOS, cur, 240*time.Second):
			out = append(out, hbo.Decision{Action: hbo.ActDeployVyOS, Reason: reason, At: now})
			b.note(hbo.ActDeployVyOS, cur)
			st.lastOut["vy"] = now
			scaledOut = true
		case cur > n0 && needVY(math.Max(winMax, fc["vy"])) <= cur-1 && dwellOK("vy", dwellVM) &&
			!b.inflight(hbo.ActDeployVyOS, cur, 240*time.Second) && !b.inflight(hbo.ActDeleteVyOS, cur, 240*time.Second):
			out = append(out, hbo.Decision{Action: hbo.ActDeleteVyOS, Reason: reason + " scale-in", At: now})
			b.note(hbo.ActDeleteVyOS, cur)
			st.lastIn["vy"] = now
		}
	}

	if cur := len(active); cur > 0 {
		want := needUP(fc["up"])
		if n := needUP(x); n > want {
			want = n
		}
		reason := fmt.Sprintf("B6 up sess=%d fc=%.1f(%s) cur=%d want=%d", total, fc["up"], who["up"], cur, want)
		if want > positions {
			needWorker = true
		}
		if want > cur && !b.inflight(hbo.ActScaleOutUP, cur, 90*time.Second) {
			n := want - cur
			if mb := envcfg.Int("HPA_MAX_BATCH", 3); n > mb {
				n = mb
			}
			if free := positions - cur; n > free {
				n = free
			}
			if n > 0 {
				for i := 0; i < n; i++ {
					out = append(out, hbo.Decision{Action: hbo.ActScaleOutUP, Reason: reason, At: now})
				}
				b.note(hbo.ActScaleOutUP, cur)
				st.lastOut["up"] = now
				scaledOut = true
			} else {
				d.log.Info("baseline b6: slot scale-out waits for worker", "want", want, "cur", cur, "positions", positions, "workers", curW)
			}
		} else if cur > upMin && needUP(math.Max(winMax, fc["up"])) <= cur-1 && dwellOK("up", dwellUP) &&
			!b.inflight(hbo.ActScaleOutUP, cur, 90*time.Second) && !b.inflight(hbo.ActScaleInUP, cur, 300*time.Second) {
			out = append(out, hbo.Decision{Action: hbo.ActScaleInUP, Reason: reason + " scale-in", At: now})
			b.note(hbo.ActScaleInUP, cur)
			st.lastIn["up"] = now
		}
	}

	if curW < wkMax && !b.inflight(hbo.ActCreateWorker, curW, 240*time.Second) {
		needW := needWK(fc["wk"])
		if n := needWK(x); n > needW {
			needW = n
		}
		if needWorker && needW < curW+1 {
			needW = curW + 1
		}
		if needW > curW {
			out = append(out, hbo.Decision{Action: hbo.ActCreateWorker,
				Reason: fmt.Sprintf("B6 wk fc=%.1f(%s) needs %d workers > %d (ready %d, vms %d)", fc["wk"], who["wk"], needW, curW, s.WorkerCount, s.WorkerVMCount), At: now})
			b.note(hbo.ActCreateWorker, curW)
			st.lastOut["wk"] = now
			scaledOut = true
		}
	}
	if !scaledOut && s.IdleWorker != "" && curW > wkMin && dwellOK("wk", dwellVM) &&
		needWK(math.Max(winMax, fc["wk"])) <= curW-1 &&
		!b.inflight(hbo.ActDeleteWorker, s.WorkerCount, 180*time.Second) {
		out = append(out, hbo.Decision{Action: hbo.ActDeleteWorker,
			Reason: fmt.Sprintf("B6 idle worker reclaim (%s) fc_wk=%.1f", s.IdleWorker, fc["wk"]), At: now})
		b.note(hbo.ActDeleteWorker, s.WorkerCount)
		st.lastIn["wk"] = now
	}
	return out
}
