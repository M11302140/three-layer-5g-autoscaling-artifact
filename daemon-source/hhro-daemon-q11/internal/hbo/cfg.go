package hbo

import (

	"github.com/anon/hhro-daemon/internal/envcfg"
)

// Cfg holds every HBO-HHRO tunable. All env-overridable.
type Cfg struct {
	Enabled bool

	// --- Prometheus windows ---
	WindowShort string // avg/p90 short (default "60s")
	WindowSlope string // deriv window (default "120s")
	WindowLong  string // p95 long for scale-in (default "300s")
	WindowIdle  string // p95 idle for worker delete (default "600s")

	// --- NF thresholds (normalized 0~1) ---
	// v4.53: predictive scale-in margin. Delete a VyOS only if the busiest node's
	// load × N/(N-1) (post-removal projection) ≤ VyosHigh × this fraction, so the
	// removal can't re-trip scale-out (rebound-free).

	// --- Slope thresholds (for bottleneck classification) ---

	// --- Normalization ---
	MaxDropPPS float64

	// VyOS norm

	// --- Risk ---

	// --- Worker capacity ---

	// --- Resource bounds ---
	MinCP      int
	MaxCP      int
	MinUP      int
	MaxUP      int
	MinVyos    int
	MaxVyos    int
	MinWorkers int
	MaxWorkers int

	// --- Cooldowns (asymmetric: scale-out fast, scale-in slow) ---
	EupfMode bool

	// --- Direction lock ---

	// --- Utility weights ---

	// --- SLO gain coefficients ---

	// --- Scale-in guards ---
	DropSafe float64

	// --- UPF evidence thresholds ---
	// Effective per-pod UPF capacity in cores: the open5gs data plane is
	// single-threaded, so utilization is normalized by min(limit, this) —
	// not the raw cgroup limit.
	UpEffCapCores float64
	// Idle CPU floor in cores: an open5gs UPF burns ~this many cores at ZERO
	// traffic (event loop + metrics). Subtracted per-pod before normalizing so
	// idle pods read 0 (else C_up floors above scale-in thresholds and
	// scale-in only fires at deep idle — v4.15).
	UpIdleFloorCores float64
	// v4.70 — new throughput-dominant pressure: p.UP = 0.5*max(pps_util,bw_util) + 0.3*cpu + 0.2*drop_score.
	// Scale-in drop-safety as a fraction of UPF throughput (DropUP/PktRateUP).
	// Replaces the absolute DropSafe×MaxDropPPS gate which blocked scale-in on
	// negligible session-teardown drops. 0.005 = 0.5%; teardown noise (~0.003%)
	// passes, sustained congestion blocks.
	DropSafeRatio float64

	// --- CP evidence thresholds ---

	// --- Rebalance ---

	// --- Drop critical (emergency override) ---

	// --- v5.0 eUPF mode ---
	// The data plane is eBPF/XDP eUPF instances (8 pre-provisioned slots, 2 per
	// worker), NOT open5gs UPF pods. Every UPF metric flips source:
	//   • pod cgroup CPU is meaningless (XDP runs in the worker VM's kernel
	//     softirq, the eUPF Go process is idle) — capacity is expressed in
	//     BIDIRECTIONAL pps against the AMBR policy cap instead.
	//   • container_network_* counters are blind (hostNetwork + XDP bypasses
	//     the pod netdev) — throughput comes from the eUPF's own upf_xdp_*
	//     Prometheus counters (job="eupf", scraped from 10.0.1.3x:9090).
	//     upf_xdp_tx counts BOTH directions with the vftx image (UL decap-out
	//     + DL encap-out are both XDP_TX on the instance's own VF).
	EupfEnabled bool
	// Per-eUPF combined UL+DL pps that maps to utilization 1.0. This is the
	// AMBR-derived POLICY capacity (4 UE × 150k pps × 2 directions = 1.2M),
	// deliberately far below the XDP hardware ceiling (~6.5M) — the policy cap
	// is what makes 8 instances necessary at the 4.8M peak.
	EupfPpsCap float64
}

// eupfDefault returns d, or dEupf when EUPF_ENABLED (recalibrated defaults for
// the eUPF data plane). An explicit env var still overrides either.
func eupfDefault(eupf bool, name string, d, dEupf float64) float64 {
	if eupf {
		return envcfg.Float(name, dEupf)
	}
	return envcfg.Float(name, d)
}

