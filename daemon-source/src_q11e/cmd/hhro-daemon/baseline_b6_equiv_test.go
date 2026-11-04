package main


import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"math"
	"os"
	"sort"
	"testing"
	"time"

	"github.com/anon/hhro-daemon/internal/hbo"
)

type b6Unit struct {
	disp, ready, gone float64
	removing          bool
}
type b6Model struct {
	t                                float64
	leadUP, leadVY, leadWK           float64
	delUP, delVY, delWK              float64
	capUP, capVY                     float64
	spw                              int
	pods, vys, wks                   []*b6Unit
	idleSince                        map[int]float64 // worker index (position in wks) → idle since
	events                           []string
	alloc                            float64
	lossMin, offMin                  [60]float64
}

func newB6Model(d0 float64) *b6Model {
	m := &b6Model{leadUP: 15, leadVY: 85, leadWK: 100, delUP: 30, delVY: 30, delWK: 60, capUP: 5, capVY: 4.45e6 * 0.93 / 250e3, spw: 2, idleSince: map[int]float64{}}
	need := func(x, c float64, lo, hi int) int {
		n := int(math.Ceil(x/c - 1e-9))
		if n < lo {
			n = lo
		}
		if n > hi {
			n = hi
		}
		return n
	}
	nVY := need(d0, m.capVY, 1, 3)
	nUP := int(math.Ceil(math.Ceil(d0-0.25) / m.capUP))
	if nUP < 2 {
		nUP = 2
	}
	if nUP > 8 {
		nUP = 8
	}
	nWK := int(math.Ceil(float64(nUP) / float64(m.spw)))
	if nWK < 1 {
		nWK = 1
	}
	for i := 0; i < nUP; i++ {
		m.pods = append(m.pods, &b6Unit{disp: -1e6, ready: -1e6, gone: 1e18})
	}
	for i := 0; i < nVY; i++ {
		m.vys = append(m.vys, &b6Unit{disp: -1e6, ready: -1e6, gone: 1e18})
	}
	for i := 0; i < nWK; i++ {
		m.wks = append(m.wks, &b6Unit{disp: -1e6, ready: -1e6, gone: 1e18})
	}
	return m
}
func (m *b6Model) cnt(us []*b6Unit, f func(*b6Unit) bool) int {
	n := 0
	for _, u := range us {
		if u.gone > m.t && f(u) {
			n++
		}
	}
	return n
}
func (m *b6Model) readyUP() int { return m.cnt(m.pods, func(u *b6Unit) bool { return u.ready <= m.t && !u.removing }) }
func (m *b6Model) readyVY() int { return m.cnt(m.vys, func(u *b6Unit) bool { return u.ready <= m.t && !u.removing }) }
func (m *b6Model) readyWK() int { return m.cnt(m.wks, func(u *b6Unit) bool { return u.ready <= m.t && !u.removing }) }
func (m *b6Model) vmWK() int    { return m.cnt(m.wks, func(u *b6Unit) bool { return u.disp <= m.t }) }

func (m *b6Model) step(D float64) {
	nUP, nVY := m.readyUP(), m.readyVY()
	l := 0.0
	if cv := float64(nVY) * m.capVY; D > cv {
		l = 1 - cv/D
	}
	x := D * (1 - l)
	if cu := float64(nUP) * m.capUP; x > cu {
		l = 1 - (1-l)*cu/x
	}
	mi := int(m.t) / 60
	if mi > 59 {
		mi = 59
	}
	m.lossMin[mi] += l * D * 5
	m.offMin[mi] += D * 5
	bUP := m.cnt(m.pods, func(u *b6Unit) bool { return u.disp <= m.t })
	bVY := m.cnt(m.vys, func(u *b6Unit) bool { return u.disp <= m.t })
	bWK := m.cnt(m.wks, func(u *b6Unit) bool { return u.disp <= m.t })
	m.alloc += (2.0*float64(bVY) + 0.8*float64(bUP) + 3.0*float64(bWK)) * 5 / 60
	m.t += 5
}

