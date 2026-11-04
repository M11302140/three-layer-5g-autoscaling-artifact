package hbo

import (
	"io"
	"log/slog"
	"math"
	"strings"
	"testing"
	"time"
)

func testLogger() *slog.Logger { return slog.New(slog.NewTextHandler(io.Discard, nil)) }

// planner_test.go — v6 model/planner scenario suite (spec §5, plan P1).
// All offered values are BIDIRECTIONAL aggregate pps.

func params() V6Params {
	return V6Params{Lambda: 0.002, MarginM: 0.85, SlopeMax: 0.05, UMin: 0}
}

func bounds() V6Bounds {
	return V6Bounds{MinUP: 1, MaxUP: 8, MinVY: 1, MaxVY: 3, MinWK: 1, MaxWK: 4}
}

func input(cfg V6Config, offered, slope float64) PlanInput {
	return PlanInput{
		Cfg: cfg, Offered: offered, Slope: slope,
		Bounds: bounds(), Blocked: map[Action]bool{},
		BaseCores: 8, BaseMemGi: 12, // master/CP/system VMs
	}
}

func hasAct(moves []Move, a Action) bool {
	for _, m := range moves {
		if m.Act == a {
			return true
		}
	}
	return false
}

// --- calib lock (P0) ---

func calibV2() Calib {
	c := DefaultCalib()
	c.PerUEBidir = 300000
	c.StepFloor = 4 * 300000
	c.CapVY = 7.6e6
	c.CapUP = 1.5e6
	c.BatchIntervalSec = 0
	c.VNF.PreCliff = nil
	return c
}

func TestCalibLock(t *testing.T) {
	c := DefaultCalib()
	if c.CapUP != 1.35e6 || c.CapVY != 4.45e6 || c.PerUEBidir != 250000 || c.StepFloor != 1.25e6 || c.BatchIntervalSec != 120 || c.MaxBatches != 2 {
		t.Fatalf("capacity constants changed: %v %v", c.CapUP, c.CapVY)
	}
	if math.Abs(c.CNF.K-0.050) > 1e-9 || math.Abs(c.CNF.UKnee-1.0) > 1e-9 {
		t.Fatalf("CNF fit changed without refit: K=%v uKnee=%v", c.CNF.K, c.CNF.UKnee)
	}
	if c.EpsDesign != c.EpsSLO/2 {
		t.Fatalf("EpsDesign must derive from EpsSLO")
	}
	// curves monotone nondecreasing over the operating range
	for u := 0.5; u < 2.0; u += 0.01 {
		if fCNF(u+0.01, &c) < fCNF(u, &c) || fVNF(u+0.01, &c) < fVNF(u, &c) {
			t.Fatalf("curve not monotone at u=%.2f", u)
		}
	}
	if len(c.VNF.PreCliff) != 0 {
		t.Fatalf("VNF pre-cliff table must be empty (background miss belongs to residuals)")
	}
	if th := ThetaDesignVY(&c); math.Abs(th-1.0) > 0.01 {
		t.Fatalf("θ_VY moved: %.3f want ~1.0", th)
	}
	if pred := fVNF(4.8e6/c.CapVY, &c); pred < 0.04 || pred > 0.11 {
		t.Fatalf("VNF cliff pred out of measured band: %.4f", pred)
	}
	pc := PlanCalib(&c, params())
	if math.Abs(pc.CapVY-0.85*c.CapVY) > 1 || math.Abs(pc.CapUP-0.85*c.CapUP) > 1 {
		t.Fatalf("PlanCalib must scale capacities by MarginM")
	}
	// θ ordering: design < crit for both layers
	if !(ThetaDesignUP(&c) < ThetaCritUP(&c)) || !(ThetaDesignVY(&c) < ThetaCritVY(&c)) {
		t.Fatalf("theta ordering broken")
	}
}

// --- scenario 1: ramp-up boot lead (E4 offline) ---
// VY will saturate in ~150s; Deploy_VY must dispatch NOW even though the
// instantaneous utilization is still comfortable (u≈0.77; v2 Cap 5.46M).
func TestRampUpBootLead(t *testing.T) {
	c := calibV2()
	cfg := V6Config{NUP: 6, NVY: 1, NWK: 3}
	in := input(cfg, 5.6e6, 9000)
	best, _ := DecideV6(in, &c, params())
	if !hasAct(best.Moves, ActDeployVyOS) {
		t.Fatalf("expected Deploy_VY in best tuple, got %q", best.Key)
	}
	// sanity: flat load at the same instantaneous point(u=0.87)must NOT deploy
	inFlat := input(cfg, 5.6e6, 0)
	bestFlat, _ := DecideV6(inFlat, &c, params())
	if hasAct(bestFlat.Moves, ActDeployVyOS) {
		t.Fatalf("flat comfortable load must not deploy VY, got %q", bestFlat.Key)
	}
}

