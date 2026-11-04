// Package collect runs the PromQL queries that derive each State_t field
// per goal.md §1. All query strings are gathered here so the operator can
// tweak them without touching logic.
package collect

import (
	"context"
	"regexp"
	"strings"
	"time"

	"github.com/anon/hhro-daemon/internal/harvester"
	"github.com/anon/hhro-daemon/internal/promq"
	"github.com/anon/hhro-daemon/internal/state"
	"github.com/anon/hhro-daemon/internal/envcfg"
)

type Queries struct {
	WorkerNodeFilter string
	VyosNameRegex    string
	AmfRegex         string
	UpfRegex         string
	MongoRegex       string
	AmfDeployment    string
	UpfDeployment    string
	MongoDeployment  string
	Open5gsNs        string
	// v5.0: eUPF data plane — the UPF group is bare pods (eupf-0..7), not
	// deployments; Rep/Ready count pods instead of deployment replicas.
	EupfMode bool
}

func DefaultQueries() Queries {
	eupf := envcfg.Get("EUPF_ENABLED", "true") == "true"
	upfRegex := `open5gs-upf(-[0-9]+)?-.*`
	if eupf {
		upfRegex = `eupf-[0-9]+`
	}
	return Queries{
		EupfMode:         eupf,
		WorkerNodeFilter: `node!=""`,
		VyosNameRegex:    `.*vyos.*`,
		AmfRegex:         `open5gs-amf-.*`,
		UpfRegex:         upfRegex,
		MongoRegex:       `open5gs-mongodb-.*`,
		AmfDeployment:    `open5gs-amf`,
		UpfDeployment:    `open5gs-upf(-[0-9]+)?`,
		MongoDeployment:  `open5gs-mongodb`,
		Open5gsNs:        `open5gs`,
	}
}

type Collector struct {
	Prom *promq.Prom
	H    *harvester.Harvester // optional; if nil, V.Count falls back to Prometheus
	q    Queries
}

func New(p *promq.Prom, q Queries) *Collector { return &Collector{Prom: p, q: q} }

// NewWithHarvester is preferred — it gives V.Count a real-time KubeVirt source
// instead of Prometheus-scraped count, which lags 60s+ after spawn and made the
// autoscaler think the pool was smaller than it actually was → cascaded extra
// scale_outs.
func NewWithHarvester(p *promq.Prom, h *harvester.Harvester, q Queries) *Collector {
	return &Collector{Prom: p, H: h, q: q}
}

func (c *Collector) expand(s string) string {
	r := strings.NewReplacer(
		"{NS}", c.q.Open5gsNs,
		"{AMF}", c.q.AmfRegex,
		"{UPF}", c.q.UpfRegex,
		"{MONGO}", c.q.MongoRegex,
		"{VYOS}", c.q.VyosNameRegex,
		"{DEP_AMF}", c.q.AmfDeployment,
		"{DEP_UPF}", c.q.UpfDeployment,
	)
	return r.Replace(s)
}

func (c *Collector) scalar(ctx context.Context, q string) float64 {
	v, err := c.Prom.QueryScalar(ctx, c.expand(q))
	if err != nil {
		return 0
	}
	return v
}