func eupfDefaultInt(eupf bool, name string, d, dEupf int) int {
	if eupf {
		return envcfg.Int(name, dEupf)
	}
	return envcfg.Int(name, d)
}

func DefaultCfg() Cfg {
	eupf := envcfg.Get("EUPF_ENABLED", "true") == "true"
	return Cfg{
		Enabled: envcfg.Get("AUTOSCALE_ENABLED", "false") == "true",

		EupfEnabled: eupf,
		EupfPpsCap:  envcfg.Float("EUPF_PPS_CAP", 1200000),

		WindowShort: envcfg.Get("WINDOW_SHORT", "60s"),
		WindowSlope: envcfg.Get("WINDOW_SLOPE", "120s"),
		WindowLong:  envcfg.Get("WINDOW_LONG", "300s"),
		WindowIdle:  envcfg.Get("WINDOW_IDLE", "600s"),

		MaxDropPPS: envcfg.Float("MAX_DROP_PPS", 1000),

		MinCP:      envcfg.Int("MIN_CP", 1),
		MaxCP:      envcfg.Int("MAX_CP", 5),
		MinUP:      envcfg.Int("MIN_UP", 1),
		MaxUP:      eupfDefaultInt(eupf, "MAX_UP", 6, 8), // eUPF: 8 pre-provisioned slots (2 per worker)
		MinVyos:    envcfg.Int("MIN_VYOS", 1),
		MaxVyos:    eupfDefaultInt(eupf, "MAX_VYOS", 4, 3), // eUPF-era peak 4.8M needs exactly 3 (1-worker VPP each)
		MinWorkers: envcfg.Int("MIN_WORKERS", 1),
		MaxWorkers: eupfDefaultInt(eupf, "MAX_WORKERS", 5, 4), // eUPF: 4 workers host the 8 slots

		EupfMode: envcfg.Get("EUPF_ENABLED", "true") == "true",

		DropSafe: envcfg.Float("DROP_SAFE", 0.02),

		UpEffCapCores:    envcfg.Float("UP_EFF_CAP_CORES", 1.0),
		UpIdleFloorCores: envcfg.Float("UP_IDLE_FLOOR_CORES", 0.18),
		// v4.70: cap is BIDIRECTIONAL — PktRateUP = rx+tx ≈ 2.2× the offered UL, so the
		// per-UPF saturation is ~2.2×200k ≈ 440k rx+tx pps. Cap = 85% of that (~370k) so
		// throughput_util reads TRUE utilisation across the load range (0.59 at half load)
		// → scale-IN tracks the ramp-down (the 170k unidirectional cap saturated thru at
		// 1.0 above ~680k offered, so scale-in couldn't fire until rd2/rd3). Scale-OUT is
		// unaffected: at high load thru≈1.0 either way.
		// v4.76 — VyOS throughput-dominant pressure (mirrors UPF). VyosThruCap = per-VyOS
		// bidirectional pps (PktRateUP/vyos_count) that maps to throughput=1.0. Calibrated
		// from REAL phaseF data: 1 VyOS saturates (guest CPU 85-99%) at 16 UE where
		// PktRateUP≈1.8M bidirectional. Set to 1.5M (≈83% of saturation) as a deliberate
		// ANTICIPATION margin so the throughput term reaches the deploy line ~1 step before
		// the wall, giving the ~2min VM boot its lead. Node-count division separates stages:
		// 1 VyOS@ru2 thru→1.0 (deploy); 2 VyOS@ru2 thru→0.6, p.Vyos≈0.43 (hold); 2 VyOS@ru3
		// thru→0.83 (deploy). (700k was wrong — it read 2-VyOS-comfortable load as saturated.)
		// v4.79: robust peak-rebound guard. If removing a VyOS would push the survivors'
		// per-node throughput above this, REJECT the delete regardless of the (vbash/scrape-
		// noisy) CPU reading. phaseG peak: CPU read 10% (real ~40%) → p.Vyos dipped to 0.295
		// → spurious 3→2 → 2 survivors saturated → re-deploy flap. Throughput is vbash-immune.
		// Separates cleanly: peak 3→2 projThru≈0.8 (reject), rd1 3→2 projThru≈0.4 (allow).
		DropSafeRatio: envcfg.Float("DROP_SAFE_RATIO", 0.005),
	}
}