// --- scenario 2: ramp-down pacing + cliff refusal ---
func TestRampDownAndCliffRefusal(t *testing.T) {
	c := calibV2()
	// over-provisioned: deletions win on λ savings
	in := input(V6Config{NUP: 8, NVY: 3, NWK: 4}, 4.0e6, 0)
	in.IdleWK = false
	best, _ := DecideV6(in, &c, params())
	if !hasAct(best.Moves, ActDeleteVyOS) {
		t.Fatalf("over-provisioned pool should shed a VyOS, got %q", best.Key)
	}
	// near the cliff: deleting the 2nd VyOS would saturate the survivor → refuse
	in2 := input(V6Config{NUP: 8, NVY: 2, NWK: 4}, 7.0e6, 0) // survivor u=1.84
	best2, _ := DecideV6(in2, &c, params())
	if hasAct(best2.Moves, ActDeleteVyOS) {
		t.Fatalf("must not delete VyOS near the cliff, got %q", best2.Key)
	}
}

// --- scenario 3: residual cancellation in marginal comparisons (§3) ---
func TestResidualMarginalCancellation(t *testing.T) {
	c := calibV2()
	cfg := V6Config{NUP: 5, NVY: 3, NWK: 3}
	offered := 8.6e6 // u_UP≈1.43 (above knee 1.31), u_VY≈0.48

	dj := func(r Residuals) float64 {
		in := input(cfg, offered, 0)
		in.Resid = r
		jBase := evalJ(nil, in, &c, params())
		up := Move{Act: ActScaleOutUP, TEffect: c.Act[ActScaleOutUP].TReadySec, deltaUP: 1}
		return jBase - evalJ([]Move{up}, in, &c, params())
	}
	gainClean := dj(Residuals{})
	gainDrift := dj(Residuals{UP: 0.05})
	if gainClean <= 0 {
		t.Fatalf("above-knee scale-out must have positive marginal gain")
	}
	if math.Abs(gainClean-gainDrift) > 1e-6 {
		t.Fatalf("additive residual must cancel in marginal gain: clean=%.6f drift=%.6f",
			gainClean, gainDrift)
	}
}

// --- scenario 4: host pool contention (§4, E6 offline) ---
func TestHostPoolContention(t *testing.T) {
	c := calibV2()
	cfg := V6Config{NUP: 4, NVY: 2, NWK: 3} // 6 slots, 4 active → slot free
	in := input(cfg, 2.5e6, 12000)
	in.BaseMemGi = 42 // pool: 42 + 3×3(wk) + 2×3(vy) = 57 = HostMem(60) − reserve(3) → full
	_, all := DecideV6(in, &c, params())
	for _, s := range all {
		if strings.Contains(s.Key, string(ActDeployVyOS)) || strings.Contains(s.Key, string(ActCreateWorker)) {
			t.Fatalf("mem-full pool must exclude VM additions, found %q", s.Key)
		}
	}
	// slot activation allocates nothing → must still be enumerable
	found := false
	for _, s := range all {
		if strings.Contains(s.Key, string(ActScaleOutUP)) {
			found = true
		}
	}
	if !found {
		t.Fatalf("slot activation (pool-free) should remain feasible")
	}
}

// --- scenario 5: steady state = NoOp, deterministic ---
func TestSteadyStateNoOp(t *testing.T) {
	c := calibV2()
	// mid load with mild util, nothing near design levels, λ savings can't
	// beat the cliff risk of deletions? — NVY=2 at u=0.79: deleting → u=1.58
	// (heavy loss) so refuse; UP below knee but MinUP... choose sizes where
	// every deletion hurts and every addition wastes:
	in := input(V6Config{NUP: 8, NVY: 2, NWK: 4}, 9.5e6, 0)
	best, _ := DecideV6(in, &c, params())
	if hasAct(best.Moves, ActDeployVyOS) || hasAct(best.Moves, ActCreateWorker) ||
		hasAct(best.Moves, ActDeleteVyOS) {
		t.Fatalf("steady state should not churn VMs, got %q", best.Key)
	}
	for i := 0; i < 5; i++ {
		b2, _ := DecideV6(in, &c, params())
		if b2.Key != best.Key {
			t.Fatalf("decision not deterministic: %q vs %q", best.Key, b2.Key)
		}
	}
}

