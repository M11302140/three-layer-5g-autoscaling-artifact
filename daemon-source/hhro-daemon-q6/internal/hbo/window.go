package hbo

import (
	"context"
	"fmt"
	"log/slog"

	"github.com/anon/hhro-daemon/internal/promq"
)

// WindowCollector extracts windowed features from Prometheus for every metric
// the HBO-HHRO controller needs. PromQL templates are expanded once at build;
// each tick issues the queries and fills a FeatureSet.
type WindowCollector struct {
	prom *promq.Prom
	cfg  Cfg
	q    querySet
}

type querySet struct {
	// raw PromQL for each metric's "now" value
	cpuCP           string
	cpuUP           string
	meanCpuUP       string
	cpuVyos         string
	cpuVyosReal     string
	meanCpuVyosReal string
	readyCP         string
	dropUP          string
	pktRateUP       string
	bwUP            string
	ueCount         string

	vyosDropErr   string
	vyosLossRatio string
	vyosImbalance string

	workerCpu string
	workerMem string

	hhroCpScore   string
	hhroUpScore   string
	hhroVyosScore string
}

func NewWindowCollector(p *promq.Prom, cfg Cfg) *WindowCollector {
	q := defaultQuerySet(cfg)
	if cfg.EupfEnabled {
		q = eupfQuerySet(cfg, q)
	}
	return &WindowCollector{
		prom: p,
		cfg:  cfg,
		q:    q,
	}
}

// eupfQuerySet is the v5.0 metric source set for the eBPF/XDP eUPF data plane.
// Sources flip completely versus the open5gs-UPF set:
//   - pod cgroup CPU is meaningless (the XDP datapath runs in the worker VM's
//     kernel softirq; the eUPF Go process is ~idle) → the "CPU" features are
//     repurposed as PER-INSTANCE THROUGHPUT UTILIZATION: combined UL+DL pps
//     divided by the AMBR policy cap (EupfPpsCap). max/mean/sum keep their
//     old semantics ("hottest instance", "pool mean", "UPF-equivalents of
//     load"), so pressure/guards/bottleneck formulas carry over unchanged.
//   - container_network_* counters are blind (hostNetwork + XDP bypasses the
//     pod netdev) → throughput/drops come from the eUPF's own upf_xdp_*
//     Prometheus counters (job="eupf", 10.0.1.3x:9090). With the vftx image
//     both directions leave via XDP_TX on the instance's own VF, so
//     rate(upf_xdp_tx) ≈ UL + DL combined pps. upf_xdp_drop counts the
//     QER/AMBR policer — sustained drops == instances over policy cap.
//   - VyOS telegraf CPU is a DEAD signal with the 1-worker VPP config (pure
//     poll mode pins the worker core at 100% at ANY load; measured identical
//     34.7% cpu-total idle vs 4.8M) → queries kept for observability but the
//     score drops the CPU term (see pressure.go).
func eupfQuerySet(cfg Cfg, base querySet) querySet {
	perInst := `(rate(upf_xdp_tx{job="eupf"}[1m]) + rate(upf_xdp_redirect{job="eupf"}[1m]))`
	cap := cfg.EupfPpsCap
	if cap <= 0 {
		cap = 1200000
	}
	q := base
	q.cpuUP = fmt.Sprintf(`max(%s) / %.0f`, perInst, cap)
	q.meanCpuUP = fmt.Sprintf(`avg(%s) / %.0f`, perInst, cap)
	q.pktRateUP = `clamp_max(sum(rate(upf_xdp_tx{job="eupf"}[1m]) + rate(upf_xdp_redirect{job="eupf"}[1m])), 20000000)`
	// RATIO computed inside prometheus per-instant. Pod restarts reset the
	// upf_xdp_* counters; mixing drop/tx epochs in the daemon-side window
	// produced garbage (thr spikes to 291M pps, UpDrop stuck at 7 pinning
	// P_up=1 for 20+ min — smoke v2). clamp_min guards the division.
	q.dropUP = `clamp_max((sum(rate(upf_xdp_drop{job="eupf"}[1m])) + (sum(rate(upf_vf_rx_out_of_buffer[1m])) or vector(0)) + (sum(rate(upf_vf_rx_xdp_tx_full[1m])) or vector(0))) / clamp_min(sum(rate(upf_xdp_tx{job="eupf"}[1m]) + rate(upf_xdp_redirect{job="eupf"}[1m])) + (sum(rate(upf_vf_rx_out_of_buffer[1m])) or vector(0)), 1), 1)`
	// no byte counters in upf_xdp_* — bw term intentionally Missing so the
	// pressure throughput reduces to max(pps_util, 0) = pps_util.
	q.bwUP = ""
	return q
}

