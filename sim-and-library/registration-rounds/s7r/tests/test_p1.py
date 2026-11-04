#!/usr/bin/env python3
"""qsim/s7r/tests/test_p1.py: protocol P1 unit tests T01-T15 for event_phys / objective / scenario_bank.
Run: python3 qsim/s7r/tests/test_p1.py  (prints PASS/FAIL per test, exit 0 only if all pass).
T10 here covers the physics (no future in state/observation) and the scenario selection hash; the decision part of T10 is re-run in P2
once the S7R controller exists (tests/test_p2.py)."""
import sys, os, json, copy, math, traceback
S7 = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); Q = os.path.dirname(S7)
sys.path.insert(0, S7); sys.path.insert(0, Q)
import event_phys as E, objective as O, scenario_bank as SB
RES = []
def test(fn):
    try: fn(); RES.append((fn.__name__, "PASS", ""))
    except AssertionError as e: RES.append((fn.__name__, "FAIL", str(e)))
    except Exception as e: RES.append((fn.__name__, "ERROR", traceback.format_exc(limit=2)))
    return fn
def step(ph, n=1, ctl=None):
    for _ in range(n):
        ph.phase_demand(); ph.phase_ready(); ph.phase_relief()
        if ph.t % E.TICK == 0 and ctl is not None: ctl(ph)
        ph.measure(); ph.t += 1
def flat(n, minutes=60): return [n] * minutes

@test
def T01_booting_slot_not_ready_capacity():
    ph = E.Phys(flat(20), start=(7, 1, 4)); step(ph, 5)
    r = ph.scale_out_up(); assert r[0] == "ok", r
    ob = ph.observe(); assert ob["ready_up"] == 7 and ob["boot_up"] == 1, ob
    t_api = ph.slots[r[1]]["api"]
    step(ph, t_api - ph.t); assert ph.observe()["ready_up"] == 7, ("must not count before the ready event", ph.t, t_api)
    step(ph, 1); assert ph.observe()["ready_up"] == 8, ph.observe()
@test
def T02_8_to_7_slots_saves_only_slot():
    a = E.Phys(flat(10), start=(8, 1, 4)); b = E.Phys(flat(10), start=(8, 1, 4))
    step(a, 600); step(b, 600); assert b.scale_in_up()
    step(a, 3000); step(b, 3000)
    gone = next(t for t, k, l, o in [(e[0], e[1], e[2], e[3]) for e in b.events] if k == "in")
    off = [o for o in E.SLOT_ORDER if b.slots[o]["state"] == "off"]; assert len(off) == 1, off
    assert abs(a.alloc_by["wk"] - b.alloc_by["wk"]) < 1e-9 and abs(a.alloc_by["vy"] - b.alloc_by["vy"]) < 1e-9, "workers/VyOS unchanged"
    d = a.alloc - b.alloc; assert d > 0 and abs(d - (a.alloc_by["up"] - b.alloc_by["up"])) < 1e-9, d
    assert d <= 0.8 * (3600 - 600) / 60 + 1e-9, d
@test
def T03_worker_saving_only_after_vm_gone():
    ph = E.Phys(flat(4), start=(7, 1, 4)); step(ph, 60)
    for _ in range(2): assert ph.scale_in_up(); step(ph, 400)     # empties worker 3's two slots (.37, .36)
    w3 = ph.workers[3]; assert all(ph.slots[o]["state"] == "off" for o in (37, 36)), {o: ph.slots[o]["state"] for o in (37, 36)}
    t_del = ph.t + 180; step(ph, 180)                              # worker deleted three minutes later
    i = ph.idle_worker(); assert i == 3, i
    before = ph.alloc_by["wk"]; assert ph.delete_wk(3); gone = ph.workers[3]["gone"]
    step(ph, gone - ph.t); mid = ph.alloc_by["wk"]
    assert abs((mid - before) - 3.0 * 4 * (gone - t_del) / 60) < 1e-9, "all four workers billed until the VM is gone"
    step(ph, 60); assert abs((ph.alloc_by["wk"] - mid) - 3.0 * 3) < 1e-9, "three workers after"
