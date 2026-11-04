// Package hbo implements the HBO-HHRO controller: History-aware Bottleneck-
// Oriented Hierarchical Hybrid Resource Orchestration. It replaces the old
// threshold if-return tree with: window features → NF pressure → bottleneck
// classification → risk estimation → feasible action enumeration → utility-
// based selection → stability guards.
package hbo

import "time"

// --- Window Feature ---

type WindowFeature struct {
	Now      float64
	Avg30    float64
	Avg60    float64
	P90_60   float64
	P95_300  float64
	P95_600  float64
	Slope120 float64
	Slope300 float64
	Missing  bool
}

// Robust60 returns a smoothed value that resists single-scrape noise.
// p90_60 weighted highest to capture sustained high pressure without being
// as volatile as max.
func (w WindowFeature) Robust60() float64 {
	return clamp01(0.50*w.P90_60 + 0.30*w.Avg60 + 0.20*w.Now)
}

// Robust60Raw is Robust60 without the [0,1] clamp — for features that are raw
// magnitudes (e.g. packets/s), not already-normalized fractions. Clamping a
// raw pps to 1.0 then dividing by a norm yields ~0 (the C_vyos-from-UPF-pps bug).
func (w WindowFeature) Robust60Raw() float64 {
	return 0.50*w.P90_60 + 0.30*w.Avg60 + 0.20*w.Now
}

// --- Feature Set ---

type FeatureSet struct {
	CpuCP           WindowFeature
	CpuUP           WindowFeature
	MeanCpuUP       WindowFeature
	CpuVyos         WindowFeature
	CpuVyosReal     WindowFeature // max across VyOS — scale-OUT (any one saturating)
	MeanCpuVyosReal WindowFeature // v4.50: avg across VyOS — scale-IN (pool over-provisioned)
	ReadyCP         WindowFeature
	DropUP          WindowFeature
	PktRateUP       WindowFeature
	BwUP            WindowFeature // v4.70: aggregate UPF data-plane Mbps (for max(pps,bw) throughput)
	UECount         WindowFeature

	// VyOS network
	VyosDropErr   WindowFeature
	VyosLossRatio WindowFeature
	VyosImbalance WindowFeature

	// Worker
	WorkerCpu WindowFeature
	WorkerMem WindowFeature

	// HHRO exported scores (for long-window scale-in)
	HhroCpScore   WindowFeature
	HhroUpScore   WindowFeature
	HhroVyosScore WindowFeature
}

// --- Pressure ---

type PressureSet struct {
	CP   float64
	UP   float64
	Vyos float64
	// v4.70 diagnostics: UP pressure component breakdown (for calibration/validation).
	UpThroughput float64 // max(pps_util, bw_util)
	UpCpu        float64 // cpu blend
	UpDrop       float64 // exp drop_score
	// v4.71 diagnostics: VyOS pressure component breakdown.
	VyosThroughput float64
	VyosCpu        float64
	VyosLoss       float64
}

// --- Bottleneck ---

type Bottleneck string

const (
	BNNone  Bottleneck = "BN_NONE"
	BNCP    Bottleneck = "BN_CP"
	BNUPF   Bottleneck = "BN_UPF"
	BNVyos  Bottleneck = "BN_VYOS"
	BNInfra Bottleneck = "BN_INFRA"
	BNMixed Bottleneck = "BN_MIXED"
)

// --- Risk ---

type RiskSet struct {
	CP   float64
	UP   float64
	Vyos float64

	ForecastMaxCP   float64
	ForecastMaxUP   float64
	ForecastMaxVyos float64
}

func (r RiskSet) Max() float64 {
	m := r.CP
	if r.UP > m {
		m = r.UP
	}
	if r.Vyos > m {
		m = r.Vyos
	}
	return m
}

// --- Action ---

type Action string

const (
	ActNone         Action = "NONE"
	ActScaleOutCP   Action = "SCALE_OUT_CP"
	ActScaleInCP    Action = "SCALE_IN_CP"
	ActScaleOutUP   Action = "SCALE_OUT_UP"
	ActScaleInUP    Action = "SCALE_IN_UP"
	ActDeployVyOS   Action = "DEPLOY_VYOS"
	ActDeleteVyOS   Action = "DELETE_VYOS"
	ActCreateWorker Action = "CREATE_WORKER"
	ActDeleteWorker Action = "DELETE_WORKER"
	ActRebalanceUPF Action = "REBALANCE_UPF"
	ActRebalanceVy  Action = "REBALANCE_VYOS"
)

func (a Action) IsScaleOut() bool {
	return a == ActScaleOutCP || a == ActScaleOutUP || a == ActDeployVyOS || a == ActCreateWorker
}

func (a Action) IsScaleIn() bool {
	return a == ActScaleInCP || a == ActScaleInUP || a == ActDeleteVyOS || a == ActDeleteWorker
}

// --- Action Utility ---

type ActionUtility struct {
	Action         Action
	Utility        float64
	SLOGain        float64
	InfraCost      float64
	ChurnCost      float64
	MismatchCost   float64
	DisruptionCost float64
}

// --- Decision ---

type Decision struct {
	Action     Action      `json:"action"`
	Bottleneck Bottleneck  `json:"bottleneck"`
	Pressure   PressureSet `json:"pressure"`
	Risk       RiskSet     `json:"risk"`
	Reason     string      `json:"reason"`
	BlockedBy  string      `json:"blocked_by,omitempty"`
	At         time.Time   `json:"at"`
}

// --- System State (consumed by the controller) ---

// OfferedSample is one sender-egress UL pps sample (from the agent /offered history).
type OfferedSample struct {
	T   time.Time
	PPS float64
}

type SystemState struct {
	// Worker info
	WorkerCount       int
	ReadyWorkers      int    // Ready worker nodes; WorkerCount>ReadyWorkers ⇒ one booting
	WorkerVMCount     int    // Harvester worker VMs (incl. booting before kubeadm join — invisible to WorkerCount)
	IdleWorker        string // Ready >10min scaled worker with no UPF pods — reclaim target ("" = none)
	WorkerFreeCpuM    float64
	MaxWorkerFreeCpuM float64 // free CPU on the emptiest single worker (millicores)
	WorkerFreeMemMiB  float64
	WorkerCpu         float64
	PodPendingCount   int
	NodePressure      bool

	// CNF replicas
	RepCP   int
	RepUP   int
	ReadyCP int
	ReadyUP int

	// VyOS
	VyosCount int
	VyosAdmitted int

	// OfferedPPS is the sender-egress measured UL pps (agent /offered) — a
	// demand-side invariant: unlike eUPF/VyOS counters it does not collapse
	// when the daemon's own action blackholes a downstream hop, so capacity
	// projections built on it cannot chain-shrink on self-inflicted dips.
	OfferedPPS float64
	OfferedHist []OfferedSample

	// QoS
	UECount int
}

// --- Helpers ---

func clamp01(x float64) float64 {
	if x < 0 {
		return 0
	}
	if x > 1 {
		return 1
	}
	return x
}

func clamp(x, lo, hi float64) float64 {
	if x < lo {
		return lo
	}
	if x > hi {
		return hi
	}
	return x
}
