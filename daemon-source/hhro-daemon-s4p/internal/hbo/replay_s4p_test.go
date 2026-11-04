package hbo


import (
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"testing"
	"time"

	"github.com/anon/hhro-daemon/internal/state"
)

type rpTick struct {
	T        float64    `json:"t"`
	D        int        `json:"D"`
	RepUP    int        `json:"rep_up"`
	ReadyUP  int        `json:"ready_up"`
	DrainUP  int        `json:"drain_up"`
	VyVM     int        `json:"vy_vm"`
	VyAdm    int        `json:"vy_adm"`
	WkVM     int        `json:"wk_vm"`
	WkReady  int        `json:"wk_ready"`
	Idle     bool       `json:"idle"`
	Intents  [][]any    `json:"intents"`
	Executed [][]string `json:"executed"`
}
type rpCase struct {
	Name  string             `json:"name"`
	Trace string             `json:"trace"`
	L     map[string]float64 `json:"L"`
	Ticks []rpTick           `json:"ticks"`
	D5    []int              `json:"d5"`
}
type rpDiff struct {
	T      float64  `json:"t"`
	Python []string `json:"python"`
	Daemon []string `json:"daemon"`
}
type rpResult struct {
	Name, Trace string
	Flags       map[string]string
	Ticks       int
	Differing   int
	Diffs       []rpDiff
	Daemon      [][]string // per tick, daemon intents (for Go-vs-Go comparisons)
	Q           [][6]float64 // per tick: NeedUP, NeedVY, NeedWK, MarginUP, MarginVY, MarginWK (UE)
}

func replayCase(t *testing.T, c rpCase, env map[string]string) rpResult {
	t.Helper()
	t.Setenv("V6_DEMAND_MODEL", "sigma")
	t.Setenv("V6_LAMBDA_VM", fmt.Sprint(c.L["wk"]))
	t.Setenv("V6_LAMBDA_UP", fmt.Sprint(c.L["up"]))
	t.Setenv("V6_TREADY_MEASURED", "true")
	t.Setenv("V6_ENABLED", "true")
	t.Setenv("V6_SHADOW", "true")
	t.Setenv("V6_RISE_WARM_S", "0")
	for k, v := range env {
		t.Setenv(k, v)
	}
	cfg := Cfg{Enabled: true, MinUP: 2, MaxUP: 8, MinVyos: 1, MaxVyos: 3, MinWorkers: 1, MaxWorkers: 4, EupfMode: true}
	var lw io.Writer = io.Discard
	if os.Getenv("REPLAY_DEBUG") != "" {
		lw = os.Stderr
	}
	ctrl := NewController(cfg, nil, state.NewFreeze(), slog.New(slog.NewTextHandler(lw, nil)))
	if ctrl.shadow.rise == nil || !ctrl.shadow.rise.SigmaMode() {
		t.Fatal("sigma prior not loaded")
	}
	t0 := time.Date(2026, 10, 5, 0, 0, 0, 0, time.UTC)
	sim := 0.0
	nowFn = func() time.Time { return t0.Add(time.Duration(sim * float64(time.Second))) }
	defer func() { nowFn = time.Now }()
	ctrl.V6ResetEpisode()
	perUE := 250000.0
	res := rpResult{Name: c.Name, Trace: c.Trace, Flags: env, Ticks: len(c.Ticks)}
	for i, tk := range c.Ticks {
		sim = tk.T
		idle := ""
		if tk.Idle {
			idle = "worker-x"
		}
		s := SystemState{OfferedPPS: float64(tk.D) * perUE / 2, UECount: tk.D, RepUP: tk.RepUP, ReadyUP: tk.ReadyUP,
			VyosCount: tk.VyVM, VyosAdmitted: tk.VyAdm, WorkerCount: tk.WkReady, ReadyWorkers: tk.WkReady, WorkerVMCount: tk.WkVM, IdleWorker: idle}
		if os.Getenv("REPLAY_HIST") == "fine" {
			j1 := int(tk.T) / 5
			for j := j1 - 48; j <= j1; j++ {
				if j < 0 || j >= len(c.D5) {
					continue
				}
				s.OfferedHist = append(s.OfferedHist, OfferedSample{T: t0.Add(time.Duration(j*5) * time.Second), PPS: float64(c.D5[j]) * perUE / 2})
			}
		} else {
			for k := 8; k >= 0; k-- {
				j := i - k
				if j < 0 {
					continue
				}
				s.OfferedHist = append(s.OfferedHist, OfferedSample{T: t0.Add(time.Duration(c.Ticks[j].T * float64(time.Second))), PPS: float64(c.Ticks[j].D) * perUE / 2})
			}
		}
		miss := WindowFeature{Missing: true}
		f := FeatureSet{CpuCP: miss, CpuUP: miss, MeanCpuUP: miss, CpuVyos: miss, CpuVyosReal: miss, MeanCpuVyosReal: miss, ReadyCP: miss, DropUP: miss, PktRateUP: miss, BwUP: miss, UECount: miss, VyosDropErr: miss, VyosLossRatio: miss, VyosImbalance: miss}
		ctrl.shadow.Tick(f, s, cfg)
		ctrl.mu.Lock()
		ctrl.lastFeatures = f
		ctrl.mu.Unlock()
		lq := ctrl.shadow.LastQ
		res.Q = append(res.Q, [6]float64{float64(lq.NeedUP), float64(lq.NeedVY), float64(lq.NeedWK), lq.MarginUP / perUE, lq.MarginVY / perUE, lq.MarginWK / perUE})
		var dm []string
		if os.Getenv("REPLAY_INCL") != "" {
			sim = tk.T - 0.001
		}
		decs := ctrl.V6Decisions(s)
		sim = tk.T
		for _, dec := range decs {
			switch dec.Action {
			case ActScaleOutUP:
				if tk.DrainUP > 0 {
					dm = append(dm, "CANCEL_DRAIN")
				} else if tk.RepUP < tk.WkReady*slotsPerWorker {
					dm = append(dm, "SCALE_OUT_UP")
				}
			case ActScaleInUP:
				dm = append(dm, "SCALE_IN_UP")
			case ActDeployVyOS:
				dm = append(dm, "DEPLOY_VYOS")
			case ActDeleteVyOS:
				dm = append(dm, "DELETE_VYOS")
			case ActCreateWorker:
				dm = append(dm, "CREATE_WORKER")
			case ActDeleteWorker:
				dm = append(dm, "DELETE_WORKER")
			default:
				dm = append(dm, "OTHER:"+string(dec.Action))
			}
		}
		var py []string
		for _, x := range tk.Intents {
			py = append(py, x[0].(string))
		}
		sort.Strings(dm)
		sort.Strings(py)
		res.Daemon = append(res.Daemon, dm)
		if strings.Join(dm, ",") != strings.Join(py, ",") {
			res.Differing++
			res.Diffs = append(res.Diffs, rpDiff{T: tk.T, Python: py, Daemon: dm})
		}
		for _, e := range tk.Executed {
			switch e[0] + ":" + e[1] {
			case "out:up":
				ctrl.V6NoteDispatched(ActScaleOutUP)
				ctrl.V6DropInFlight(ActScaleInUP)
			case "cancel-drain:up":
				ctrl.V6DropInFlight(ActScaleInUP)
			case "in:up":
				ctrl.V6NoteDispatched(ActScaleInUP)
			case "out:vy":
				ctrl.V6NoteDispatched(ActDeployVyOS)
			case "in:vy":
				ctrl.V6NoteDispatched(ActDeleteVyOS)
			case "out:wk":
				ctrl.V6NoteDispatched(ActCreateWorker)
			case "in:wk":
				ctrl.V6NoteDispatched(ActDeleteWorker)
			}
		}
	}
	return res
}