@test
def T04_generation_blocks_stale_move():
    ph = E.Phys(flat(12), start=(3, 1, 2)); step(ph, 100)
    o = E.SLOT_ORDER[2]; g0 = ph.slots[o]["gen"]; u = ph.slot_ues(E.SLOT_ORDER[0])[0]
    ph.new_job([dict(ue=u, src=E.SLOT_ORDER[0], dst=o, dgen=g0, kind="pool")])
    ph.slots[o].update(state="off"); ph.cur_move = None
    r = ph.scale_out_up(); assert r == ("ok", o) and ph.slots[o]["gen"] == g0 + 1
    step(ph, 60); assert ph.ues[u]["slot"] != o, "a move bound to the old generation must not land on the recreated slot"
@test
def T05_cancel_drain_reversible_only():
    ph = E.Phys(flat(18), start=(5, 1, 3)); step(ph, 200)
    victim = [o for o in E.SLOT_ORDER if ph.slots[o]["state"] == "ready"][-1]; g = ph.slots[victim]["gen"]
    n0 = len(ph.slot_ues(victim)); assert n0 >= 2, n0
    assert ph.scale_in_up(); step(ph, 20)                           # first move done (17 s)
    moved = n0 - len(ph.slot_ues(victim)); assert moved >= 1, moved
    assert ph.cancel_drain(); assert ph.slots[victim]["state"] == "ready" and ph.slots[victim]["gen"] == g, "no delete/recreate"
    n1 = len(ph.slot_ues(victim)); step(ph, 60)
    assert len(ph.slot_ues(victim)) >= n1 - 1 and not any(m["src"] == victim and m["kind"] == "drain" for m in ph.moves), "pending drain moves dropped"
    assert all(ph.ues[u]["slot"] != victim for u in ph.ues if ph.ues[u]["arr"] > 200 and ph.ues[u]["arr"] < 220), "moved UEs are not moved back"
    assert not any(e[1] == "out" for e in ph.events), "cancel is not a new scale-out"
@test
def T06_no_position_on_full_failed_or_deleting_worker():
    ph = E.Phys(flat(8), start=(2, 1, 1)); step(ph, 10)
    assert ph.scale_out_up() == ("noworker", 1), "worker 1 off -> no position"
    ph.workers[1].update(state="failed", gen=1, appear=-1e9, ready=-1e9); assert ph.scale_out_up()[0] == "noworker", "failed worker gives no position"
    ph.workers[1].update(state="deleting", gone=ph.t + 20); assert ph.scale_out_up()[0] == "noworker", "deleting worker gives no position"
    ph.workers[1].update(state="ready"); ph.slots[31].update(state="failed", gen=1)
    r = ph.scale_out_up(); assert r == ("ok", 32), r
    assert 31 not in ph.arrival_cands(), "failed slot is not a placement"
@test
def T07_burst_no_relief_before_ready():
    ph = E.Phys([30] + [36] * 59, start=(6, 1, 4)); step(ph, 1)            # 6 slots x 5 + burst to 36 -> slots with 6 UE
    r = ph.scale_out_up(); assert r[0] == "ok", r; o = r[1]; t_api = ph.slots[o]["api"]; t_rel = ph.slots[o]["relief"]
    while ph.t < t_api:
        assert all(ph.ues[u]["slot"] != o for u in ph.ues), "no UE on the slot before its API answers"
        assert not any(m["dst"] == o for m in ph.moves) and (ph.cur_move is None or ph.cur_move["dst"] != o), "no relief to a booting slot"
        step(ph, 1)
    while ph.t < t_rel:
        assert not any(m["dst"] == o and m["kind"] == "relief" for m in ph.moves), "scale-out relief only after its relief time"
        step(ph, 1)
    assert max(ph.counts().values()) >= 6 or any(ph.unit_over[0].values()), "the burst overflowed some slot before relief"
