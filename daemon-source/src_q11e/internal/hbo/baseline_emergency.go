package hbo

import (
	"fmt"
	"time"

	"github.com/anon/hhro-daemon/internal/envcfg"
)

// BaselineEmergencyForce (2026-10-22, spec §4.114 item 3, hardware A/B of the emergency rule):
// applies to a BASELINE tick's decisions the same measured-level emergency force +1 that
// V6Decisions applies on the v6/S path. The block below is a verbatim copy of V6Decisions'
// V6_EMERG_REFRACTORY_SEC refractory, same layer choice, same reverse-of-recent-scale-in guard),
// with its refractory clock passed in by the caller so the v6/S state is untouched.
// Reached only when the daemon env BASELINE_EMERGENCY=true and BASELINE_MODE is set.
func (c *Controller) BaselineEmergencyForce(s SystemState, out []Decision, last *time.Time) []Decision {
	if !c.v6Active || !c.enabled.Load() {
		return out
	}
	c.shadow.mu.Lock()
	valid := c.shadow.Last.Valid
	emerg := c.shadow.Last.Emergency
	meas := c.shadow.Last.Meas
	c.shadow.mu.Unlock()
	if !valid || !emerg {
		return out
	}
	now := nowFn()
	hasOut := false
	for _, d := range out {
		if d.Action.IsScaleOut() {
			hasOut = true
		}
	}
	if !hasOut && sinceFn(*last) >
		time.Duration(envcfg.Int("V6_EMERG_REFRACTORY_SEC", 90))*time.Second {
		var act Action
		if meas.VY >= meas.UP && s.VyosCount < c.cfg.MaxVyos {
			act = ActDeployVyOS
		} else if s.RepUP < c.cfg.MaxUP && s.PodPendingCount == 0 && s.ReadyUP >= s.RepUP {
			act = ActScaleOutUP
		}
		if act != "" {
			var rev Action
			switch act {
			case ActDeployVyOS:
				rev = ActDeleteVyOS
			case ActScaleOutUP:
				rev = ActScaleInUP
			}
			if rev != "" {
				win := time.Duration((c.shadow.calib.Act[rev].TReadySec + c.shadow.calib.Act[act].TReadySec + v6Grid) * float64(time.Second))
				if c.shadow.RecentlyDispatched(rev, win) {
					c.log.Info("v6 emergency force suppressed: reverse of recent scale-in", "action", act, "recent", rev, "window_s", win.Seconds(), "path", "baseline")
					act = ""
				}
			}
		}
		if act != "" {
			*last = now
			c.log.Info("v6 emergency force", "action", act,
				"meas_up", meas.UP, "meas_vy", meas.VY, "path", "baseline")
			out = append(out, Decision{
				Action: act,
				Reason: fmt.Sprintf("v6 emergency force +1 (meas UP=%.4f VY=%.4f) [baseline]", meas.UP, meas.VY),
				At:     now,
			})
		}
	}
	return out
}