func (c *Collector) Collect(ctx context.Context) state.State {
	st := state.State{Time: time.Now().UTC()}

	// ---- W_t : CNF-bearing workers ONLY (master excluded, O9 2026-05-20) ----
	st.W.N = int(c.scalar(ctx, `count(kube_node_info{node=~"worker-.*"})`))
	st.W.Ready = int(c.scalar(ctx,
		`count(kube_node_status_condition{condition="Ready",status="true",node=~"worker-.*"})`))
	st.W.VMCount = c.countWorkerVMs(ctx)
	st.W.IdleWorker = c.idleWorker(ctx)
	st.W.Cpu = c.scalar(ctx,
		`1 - avg(rate(node_cpu_seconds_total{mode="idle",source!="harvester",instance!~"192\\.168\\.0\\.50:.*"}[2m]))`)
	st.W.Mem = c.scalar(ctx,
		`1 - sum(node_memory_MemAvailable_bytes{source!="harvester",instance!~"192\\.168\\.0\\.50:.*"})/sum(node_memory_MemTotal_bytes{source!="harvester",instance!~"192\\.168\\.0\\.50:.*"})`)
	st.W.AllocCpu = c.scalar(ctx,
		`(sum(kube_node_status_allocatable{resource="cpu",node=~"worker-.*"})
		 - sum(kube_pod_container_resource_requests{resource="cpu",node=~"worker-.*"})) * 1000`)
	// Max free CPU on the SINGLE least-loaded worker (millicores). Used for
	// per-worker bin-packing: a worker is only created when even the emptiest
	// existing worker can't fit another UPF — not just when AGGREGATE free is
	// low (which over-creates when one worker is full but another has room).
	// Exclude worker-0 (the infra node, labelled hhro.io/infra): UPF clones have
	// a required nodeAffinity that forbids it, so its free CPU does NOT mean a UPF
	// can fit. Counting it deadlocked scale-out (daemon saw worker-0 free → never
	// created a scaled worker → clone stuck Pending). With no scaled worker the
	// max over the empty set is 0 → BN_INFRA → a real worker is created.
	// `allocatable - requests` drops nodes with NO pod requests (empty workers
	// have no request series → vector match drops them), so an idle scaled worker
	// was invisible → daemon thought no worker could fit a UPF and created workers
	// forever instead of scaling UPFs onto them. Default missing requests to 0 via
	// `(requests or allocatable*0)` so empty workers count at full free capacity.
	st.W.MaxFreeCpu = c.scalar(ctx,
		`max(
		   sum by(node)(kube_node_status_allocatable{resource="cpu",node=~"worker-.*",node!="worker-0"})
		   - (sum by(node)(kube_pod_container_resource_requests{resource="cpu",node=~"worker-.*",node!="worker-0"})
		      or sum by(node)(kube_node_status_allocatable{resource="cpu",node=~"worker-.*",node!="worker-0"}) * 0)
		 ) * 1000`)
	st.W.AllocMem = c.scalar(ctx,
		`sum(kube_node_status_allocatable{resource="memory",node=~"worker-.*"})
		 - sum(kube_pod_container_resource_requests{resource="memory",node=~"worker-.*"})`)

	// ---- V_t : VyOS VM (federated kubevirt metrics) ----
	st.V.Exist = c.scalar(ctx,
		`count(kubevirt_vmi_memory_available_bytes{name=~"{VYOS}"})
		 + count(kubevirt_vmi_network_traffic_bytes_total{name=~"{VYOS}"}) > 0`) > 0
	// cpu_v = max per-VM GUEST utilization. Two fixes from v22l post-mortem:
	//
	// (1) Switched from `kubevirt_vmi_cpu_usage_seconds_total` (host-side QEMU
	//     process CPU collected by virt-handler — includes hypervisor + I/O
	//     overhead; observed 0.03 at idle vs guest's true 0.003) to
	//     `kubevirt_vmi_vcpu_seconds_total` (per-vCPU guest active time, what
	//     `top` inside the VM actually reports). The wrong metric reported
	//     ~3-10× the guest CPU and triggered scale_out at 0.53 when the
	//     hottest VyOS guest was only at ~10%.
	//
	// (2) Rate window [3m]. Scrape interval is 60s. [2m] catches only 2 samples
	//     and frequently returns EMPTY (Prom needs ≥2 samples for rate, with no
	//     jitter margin), which scalar() turned into 0. The decide loop then
	//     thrashed: a real value triggered scale_out, three empty-→-0 ticks
	//     immediately after looked like 4-tick "low" → scale_in fired 2 min
	//     after the spawn. [3m] gives 3 samples = reliable values, no empty.
	//
	// Pool-average is intentionally avoided: it masks hotspots. With 2 VMs and
	// load on one at 60%, average=30% never trips scale_out — but the loaded
	// VM IS at the latency cliff. Max-per-VM catches that.
	st.V.Cpu = c.scalar(ctx,
		`max(
		   sum by(name)(rate(kubevirt_vmi_vcpu_seconds_total{name=~"{VYOS}"}[2m]))
		   / on(name) group_left()
		   count by(name)(kubevirt_vmi_vcpu_seconds_total{name=~"{VYOS}"})
		 )`)
	st.V.Mem = c.scalar(ctx,
		`sum(kubevirt_vmi_memory_used_bytes{name=~"{VYOS}"})
		 / clamp_min(sum(kubevirt_vmi_memory_available_bytes{name=~"{VYOS}"}),1)`)
	st.V.Bw = c.scalar(ctx,
		`sum(rate(kubevirt_vmi_network_traffic_bytes_total{name=~"{VYOS}"}[2m])) * 8`)
	// V.Count: prefer real-time KubeVirt list (Harvester API) over Prometheus
	// count. The Prom scrape is every 60s and a freshly-spawned VM only appears
	// in metrics after one scrape interval — so post-scale_out, count_v lagged
	// by 60s+ and the decide loop saw count_v=N when reality was N+1, firing
	// another scale_out and cascading to MAX.
	st.V.Count = c.countVyos(ctx)

	// ---- G_cp : AMF group ----
	st.Cp.Rep = int(c.scalar(ctx, `kube_deployment_spec_replicas{deployment="{DEP_AMF}",namespace="{NS}"}`))
	st.Cp.Ready = int(c.scalar(ctx, `kube_deployment_status_replicas_ready{deployment="{DEP_AMF}",namespace="{NS}"}`))
	st.Cp.Cpu = c.scalar(ctx,
		`sum(rate(container_cpu_usage_seconds_total{namespace="{NS}",pod=~"{AMF}",container!="",container!="POD"}[1m]))
		 / clamp_min(sum(kube_pod_container_resource_limits{namespace="{NS}",pod=~"{AMF}",resource="cpu"}),1)`)
	st.Cp.Mem = c.scalar(ctx,
		`sum(container_memory_working_set_bytes{namespace="{NS}",pod=~"{AMF}",container!="",container!="POD"})
		 / clamp_min(sum(kube_pod_container_resource_limits{namespace="{NS}",pod=~"{AMF}",resource="memory"}),1)`)

	// ---- G_up : UPF group ----
	if c.q.EupfMode {
		// bare eupf-N pods (8 pre-provisioned slots); Rep = pods that exist,
		// Ready = pods Running. The actuator creates/deletes the pod objects,
		// so "exists" is the desired count.
		st.Up.Rep = int(c.scalar(ctx, `count(kube_pod_info{namespace="{NS}",pod=~"{UPF}"})`))
		st.Up.Ready = int(c.scalar(ctx, `sum(kube_pod_status_phase{namespace="{NS}",pod=~"{UPF}",phase="Running"})`))
	} else {
		st.Up.Rep = int(c.scalar(ctx, `sum(kube_deployment_spec_replicas{deployment=~"{DEP_UPF}",namespace="{NS}"})`))
		st.Up.Ready = int(c.scalar(ctx, `sum(kube_deployment_status_replicas_ready{deployment=~"{DEP_UPF}",namespace="{NS}"})`))
	}
	// Unschedulable UPF pods. KSM free-CPU arithmetic can disagree with the
	// scheduler by ~100m (init/unaccounted requests), so Pending pods are the
	// authoritative "no room" signal (v44: upf-5/6 stranded at exactly 1500m
	// "free" while the scheduler saw 1400m).
	st.Up.PendingPods = int(c.scalar(ctx,
		`count(kube_pod_status_phase{namespace="{NS}",pod=~"{UPF}",phase="Pending"} == 1) or vector(0)`))
	st.Up.Cpu = c.scalar(ctx,
		`sum(rate(container_cpu_usage_seconds_total{namespace="{NS}",pod=~"{UPF}",container!="",container!="POD"}[1m]))
		 / clamp_min(sum(kube_pod_container_resource_limits{namespace="{NS}",pod=~"{UPF}",resource="cpu"}),1)`)
	st.Up.Mem = c.scalar(ctx,
		`sum(container_memory_working_set_bytes{namespace="{NS}",pod=~"{UPF}",container!="",container!="POD"})
		 / clamp_min(sum(kube_pod_container_resource_limits{namespace="{NS}",pod=~"{UPF}",resource="memory"}),1)`)
	st.Up.Bw = c.scalar(ctx,
		`sum(rate(container_network_receive_bytes_total{namespace="{NS}",pod=~"{UPF}"}[30s])
		 + rate(container_network_transmit_bytes_total{namespace="{NS}",pod=~"{UPF}"}[30s])) * 8`)
	st.Up.Drop = c.scalar(ctx,
		`sum(rate(container_network_receive_packets_dropped_total{namespace="{NS}",pod=~"{UPF}"}[30s])
		 + rate(container_network_transmit_packets_dropped_total{namespace="{NS}",pod=~"{UPF}"}[30s]))`)

	// ---- G_db : MongoDB ----
	st.Db.Rep = int(c.scalar(ctx, `kube_deployment_spec_replicas{deployment="open5gs-mongodb",namespace="{NS}"}`))
	st.Db.Ready = int(c.scalar(ctx, `kube_deployment_status_replicas_ready{deployment="open5gs-mongodb",namespace="{NS}"}`))
	st.Db.Cpu = c.scalar(ctx,
		`sum(rate(container_cpu_usage_seconds_total{namespace="{NS}",pod=~"{MONGO}",container!="",container!="POD"}[1m]))`)
	st.Db.Mem = c.scalar(ctx,
		`sum(container_memory_working_set_bytes{namespace="{NS}",pod=~"{MONGO}",container!="",container!="POD"})
		 / clamp_min(sum(kube_pod_container_resource_limits{namespace="{NS}",pod=~"{MONGO}",resource="memory"}),1)`)
	st.Db.Lat = c.scalar(ctx,
		`sum(rate(mongodb_mongod_op_latencies_latency_total{type="writes"}[1m]))
		 / clamp_min(sum(rate(mongodb_mongod_op_latencies_ops_total{type="writes"}[1m])),1)`)

	// ---- Q_t ----
	st.Q.Thr = st.Up.Bw
	st.Q.Drop = st.Up.Drop
	if st.Cp.Rep > 0 {
		st.Q.ReadyRatioCp = float64(st.Cp.Ready) / float64(st.Cp.Rep)
	}
	if st.Up.Rep > 0 {
		st.Q.ReadyRatioUp = float64(st.Up.Ready) / float64(st.Up.Rep)
	}
	return st
}

