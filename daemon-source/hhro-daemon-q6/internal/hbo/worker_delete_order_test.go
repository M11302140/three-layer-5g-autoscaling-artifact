package hbo

import (
	"testing"
	"time"
)

func r50TailShadow(withDrain bool) *V6Shadow {
	v := NewV6Shadow(testLogger())
	v.calib = DefaultCalib()
	v.Enabled = true
	now := time.Now()
	var flat [][2]float64
	for ago := 600.0; ago >= 30; ago -= 30 {
		flat = append(flat, [2]float64{ago, 2.5})
	}
	v.offHist = hist(now, flat)
	if withDrain {
		v.inflight = []inflightMove{{Act: ActScaleInUP, T0: now.Add(-117 * time.Second), Base: V6Config{NUP: 5, NVY: 2, NWK: 3}}}
	}
	return v
}

func r50TailState() (FeatureSet, SystemState) {
	f := FeatureSet{PktRateUP: WindowFeature{Now: 2.5e6, Avg30: 2.5e6, Avg60: 2.5e6, P90_60: 2.5e6, Slope120: -3}}
	s := SystemState{RepUP: 4, ReadyUP: 4, WorkerCount: 3, ReadyWorkers: 3, VyosCount: 2, VyosAdmitted: 2,
		OfferedPPS: 1.25e6, UECount: 10, IdleWorker: "worker-2"}
	return f, s
}

func TestInFlightSlotDrainBlocksWorkerDelete(t *testing.T) {
	cfg := DefaultCfg()
	f, s := r50TailState()

	v0 := r50TailShadow(false)
	v0.Tick(f, s, NewTimers(cfg), cfg, false)
	if !v0.Last.Valid || v0.Last.In.Blocked[ActDeleteWorker] {
		t.Fatalf("baseline: DELETE_WORKER must not be blocked without an in-flight drain (valid=%v)", v0.Last.Valid)
	}
	if !hasAct(v0.Last.Best.Moves, ActDeleteWorker) {
		t.Fatalf("baseline: idle worker at 10 UE plateau should be a delete candidate, got %q", v0.Last.Best.Key)
	}

	v1 := r50TailShadow(true)
	v1.Tick(f, s, NewTimers(cfg), cfg, false)
	if !v1.Last.Valid || !v1.Last.In.Blocked[ActDeleteWorker] {
		t.Fatalf("in-flight slot drain must block DELETE_WORKER (valid=%v blocked=%v)", v1.Last.Valid, v1.Last.In.Blocked[ActDeleteWorker])
	}
	if hasAct(v1.Last.Best.Moves, ActDeleteWorker) {
		t.Fatalf("DELETE_WORKER dispatched while slot drain in flight: %q", v1.Last.Best.Key)
	}
}

func TestSlotDrainBeforeWorkerDelete(t *testing.T) {
	in := []Decision{{Action: ActDeleteWorker}, {Action: ActScaleInUP}, {Action: ActDeleteVyOS}}
	kept, dropped := slotDrainBeforeWorkerDelete(in)
	if !dropped || len(kept) != 2 || kept[0].Action != ActScaleInUP || kept[1].Action != ActDeleteVyOS {
		t.Fatalf("worker delete must be dropped behind a same-tick slot drain: dropped=%v kept=%v", dropped, kept)
	}
	only := []Decision{{Action: ActDeleteWorker}, {Action: ActDeleteVyOS}}
	kept, dropped = slotDrainBeforeWorkerDelete(only)
	if dropped || len(kept) != 2 {
		t.Fatalf("no slot drain this tick: list must pass through unchanged, dropped=%v kept=%v", dropped, kept)
	}
}

func TestWorkerDeleteDeferredWhileSlotScaleInWanted(t *testing.T) {
	_, cal := holdFixture()
	moves := []Move{{Act: ActDeleteWorker}, {Act: ActScaleInUP}, {Act: ActDeleteVyOS}}
	t.Setenv("V6_UP_SCALEIN_HOLD_S", "0")
	if !workerDeleteLocksSlotLayer(moves, SystemState{RepUP: 4, WorkerCount: 3}, cal) {
		t.Fatal("4 slots / 3 workers with SCALE_IN_UP wanted: deleting a worker leaves the pool full — must defer")
	}
	if workerDeleteLocksSlotLayer(moves, SystemState{RepUP: 4, WorkerCount: 4}, cal) {
		t.Fatal("4 slots / 4 workers: a free position remains after deletion — no need to defer (r51 19:19:09)")
	}
	if workerDeleteLocksSlotLayer([]Move{{Act: ActDeleteWorker}}, SystemState{RepUP: 4, WorkerCount: 3}, cal) {
		t.Fatal("no SCALE_IN_UP wanted: idle worker delete must not be deferred")
	}
	t.Setenv("V6_UP_SCALEIN_HOLD_S", "300")
	if workerDeleteLocksSlotLayer(moves, SystemState{RepUP: 6, WorkerCount: 4}, cal) {
		t.Fatal("p5u10: 6 slots / 4 workers under a 300 s hold — the scale-in window does not lengthen, must not defer")
	}
	t.Setenv("V6_UP_SCALEIN_HOLD_S", "0")
	if !workerDeleteLocksSlotLayer(moves, SystemState{RepUP: 8, WorkerCount: 4}, cal) {
		t.Fatal("p5u10: 8 slots / 4 workers — after deletion even the scaled-in pool is full, window lengthens, must defer")
	}
}

func TestWorkerDeleteHeadroom(t *testing.T) {
	c := DefaultCalib()
	cal := PlanCalib(&c, V6Params{Lambda: 0.002, MarginM: 0.93, SlopeMax: 0.05, UMin: 0})
	if nb := workerLeadBatches(cal); nb != 2 {
		t.Fatalf("calib lead (100+15+30 s)/120 s → 2 batches, got %d", nb)
	}
	if need, pos, _, ok := workerDeleteHeadroomOK(4.75e6, SystemState{RepUP: 6, WorkerCount: 4}, cal); !ok {
		t.Fatalf("r77 tail: 19 UE + 2 batches fits 6 positions, must allow (need %d pos %d)", need, pos)
	}
	if need, pos, _, ok := workerDeleteHeadroomOK(6.27e6, SystemState{RepUP: 6, WorkerCount: 4}, cal); ok {
		t.Fatalf("r79 min3: 25 UE + 2 batches needs 7 slots > 6 positions, must defer (need %d pos %d)", need, pos)
	}
	if _, _, _, ok := workerDeleteHeadroomOK(1e6, SystemState{RepUP: 8, WorkerCount: 4}, cal); ok {
		t.Fatal("8 slots cannot fit 6 positions regardless of load")
	}
	if _, _, _, ok := workerDeleteHeadroomOK(3.75e6, SystemState{RepUP: 5, WorkerCount: 4}, cal); !ok {
		t.Fatal("trace 1 tail 15 UE / 5 slots / 4 workers must allow")
	}
}