func (m *b6Model) state() hbo.SystemState {
	rw := m.readyWK()
	rep := m.cnt(m.pods, func(u *b6Unit) bool { return u.disp <= m.t })
	idle := ""
	if rw > 1 && rep <= (rw-1)*m.spw {
		if _, ok := m.idleSince[rw-1]; !ok {
			m.idleSince[rw-1] = m.t
		}
		if m.t-m.idleSince[rw-1] >= 120 {
			idle = fmt.Sprintf("worker-%d", rw-1)
		}
	} else {
		for k := range m.idleSince {
			delete(m.idleSince, k)
		}
	}
	return hbo.SystemState{WorkerCount: rw, ReadyWorkers: rw, WorkerVMCount: m.vmWK(), IdleWorker: idle,
		VyosCount: m.readyVY(), VyosAdmitted: m.readyVY(), RepUP: rep, ReadyUP: m.readyUP()}
}
func (m *b6Model) sessions(ue int) (int, map[int]int, []int) {
	n := m.readyUP()
	per := map[int]int{}
	act := []int{}
	for i := 0; i < n; i++ {
		o := 31 + i
		act = append(act, o)
		per[o] = ue / n
		if i < ue%n {
			per[o]++
		}
	}
	return ue, per, act
}
func (m *b6Model) apply(decs []hbo.Decision) {
	tick := int(m.t / 30)
	for _, d := range decs {
		switch d.Action {
		case hbo.ActScaleOutUP:
			if m.cnt(m.pods, func(u *b6Unit) bool { return u.disp <= m.t }) < m.readyWK()*m.spw {
				m.pods = append(m.pods, &b6Unit{disp: m.t, ready: m.t + m.leadUP, gone: 1e18})
				m.events = append(m.events, fmt.Sprintf("%d:out:up", tick))
			} else {
				m.events = append(m.events, fmt.Sprintf("%d:nopos:up", tick))
			}
		case hbo.ActScaleInUP:
			var v *b6Unit
			for _, p := range m.pods {
				if p.gone > m.t && !p.removing && p.ready <= m.t {
					v = p
				}
			}
			if v != nil {
				v.removing = true
				v.gone = m.t + m.delUP
				m.events = append(m.events, fmt.Sprintf("%d:in:up", tick))
			}
		case hbo.ActDeployVyOS:
			m.vys = append(m.vys, &b6Unit{disp: m.t, ready: m.t + m.leadVY, gone: 1e18})
			m.events = append(m.events, fmt.Sprintf("%d:out:vy", tick))
		case hbo.ActDeleteVyOS:
			var v *b6Unit
			for _, p := range m.vys {
				if p.gone > m.t && !p.removing && p.ready <= m.t {
					v = p
				}
			}
			if v != nil {
				v.removing = true
				v.gone = m.t + m.delVY
				m.events = append(m.events, fmt.Sprintf("%d:in:vy", tick))
			}
		case hbo.ActCreateWorker:
			m.wks = append(m.wks, &b6Unit{disp: m.t, ready: m.t + m.leadWK, gone: 1e18})
			m.events = append(m.events, fmt.Sprintf("%d:out:wk", tick))
		case hbo.ActDeleteWorker:
			var v *b6Unit
			for _, p := range m.wks {
				if p.gone > m.t && !p.removing && p.ready <= m.t {
					v = p
				}
			}
			if v != nil && m.readyWK() > 1 {
				v.removing = true
				v.gone = m.t + m.delWK
				m.events = append(m.events, fmt.Sprintf("%d:in:wk", tick))
			}
		}
	}
}