// countWorkerVMs returns how many worker VMs EXIST at the VM level (Harvester),
// including those still booting/joining k8s. Gating worker creation on k8s node
// counts alone has a blind window between VM creation and kubeadm join (~4 min)
// during which a booting worker is invisible → the daemon over-created (the
// redundant worker-3 incident 2026-06-11).
func (c *Collector) countWorkerVMs(ctx context.Context) int {
	if c.H != nil {
		if vms, err := c.H.ListVMs(ctx, ""); err == nil {
			n := 0
			for _, v := range vms {
				// Stopped VMs are deliberate; everything else (Running/
				// Starting/Scheduling/ErrorUnschedulable) counts: a failed-to-
				// schedule VM must BLOCK further creation (else the daemon
				// re-creates into the same full disk every cooldown — the
				// worker-3..7 cascade). ReapStuckVMs clears failures after
				// VM_STUCK_REAP_AFTER, which unblocks creation again.
				if strings.HasPrefix(v.Name, "worker-") &&
					v.Phase != "Stopped" && v.Phase != "Stopping" {
					n++
				}
			}
			return n
		}
	}
	return int(c.scalar(ctx, `count(count by(name)(kubevirt_vmi_memory_available_bytes{name=~"worker-.*"}))`))
}

// idleWorker returns a scaled worker (worker-1+, never the infra node) that is
// Ready, older than 10 min, and hosts ZERO UPF pods — a reclaim candidate.
// The old reclaim condition used AGGREGATE worker CPU, which never fires while
// other workers are busy, so a redundant worker survived whole runs.
func (c *Collector) idleWorker(ctx context.Context) string {
	// v4.22: the "no UPF pods" clause uses a 120s lookback (max_over_time) so a
	// worker counts as idle only after it has been EMPTY for 120s — not the
	// instant UPF scale-in vacates it. Without the dwell, worker scale-in
	// tracked UPF scale-in too tightly (a VM resource reclaimed the moment its
	// last UPF leaves, risking re-create churn if UPF rebounds). The dwell
	// decouples worker reclaim from UPF, lagging it by ~120s.
	q := `(kube_node_status_condition{condition="Ready",status="true",node=~"worker-[1-9].*"} == 1)
	 and on(node) ((time() - kube_node_created) > 300)
	 unless on(node) (max_over_time((count by(node)(kube_pod_info{namespace="open5gs",pod=~"open5gs-upf.*|eupf-[0-9]+"}))[120s:30s]) > 0)`
	samples, err := c.Prom.Query(ctx, q)
	if err != nil {
		return ""
	}
	best := ""
	for _, s := range samples {
		if n := s.Metric["node"]; n > best {
			best = n // prefer the highest index for deletion
		}
	}
	return best
}

// countVyos returns the live VyOS pool size using the Harvester API when
// available, falling back to Prometheus if not. The regex filter matches the
// same VyosNameRegex used for the Prom queries so test-vyos and daemon-managed
// vyos-N are both counted.
func (c *Collector) countVyos(ctx context.Context) int {
	if c.H != nil {
		vms, err := c.H.ListVMs(ctx, "")
		if err == nil {
			re, rerr := regexp.Compile(c.q.VyosNameRegex)
			if rerr == nil {
				n := 0
				for _, v := range vms {
					if re.MatchString(v.Name) {
						n++
					}
				}
				return n
			}
		}
	}
	return int(c.scalar(ctx, `count(count by(name)(kubevirt_vmi_memory_available_bytes{name=~"{VYOS}"}))`))
}
