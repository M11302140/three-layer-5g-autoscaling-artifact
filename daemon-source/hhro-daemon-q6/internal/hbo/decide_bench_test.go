package hbo

// Micro-benchmark for the pure decision pipeline (post-collection):
// ComputePressure -> ClassifyBottleneck -> EstimateRisk ->
// EnumerateFeasibleActions -> SelectActionByUtility -> ApplyStabilityGuards.
// Prometheus collection is excluded on purpose — it is I/O, not decision compute.

import "testing"

func wf(now float64) WindowFeature {
	return WindowFeature{Now: now, Avg30: now * 0.97, Avg60: now * 0.95,
		P90_60: now * 1.02, P95_300: now * 1.05, P95_600: now * 1.05,
		Slope120: 0.002, Slope300: 0.001}
}

func benchState() (FeatureSet, SystemState) {
	f := FeatureSet{
		CpuCP: wf(0.35), CpuUP: wf(0.72), MeanCpuUP: wf(0.72),
		CpuVyos: wf(0.6), CpuVyosReal: wf(72), MeanCpuVyosReal: wf(65),
		ReadyCP: wf(1), DropUP: wf(12000),
		PktRateUP: wf(3.9e6), BwUP: wf(4200), UECount: wf(24),
		VyosDropErr: wf(10), VyosImbalance: wf(0.2),
		WorkerCpu: wf(0.65), WorkerMem: wf(0.55),
		HhroCpScore: wf(0.3), HhroUpScore: wf(0.75), HhroVyosScore: wf(0.6),
	}
	s := SystemState{
		WorkerCount: 3, ReadyWorkers: 3, WorkerVMCount: 3,
		WorkerFreeCpuM: 2600, MaxWorkerFreeCpuM: 1400, WorkerFreeMemMiB: 9000,
		WorkerCpu: 0.65,
		RepCP:     1, RepUP: 6, ReadyCP: 1, ReadyUP: 6,
		VyosCount: 2, OfferedPPS: 3.9e6, UECount: 24,
	}
	return f, s
}

func BenchmarkHHRODecidePipeline(b *testing.B) {
	cfg := DefaultCfg()
	f, s := benchState()
	timers := NewTimers(cfg)
	b.ReportAllocs()
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		p := ComputePressure(f, cfg, s.VyosCount, s.RepUP)
		bn := ClassifyBottleneck(f, p, s, cfg)
		risk := EstimateRisk(p, f, cfg)
		acts := EnumerateFeasibleActions(s, timers, cfg)
		a, _ := SelectActionByUtility(acts, bn, risk, s, f, p, cfg)
		ApplyStabilityGuards(a, bn, risk, s, f, p, timers, cfg)
	}
}
