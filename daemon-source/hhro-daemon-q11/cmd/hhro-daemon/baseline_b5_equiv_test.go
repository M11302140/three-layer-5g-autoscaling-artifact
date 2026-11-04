package main


import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"os"
	"sort"
	"strings"
	"testing"
	"time"

	"github.com/anon/hhro-daemon/internal/hbo"
)

type b5Model struct {
	t        float64
	slots    map[int]float64 // octet → ready time
	pending  map[int]float64
	draining map[int]float64 // octet → done time
	workers  map[int]float64
	idleSince map[int]float64
	vy       int
	vyDeploy []float64
	vyDelete []float64
	events   []string
	doubleAt []int
}

var slotOctets = map[int][]int{0: {38, 33}, 1: {31, 32}, 2: {34, 35}, 3: {36, 37}}

func newB5Model() *b5Model {
	m := &b5Model{slots: map[int]float64{}, pending: map[int]float64{}, draining: map[int]float64{}, workers: map[int]float64{}, idleSince: map[int]float64{}, vy: 1}
	m.workers[0] = 0
	m.slots[38] = 0
	m.slots[33] = 0
	return m
}

func (m *b5Model) ready(idx int) bool { r, ok := m.workers[idx]; return ok && r <= m.t }
func (m *b5Model) readyWorkers() int {
	n := 0
	for i := range m.workers {
		if m.ready(i) {
			n++
		}
	}
	return n
}
func (m *b5Model) freePosition() (int, bool) {
	idxs := []int{}
	for i := range m.workers {
		idxs = append(idxs, i)
	}
	sort.Ints(idxs)
	for _, i := range idxs {
		if !m.ready(i) {
			continue
		}
		for _, o := range slotOctets[i] {
			if _, a := m.slots[o]; a {
				continue
			}
			if _, p := m.pending[o]; p {
				continue
			}
			if _, d := m.draining[o]; d {
				continue
			}
			return o, true
		}
	}
	return 0, false
}
func (m *b5Model) createWorker(tag string) {
	idx := 0
	for i := range m.workers {
		if i >= idx {
			idx = i + 1
		}
	}
	m.workers[idx] = m.t + 100
	m.events = append(m.events, fmt.Sprintf("%d:%s:worker-%d", int(m.t/30), tag, idx))
}
func (m *b5Model) activeSlots() []int {
	out := []int{}
	for o, r := range m.slots {
		if r <= m.t {
			out = append(out, o)
		}
	}
	sort.Ints(out)
	return out
}
func (m *b5Model) step() {
	m.t += 30
	for o, r := range m.pending {
		if r <= m.t {
			m.slots[o] = r
			delete(m.pending, o)
		}
	}
	for o, d := range m.draining {
		if d <= m.t {
			delete(m.slots, o)
			delete(m.draining, o)
		}
	}
	keep := m.vyDeploy[:0]
	for _, r := range m.vyDeploy {
		if r <= m.t {
			m.vy++
		} else {
			keep = append(keep, r)
		}
	}
	m.vyDeploy = keep
	keep2 := m.vyDelete[:0]
	for _, r := range m.vyDelete {
		if r <= m.t {
			m.vy--
		} else {
			keep2 = append(keep2, r)
		}
	}
	m.vyDelete = keep2
}
func (m *b5Model) state() hbo.SystemState {
	idle := ""
	for i := range m.workers {
		if i == 0 || !m.ready(i) {
			continue
		}
		busy := false
		for _, o := range slotOctets[i] {
			_, a := m.slots[o]
			_, p := m.pending[o]
			_, d := m.draining[o]
			if a || p || d {
				busy = true
			}
		}
		if !busy {
			if _, ok := m.idleSince[i]; !ok {
				m.idleSince[i] = m.t
			}
			if m.t-m.idleSince[i] >= 120 && idle == "" {
				idle = fmt.Sprintf("worker-%d", i)
			}
		} else {
			delete(m.idleSince, i)
		}
	}
	return hbo.SystemState{WorkerCount: m.readyWorkers(), ReadyWorkers: m.readyWorkers(), WorkerVMCount: len(m.workers), IdleWorker: idle, VyosCount: m.vy}
}
func (m *b5Model) sessions(ue int) (int, map[int]int, []int) {
	act := m.activeSlots()
	per := map[int]int{}
	for i, o := range act {
		per[o] = ue / len(act)
		if i < ue%len(act) {
			per[o]++
		}
	}
	return ue, per, act
}
func (m *b5Model) apply(decs []hbo.Decision) {
	tick := int(m.t / 30)
	execWorker, b5Worker := false, false
	for _, d := range decs {
		switch d.Action {
		case hbo.ActScaleOutUP:
			if o, ok := m.freePosition(); ok {
				m.pending[o] = m.t + 45
				m.events = append(m.events, fmt.Sprintf("%d:slot+:%d", tick, o))
			} else {
				m.createWorker("exec-worker")
				execWorker = true
			}
		case hbo.ActScaleInUP:
			act := m.activeSlots()
			if len(act) > 0 {
				o := act[len(act)-1]
				m.draining[o] = m.t + 150
				m.events = append(m.events, fmt.Sprintf("%d:slot-:%d", tick, o))
			}
		case hbo.ActCreateWorker:
			m.createWorker("b5-worker")
			b5Worker = true
		case hbo.ActDeleteWorker:
			var victim int = -1
			fmt.Sscanf(m.state().IdleWorker, "worker-%d", &victim)
			if victim > 0 {
				delete(m.workers, victim)
				delete(m.idleSince, victim)
				m.events = append(m.events, fmt.Sprintf("%d:worker-:%d", tick, victim))
			}
		case hbo.ActDeployVyOS:
			m.vyDeploy = append(m.vyDeploy, m.t+150)
			m.events = append(m.events, fmt.Sprintf("%d:vy+", tick))
		case hbo.ActDeleteVyOS:
			m.vyDelete = append(m.vyDelete, m.t+60)
			m.events = append(m.events, fmt.Sprintf("%d:vy-", tick))
		}
	}
	if execWorker && b5Worker {
		m.doubleAt = append(m.doubleAt, tick)
	}
}

