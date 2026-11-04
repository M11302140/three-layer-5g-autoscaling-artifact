package hbo

import (
	"time"

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
	CpHigh     float64
	CpLow      float64
	CpCritical float64
	UpHigh     float64
	UpLow      float64
	UpCritical float64
	VyosHigh   float64
	VyosLow    float64
	// v4.53: predictive scale-in margin. Delete a VyOS only if the busiest node's
	// load × N/(N-1) (post-removal projection) ≤ VyosHigh × this fraction, so the
	// removal can't re-trip scale-out (rebound-free).
	VyosInSafetyFrac float64
	VyosCrit         float64

	// --- Slope thresholds (for bottleneck classification) ---
	CpSlopeHigh float64

	// --- Normalization ---
	MaxDropPPS      float64
	MaxPktRateSlope float64
	CpCpuNorm       float64 // raw CPU cores → ratio (AMF has no limit)

	// VyOS norm
	VyosCpuNorm         float64 // % guest CPU that maps to full VyOS pressure (real telegraf CPU)
	VyosImbalanceNorm   float64 // ratio
	VyosThruCap         float64 // v4.71: per-VyOS pps that maps to throughput_util=1.0
	VyosDropExpK        float64 // v4.71: exp coeff for VyOS loss term
	VyosScaleInThruCeil float64 // v4.79: reject VyOS delete if survivors' projected throughput exceeds this (vbash-immune peak-rebound guard)

	// --- Risk ---
	RiskHorizonTicks int
	RiskHigh         float64
	RiskCritical     float64
	MaxScoreSlope    float64
	MidIntervalSec   float64

	// --- Worker capacity ---
	MinFreeCpuM             int
	WorkerPrecreateFreeCpuM int // v4.78: predictive worker pre-create fires when emptiest worker free CPU drops below THIS (≈ MinFreeCpuM + 1 UPF) so the next worker boots a slot EARLY, not at exhaustion
	MinFreeMemMiB           int
	WorkerCpuLow            float64
	WorkerMemLow            float64
	PodPendingHigh          int

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
	CpScaleOutCooldown     time.Duration
	CpScaleInCooldown      time.Duration
	UpScaleOutCooldown     time.Duration
	UpScaleInCooldown      time.Duration
	VyosScaleOutCooldown   time.Duration
	VyosScaleInCooldown    time.Duration
	EupfMode               bool
	WorkerScaleOutCooldown time.Duration
	WorkerScaleInCooldown  time.Duration
	RebalanceUpfCooldown   time.Duration
	RebalanceVyosCooldown  time.Duration
	TransitionFreeze       time.Duration

	// --- Direction lock ---
	DirectionLockCP     time.Duration
	DirectionLockUP     time.Duration
	DirectionLockVyos   time.Duration
	DirectionLockWorker time.Duration

	// --- Utility weights ---
	LambdaCost    float64
	LambdaChurn   float64
	LambdaWrong   float64
	LambdaDisrupt float64
	MinActionGain float64

	// --- SLO gain coefficients ---
	EtaCP            float64
	EtaUP            float64
	EtaVyos          float64
	EtaWorker        float64
	EtaWorkerPrepare float64
	EtaRebalance     float64
	EtaCostSaving    float64

	// --- Scale-in guards ---
	LowDwellTicks int
	LowUEMax      int
	DropSafe      float64

	// --- UPF evidence thresholds ---
	UpCpuHigh float64
	// Effective per-pod UPF capacity in cores: the open5gs data plane is
	// single-threaded, so utilization is normalized by min(limit, this) —
	// not the raw cgroup limit.
	UpEffCapCores float64
	// Idle CPU floor in cores: an open5gs UPF burns ~this many cores at ZERO
	// traffic (event loop + metrics). Subtracted per-pod before normalizing so
	// idle pods read 0 (else C_up floors above scale-in thresholds and
	// scale-in only fires at deep idle — v4.15).
	UpIdleFloorCores float64
	UpfPpsCap        float64 // v4.62: per-UPF safe RX+TX pps; scale in while total/(N-1) ≤ this (throughput-based, no idle-CPU-baseline pollution)
	// v4.70 — new throughput-dominant pressure: p.UP = 0.5*max(pps_util,bw_util) + 0.3*cpu + 0.2*drop_score.
	UpPressurePpsCap float64 // per-UPF pps that maps to throughput_util=1.0 (single-UPF saturation)
	UpPressureBwCap  float64 // per-UPF Mbps that maps to throughput_util=1.0
	UpDropExpK       float64 // exp coefficient: drop_score = exp(K*sustained_drop_ratio) - 1
	// Scale-in drop-safety as a fraction of UPF throughput (DropUP/PktRateUP).
	// Replaces the absolute DropSafe×MaxDropPPS gate which blocked scale-in on
	// negligible session-teardown drops. 0.005 = 0.5%; teardown noise (~0.003%)
	// passes, sustained congestion blocks.
	DropSafeRatio float64

	// --- CP evidence thresholds ---
	ReadyMin float64

	// --- Rebalance ---
	RebalanceEnabled  bool
	UpfImbalanceHigh  float64
	VyosImbalanceHigh float64

	// --- Drop critical (emergency override) ---
	DropCritical float64

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

		CpHigh:           envcfg.Float("CP_HIGH", 0.70),
		CpLow:            envcfg.Float("CP_LOW", 0.30),
		CpCritical:       envcfg.Float("CP_CRITICAL", 0.90),
		UpHigh:           envcfg.Float("UP_HIGH", 0.70),
		UpLow:            envcfg.Float("UP_LOW", 0.40), // v4.70: 0.30→0.40 widens the scale-out/in hysteresis band (out@~170k/UPF, in@~82k/UPF)
		UpCritical:       envcfg.Float("UP_CRITICAL", 0.90),
		VyosHigh:         envcfg.Float("VYOS_HIGH", 0.70),
		VyosLow:          envcfg.Float("VYOS_LOW", 0.30),
		VyosInSafetyFrac: envcfg.Float("VYOS_IN_SAFETY_FRAC", 0.85),
		VyosCrit:         envcfg.Float("VYOS_CRITICAL", 0.90),

		CpSlopeHigh: envcfg.Float("CP_SLOPE_HIGH", 0.005),

		MaxDropPPS:      envcfg.Float("MAX_DROP_PPS", 1000),
		MaxPktRateSlope: envcfg.Float("MAX_PKT_RATE_SLOPE", 10000),
		CpCpuNorm:       envcfg.Float("CP_CPU_NORM", 1.0),

		VyosCpuNorm:       envcfg.Float("VYOS_CPU_NORM", 40), // 40% guest CPU = full pressure (VyOS is throughput-bound, peaks ~25-30%); calibrate in load test
		VyosImbalanceNorm: envcfg.Float("VYOS_IMBALANCE_NORM", 1.0),

		RiskHorizonTicks: envcfg.Int("RISK_HORIZON_TICKS", 3),
		RiskHigh:         envcfg.Float("RISK_HIGH", 0.03),
		RiskCritical:     envcfg.Float("RISK_CRITICAL", 0.08),
		MaxScoreSlope:    envcfg.Float("MAX_SCORE_SLOPE", 0.05),
		MidIntervalSec:   envcfg.Float("MID_INTERVAL_SEC", 30),

		MinFreeCpuM:             envcfg.Int("MIN_FREE_CPU_M", 500),
		WorkerPrecreateFreeCpuM: envcfg.Int("WORKER_PRECREATE_FREE_M", 3200),
		MinFreeMemMiB:           envcfg.Int("MIN_FREE_MEM_MIB", 512),
		WorkerCpuLow:            envcfg.Float("WORKER_CPU_LOW", 0.20),
		WorkerMemLow:            envcfg.Float("WORKER_MEM_LOW", 0.20),
		PodPendingHigh:          envcfg.Int("POD_PENDING_HIGH", 1),

		MinCP:      envcfg.Int("MIN_CP", 1),
		MaxCP:      envcfg.Int("MAX_CP", 5),
		MinUP:      envcfg.Int("MIN_UP", 1),
		MaxUP:      eupfDefaultInt(eupf, "MAX_UP", 6, 8), // eUPF: 8 pre-provisioned slots (2 per worker)
		MinVyos:    envcfg.Int("MIN_VYOS", 1),
		MaxVyos:    eupfDefaultInt(eupf, "MAX_VYOS", 4, 3), // eUPF-era peak 4.8M needs exactly 3 (1-worker VPP each)
		MinWorkers: envcfg.Int("MIN_WORKERS", 1),
		MaxWorkers: eupfDefaultInt(eupf, "MAX_WORKERS", 5, 4), // eUPF: 4 workers host the 8 slots

		CpScaleOutCooldown:     envcfg.Dur("CP_SCALE_OUT_COOLDOWN", 60*time.Second),
		CpScaleInCooldown:      envcfg.Dur("CP_SCALE_IN_COOLDOWN", 180*time.Second),
		UpScaleOutCooldown:     envcfg.Dur("UP_SCALE_OUT_COOLDOWN", 60*time.Second),
		UpScaleInCooldown:      envcfg.Dur("UP_SCALE_IN_COOLDOWN", 180*time.Second),
		VyosScaleOutCooldown:   envcfg.Dur("VYOS_SCALE_OUT_COOLDOWN", 180*time.Second),
		VyosScaleInCooldown:    envcfg.Dur("VYOS_SCALE_IN_COOLDOWN", 600*time.Second),
		EupfMode:               envcfg.Get("EUPF_ENABLED", "true") == "true",
		WorkerScaleOutCooldown: envcfg.Dur("WORKER_SCALE_OUT_COOLDOWN", 300*time.Second),
		WorkerScaleInCooldown:  envcfg.Dur("WORKER_SCALE_IN_COOLDOWN", 900*time.Second),
		RebalanceUpfCooldown:   envcfg.Dur("UPF_REBALANCE_COOLDOWN", 90*time.Second),
		RebalanceVyosCooldown:  envcfg.Dur("VYOS_REBALANCE_COOLDOWN", 90*time.Second),
		TransitionFreeze:       envcfg.Dur("TRANSITION_FREEZE_DEFAULT", 30*time.Second),

		DirectionLockCP:     envcfg.Dur("DIRECTION_LOCK_CP", 300*time.Second),
		DirectionLockUP:     envcfg.Dur("DIRECTION_LOCK_UP", 300*time.Second),
		DirectionLockVyos:   envcfg.Dur("DIRECTION_LOCK_VYOS", 600*time.Second),
		DirectionLockWorker: envcfg.Dur("DIRECTION_LOCK_WORKER", 900*time.Second),

		LambdaCost:    envcfg.Float("LAMBDA_COST", 0.10),
		LambdaChurn:   envcfg.Float("LAMBDA_CHURN", 0.15),
		LambdaWrong:   envcfg.Float("LAMBDA_WRONG", 0.40),
		LambdaDisrupt: envcfg.Float("LAMBDA_DISRUPT", 0.30),
		MinActionGain: envcfg.Float("MIN_ACTION_GAIN", 0.01),

		EtaCP:            envcfg.Float("ETA_CP", 2.0),
		EtaUP:            envcfg.Float("ETA_UP", 2.0),
		EtaVyos:          envcfg.Float("ETA_VYOS", 2.0),
		EtaWorker:        envcfg.Float("ETA_WORKER", 0.8),
		EtaWorkerPrepare: envcfg.Float("ETA_WORKER_PREPARE", 0.4),
		EtaRebalance:     envcfg.Float("ETA_REBALANCE", 0.3),
		EtaCostSaving:    envcfg.Float("ETA_COST_SAVING", 0.2),

		LowDwellTicks: envcfg.Int("LOW_DWELL_TICKS", 2),
		LowUEMax:      envcfg.Int("LOW_UE_MAX", 5),
		DropSafe:      envcfg.Float("DROP_SAFE", 0.02),

		UpCpuHigh:        envcfg.Float("UP_CPU_HIGH", 0.65),
		UpEffCapCores:    envcfg.Float("UP_EFF_CAP_CORES", 1.0),
		UpIdleFloorCores: envcfg.Float("UP_IDLE_FLOOR_CORES", 0.18),
		UpfPpsCap:        eupfDefault(eupf, "UP_SCALEIN_PPS_CAP", 250000, 780000), // eUPF: survivors' combined UL+DL pps ≤ 65% of the 1.2M policy cap
		// v4.70: cap is BIDIRECTIONAL — PktRateUP = rx+tx ≈ 2.2× the offered UL, so the
		// per-UPF saturation is ~2.2×200k ≈ 440k rx+tx pps. Cap = 85% of that (~370k) so
		// throughput_util reads TRUE utilisation across the load range (0.59 at half load)
		// → scale-IN tracks the ramp-down (the 170k unidirectional cap saturated thru at
		// 1.0 above ~680k offered, so scale-in couldn't fire until rd2/rd3). Scale-OUT is
		// unaffected: at high load thru≈1.0 either way.
		UpPressurePpsCap: eupfDefault(eupf, "UP_PRESSURE_PPS_CAP", 370000, 1200000), // eUPF: per-instance combined saturation = policy cap (EUPF_PPS_CAP)
		UpPressureBwCap:  envcfg.Float("UP_PRESSURE_BW_CAP", 350),                   // bidirectional, tracks the pps cap
		UpDropExpK:       envcfg.Float("UP_DROP_EXP_K", 20),                         // drop_score = exp(20*ratio)-1
		// v4.76 — VyOS throughput-dominant pressure (mirrors UPF). VyosThruCap = per-VyOS
		// bidirectional pps (PktRateUP/vyos_count) that maps to throughput=1.0. Calibrated
		// from REAL phaseF data: 1 VyOS saturates (guest CPU 85-99%) at 16 UE where
		// PktRateUP≈1.8M bidirectional. Set to 1.5M (≈83% of saturation) as a deliberate
		// ANTICIPATION margin so the throughput term reaches the deploy line ~1 step before
		// the wall, giving the ~2min VM boot its lead. Node-count division separates stages:
		// 1 VyOS@ru2 thru→1.0 (deploy); 2 VyOS@ru2 thru→0.6, p.Vyos≈0.43 (hold); 2 VyOS@ru3
		// thru→0.83 (deploy). (700k was wrong — it read 2-VyOS-comfortable load as saturated.)
		VyosThruCap:  eupfDefault(eupf, "VYOS_THRU_CAP", 1500000, 3500000), // eUPF: per-VyOS(3vCPU/1 VPP worker) combined UL+DL; system-clean ceiling ~6.3M, cap at 3.5M → peak/3 = 0.91 fires scale-out, single vy collapses (measured 82% loss)
		VyosDropExpK: envcfg.Float("VYOS_DROP_EXP_K", 20),
		// v4.79: robust peak-rebound guard. If removing a VyOS would push the survivors'
		// per-node throughput above this, REJECT the delete regardless of the (vbash/scrape-
		// noisy) CPU reading. phaseG peak: CPU read 10% (real ~40%) → p.Vyos dipped to 0.295
		// → spurious 3→2 → 2 survivors saturated → re-deploy flap. Throughput is vbash-immune.
		// Separates cleanly: peak 3→2 projThru≈0.8 (reject), rd1 3→2 projThru≈0.4 (allow).
		VyosScaleInThruCeil: envcfg.Float("VYOS_SCALEIN_THRU_CEIL", 0.72),
		DropSafeRatio:       envcfg.Float("DROP_SAFE_RATIO", 0.005),

		ReadyMin: envcfg.Float("READY_MIN", 0.90),

		RebalanceEnabled:  envcfg.Get("REBALANCE_ENABLED", "false") == "true",
		UpfImbalanceHigh:  envcfg.Float("UPF_IMBALANCE_HIGH", 0.30),
		VyosImbalanceHigh: envcfg.Float("VYOS_IMBALANCE_HIGH", 0.10),

		DropCritical: envcfg.Float("DROP_CRITICAL", 0.80),
	}
}
