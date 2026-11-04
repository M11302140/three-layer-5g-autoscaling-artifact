package state

import (
	"sync/atomic"
	"time"
)

// Freeze gates autoscale + rebalance during a known transient (e.g.
// experiment.py killing/respawning UEs between stages). Driven by POST
// /hint/transition. Lock-free atomic; nil-safe.
type Freeze struct {
	until atomic.Int64
}

func NewFreeze() *Freeze { return &Freeze{} }

func (f *Freeze) Set(d time.Duration) {
	if f == nil || d <= 0 {
		return
	}
	f.until.Store(time.Now().Add(d).UnixNano())
}

func (f *Freeze) Active() (bool, time.Duration) {
	if f == nil {
		return false, 0
	}
	u := f.until.Load()
	if u == 0 {
		return false, 0
	}
	remain := time.Until(time.Unix(0, u))
	if remain <= 0 {
		return false, 0
	}
	return true, remain
}

// SteadyGate (D9c) is raised by the Decisioner once C^up has been in
// (UpLow, UpHigh) for SteadyBandTicks ticks — pool is coasting. Both
// Decisioner.LOW path and Rebalancer.quarantine read it to dampen themselves.
type SteadyGate struct {
	on atomic.Bool
}

func NewSteadyGate() *SteadyGate { return &SteadyGate{} }

func (g *SteadyGate) Set(on bool) {
	if g == nil {
		return
	}
	g.on.Store(on)
}

func (g *SteadyGate) Active() bool {
	if g == nil {
		return false
	}
	return g.on.Load()
}
