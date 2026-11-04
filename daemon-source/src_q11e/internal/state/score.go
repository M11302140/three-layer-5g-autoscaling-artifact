package state

// Weights mirror the spec in goal.md §2.
type Weights struct {
	W [4]float64 // cp: cpu, mem, 1-ready_ratio, lat_db
	U [5]float64 // up: cpu, mem, bw, drop, cpu_v
	C [3]float64 // infra: n_w, rep_cp, rep_up
	A float64    // α
	B float64    // β
	G float64    // γ
}

func DefaultWeights() Weights {
	return Weights{
		W: [4]float64{0.25, 0.25, 0.25, 0.25},
		U: [5]float64{0.20, 0.20, 0.20, 0.20, 0.20},
		C: [3]float64{0.001, 0.001, 0.001},
		A: 0.4, B: 0.4, G: 0.2,
	}
}

// Norms hold the upper bounds used to map raw values into [0,1]. Tune via env
// once you know the target SLO of the testbed.
type Norms struct {
	MaxBwBps   float64 // for bw_up, bw_v
	MaxDropPps float64 // for drop_up
	MaxLatUs   float64 // for lat_db
}

func DefaultNorms() Norms { return Norms{MaxBwBps: 10e9, MaxDropPps: 10000, MaxLatUs: 50000} }

func clamp01(x float64) float64 {
	if x < 0 {
		return 0
	}
	if x > 1 {
		return 1
	}
	return x
}

// Compute returns the four cost terms defined in §2.
func Compute(s State, w Weights, n Norms) Scores {
	cpuCp := clamp01(s.Cp.Cpu)
	memCp := clamp01(s.Cp.Mem)
	notReadyCp := 1 - clamp01(s.Q.ReadyRatioCp)
	latDb := clamp01(s.Db.Lat / n.MaxLatUs)
	cCp := w.W[0]*cpuCp + w.W[1]*memCp + w.W[2]*notReadyCp + w.W[3]*latDb

	cpuUp := clamp01(s.Up.Cpu)
	memUp := clamp01(s.Up.Mem)
	bwUp := clamp01(s.Up.Bw / n.MaxBwBps)
	dropUp := clamp01(s.Up.Drop / n.MaxDropPps)
	cpuV := clamp01(s.V.Cpu)
	cUp := w.U[0]*cpuUp + w.U[1]*memUp + w.U[2]*bwUp + w.U[3]*dropUp + w.U[4]*cpuV

	cInfra := w.C[0]*float64(s.W.N) + w.C[1]*float64(s.Cp.Rep) + w.C[2]*float64(s.Up.Rep)

	j := w.A*cCp + w.B*cUp + w.G*cInfra
	return Scores{Cp: cCp, Up: cUp, Infra: cInfra, J: j}
}