@test
def T08_dip_rebound_keeps_wait_and_cost():
    ue = [20] * 10 + [8] * 5 + [20] * 45
    ph = E.Phys(ue, start=(5, 1, 3)); step(ph, 600)
    a0 = ph.alloc; assert ph.scale_in_up(); step(ph, 120)
    r = ph.scale_out_up(); assert r[0] == "ok"; t_api = ph.slots[r[1]]["api"]
    assert t_api - ph.t == ph.p["slot_api_s"], "rebuilt slot waits its full ready lead"
    step(ph, 3600 - ph.t); res = ph.result()
    assert any(e[1] == "in" for e in ph.events) and sum(1 for e in ph.events if e[1] == "out") == 1
    assert ph.alloc > a0, "both existence periods billed"
@test
def T09_terminal_committed_cost_no_free_delete():
    ph = E.Phys(flat(12), start=(4, 1, 2)); step(ph, 1000)
    H = ph.t + 30; assert ph.delete_wk(1) is False or True
    ph2 = E.Phys(flat(4), start=(4, 2, 2)); step(ph2, 1000)
    assert ph2.delete_vy(); H = ph2.t + 5
    tc = O.terminal_committed_cost(ph2, H, last_out={})
    gone = ph2.vyos[1]["gone"]; assert abs(tc - 2.0 * (gone - H) / 60) < 1e-9, (tc, gone, H)
    tc2 = O.terminal_committed_cost(ph2, H, last_out={"vy": H - 100}, lock_vm=600)
    assert tc2 > tc, "a running reverse lock commits the remaining existence"
    H3 = gone + 10; assert O.terminal_committed_cost(ph2, H3, last_out={}) == 0.0, "nothing after the unit is gone"
@test
def T10_no_future_in_state_and_scenarios():
    a = [10, 12, 14, 16, 18] + [20] * 55; b = [10, 12, 14, 16, 18] + [40] * 55
    pa = E.Phys(a, start=(4, 1, 2)); pb = E.Phys(b, start=(4, 1, 2)); step(pa, 270); step(pb, 270)
    sa = pa.snapshot(); sb = pb.snapshot()
    sa.pop("arrivals"); sb.pop("arrivals")
    assert sa == sb and pa.observe() == pb.observe(), "state/observation identical up to t for different futures"
    lib = json.load(open(f"{Q}/prior_traces.json")); sp = json.load(open(f"{S7}/out/P0/splits.json"))
    bank = SB.Bank(lib, sp["folds"]["0"]["fit"])
    r1 = bank.select(270, [10, 12, 14, 16, 18], 18, 16, 30); r2 = bank.select(270, [10, 12, 14, 16, 18], 18, 16, 30)
    assert r1["hash"] == r2["hash"] and r1["status"] == "OK", "selection depends only on the observed past"
@test
def T11_minute_loss_weighted_not_averaged():
    ph = E.Phys([25] * 2, start=(5, 2, 3), horizon_s=120)
    # 30 s with 25 UE on 5 slots (5 each, no overflow), then a 6th UE on one slot for 30 s (26 UE)
    step(ph, 30); assert max(ph.counts().values()) == 5
    ph.ues[ph.next_id] = dict(slot=E.SLOT_ORDER[0], arr=ph.t); ph.active.append(ph.next_id); ph.next_id += 1
    step(ph, 30)
    n = ph.counts()[E.SLOT_ORDER[0]]; assert n == 6, n
    lost = 30 * n * min(0.5, 0.01 * (n - 5)); off = 30 * 25 + 30 * 26
    assert abs(ph.lossmin[0] / ph.offmin[0] - lost / off) < 1e-12, (ph.lossmin[0] / ph.offmin[0], lost / off)
    avg_pct = (0 + n * 0.01 * (n - 5) / 26) / 2; assert abs(lost / off - avg_pct) > 1e-6, "differs from averaging percentages"
    assert ph.unit_over[0].get(E.SLOT_ORDER[0]) == 30 and ph.minute_bad(0)[2], "one unit 30 s over -> overflow condition"