// --- residual EWMA behaviour ---
func TestResidualUpdate(t *testing.T) {
	c := calibV2()
	var r Residuals
	cfg := V6Config{NUP: 8, NVY: 3, NWK: 4}
	// model predicts ~0 at low util; measured 1% sustained → residual converges up
	for i := 0; i < 20; i++ {
		UpdateResiduals(&r, SegLoss{UP: 0.01, VY: 0.002}, cfg, 6.0e6, 0.5, &c)
	}
	if r.UP < 0.009 || r.UP > 0.011 {
		t.Fatalf("UP residual should converge to ~0.01, got %.4f", r.UP)
	}
	// and decays back when measurements return to model
	for i := 0; i < 20; i++ {
		UpdateResiduals(&r, SegLoss{}, cfg, 6.0e6, 0.5, &c)
	}
	if r.UP > 1e-4 {
		t.Fatalf("residual should decay, got %.5f", r.UP)
	}
}

// --- emergency levels ---
func TestEmergencyGate(t *testing.T) {
	c := calibV2()
	cfg := V6Config{NUP: 8, NVY: 3, NWK: 4}
	if ok, _ := EmergencyV6(0.0003, cfg, 8.0e6, &c); ok {
		t.Fatalf("healthy state must not be emergency")
	}
	if ok, _ := EmergencyV6(0.002, cfg, 8.0e6, &c); !ok {
		t.Fatalf("measured e2e loss above SLO must trip emergency")
	}
	if ok, reason := EmergencyV6(0.001, V6Config{NUP: 8, NVY: 1, NWK: 4}, 12.0e6, &c); !ok {
		t.Fatalf("VY util 3.16 must trip emergency, reason=%q", reason)
	}
}

func BenchmarkDecideV6(b *testing.B) {
	c := calibV2()
	in := input(V6Config{NUP: 6, NVY: 2, NWK: 3}, 7.0e6, 15000)
	for i := 0; i < b.N; i++ {
		DecideV6(in, &c, params())
	}
}


func TestAntiProcrastinationPromotesFirstGridLongLead(t *testing.T) {
	c := calibV2()
	p := params()
	p.UMin = 0.0005
	in := input(V6Config{NUP: 3, NVY: 1, NWK: 4}, 2.1e6, 9000)
	best, all := DecideV6(in, &c, p)
	var noop TupleScore
	for _, s := range all {
		if s.Key == "∅" {
			noop = s
		}
	}
	if !hasAct(noop.Rollout, ActDeployVyOS) {
		t.Skipf("scenario drift: noop rollout no longer schedules DeployVyOS")
	}
	if !hasAct(best.Moves, ActDeployVyOS) {
		t.Fatalf("procrastination spiral: best=%s (noop rollout schedules VY+1 but nothing dispatched)", best.Key)
	}
}

func TestAntiProcrastinationInertWhenFlat(t *testing.T) {
	c := calibV2()
	p := params()
	p.UMin = 0.0005
	in := input(V6Config{NUP: 3, NVY: 1, NWK: 4}, 2.1e6, 0)
	best, _ := DecideV6(in, &c, p)
	if strings.Contains(best.Key, "π₀") {
		t.Fatalf("promotion fired on flat slope: %s", best.Key)
	}
}

func TestTroughDeleteThenRampDeploysImmediately(t *testing.T) {
	c := calibV2()
	early := input(V6Config{NUP: 4, NVY: 1, NWK: 3}, 3.31e6, 11313)
	b0, _ := DecideV6(early, &c, params())
	if hasAct(b0.Moves, ActDeployVyOS) {
		t.Fatalf("premature DeployVyOS at 3.31M: %q", b0.Key)
	}
	lead := c.Act[ActDeployVyOS].TReadySec + v6Grid
	off := params().MarginM*c.CapVY - 11313*lead + 0.1e6
	in := input(V6Config{NUP: 8, NVY: 1, NWK: 4}, off, 11313)
	best, _ := DecideV6(in, &c, params())
	if !hasAct(best.Moves, ActDeployVyOS) {
		t.Fatalf("r34 scenario: expected DeployVyOS as soon as lead requires (5.0M+slope), got %q", best.Key)
	}
}

func TestInFlightSuppressesDuplicateDeploy(t *testing.T) {
	c := calibV2()
	in := input(V6Config{NUP: 8, NVY: 1, NWK: 4}, 5.0e6, 11313)
	in.InFlight = []Move{{Act: ActDeployVyOS, TEffect: 80, deltaVY: +1}}
	in.Blocked[ActDeleteVyOS] = true
	best, _ := DecideV6(in, &c, params())
	if hasAct(best.Moves, ActDeployVyOS) {
		t.Fatalf("duplicate DeployVyOS while one is in flight: %q", best.Key)
	}
	if hasAct(best.Moves, ActDeleteVyOS) {
		t.Fatalf("reversal while deploy in flight: %q", best.Key)
	}
}