func runB6(ue []int, u string) *b6Model {
	for k, v := range map[string]string{"B6_U": u, "B5_LEAD_TICKS_UP": "2", "B5_LEAD_TICKS_VY": "5", "B5_LEAD_TICKS_WK": "5", "B6_BACKTEST_W": "10",
		"B6_CAP_VY_SESS": "17.8", "B6_CAP_UP_SESS": "5.0", "B6_SLOTS_PER_WORKER": "2", "DASA_N0": "1", "DASA_K_MAX": "2", "HPA_MIN": "2", "HPA_MAX": "8",
		"MIN_WORKERS": "1", "MAX_WORKERS": "4", "HPA_MAX_BATCH": "3", "B6_DWELL_UP": "300s", "B6_DWELL_VM": "600s"} {
		os.Setenv(k, v)
	}
	m := newB6Model(float64(ue[0]))
	d := &Daemon{log: slog.New(slog.NewTextHandler(io.Discard, nil))}
	base := time.Date(2026, 10, 14, 0, 0, 0, 0, time.UTC)
	baselineNow = func() time.Time { return base.Add(time.Duration(m.t * float64(time.Second))) }
	baselineEnabled = func(*Daemon) bool { return true }
	baselineSessions = func(*Daemon, context.Context) (int, map[int]int, []int) {
		mi := int(m.t / 60)
		if mi >= len(ue) {
			mi = len(ue) - 1
		}
		return m.sessions(ue[mi])
	}
	defer func() {
		baselineNow = time.Now
		baselineEnabled = func(d *Daemon) bool { return d.hbo.IsEnabled() }
		baselineSessions = func(d *Daemon, ctx context.Context) (int, map[int]int, []int) { return d.collectSlotSessions(ctx) }
	}()
	for i := 0; i < 60*12; i++ { // 60 min × 12 steps of 5 s
		if int(m.t)%30 == 0 {
			decs := d.decideBaseline(context.Background(), "b6", m.state())
			m.apply(decs)
		}
		m.step(float64(ue[int(m.t)/60]))
	}
	return m
}

func TestB6Equiv(t *testing.T) {
	dir := os.Getenv("TRACE_DIR")
	if dir == "" {
		dir = "/exp"
	}
	u := os.Getenv("B6_EQUIV_U")
	if u == "" {
		u = "0.70"
	}
	type out struct {
		Trace  string   `json:"trace"`
		U      string   `json:"u"`
		Alloc  float64  `json:"alloc"`
		SLO    int      `json:"slo"`
		Worst  float64  `json:"worst"`
		Events []string `json:"events"`
	}
	os.MkdirAll("testdata/b6equiv", 0o755)
	files := map[string]string{"t1": "trace_ue_60min_v3_40.json", "t2": "trace_ue_60min_v3_pm.json", "t3": "trace_ue_60min_v3_t3.json", "t4": "trace_ue_60min_v3_t4.json", "t5": "trace_ue_60min_v3_t5.json", "t6": "trace_ue_60min_v3_t6.json", "t7": "trace_ue_60min_v3_t7.json"}
	names := []string{}
	for k := range files {
		names = append(names, k)
	}
	sort.Strings(names)
	for _, tn := range names {
		var tr struct {
			UE []int `json:"ue"`
		}
		b, err := os.ReadFile(dir + "/" + files[tn])
		if err != nil {
			continue
		}
		json.Unmarshal(b, &tr)
		if len(tr.UE) < 60 {
			continue
		}
		m := runB6(tr.UE[:60], u)
		slo, worst := 0, 0.0
		for i := 0; i < 60; i++ {
			pct := 100 * m.lossMin[i] / math.Max(m.offMin[i], 1e-9)
			if pct <= 0.1 {
				slo++
			}
			if pct > worst {
				worst = pct
			}
		}
		o := out{Trace: tn, U: u, Alloc: m.alloc, SLO: slo, Worst: worst, Events: m.events}
		j, _ := json.MarshalIndent(o, "", " ")
		os.WriteFile("testdata/b6equiv/"+tn+".json", j, 0o644)
		t.Logf("%s u=%s: SLO %d/60 alloc %.0f worst %.2f%% events %d", tn, u, slo, m.alloc, worst, len(m.events))
	}
}