func defaultQuerySet(cfg Cfg) querySet {
	// Effective UPF capacity: the open5gs data plane is single-threaded, so a
	// pod saturates at ~UpEffCapCores regardless of its cgroup limit. Dividing
	// by the raw limit (e.g. 1500m) caps the utilization ratio at 0.66 and the
	// composite C_up at ~0.33 — below every "high" threshold — so scale-out
	// never fired until drops piled up. Normalize by min(limit, eff) instead.
	// Effective capacity ABOVE the idle floor. An open5gs UPF burns
	// UpIdleFloorCores (~0.18 core) just running its event loop + metrics at
	// ZERO traffic. Dividing raw cores by the cap left every idle pod reading
	// ~0.18 → with 7 pods SumCpuUP floored at ~1.3 and the max-term floored
	// C_up at ~0.34 (> UP_LOW 0.30), so BOTH scale-in paths stayed blocked
	// through the whole ramp-down and only released after ~6min at 0 UE (v4.15:
	// scale-in fired only in cool). Subtract the idle floor per-pod (clamped at
	// 0) and normalize by (eff − idle) so an idle UPF reads 0 and a saturated
	// one still reads ~1.0 — C_up/SumCpuUP now track REAL load and scale-in
	// fires in ramp-down. Scale-OUT is unaffected: a saturated pod still →1.0.
	idle := cfg.UpIdleFloorCores
	perPodBusy := fmt.Sprintf(
		`clamp_min(sum by(pod)(rate(container_cpu_usage_seconds_total{namespace="open5gs",pod=~"open5gs-upf(-[0-9]+)?-.*",container!="",container!="POD"}[1m])) - %.3f, 0)`,
		idle)
	upCap := fmt.Sprintf(
		`(clamp_max(sum by(pod)(kube_pod_container_resource_limits{namespace="open5gs",pod=~"open5gs-upf(-[0-9]+)?-.*",resource="cpu"}), %.3f) - %.3f)`,
		cfg.UpEffCapCores, idle)
	return querySet{
		// CP CPU: AMF has no resource limits, use raw cores normalized externally
		cpuCP: `sum(rate(container_cpu_usage_seconds_total{namespace="open5gs",pod=~"open5gs-amf-.*",container!="",container!="POD"}[1m]))`,

		// UPF CPU: MAX per-pod busy ratio (idle-floored). Catches the hottest UPF
		// even when other UPFs are idle. With aggregate sum/sum, a single
		// saturated UPF (993m/1000m) gets diluted by idle clones (0m/1000m)
		// → 50% instead of 99% → never triggers scale-out.
		cpuUP: `max(` + perPodBusy + ` / on(pod) group_left() ` + upCap + `)`,
		// MEAN per-pod busy ratio. C_up blends 0.6·max + 0.4·mean so pressure
		// reflects the POOL, not just the hottest pod — after scale-out+migrate
		// spread the load, mean (and thus C_up) actually drops, so bn can return
		// to NONE. Pure max kept C_up plateaued whenever any single pod stayed hot.
		meanCpuUP: `avg(` + perPodBusy + ` / on(pod) group_left() ` + upCap + `)`,

		// VyOS CPU: max per-VM guest utilization. rate[2m] matches 60s scrape
		// interval (needs ≥2 samples; [3m] mixed too much history and inflated
		// the value during stage transitions with idle gaps).
		cpuVyos: `max(sum by(name)(rate(kubevirt_vmi_vcpu_seconds_total{name=~".*vyos.*"}[2m])) / on(name) group_left() count by(name)(kubevirt_vmi_vcpu_seconds_total{name=~".*vyos.*"}))`,

		// Real VyOS guest CPU (%) from telegraf prometheus_client on each VyOS
		// (job="vyos"). max() = busiest VyOS in the pool. Captures SR-IOV
		// forwarding load the kubevirt vCPU metric undercounts. Uses
		// 100-idle (idle always exists) instead of cpu_usage_active, which the
		// scaled VyOS' NATIVE telegraf (set service monitoring telegraf
		// prometheus-client) doesn't export (no report_active there).
		// v4.34: RAW (no avg_over_time). v4.32 smoothed this query, but P_vyos uses
		// CpuVyosReal.Robust60Raw() → smoothing the query double-smoothed it and
		// HALVED the VyOS pressure signal (run#8 peak P_vyos 0.24 vs run#7 0.51).
		// The scale-in slope-guard false-positive is handled in guards.go instead
		// (require rising AND still-loaded), so the pressure magnitude is restored.
		cpuVyosReal: `max(100 - cpu_usage_idle{job="vyos",cpu="cpu-total"})`,
		// v4.50: POOL-MEAN VyOS CPU for scale-IN. The max above is spiked by the
		// route-move transients each UPF scale-in triggers during ramp-down (one
		// VyOS briefly gets the moved /32s) → it kept p.Vyos ≥ VyosLow the whole
		// ramp-down → VyOS only released in cool (run21-23 stuck at vy=3→2). The
		// mean reflects whether the POOL is over-provisioned, immune to a single
		// transient hot VyOS → scale-in steps down in pace with the load.
		meanCpuVyosReal: `avg(100 - cpu_usage_idle{job="vyos",cpu="cpu-total"})`,

		readyCP: `kube_deployment_status_replicas_ready{deployment="open5gs-amf",namespace="open5gs"} / clamp_min(kube_deployment_spec_replicas{deployment="open5gs-amf",namespace="open5gs"},1)`,

		dropUP:    `sum(rate(container_network_receive_packets_dropped_total{namespace="open5gs",pod=~"open5gs-upf(-[0-9]+)?-.*"}[1m]) + rate(container_network_transmit_packets_dropped_total{namespace="open5gs",pod=~"open5gs-upf(-[0-9]+)?-.*"}[1m]))`,
		pktRateUP: `sum(rate(container_network_receive_packets_total{namespace="open5gs",pod=~"open5gs-upf(-[0-9]+)?-.*"}[1m]) + rate(container_network_transmit_packets_total{namespace="open5gs",pod=~"open5gs-upf(-[0-9]+)?-.*"}[1m]))`,
		// v4.70: aggregate UPF data-plane bandwidth in Mbps (bytes*8/1e6) for the max(pps,bw) throughput term.
		bwUP: `sum(rate(container_network_receive_bytes_total{namespace="open5gs",pod=~"open5gs-upf(-[0-9]+)?-.*"}[1m]) + rate(container_network_transmit_bytes_total{namespace="open5gs",pod=~"open5gs-upf(-[0-9]+)?-.*"}[1m])) * 8 / 1e6`,

		// UE count is fetched via SSH by daemon, we read the exported gauge
		ueCount: `hhro_ue_count`,

		vyosDropErr:   `sum(rate(kubevirt_vmi_network_receive_errors_total{name=~".*vyos.*"}[2m]) + rate(kubevirt_vmi_network_transmit_errors_total{name=~".*vyos.*"}[2m]) + rate(kubevirt_vmi_network_receive_packets_dropped_total{name=~".*vyos.*"}[2m]) + rate(kubevirt_vmi_network_transmit_packets_dropped_total{name=~".*vyos.*"}[2m]))`,
		vyosLossRatio: `sum(rate(vpp_iface_rx_out_of_buffer{interface="eth1"}[2m]) + rate(vpp_iface_drops{interface="eth1"}[2m])) / clamp_min(sum(rate(vpp_iface_rx_packets{interface="eth1"}[2m]) + rate(vpp_iface_rx_out_of_buffer{interface="eth1"}[2m]) + rate(vpp_iface_drops{interface="eth1"}[2m])), 1)`,
		vyosImbalance: `max(sum by(name)(rate(kubevirt_vmi_vcpu_seconds_total{name=~".*vyos.*"}[2m])) / on(name) group_left() count by(name)(kubevirt_vmi_vcpu_seconds_total{name=~".*vyos.*"})) - min(sum by(name)(rate(kubevirt_vmi_vcpu_seconds_total{name=~".*vyos.*"}[2m])) / on(name) group_left() count by(name)(kubevirt_vmi_vcpu_seconds_total{name=~".*vyos.*"}))`,

		workerCpu: `1 - avg(rate(node_cpu_seconds_total{mode="idle",source!="harvester",instance!~"192\\.168\\.0\\.50:.*"}[2m]))`,
		workerMem: `1 - sum(node_memory_MemAvailable_bytes{source!="harvester",instance!~"192\\.168\\.0\\.50:.*"})/clamp_min(sum(node_memory_MemTotal_bytes{source!="harvester",instance!~"192\\.168\\.0\\.50:.*"}),1)`,

		hhroCpScore:   `hhro_pressure_cp`,
		hhroUpScore:   `hhro_pressure_up`,
		hhroVyosScore: `hhro_pressure_vyos`,
	}
}

