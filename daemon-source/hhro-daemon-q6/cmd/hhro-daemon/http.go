package main

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"github.com/anon/hhro-daemon/internal/envcfg"
	"github.com/anon/hhro-daemon/internal/hbo"
	"github.com/anon/hhro-daemon/internal/state"
)

func (d *Daemon) writeMetrics(w http.ResponseWriter, _ *http.Request) {
	d.mu.RLock()
	st, sc := d.lastMid, d.lastScore
	d.mu.RUnlock()

	w.Header().Set("Content-Type", "text/plain; version=0.0.4")
	g := func(name, help string, v float64) {
		fmt.Fprintf(w, "# HELP %s %s\n# TYPE %s gauge\n%s %g\n", name, help, name, name, v)
	}

	// Legacy scores (backwards compat)
	g("hhro_cp_score", "legacy control-plane cost C^cp", sc.Cp)
	g("hhro_up_score", "legacy user-plane cost C^up", sc.Up)
	g("hhro_infra_score", "legacy infrastructure cost C^infra", sc.Infra)
	g("hhro_j", "legacy total objective J", sc.J)

	// Standard state
	g("hhro_cp_replicas", "rep_cp", float64(st.Cp.Rep))
	g("hhro_up_replicas", "rep_up", float64(st.Up.Rep))
	g("hhro_cp_ready_ratio", "ready_ratio_cp", st.Q.ReadyRatioCp)
	g("hhro_up_ready_ratio", "ready_ratio_up", st.Q.ReadyRatioUp)
	g("hhro_up_bw_bps", "user-plane bandwidth bps", st.Up.Bw)
	g("hhro_up_drop_pps", "user-plane drop pps", st.Up.Drop)
	g("hhro_db_latency_us", "db write latency us", st.Db.Lat)
	g("hhro_vyos_cpu", "vyos cpu fraction", st.V.Cpu)
	g("hhro_vyos_bw_bps", "vyos forwarding bps", st.V.Bw)
	g("hhro_n_w", "worker node count", float64(st.W.N))
	g("hhro_n_vyos", "vyos VM count (incl base test-vyos)", float64(st.V.Count))
	g("hhro_alloc_cpu_m", "allocatable cpu millicores", st.W.AllocCpu)
	g("hhro_ue_count", "attached UE count", float64(st.Q.UeCount))

	// HBO-HHRO pressure scores
	_, p, risk, bn := d.hboSnapshot()
	g("hhro_pressure_cp", "HBO CP pressure score", p.CP)
	g("hhro_pressure_up", "HBO UP pressure score", p.UP)
	g("hhro_pressure_vyos", "HBO VyOS pressure score", p.Vyos)

	// HBO-HHRO risk scores
	g("hhro_risk_cp", "HBO CP short-horizon risk", risk.CP)
	g("hhro_risk_up", "HBO UP short-horizon risk", risk.UP)
	g("hhro_risk_vyos", "HBO VyOS short-horizon risk", risk.Vyos)

	// HBO bottleneck (as numeric for Prom)
	bnVal := map[hbo.Bottleneck]float64{
		hbo.BNNone: 0, hbo.BNCP: 1, hbo.BNUPF: 2,
		hbo.BNVyos: 3, hbo.BNInfra: 4, hbo.BNMixed: 5,
	}
	g("hhro_bottleneck", "HBO bottleneck type (0=none,1=cp,2=upf,3=vyos,4=infra,5=mixed)", bnVal[bn])

	// Bottleneck as labeled metric
	for _, b := range []hbo.Bottleneck{hbo.BNNone, hbo.BNCP, hbo.BNUPF, hbo.BNVyos, hbo.BNInfra, hbo.BNMixed} {
		v := float64(0)
		if b == bn {
			v = 1
		}
		fmt.Fprintf(w, "hhro_bottleneck_type{type=%q} %g\n", string(b), v)
	}

	// v6 shadow planner (P2: logged decisions, never actuated)
	if d.hbo != nil {
		if best, noopJ, resid, emerg, valid := d.hbo.Shadow().Snapshot(); valid {
			g("hhro_v6_best_j", "v6 shadow: J of the argmin tuple", best.J)
			g("hhro_v6_noop_j", "v6 shadow: J of the NoOp tuple", noopJ)
			g("hhro_v6_resid_up", "v6 shadow: UP curve residual", resid.UP)
			g("hhro_v6_resid_vy", "v6 shadow: VY curve residual", resid.VY)
			ev := float64(0)
			if emerg {
				ev = 1
			}
			g("hhro_v6_emergency", "v6 shadow: measured-level emergency gate", ev)
			fmt.Fprintf(w, "hhro_v6_best_tuple{tuple=%q} 1\n", best.Key)
		}
	}
}

