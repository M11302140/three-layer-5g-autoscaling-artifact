// hhro-daemon — HBO-HHRO: History-aware Bottleneck-Oriented Hierarchical
// Hybrid NF Resource Orchestrator. Non-learning controller using Prometheus
// window statistics, bottleneck classification, and constrained utility
// selection to coordinate CNF, VNF, and worker-level scaling.
package main

import (
	"context"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/anon/hhro-daemon/internal/actuate"
	"github.com/anon/hhro-daemon/internal/collect"
	"github.com/anon/hhro-daemon/internal/envcfg"
	"github.com/anon/hhro-daemon/internal/harvester"
	"github.com/anon/hhro-daemon/internal/hbo"
	"github.com/anon/hhro-daemon/internal/master"
	"github.com/anon/hhro-daemon/internal/promq"
	"github.com/anon/hhro-daemon/internal/sshexec"
	"github.com/anon/hhro-daemon/internal/state"
)

func main() {
	log := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo}))
	slog.SetDefault(log)

	promURL := envcfg.Get("PROM_URL", "http://kps-kube-prometheus-stack-prometheus.monitoring.svc:9090")
	listen := envcfg.Get("LISTEN", ":8080")
	mid := envcfg.Dur("MID_INTERVAL", 30*time.Second)
	slow := envcfg.Dur("SLOW_INTERVAL", 5*time.Minute)

	w := state.DefaultWeights()
	w.A = envcfg.Float("ALPHA", w.A)
	w.B = envcfg.Float("BETA", w.B)
	w.G = envcfg.Float("GAMMA", w.G)
	n := state.DefaultNorms()
	n.MaxBwBps = envcfg.Float("MAX_BW_BPS", n.MaxBwBps)
	n.MaxDropPps = envcfg.Float("MAX_DROP_PPS", n.MaxDropPps)
	n.MaxLatUs = envcfg.Float("MAX_LAT_US", n.MaxLatUs)

	freeze := state.NewFreeze()
	steady := state.NewSteadyGate()
	prom := promq.New(promURL)

	// HBO-HHRO controller
	hboCfg := hbo.DefaultCfg()
	hboCtrl := hbo.NewController(hboCfg, prom, freeze, log)

	d := &Daemon{
		col:               collect.New(prom, collect.DefaultQueries()),
		weights:           w,
		norms:             n,
		freeze:            freeze,
		steady:            steady,
		hbo:               hboCtrl,
		transitionDefault: envcfg.Dur("TRANSITION_FREEZE_DEFAULT", 30*time.Second),
		log:               log,
	}
	log.Info("hbo-hhro autoscale", "enabled", hboCtrl.IsEnabled())
	log.Info("freeze ready", "transition_default", d.transitionDefault)

	// Optional actuator
	if os.Getenv("HARVESTER_URL") != "" {
		hv, err := harvester.NewFromEnv()
		if err != nil {
			log.Error("harvester init failed; actuator disabled", "err", err)
		} else {
			act := &actuate.Actuator{
				H:       hv,
				Cfg:     actuate.DefaultWorkerCfg(),
				VyosCfg: actuate.DefaultVyosCfg(),
				Groups:  actuate.DefaultGroupCfg(),
			}
			if jc, err := master.NewFromEnv(); err != nil {
				log.Warn("master-cluster client unavailable", "err", err)
			} else {
				act.M = jc
				act.JoinProvider = jc.IssueJoinCommand
				act.NodeReaper = jc.DrainAndDeleteNode
			}
			d.act = act
			d.col = collect.NewWithHarvester(prom, hv, collect.DefaultQueries())
			log.Info("actuator ready",
				"harvester", os.Getenv("HARVESTER_URL"),
				"image", act.Cfg.ImageRef,
				"vyos_image", act.VyosCfg.ImageRef)

			if act.M != nil && sshexec.Enabled() {
				host := sshexec.NewFromEnv()
				if err := host.SanityCheck(); err != nil {
					log.Warn("upf actuator disabled (host ssh sanity)", "err", err)
				} else {
					act.Host = host
					// v5.0: eUPF slot actuator replaces the open5gs clone
					// flow; the legacy CNF rebalancer/dual-leg paths stay off.
					d.eupfAct = actuate.NewEupfActuator(act, host)
					d.ueProbe = sshexec.NewUeProbe(host, envcfg.Get("UERANSIM_NR_CLI", "/home/user/UERANSIM/build/nr-cli"))
					log.Info("eupf actuator ready", "slots", len(d.eupfAct.Cfg.Slots), "image", d.eupfAct.Cfg.Image)
				}
			}
		}
	}

	mux := http.NewServeMux()
	d.registerHandlers(mux)
	srv := &http.Server{Addr: listen, Handler: mux}

	ctx, cancel := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer cancel()

	go func() {
		log.Info("http listen", "addr", listen)
		go func() { time.Sleep(30 * time.Second); d.hostVfioIrqPin("startup") }()
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Error("http", "err", err)
		}
	}()

	d.tickMid(ctx)
	d.tickSlow(ctx)

	tMid := time.NewTicker(mid)
	tSlow := time.NewTicker(slow)
	defer tMid.Stop()
	defer tSlow.Stop()

	log.Info("hbo-hhro daemon started",
		"prom", promURL, "mid", mid.String(), "slow", slow.String())

	for {
		select {
		case <-ctx.Done():
			shutdown, cancelShutdown := context.WithTimeout(context.Background(), 5*time.Second)
			srv.Shutdown(shutdown)
			cancelShutdown()
			log.Info("bye")
			return
		case <-tMid.C:
			d.tickMid(ctx)
		case <-tSlow.C:
			d.tickSlow(ctx)
		}
	}
}