func (wc *WindowCollector) scalar(ctx context.Context, q string) float64 {
	v, err := wc.prom.QueryScalar(ctx, q)
	if err != nil {
		return 0
	}
	return v
}

// wrapWindow generates windowed PromQL from a raw instant query.
func wrapAvg(raw, window string) string {
	return fmt.Sprintf("avg_over_time((%s)[%s:])", raw, window)
}

func wrapQuantile(raw string, q float64, window string) string {
	return fmt.Sprintf("quantile_over_time(%g, (%s)[%s:])", q, raw, window)
}

func wrapDeriv(raw, window string) string {
	return fmt.Sprintf("deriv((%s)[%s:])", raw, window)
}

func (wc *WindowCollector) collectFeature(ctx context.Context, raw string) WindowFeature {
	if raw == "" {
		return WindowFeature{Missing: true}
	}
	ws := wc.cfg.WindowShort
	wsl := wc.cfg.WindowSlope
	wl := wc.cfg.WindowLong
	wi := wc.cfg.WindowIdle

	f := WindowFeature{
		Now:      wc.scalar(ctx, raw),
		Avg30:    wc.scalar(ctx, wrapAvg(raw, "30s")), // v4.49: faster sustained-low window for VyOS scale-in (rd2/rd3 vs cool)
		Avg60:    wc.scalar(ctx, wrapAvg(raw, ws)),
		P90_60:   wc.scalar(ctx, wrapQuantile(raw, 0.90, ws)),
		P95_300:  wc.scalar(ctx, wrapQuantile(raw, 0.95, wl)),
		P95_600:  wc.scalar(ctx, wrapQuantile(raw, 0.95, wi)),
		Slope120: wc.scalar(ctx, wrapDeriv(raw, wsl)),
		Slope300: wc.scalar(ctx, wrapDeriv(raw, wl)),
	}
	// Mark missing if we got 0 for everything and the raw query returned 0
	// This is normal for idle metrics — not actually missing.
	return f
}