func runB5(t *testing.T, ue []int, legacy bool) *b5Model {
	for k, v := range map[string]string{"HPA_TARGET_SESS": "4.0", "DASA_MU_SESS": "14", "HPA_TOLERANCE": "0.05", "HPA_DOWN_WINDOW": "600s", "DASA_SCALEIN_MARGIN": "0.8",
		"B5_LEAD_TICKS_VY": "5", "HOLT_ALPHA": "0.3", "HOLT_BETA": "0.05", "MAX_WORKERS": "4", "MIN_WORKERS": "1", "HPA_MAX": "8", "HPA_MIN": "2", "DASA_N0": "1", "DASA_K_MAX": "2", "HPA_MAX_BATCH": "3"} {
		os.Setenv(k, v)
	}
	os.Setenv("B5_LEGACY_WORKER", map[bool]string{true: "true", false: "false"}[legacy])
	m := newB5Model()
	d := &Daemon{log: slog.New(slog.NewTextHandler(io.Discard, nil))}
	base := time.Date(2026, 10, 10, 0, 0, 0, 0, time.UTC)
	baselineNow = func() time.Time { return base.Add(time.Duration(m.t * float64(time.Second))) }
	baselineEnabled = func(*Daemon) bool { return true }
	baselineSessions = func(*Daemon, context.Context) (int, map[int]int, []int) {
		mi := int(m.t / 60)
		if mi >= len(ue) {
			mi = len(ue) - 1
		}
		return m.sessions(ue[mi])
	}
	defer func() { baselineNow = time.Now; baselineEnabled = func(d *Daemon) bool { return d.hbo.IsEnabled() }; baselineSessions = func(d *Daemon, ctx context.Context) (int, map[int]int, []int) { return d.collectSlotSessions(ctx) } }()
	for tick := 0; tick < 120; tick++ {
		decs := d.decideBaseline(context.Background(), "b5", m.state())
		m.apply(decs)
		m.step()
	}
	return m
}

func TestB5Equiv(t *testing.T) {
	dir := os.Getenv("TRACE_DIR")
	if dir == "" {
		dir = "/exp"
	}
	type out struct {
		Trace     string   `json:"trace"`
		Identical int      `json:"identical_prefix_events"`
		Legacy    []string `json:"legacy"`
		New       []string `json:"q10"`
		DoubleAt  []int    `json:"legacy_double_creation_ticks"`
		FirstDiff string   `json:"first_diff"`
	}
	os.MkdirAll("testdata/b5equiv", 0o755)
	for tn, f := range map[string]string{"t1": "trace_ue_60min_v3_40.json", "t2": "trace_ue_60min_v3_pm.json"} {
		var tr struct {
			UE []int `json:"ue"`
		}
		b, err := os.ReadFile(dir + "/" + f)
		if err != nil {
			t.Skipf("trace %s missing: %v", f, err)
		}
		json.Unmarshal(b, &tr)
		leg := runB5(t, tr.UE, true)
		nw := runB5(t, tr.UE, false)
		norm := func(ev []string) []string {
			out := make([]string, len(ev))
			for i, e := range ev {
				out[i] = strings.Replace(strings.Replace(e, ":exec-worker:", ":worker+:", 1), ":b5-worker:", ":worker+:", 1)
			}
			return out
		}
		le, ne := norm(leg.events), norm(nw.events)
		n := 0
		for n < len(le) && n < len(ne) && le[n] == ne[n] {
			n++
		}
		firstDoubleTick := -1
		if len(leg.doubleAt) > 0 {
			firstDoubleTick = leg.doubleAt[0]
		}
		diffTick := -1
		if n < len(le) {
			fmt.Sscanf(le[n], "%d:", &diffTick)
		}
		fd := "none"
		if n < len(le) || n < len(ne) {
			l, r := "<end>", "<end>"
			if n < len(le) {
				l = le[n]
			}
			if n < len(ne) {
				r = ne[n]
			}
			fd = fmt.Sprintf("event#%d (tick %d) legacy=%s q10=%s; legacy first double-creation tick=%d", n, diffTick, l, r, firstDoubleTick)
		}
		o := out{Trace: tn, Identical: n, Legacy: leg.events, New: nw.events, DoubleAt: leg.doubleAt, FirstDiff: fd}
		j, _ := json.MarshalIndent(o, "", " ")
		os.WriteFile("testdata/b5equiv/"+tn+".json", j, 0o644)
		t.Logf("%s: legacy %d events, q10 %d events, identical prefix %d, legacy double-creation ticks %v, first diff: %s", tn, len(leg.events), len(nw.events), n, leg.doubleAt, fd)
		for _, e := range nw.events {
			if strings.Contains(e, ":exec-worker:") {
				t.Errorf("%s: q11 used executor fallback: %s", tn, e)
			}
		}
		if n != len(le) || n != len(ne) {
			if firstDoubleTick < 0 || diffTick != firstDoubleTick {
				t.Errorf("%s: sequences diverge at tick %d but legacy first double-creation tick is %d", tn, diffTick, firstDoubleTick)
			}
		}
	}
}