func TestReplayS4p(t *testing.T) {
	dir := os.Getenv("REPLAY_DIR")
	if dir == "" {
		t.Skip("REPLAY_DIR not set")
	}
	outDir := os.Getenv("REPLAY_OUT")
	flagSets := map[string]map[string]string{"off": {}}
	if os.Getenv("REPLAY_FLAGS_ON") != "" { // S4′:b′ + R2(w 1600)
		flagSets["on"] = map[string]string{"V6_S4P_INDEP_WK": "true", "V6_S4P_R2_W": "1600"}
	}
	files, _ := filepath.Glob(filepath.Join(dir, "*.json"))
	sort.Strings(files)
	total := map[string]int{}
	for _, fn := range files {
		raw, err := os.ReadFile(fn)
		if err != nil {
			t.Fatal(err)
		}
		var c rpCase
		if err := json.Unmarshal(raw, &c); err != nil {
			t.Fatal(err)
		}
		if only := os.Getenv("REPLAY_ONLY"); only != "" && !strings.HasPrefix(c.Name, only) {
			continue
		}
		for tag, env := range flagSets {
			r := replayCase(t, c, env)
			total[tag] += r.Differing
			t.Logf("%-6s %-4s flags=%-3s ticks %d differing %d", c.Name, c.Trace, tag, r.Ticks, r.Differing)
			for i, d := range r.Diffs {
				if i >= 6 {
					break
				}
				t.Logf("    t=%5.0f python %v daemon %v", d.T, d.Python, d.Daemon)
			}
			if outDir != "" {
				b, _ := json.Marshal(r)
				_ = os.WriteFile(filepath.Join(outDir, fmt.Sprintf("%s_%s_%s.json", c.Name, c.Trace, tag)), b, 0o644)
			}
		}
	}
	t.Logf("TOTAL differing ticks: %v", total)
}