func (d *Daemon) writeState(w http.ResponseWriter, _ *http.Request) {
	d.mu.RLock()
	defer d.mu.RUnlock()

	_, p, risk, bn := d.hboSnapshot()

	var v6 map[string]any
	if d.hbo != nil {
		if best, noopJ, resid, emerg, valid := d.hbo.Shadow().Snapshot(); valid {
			v6 = map[string]any{
				"tuple": best.Key, "j": best.J, "j_noop": noopJ,
				"resid_up": resid.UP, "resid_vy": resid.VY, "emergency": emerg,
				"inflight": d.hbo.V6InFlight(),
				"q":        d.hbo.V6QState(),
			}
		}
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(struct {
		Mid      state.State     `json:"mid"`
		Slow     state.State     `json:"slow"`
		Scores   state.Scores    `json:"scores"`
		Pressure hbo.PressureSet `json:"pressure"`
		Risk     hbo.RiskSet     `json:"risk"`
		BN       hbo.Bottleneck  `json:"bottleneck"`
		V6Shadow map[string]any  `json:"v6_shadow,omitempty"`
	}{d.lastMid, d.lastSlow, d.lastScore, p, risk, bn, v6})
}

func (d *Daemon) handleDecideLast(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	if d.hbo == nil {
		json.NewEncoder(w).Encode(map[string]string{"action": "NONE", "reason": "controller not initialized"})
		return
	}
	last := d.hbo.LastDecision()
	if last == nil {
		json.NewEncoder(w).Encode(map[string]string{"action": "NONE", "reason": "no decision recorded yet"})
		return
	}
	out := map[string]any{
		"action":     last.Action,
		"bottleneck": last.Bottleneck,
		"reason":     last.Reason,
		"at":         last.At.UTC().Format(time.RFC3339Nano),
		"age_sec":    envcfg.Round3(time.Since(last.At).Seconds()),
		"pressure": map[string]float64{
			"cp":   envcfg.Round3(last.Pressure.CP),
			"up":   envcfg.Round3(last.Pressure.UP),
			"vyos": envcfg.Round3(last.Pressure.Vyos),
		},
		"risk": map[string]float64{
			"cp":   envcfg.Round3(last.Risk.CP),
			"up":   envcfg.Round3(last.Risk.UP),
			"vyos": envcfg.Round3(last.Risk.Vyos),
		},
	}
	if last.BlockedBy != "" {
		out["blocked_by"] = last.BlockedBy
	}
	if active, remain := d.freeze.Active(); active {
		out["frozen"] = true
		out["frozen_left_sec"] = envcfg.Round3(remain.Seconds())
	}
	json.NewEncoder(w).Encode(out)
}

func (d *Daemon) handleScaleUp(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "POST", http.StatusMethodNotAllowed)
		return
	}
	if d.act == nil {
		http.Error(w, "actuator disabled", http.StatusPreconditionFailed)
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 30*time.Second)
	defer cancel()
	name, err := d.act.CreateWorker(ctx, r.URL.Query().Get("force") == "true")
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"created": name})
}

