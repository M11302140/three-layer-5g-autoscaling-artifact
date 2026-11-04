package hbo

import (
	"fmt"
	"sync"
	"time"
)

// Timers manages per-action cooldowns, direction locks, and low-dwell counters.
type Timers struct {
	mu sync.Mutex

	// Per-action cooldown expiry
	cooldowns map[Action]time.Time

	// Direction lock: last scale-out/in timestamp per resource
	lastScaleOutCP     time.Time
	lastScaleInCP      time.Time
	lastScaleOutUP     time.Time
	lastScaleInUP      time.Time
	lastScaleOutVyos   time.Time
	lastScaleInVyos    time.Time
	lastScaleOutWorker time.Time
	lastScaleInWorker  time.Time

	// Low-dwell counter for scale-in
	lowDwellCount int

	cfg Cfg

	v6calib *Calib
}

// EnableV6Derived switches cooldown/lock durations to calib-derived values.
func (t *Timers) EnableV6Derived(c *Calib) {
	t.mu.Lock()
	defer t.mu.Unlock()
	t.v6calib = c
}

const v6WSettle = 30 * time.Second

func (t *Timers) v6Cooldown(a Action) (time.Duration, bool) {
	if t.v6calib == nil {
		return 0, false
	}
	spec, ok := t.v6calib.Act[a]
	if !ok {
		return 0, false
	}
	return time.Duration(spec.TReadySec)*time.Second + v6WSettle, true
}

func (t *Timers) v6Lock(out Action) (time.Duration, bool) {
	if t.v6calib == nil {
		return 0, false
	}
	spec, ok := t.v6calib.Act[out]
	if !ok {
		return 0, false
	}
	return 2*time.Duration(spec.TReadySec)*time.Second + v6WSettle, true
}

func NewTimers(cfg Cfg) *Timers {
	return &Timers{
		cooldowns: make(map[Action]time.Time),
		cfg:       cfg,
	}
}

// CooldownActive checks if an action's cooldown is still running.
func (t *Timers) CooldownActive(a Action) bool {
	t.mu.Lock()
	defer t.mu.Unlock()
	exp, ok := t.cooldowns[a]
	if !ok {
		return false
	}
	return time.Now().Before(exp)
}

// SetCooldown arms a cooldown for the given action.
func (t *Timers) SetCooldown(a Action) {
	t.mu.Lock()
	defer t.mu.Unlock()
	dur := t.cooldownDuration(a)
	t.cooldowns[a] = time.Now().Add(dur)
}

func (t *Timers) cooldownDuration(a Action) time.Duration {
	if d, ok := t.v6Cooldown(a); ok {
		return d
	}
	switch a {
	case ActScaleOutCP:
		return t.cfg.CpScaleOutCooldown
	case ActScaleInCP:
		return t.cfg.CpScaleInCooldown
	case ActScaleOutUP:
		return t.cfg.UpScaleOutCooldown
	case ActScaleInUP:
		return t.cfg.UpScaleInCooldown
	case ActDeployVyOS:
		return t.cfg.VyosScaleOutCooldown
	case ActDeleteVyOS:
		return t.cfg.VyosScaleInCooldown
	case ActCreateWorker:
		return t.cfg.WorkerScaleOutCooldown
	case ActDeleteWorker:
		return t.cfg.WorkerScaleInCooldown
	case ActRebalanceUPF:
		return t.cfg.RebalanceUpfCooldown
	case ActRebalanceVy:
		return t.cfg.RebalanceVyosCooldown
	}
	return 60 * time.Second
}

// RecordAction updates direction lock timestamps after an action is executed.
func (t *Timers) RecordAction(a Action) {
	t.mu.Lock()
	defer t.mu.Unlock()
	now := time.Now()
	switch a {
	case ActScaleOutCP:
		t.lastScaleOutCP = now
	case ActScaleInCP:
		t.lastScaleInCP = now
	case ActScaleOutUP:
		t.lastScaleOutUP = now
	case ActScaleInUP:
		t.lastScaleInUP = now
	case ActDeployVyOS:
		t.lastScaleOutVyos = now
	case ActDeleteVyOS:
		t.lastScaleInVyos = now
	case ActCreateWorker:
		t.lastScaleOutWorker = now
	case ActDeleteWorker:
		t.lastScaleInWorker = now
	}
}

// DirectionLockBlocks checks if an action is blocked by a recent opposite action.
func (t *Timers) DirectionLockBlocks(a Action) (bool, string) {
	t.mu.Lock()
	defer t.mu.Unlock()
	now := time.Now()

	lock := func(out Action, cfgD time.Duration) time.Duration {
		if d, ok := t.v6Lock(out); ok {
			return d
		}
		return cfgD
	}
	chk := func(last time.Time, d time.Duration, msg string) (bool, string) {
		if !last.IsZero() && now.Sub(last) < d {
			return true, fmt.Sprintf("%s (%s ago < %s)", msg, now.Sub(last).Round(time.Second), d)
		}
		return false, ""
	}
	switch a {
	case ActScaleOutCP:
		return chk(t.lastScaleInCP, t.cfg.DirectionLockCP, "CP scale-out direction-locked")
	case ActScaleInCP:
		return chk(t.lastScaleOutCP, t.cfg.DirectionLockCP, "CP scale-in direction-locked")
	case ActScaleOutUP:
		return chk(t.lastScaleInUP, lock(ActScaleOutUP, t.cfg.DirectionLockUP), "UP scale-out direction-locked")
	case ActScaleInUP:
		return chk(t.lastScaleOutUP, lock(ActScaleOutUP, t.cfg.DirectionLockUP), "UP scale-in direction-locked")
	case ActDeployVyOS:
		return chk(t.lastScaleInVyos, lock(ActDeployVyOS, t.cfg.DirectionLockVyos), "VyOS deploy direction-locked")
	case ActDeleteVyOS:
		return chk(t.lastScaleOutVyos, lock(ActDeployVyOS, t.cfg.DirectionLockVyos), "VyOS delete direction-locked")
	case ActCreateWorker:
		return chk(t.lastScaleInWorker, lock(ActCreateWorker, t.cfg.DirectionLockWorker), "worker create direction-locked")
	case ActDeleteWorker:
		return chk(t.lastScaleOutWorker, lock(ActCreateWorker, t.cfg.DirectionLockWorker), "worker delete direction-locked")
	}
	return false, ""
}

// IncrementLowDwell increments the low-dwell counter.
func (t *Timers) IncrementLowDwell() {
	t.mu.Lock()
	defer t.mu.Unlock()
	t.lowDwellCount++
}

// ResetLowDwell resets the low-dwell counter.
func (t *Timers) ResetLowDwell() {
	t.mu.Lock()
	defer t.mu.Unlock()
	t.lowDwellCount = 0
}

// LowDwellReached checks if the counter has reached the threshold.
func (t *Timers) LowDwellReached(needed int) bool {
	t.mu.Lock()
	defer t.mu.Unlock()
	return t.lowDwellCount >= needed
}

// ResetOnFreeze resets transient state when transition freeze activates.
func (t *Timers) ResetOnFreeze() {
	t.mu.Lock()
	defer t.mu.Unlock()
	t.lowDwellCount = 0
}