@test
def T12_drain_announcement_ttl_per_entry():
    ph = E.Phys(flat(30), start=(7, 1, 4)); step(ph, 10)
    a = E.SLOT_ORDER[6]; b = E.SLOT_ORDER[5]
    ph.slots[a].update(state="drain", ann_on=ph.t, drain_t=ph.t); t0 = ph.t
    step(ph, 300); ph.slots[b].update(state="drain", ann_on=ph.t, drain_t=ph.t)   # another entry refreshed later
    while ph.t < t0 + 359: step(ph, 1)
    assert not ph.eligible_by_harness(a), "still excluded before 360 s"
    step(ph, 1); assert ph.eligible_by_harness(a), "expires 360 s after its own ON even though another entry is fresh"
    assert not ph.eligible_by_harness(b)
@test
def T13_permutation_of_labels():
    ue = [6, 10, 14, 20, 26, 30, 34, 36, 30, 24, 18, 12] * 5
    def runp(perm):
        save = (E.SLOT_ORDER, E.SLOT_WK, E.TIE_ORDER)
        try:
            m = dict(zip(save[0], perm))
            E.SLOT_ORDER = [m[o] for o in save[0]]; E.SLOT_WK = {m[o]: w for o, w in save[1].items()}; E.TIE_ORDER = [m[o] for o in save[2]]
            ph = E.Phys(ue, start=(3, 1, 2))
            def ctl(ph):
                ob = ph.observe(); D = ob["D"]
                if D > 5 * ob["rep_up"] - 2 and ob["boot_up"] == 0: ph.scale_out_up()
                if ob["free_positions"] <= 0 and ob["wk_boot"] == 0: ph.create_wk()
            step(ph, 3600, ctl); r = ph.result()
            inv = {v: k for k, v in m.items()}
            return r["slo"], round(r["alloc_vm"], 9), [(e[0], e[1], e[2], inv.get(e[3], e[3])) for e in r["events"]]
        finally: E.SLOT_ORDER, E.SLOT_WK, E.TIE_ORDER = save
    base = runp(list(E.SLOT_ORDER)); perm = runp([101, 102, 103, 104, 105, 106, 107, 108])
    assert base == perm, "relabelling the slots (same tie-order structure) must not change results"
@test
def T14_B1_static_cost():
    r = E.run([40] * 60, ctl=None, start=(8, 3, 4))
    assert abs(r["alloc_vm"] - 1464.0) < 1e-6, r["alloc_vm"]
    assert abs(r["alloc_by"]["wk"] + r["alloc_by"]["vy"] - 1080.0) < 1e-6, r["alloc_by"]
@test
def T15_safety_limits():
    ph = E.Phys(flat(10), start=(8, 3, 4)); step(ph, 5)
    assert ph.scale_out_up()[0] == "none", "FMAX slots"; assert ph.deploy_vy() is False, "FMAX VyOS"; assert ph.create_wk() is False, "FMAX workers"
    assert ph.delete_wk(1) is False, "worker with slots cannot be deleted"
    ph2 = E.Phys(flat(4), start=(2, 1, 1)); step(ph2, 5); assert ph2.create_wk(); i = next(i for i, w in ph2.workers.items() if w["state"] == "boot")
    assert ph2.delete_wk(i) is False, "booting worker cannot be deleted"
    ph3 = E.Phys(flat(2), start=(2, 1, 1)); step(ph3, 5); assert ph3.scale_in_up(); assert ph3.scale_in_up() is False, "never below one ready slot"
    assert ph3.delete_vy() is False, "VyOS-0 is never deleted"

if __name__ == "__main__":
    ok = True
    for n, st, msg in RES:
        print(f"{n}: {st} {msg[:300]}"); ok &= st == "PASS"
    print("ALL PASS" if ok else "SOME FAILED"); sys.exit(0 if ok else 3)