// collectFeatureGauge is like collectFeature but for gauges that are already
// exported by the daemon (hhro_pressure_*). These don't need wrapping with
// rate() and are simple gauges that Prometheus can directly window.
func (wc *WindowCollector) collectFeatureGauge(ctx context.Context, raw string) WindowFeature {
	if raw == "" {
		return WindowFeature{Missing: true}
	}
	// Check if the metric exists at all
	v := wc.scalar(ctx, raw)
	if v == 0 {
		// Could be truly 0 or missing — try to distinguish
		samples, err := wc.prom.Query(ctx, raw)
		if err != nil || len(samples) == 0 {
			return WindowFeature{Missing: true}
		}
	}
	return wc.collectFeature(ctx, raw)
}

// CollectFeatures queries Prometheus for all window features needed by HBO-HHRO.
func (wc *WindowCollector) CollectFeatures(ctx context.Context) FeatureSet {
	// For CP CPU: AMF has no resource limits, so raw query returns cores.
	// We normalize by CpCpuNorm in the pressure calculation, not here.
	// The window features should be on the raw value so derivatives are correct.
	cpuCPRaw := wc.q.cpuCP

	f := FeatureSet{
		CpuCP:           wc.collectFeature(ctx, cpuCPRaw),
		CpuUP:           wc.collectFeature(ctx, wc.q.cpuUP),
		MeanCpuUP:       wc.collectFeature(ctx, wc.q.meanCpuUP),
		CpuVyos:         wc.collectFeature(ctx, wc.q.cpuVyos),
		CpuVyosReal:     wc.collectFeature(ctx, wc.q.cpuVyosReal),
		MeanCpuVyosReal: wc.collectFeature(ctx, wc.q.meanCpuVyosReal),
		ReadyCP:         wc.collectFeature(ctx, wc.q.readyCP),
		DropUP:          wc.collectFeature(ctx, wc.q.dropUP),
		PktRateUP: func() WindowFeature {
			ft := wc.collectFeature(ctx, wc.q.pktRateUP)
			slog.Info("win pktRateUP", "now", ft.Now, "avg60", ft.Avg60, "p90_60", ft.P90_60, "q", wc.q.pktRateUP[:60])
			return ft
		}(),
		BwUP:          wc.collectFeature(ctx, wc.q.bwUP),
		VyosDropErr:   wc.collectFeature(ctx, wc.q.vyosDropErr),
		VyosLossRatio: wc.collectFeature(ctx, wc.q.vyosLossRatio),
		VyosImbalance: wc.collectFeature(ctx, wc.q.vyosImbalance),

		WorkerCpu: wc.collectFeature(ctx, wc.q.workerCpu),
		WorkerMem: wc.collectFeature(ctx, wc.q.workerMem),
	}

	// UE count: fetched by daemon via SSH, exported as hhro_ue_count gauge.
	// May not exist if ue probe is disabled.
	f.UECount = wc.collectFeatureGauge(ctx, wc.q.ueCount)

	// HHRO exported scores: only available after daemon has been running.
	f.HhroCpScore = wc.collectFeatureGauge(ctx, wc.q.hhroCpScore)
	f.HhroUpScore = wc.collectFeatureGauge(ctx, wc.q.hhroUpScore)
	f.HhroVyosScore = wc.collectFeatureGauge(ctx, wc.q.hhroVyosScore)

	return f
}

// metricAvailable checks if a feature was successfully collected.
func metricAvailable(f WindowFeature) bool {
	return !f.Missing
}

// norm normalizes a raw value to [0,1].
func norm(val, maxVal float64) float64 {
	if maxVal <= 0 {
		return 0
	}
	return clamp01(val / maxVal)
}

// cpuCPNormalized returns the CP CPU feature with values normalized by CpCpuNorm.
// This is needed because AMF has no resource limits set.
func cpuCPNormalized(f WindowFeature, cpuNorm float64) WindowFeature {
	if cpuNorm <= 0 {
		return f
	}
	return WindowFeature{
		Now:      clamp01(f.Now / cpuNorm),
		Avg60:    clamp01(f.Avg60 / cpuNorm),
		P90_60:   clamp01(f.P90_60 / cpuNorm),
		P95_300:  clamp01(f.P95_300 / cpuNorm),
		P95_600:  clamp01(f.P95_600 / cpuNorm),
		Slope120: f.Slope120 / cpuNorm,
		Slope300: f.Slope300 / cpuNorm,
		Missing:  f.Missing,
	}
}
