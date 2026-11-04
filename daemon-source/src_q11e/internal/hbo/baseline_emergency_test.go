package hbo

// 2026-10-22 spec §4.114 item 3: equivalence of the baseline-path emergency force with the v6/S path.
// For each scenario a fresh controller pair is built with the same latched shadow state; V6Decisions'
// emergency decisions (Reason contains "emergency force") must equal BaselineEmergencyForce's additions.
import (
	"io"
	"log/slog"
	"strings"
	"testing"
	"time"

	"github.com/anon/hhro-daemon/internal/state"
)

type emScen struct {
	name           string
	measUP, measVY float64
	s              SystemState
	baseOut        []Decision // baseline decisions this tick
	v6Moves        []Move     // v6 tuple moves this tick (same intent as baseOut)
	recentRev      Action     // a reverse action dispatched just before
	refrac0        bool       // V6_EMERG_REFRACTORY_SEC=0
	second         bool       // call twice in a row (refractory test)
	emerg          bool
}

func newEmCtrl(t *testing.T, sc emScen) *Controller {
	cfg := Cfg{Enabled: true, MinUP: 2, MaxUP: 8, MinVyos: 1, MaxVyos: 3, MinWorkers: 1, MaxWorkers: 4, EupfMode: true}
	c := NewController(cfg, nil, state.NewFreeze(), slog.New(slog.NewTextHandler(io.Discard, nil)))
	c.shadow.mu.Lock()
	c.shadow.Last.Valid = true
	c.shadow.Last.Emergency = sc.emerg
	c.shadow.Last.Meas = SegLoss{UP: sc.measUP, VY: sc.measVY}
	c.shadow.Last.Best = TupleScore{Moves: sc.v6Moves}
	c.shadow.mu.Unlock()
	if sc.recentRev != "" {
		c.shadow.NoteDispatched(sc.recentRev)
	}
	return c
}

func emergOnly(ds []Decision) []Action {
	var a []Action
	for _, d := range ds {
		if strings.Contains(d.Reason, "emergency force") {
			a = append(a, d.Action)
		}
	}
	return a
}

func TestBaselineEmergencyEquivalence(t *testing.T) {
	t.Setenv("V6_ENABLED", "true")
	base := SystemState{VyosCount: 2, RepUP: 5, ReadyUP: 5, PodPendingCount: 0}
	full := SystemState{VyosCount: 3, RepUP: 8, ReadyUP: 8}
	sc := []emScen{
		{name: "UP-dominant -> +1 slot", measUP: 0.010, measVY: 0.002, s: base, emerg: true},
		{name: "VY-dominant -> +1 VyOS", measUP: 0.001, measVY: 0.008, s: base, emerg: true},
		{name: "VY-dominant at MaxVyos -> +1 slot", measUP: 0.001, measVY: 0.008, s: SystemState{VyosCount: 3, RepUP: 5, ReadyUP: 5}, emerg: true},
		{name: "both layers full -> none", measUP: 0.01, measVY: 0.01, s: full, emerg: true},
		{name: "slot pending -> none (UP)", measUP: 0.01, measVY: 0.001, s: SystemState{VyosCount: 2, RepUP: 5, ReadyUP: 4}, emerg: true},
		{name: "not latched -> none", measUP: 0.01, measVY: 0.001, s: base, emerg: false},
		{name: "controller already scaling out -> none", measUP: 0.01, measVY: 0.001, s: base, emerg: true,
			baseOut: []Decision{{Action: ActScaleOutUP, Reason: "baseline hpa"}}, v6Moves: []Move{{Act: ActScaleOutUP}}},
		{name: "reverse of recent scale-in suppressed", measUP: 0.01, measVY: 0.001, s: base, emerg: true, recentRev: ActScaleInUP},
		{name: "refractory blocks second call", measUP: 0.01, measVY: 0.001, s: base, emerg: true, second: true},
		{name: "refractory 0 allows second call", measUP: 0.01, measVY: 0.001, s: base, emerg: true, second: true, refrac0: true},
	}
	for _, x := range sc {
		t.Run(x.name, func(t *testing.T) {
			if x.refrac0 {
				t.Setenv("V6_EMERG_REFRACTORY_SEC", "0")
			}
			cv, cb := newEmCtrl(t, x), newEmCtrl(t, x)
			var last time.Time
			calls := 1
			if x.second {
				calls = 2
			}
			for k := 0; k < calls; k++ {
				v := emergOnly(cv.V6Decisions(x.s))
				bo := append([]Decision(nil), x.baseOut...)
				b := emergOnly(cb.BaselineEmergencyForce(x.s, bo, &last))
				if len(v) != len(b) || (len(v) == 1 && v[0] != b[0]) {
					t.Fatalf("call %d: v6 path %v != baseline path %v", k+1, v, b)
				}
				t.Logf("call %d: v6 %v baseline %v", k+1, v, b)
			}
		})
	}
}