func (d *Daemon) handleScaleDown(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "POST", http.StatusMethodNotAllowed)
		return
	}
	if d.act == nil {
		http.Error(w, "actuator disabled", http.StatusPreconditionFailed)
		return
	}
	name := r.URL.Query().Get("name")
	if name == "" {
		http.Error(w, "?name=worker-N required", http.StatusBadRequest)
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 30*time.Second)
	defer cancel()
	if err := d.act.DeleteWorker(ctx, name, r.URL.Query().Get("force") == "true"); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	w.Write([]byte("ok"))
}

func (d *Daemon) handleScaleVyosUp(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "POST", http.StatusMethodNotAllowed)
		return
	}
	if d.act == nil {
		http.Error(w, "actuator disabled", http.StatusPreconditionFailed)
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 30*time.Second)
	defer cancel()
	name, err := d.act.DeployVyOS(ctx, r.URL.Query().Get("force") == "true")
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"created": name})
}

func (d *Daemon) handleScaleVyosDown(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "POST", http.StatusMethodNotAllowed)
		return
	}
	if d.act == nil {
		http.Error(w, "actuator disabled", http.StatusPreconditionFailed)
		return
	}
	name := r.URL.Query().Get("name")
	if name == "" {
		http.Error(w, "?name=vyos-N required", http.StatusBadRequest)
		return
	}
	if r.URL.Query().Get("drain") == "true" {
		d.vyDrainMu.Lock()
		if d.vyDrainIP != "" {
			inflight := d.vyDrainIP
			d.vyDrainMu.Unlock()
			http.Error(w, "drain in flight: "+inflight, http.StatusConflict)
			return
		}
		d.vyDrainIP = name
		d.vyDrainMu.Unlock()
		d.log.Info("manual delete_vyos with drain", "name", name)
		go d.drainAndDeleteVyos(name)
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{"draining": name})
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 30*time.Second)
	defer cancel()
	if err := d.act.DeleteVyOS(ctx, name, r.URL.Query().Get("force") == "true"); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"deleted": name})
}

func (d *Daemon) handleScaleUpfUp(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "POST", http.StatusMethodNotAllowed)
		return
	}
	if d.eupfAct == nil {
		http.Error(w, "upf actuator disabled", http.StatusPreconditionFailed)
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 120*time.Second)
	defer cancel()
	var name string
	var err error
	name, err = d.eupfAct.DeployUPF(ctx, r.URL.Query().Get("force") == "true")
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	if r.URL.Query().Get("rehome") == "true" && d.eupfAct != nil {
		go func(slot string) {
			rctx, cancel := context.WithTimeout(context.Background(), 12*time.Minute)
			defer cancel()
			if rerr := d.eupfAct.RebalanceInto(rctx, slot, true); rerr != nil {
				d.log.Warn("manual rehome (scale-out) failed", "slot", slot, "err", rerr)
				return
			}
			d.log.Info("manual rehome (scale-out) done", "slot", slot)
		}(name)
	}
	json.NewEncoder(w).Encode(map[string]string{"created": name})
}

func (d *Daemon) handleScaleUpfDown(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "POST", http.StatusMethodNotAllowed)
		return
	}
	if d.eupfAct == nil {
		http.Error(w, "upf actuator disabled", http.StatusPreconditionFailed)
		return
	}
	name := r.URL.Query().Get("name")
	if name == "" && d.eupfAct != nil {
		// eupf mode: default to the daemon's own reverse-activation-order pick
		if t, err := d.eupfAct.PickScaleInTarget(r.Context()); err == nil {
			name = t
		}
	}
	if name == "" {
		http.Error(w, "?name=open5gs-upf-N (or eupf-N) required", http.StatusBadRequest)
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 60*time.Second)
	defer cancel()
	var err error
	if d.eupfAct != nil {
		if r.URL.Query().Get("drain") == "true" {
			// drain-then-delete, async (a 4-UE drain takes minutes)
			go func(slot string) {
				rctx, cancel := context.WithTimeout(context.Background(), 12*time.Minute)
				defer cancel()
				if rerr := d.eupfAct.DrainAndDelete(rctx, slot); rerr != nil {
					d.log.Warn("manual drain-delete failed", "slot", slot, "err", rerr)
					return
				}
				d.log.Info("manual drain-delete done", "slot", slot)
			}(name)
			w.Header().Set("Content-Type", "application/json")
			json.NewEncoder(w).Encode(map[string]string{"draining": name})
			return
		}
		err = d.eupfAct.DeleteUPF(ctx, name, r.URL.Query().Get("force") == "true")
	}
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"deleted": name})
}

