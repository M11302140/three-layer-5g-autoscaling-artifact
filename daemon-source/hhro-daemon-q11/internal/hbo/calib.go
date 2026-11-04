package hbo

import "github.com/anon/hhro-daemon/internal/envcfg"

// Calib holds every measured [M], fitted [F] and SLO-derived [S] constant the
// v6 model-based controller uses. NOTHING in this file is a free tunable — the
// only free parameters of v6 live in V6Params (λ, m, s_max).
//
// Provenance discipline: every value carries its measurement source. Refit via
// experiment/p2/fit_curves.py after adding calibration points (E1/E2).

// ActionSpec is the measured characterization of one actuator action.
//
// Cores vs PoolCores: Cores is what λ prices — compute actually burned
// (DPDK poll-mode VyOS and worker VMs burn their allocation regardless of
// load; an ACTIVE eUPF slot burns its measured softirq cores INSIDE the
// worker's allocation). PoolCores is what host-pool feasibility counts —
// vCPU allocation (a slot allocates nothing extra; its worker already did).
type ActionSpec struct {
	TReadySec float64 // [M] time from dispatch to taking effect
	DLoss     float64 // [M] expected transition damage (e2e loss·s over the transition)
	Cores     float64 // [M] λ-priced compute delta (signed; + consumes)
	PoolCores float64 // [M] host vCPU allocation delta (feasibility)
	MemGi     float64 // [M] host memory allocation delta, GiB (feasibility)
}

// CurveCNF: f(u) = exp(K·max(0,u−UKnee)) − 1 — kernel/softirq queueing knee.
type CurveCNF struct {
	K     float64 // [F]
	UKnee float64 // [F]
}

// CurveVNF: f(u) = max(0, 1−1/u) + g(u) — DPDK poll-mode deterministic-rate
// overflow cliff anchored at Cap (no free shape params) plus a measured
// pre-cliff term g. g is piecewise-linear over PreCliff; empty slice = g≡0.
type CurveVNF struct {
	PreCliff []CurvePoint // [F] PROVISIONAL: empty until E1 scans u∈[0.85,1.05]
}

type CurvePoint struct{ U, Loss float64 }

type Calib struct {
	// --- capacities (bidirectional pps per instance) ---
	PerUEBidir float64
	StepFloor float64
	BatchIntervalSec float64
	MaxBatches       int
	CapUP            float64 // [M] AMBR policy arithmetic: 4 UE × 150k pps × 2 dir = 1.2M
	CapVY            float64

	// --- loss curves ---
	CNF CurveCNF // [F] fit_curves_v2.py 2026-08-23, 26 pts (N∈{5,6,7,8} × offered
	VNF CurveVNF

	// --- SLO (paper evaluation gate; e2e) ---
	EpsSLO float64
	EpsDesign float64 // [S] = EpsSLO/2, controller design margin

	// --- host pool (single Harvester host) ---
	HostCores     float64 // [M] topology: Ryzen 16C/32T → 32 schedulable threads
	HostMemGi     float64 // [M] 60G host
	HostReserveGi float64 // [M] HOST_MEM_RESERVE_GI operational value

	// --- per-action characterization ---
	Act map[Action]ActionSpec
}

// DefaultCalib returns the 2026-08 characterization of the testbed.
// T_ready sources: pod≈15s (create→Running→assoc, run logs); VyOS≈150s (VM
// boot + async VPP inject 2-3min, v5.1.4 AD-section measurements); worker≈180s
// (boot+kubeadm join); drain≈60s (cli_move×5 + hairpin regen, 07-28 Test A).
// Delete_VY replicated-DNAT route swap measured ≈0 (v4.48 era); values are
// upper bounds pending M-track refinement.
func DefaultCalib() Calib {
	return Calib{
		PerUEBidir:       250000,
		StepFloor:        5 * 250000,
		BatchIntervalSec: 120,
		MaxBatches:       2,
		CapUP:            1.35e6,
		CapVY: 4.45e6,

		CNF: CurveCNF{K: 0.050, UKnee: 1.0},
		VNF: CurveVNF{PreCliff: []CurvePoint{ // v2 08-23: 1vy+2vy residuals,
			// u∈[0.80,1.02], isotonic+merge(fit_curves_v2.py)
		}},

		EpsSLO:    0.001,
		EpsDesign: 0.0005,

		HostCores:     32,
		HostMemGi:     60,
		HostReserveGi: 3,

		Act: map[Action]ActionSpec{
			ActScaleOutUP: {TReadySec: 15, DLoss: 0, Cores: +0.8, PoolCores: 0, MemGi: 0},
			ActScaleInUP: {TReadySec: 120, DLoss: 0.005, Cores: -0.8, PoolCores: 0, MemGi: 0},
			ActDeployVyOS: {TReadySec: 85, DLoss: 0, Cores: +2, PoolCores: +2, MemGi: +3},
			ActDeleteVyOS: {TReadySec: 30, DLoss: 0.0005, Cores: -2, PoolCores: -2, MemGi: -3},
			ActCreateWorker: {TReadySec: 100, DLoss: 0, Cores: +3, PoolCores: +3, MemGi: +3},
			ActDeleteWorker: {TReadySec: 60, DLoss: 0, Cores: -3, PoolCores: -3, MemGi: -3},
			ActRebalanceUPF: {TReadySec: 45, DLoss: 0, Cores: 0, PoolCores: 0, MemGi: 0},
			ActRebalanceVy:  {TReadySec: 10, DLoss: 0, Cores: 0, PoolCores: 0, MemGi: 0},
		},
	}
}

// V6Params are the ONLY free parameters of the v6 controller [P]. Each gets a
// ±50% sensitivity sweep in evaluation (E5).
type V6Params struct {
	Lambda   float64 // cost price: e2e-loss-rate equivalent per host core
	MarginM  float64 // projection safety margin (guards scale-in projections)
	SlopeMax float64 // |offered slope| clamp, fraction of current offered per second
	UMin     float64 // anti-dither floor on J improvement vs NoOp (≈0)
}

func DefaultV6Params() V6Params {
	return V6Params{
		Lambda: envcfg.Float("V6_LAMBDA", 0.002), // 0.2% loss-rate per core — E5 sweeps this
		MarginM:  envcfg.Float("V6_MARGIN_M", 0.93),
		SlopeMax: envcfg.Float("V6_SLOPE_MAX", 0.05),
		UMin:     envcfg.Float("V6_UMIN", 0.0),
	}
}