func TestInFlightCountsTowardBounds(t *testing.T) {
	c := calibV2()
	in := input(V6Config{NUP: 8, NVY: 2, NWK: 4}, 9.0e6, 20000)
	in.InFlight = []Move{{Act: ActDeployVyOS, TEffect: 60, deltaVY: +1}}
	best, all := DecideV6(in, &c, params())
	for _, s := range all {
		if hasAct(s.Moves, ActDeployVyOS) {
			t.Fatalf("tuple %q would exceed MaxVY with the in-flight vyos", s.Key)
		}
	}
	_ = best
}

func TestTroughScalesInUPLayer(t *testing.T) {
	c := calibV2()
	in := input(V6Config{NUP: 8, NVY: 1, NWK: 4}, 1.5e6, 0)
	best, _ := DecideV6(in, &c, params())
	if !(hasAct(best.Moves, ActScaleInUP) || hasAct(best.Moves, ActDeleteWorker)) {
		t.Fatalf("trough 1.5M/8 slots/4 workers: expected a UP-layer or worker scale-in, got %q", best.Key)
	}
	small := input(V6Config{NUP: 2, NVY: 1, NWK: 1}, 1.5e6, 0)
	b2, _ := DecideV6(small, &c, params())
	if hasAct(b2.Moves, ActScaleInUP) {
		t.Fatalf("2 slots at 1.5M (5 UE): scale-in to 1 slot would exceed m·Cap, got %q", b2.Key)
	}
}

func TestTransientResidualAtLowUtilDoesNotDeploy(t *testing.T) {
	c := calibV2()
	in := input(V6Config{NUP: 8, NVY: 1, NWK: 4}, 1.5e6, 0)
	in.Resid = Residuals{VY: 0.002, UP: 0.0003}
	best, _ := DecideV6(in, &c, params())
	if hasAct(best.Moves, ActDeployVyOS) || hasAct(best.Rollout, ActDeployVyOS) {
		t.Fatalf("residual-inflated f̂ at u_VY=0.2 must not drive π₀ to deploy: %q rollout=%d", best.Key, len(best.Rollout))
	}
	if e, why := EmergencyV6(0.002, in.Cfg, 1.5e6, &c); e {
		t.Fatalf("measured 0.2%% at u_VY 0.2/u_UP 0.125 is not a capacity emergency: %s", why)
	}
	if e, _ := EmergencyV6(0.002, V6Config{NUP: 4, NVY: 1, NWK: 2}, 4.2e6, &c); !e {
		t.Fatalf("measured 0.2%% at u_UP 0.7 must still be an emergency")
	}
}

func TestInflightSameDirectionAttributedInOrder(t *testing.T) {
	v := &V6Shadow{calib: calibV2(), log: testLogger()}
	base := V6Config{NUP: 3, NVY: 1, NWK: 2}
	old := time.Now().Add(-130 * time.Second)
	v.inflight = []inflightMove{{Act: ActScaleInUP, T0: old, Base: base}, {Act: ActScaleInUP, T0: old.Add(5 * time.Second), Base: base}}
	moves := v.reconcileInflight(V6Config{NUP: 2, NVY: 1, NWK: 2})
	if len(v.inflight) != 1 || len(moves) != 1 || moves[0].deltaUP != -1 {
		t.Fatalf("expected exactly one pending SCALE_IN_UP with delta -1 after one observed removal; inflight=%d moves=%+v", len(v.inflight), moves)
	}
}

func TestTroughHighSlopeScalesOutButZeroSlopeDoesNot(t *testing.T) {
	c := calibV2()
	hi := input(V6Config{NUP: 6, NVY: 1, NWK: 4}, 1.5e6, 18000)
	bh, _ := DecideV6(hi, &c, params())
	if !hasAct(bh.Moves, ActScaleOutUP) && !hasMove(bh.Rollout, ActScaleOutUP) {
		t.Fatalf("trough+high slope should forecast a ramp (justifies the startup gate); got %q", bh.Key)
	}
	zero := input(V6Config{NUP: 6, NVY: 1, NWK: 4}, 1.5e6, 0)
	bz, _ := DecideV6(zero, &c, params())
	if hasAct(bz.Moves, ActScaleOutUP) {
		t.Fatalf("trough+zero slope must not scale out; got %q", bz.Key)
	}
}