func (d *Daemon) handleHintTransition(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "POST", http.StatusMethodNotAllowed)
		return
	}
	dur := d.transitionDefault
	if s := r.URL.Query().Get("dwell"); s != "" {
		if v, err := time.ParseDuration(s); err == nil && v > 0 {
			dur = v
		}
	}
	stage := r.URL.Query().Get("stage")
	d.freeze.Set(dur)
	d.log.Info("hint transition", "stage", stage, "dwell", dur)
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]any{"frozen_for": dur.String(), "stage": stage})
}

func (d *Daemon) handleAutoscaleSet(enable bool) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "POST", http.StatusMethodNotAllowed)
			return
		}
		if d.hbo != nil {
			if enable {
				d.hbo.V6ResetEpisode()
			}
			d.hbo.SetEnabled(enable)
		}
		d.log.Info("autoscale toggled", "enabled", enable)
		w.Write([]byte(fmt.Sprintf("autoscale=%v\n", enable)))
	}
}

func (d *Daemon) handleAutoscaleStatus(w http.ResponseWriter, _ *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	enabled := false
	if d.hbo != nil {
		enabled = d.hbo.IsEnabled()
	}
	json.NewEncoder(w).Encode(map[string]any{"enabled": enabled})
}

func (d *Daemon) registerHandlers(mux *http.ServeMux) {
	mux.HandleFunc("/metrics", d.writeMetrics)
	mux.HandleFunc("/state", d.writeState)
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, _ *http.Request) { w.Write([]byte("ok")) })
	mux.HandleFunc("/scale/worker/up", d.handleScaleUp)
	mux.HandleFunc("/provision/worker", d.handleProvisionWorker) // v5.0.1: manual eUPF VF provisioning
	mux.HandleFunc("/scale/worker/down", d.handleScaleDown)
	mux.HandleFunc("/host/vfio-pin", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			http.Error(w, "POST", http.StatusMethodNotAllowed)
			return
		}
		d.hostVfioIrqPin("manual")
		w.Write([]byte("ok\n"))
	})
	mux.HandleFunc("/scale/vyos/up", d.handleScaleVyosUp)
	mux.HandleFunc("/scale/vyos/down", d.handleScaleVyosDown)
	mux.HandleFunc("/scale/upf/up", d.handleScaleUpfUp)
	mux.HandleFunc("/scale/upf/down", d.handleScaleUpfDown)
	mux.HandleFunc("/autoscale/enable", d.handleAutoscaleSet(true))
	mux.HandleFunc("/autoscale/disable", d.handleAutoscaleSet(false))
	mux.HandleFunc("/hint/transition", d.handleHintTransition)
	mux.HandleFunc("/decide/last", d.handleDecideLast)
	mux.HandleFunc("/autoscale/status", d.handleAutoscaleStatus)
}

// handleProvisionWorker manually (re)runs the eUPF VF provisioning on a worker
// (?node=worker-N). Use after a worker reboot/recreate or a DN MAC change —
// the same routine the daemon runs automatically after CreateWorker.
func (d *Daemon) handleProvisionWorker(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "POST", http.StatusMethodNotAllowed)
		return
	}
	if d.eupfAct == nil {
		http.Error(w, "eupf actuator disabled", http.StatusPreconditionFailed)
		return
	}
	node := r.URL.Query().Get("node")
	if node == "" {
		http.Error(w, "?node=worker-N required", http.StatusBadRequest)
		return
	}
	ctx, cancel := context.WithTimeout(r.Context(), 5*time.Minute)
	defer cancel()
	if err := d.eupfAct.ProvisionWorkerVFs(ctx, node, 4*time.Minute); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"provisioned": node})
}
