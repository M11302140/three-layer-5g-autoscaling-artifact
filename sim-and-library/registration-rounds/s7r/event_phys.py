#!/usr/bin/env python3
"""qsim/s7r/event_phys.py (S7R protocol §2.1, P1): event-level physics, the common evaluation environment of every arm.

Derived from v8sim11.Phys (the per-slot engine checked in gate 1 against t1/t2/t4 runs), with these deliberate changes:
  * 1 s event grid (integer-second event times); fixed intra-second order (documented in Phys.second):
      (1) minute boundary: LIFO departures, arrival schedule; (2) arrivals due -> harness placement; (3) ready/gone transitions;
      (4) relief triggers, drain progress, serial moves; (5) control tick (t % 30 == 0): controller, hot-slot relief, pool relief;
      (6) measurement of [t, t+1): loss, per-unit overflow seconds, alloc_vm cost.
  * no R38 (no lowered knee on .38): overload is explicit -- a slot holding n > 5 UEs overflows (6 UEs on a 5-UE slot);
  * every slot / worker / VyOS carries a generation; moves and drains are bound to (id, generation), so a deleted-and-recreated slot
    cannot receive an old move or be scaled in by a stale order;
  * three separate drain notions per slot: actual_draining (state 'drain'), announced (on_ts, retracted when the pod is deleted),
    eligible_by_harness (r34c: excluded only while the announcement is younger than SLOT_DRAIN_TTL_S = 360 s, per entry);
  * 'failed' state for slots/workers (pending cleanup): occupies a position, never a placement/target, still billed;
  * bad minute = traffic-weighted loss fraction > 0.1 % OR some single unit overflowing >= 10 s in that minute (per unit, not union);
  * cost = alloc_vm (vmexist): worker 3 cores and VyOS 2 cores while the VM exists (appears +15 s after dispatch, gone +20 s after delete),
    slot 0.8 core while the pod exists (dispatch -> deletion);
  * capacities named apart: slot knee 5 UE; VyOS provisioning capacity 4.45 Mpps x 0.93 / 250 kpps = 16.55 UE (controllers' need()),
    VyOS overflow-model knee 18 UE (this file's loss model).
Physics constants (PHYS) are profiling values: v8sim11's (fit on development runs t1/t2/t4) except three taken from the logs of the
profiling runs r500/r502/r505: arrival timing (offsets p50 6-10 s, p90 14-20 s; serial spawns -> first +2 s, gap 3 s, cutoff +40 s);
worker ready 51 s (create_worker -> 'eupf worker provisioned' 47-58 s, median 51; v8sim11 had 90); scale-out relief right after the slot
API answers (dispatch -> 'rehome (scale-out) done' 18-33 s; v8sim11 had +20 s). VyOS deploy -> dataplane ready 82 s (r500) = the kept 80 s.
[disclosed] the worker/relief update was triggered by the first causal-replay smoke test on validation run r504 (injected slot orders
infeasible because the model's worker was not ready yet); the new values come from the profiling runs only.
These runs are therefore profiling runs and are excluded from model validation (protocol P1).
Not a p99 model: reports modeled_loss_risk / modeled_overflow_risk; hardware SLO risk is a separate quantity.
Interface used by the controllers (same as v8sim11): t, observe(), scale_out_up(), scale_in_up(), cancel_drain(), deploy_vy(), delete_vy(),
create_wk(), delete_wk(i), workers[i]['ready'], hot_relief(), enqueue_pool_relief(), last_pool_relief.
"""
import sys, os, math, json, copy
import numpy as np
Q = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, Q)

DT = 1; TICK = 30
SLOT_ORDER = [38, 33, 31, 32, 34, 35, 37, 36]          # activation order (eupf-0 .. eupf-7)
SLOT_WK = {38: 0, 33: 0, 31: 1, 32: 1, 34: 2, 35: 2, 37: 3, 36: 3}
TIE_ORDER = [38, 31, 32, 33, 34, 35, 36, 37]           # harness OCT_DNN order internet, internet2, ...
FMAX = dict(up=8, vy=3, wk=4); FMIN = dict(up=2, vy=1, wk=1)
CORES = dict(wk=3.0, vy=2.0, up=0.8)
PHYS = dict(knee=5, over_frac=0.01, p99_over_s=10, vy_knee=18, vy_over_frac=0.003,
            slot_api_s=15, relief_delay_s=0, move_s=17, release_delay_s=75, release_tail_s=10, empty_delete_s=30,
            vy_admit_s=80, vm_appear_s=15, vm_gone_s=20, wk_ready_s=51,
            age_min_s=90, donor_min=5, recv_max=5, pool_relief_s=150, hot_ticks=2, hot_cooldown_s=120, pack_cap=5,
            arr_first_s=2, arr_gap_s=3, arr_cutoff_s=40, idle_nopod_s=120, idle_age_s=300, drain_ttl_s=360)
LOSS_BAD = 0.001

class Phys:
    def __init__(s, ue, start=None, p=None, horizon_s=3600):
        s.p = dict(PHYS); s.p.update(p or {}); s.ue = list(ue); s.t = 0; s.horizon_s = horizon_s
        s.ues = {}; s.next_id = 0; s.active = []
        s.slots = {o: dict(state="off", gen=0, disp=None, api=None, relief=None, relief_done=True, drain_t=None, drain_empty=None,
                           ann_on=None, hot=0, hot_cool=-1e9) for o in SLOT_ORDER}
        s.workers = {i: dict(state="off", gen=0, disp=None, ready=None, gone=None, appear=None, last_pod_gone=-1e9) for i in range(4)}
        s.vyos = {i: dict(state="off", gen=0, disp=None, adm=None, gone=None, appear=None) for i in range(3)}
        s.moves = []; s.cur_move = None; s.jobs = {}; s.job_seq = 0; s.arrivals = []
        s.last_pool_relief = -1e9; s.events = []
        nmin = max(1, (horizon_s + 59) // 60)
        s.lossmin = np.zeros(nmin); s.offmin = np.zeros(nmin); s.permin = np.zeros(nmin)
        s.unit_over = [dict() for _ in range(nmin)]      # minute -> {unit: overflow seconds}
        s.alloc = 0.0; s.alloc_by = dict(wk=0.0, vy=0.0, up=0.0); s.slot_hist = []; s._over = {}
        n_up, n_vy, n_wk = start if start else (2, 1, 1)
        for i in range(n_wk): s.workers[i].update(state="ready", gen=1, disp=-1e9, ready=-1e9, appear=-1e9)
        for i in range(n_vy): s.vyos[i].update(state="adm", gen=1, disp=-1e9, adm=-1e9, appear=-1e9)
        k = 0
        for o in SLOT_ORDER:
            if k >= n_up: break
            if s.workers[SLOT_WK[o]]["state"] == "ready":
                s.slots[o].update(state="ready", gen=1, disp=-1e9, api=-1e9, relief=-1e9, relief_done=True); k += 1
        for _ in range(s.ue[0] if s.ue else 0): s.place_arrival(); s.ues[s.next_id - 1]["arr"] = -1e9   # warm-in converged
    # ---------------- helpers
    def slot_ues(s, o): return [i for i, u in s.ues.items() if u["slot"] == o]
    def counts(s): return {o: sum(1 for u in s.ues.values() if u["slot"] == o) for o in SLOT_ORDER if s.slots[o]["state"] != "off"}
    def D(s): return len(s.ues)
    def announced(s, o):
        a = s.slots[o]["ann_on"]; return a is not None
    def eligible_by_harness(s, o):
        """r34c: a DNN is excluded while its own announcement is younger than the TTL (per entry, not refreshed by other entries)"""
        a = s.slots[o]["ann_on"]; return not (a is not None and s.t - a < s.p["drain_ttl_s"])
    def api_up(s, o):
        sl = s.slots[o]
        return sl["state"] in ("ready", "drain") or (sl["state"] == "boot" and sl["api"] is not None and sl["api"] <= s.t)
    def arrival_cands(s):
        base = [o for o in SLOT_ORDER if s.api_up(o)]
        el = [o for o in base if s.eligible_by_harness(o)]
        return el if el else base                        # harness: exclusions dropped if they would leave no candidate
    def vy_admitted(s): return [i for i, v in s.vyos.items() if v["state"] == "adm"]
    def wk_ready(s): return [i for i, w in s.workers.items() if w["state"] == "ready"]
    def observe(s):
        rep = sum(1 for o in SLOT_ORDER if s.slots[o]["state"] in ("boot", "ready", "drain", "failed"))
        ready = sum(1 for o in SLOT_ORDER if s.slots[o]["state"] in ("ready", "drain"))
        drn = sum(1 for o in SLOT_ORDER if s.slots[o]["state"] == "drain")
        failed = sum(1 for o in SLOT_ORDER if s.slots[o]["state"] == "failed")
        vy_vm = sum(1 for v in s.vyos.values() if v["state"] in ("boot", "adm")); vy_adm = len(s.vy_admitted())
        wk_vm = sum(1 for w in s.workers.values() if w["state"] in ("boot", "ready", "failed")); wk_rdy = len(s.wk_ready())
        pos_used = sum(1 for o in SLOT_ORDER if s.slots[o]["state"] != "off" and s.workers[SLOT_WK[o]]["state"] == "ready")
        return dict(D=s.D(), rep_up=rep, ready_up=ready, drain_up=drn, boot_up=rep - ready - failed, failed_up=failed, vy_vm=vy_vm, vy_adm=vy_adm,
                    vy_boot=vy_vm - vy_adm, wk_vm=wk_vm, wk_ready=wk_rdy, wk_boot=sum(1 for w in s.workers.values() if w["state"] == "boot"),
                    idle_wk=s.idle_worker(), counts=s.counts(), positions_ready=wk_rdy * 2, free_positions=wk_rdy * 2 - pos_used)
    def idle_worker(s):
        for i in sorted(s.workers, reverse=True):
            w = s.workers[i]
            if i == 0 or w["state"] != "ready" or s.t - w["ready"] < s.p["idle_age_s"]: continue
            if any(s.slots[o]["state"] != "off" for o in SLOT_ORDER if SLOT_WK[o] == i): continue
            if s.t - w["last_pod_gone"] < s.p["idle_nopod_s"]: continue
            return i
        return None
    # ---------------- actions (same contract as v8sim11)
    def scale_out_up(s):
        for o in SLOT_ORDER:
            if s.slots[o]["state"] == "off":
                w = s.workers[SLOT_WK[o]]
                if w["state"] != "ready": return ("noworker", SLOT_WK[o])
                sl = s.slots[o]; sl.update(state="boot", gen=sl["gen"] + 1, disp=s.t, api=s.t + s.p["slot_api_s"],
                                            relief=s.t + s.p["slot_api_s"] + s.p["relief_delay_s"], relief_done=False, drain_t=None, drain_empty=None, ann_on=None)
                s.events.append((s.t, "out", "up", o)); return ("ok", o)
        return ("none", None)
    def scale_in_up(s):
        act = [o for o in SLOT_ORDER if s.slots[o]["state"] == "ready"]
        if len(act) <= 1: return False
        o = act[-1]; sl = s.slots[o]; sl["state"] = "drain"; sl["drain_t"] = s.t; sl["ann_on"] = s.t
        ues = sorted(s.slot_ues(o))
        if not ues: sl["drain_empty"] = s.t + s.p["empty_delete_s"]
        else:
            sl["drain_empty"] = None; mv = []
            surv = [x for x in SLOT_ORDER if s.slots[x]["state"] == "ready"]
            cnt = {x: len(s.slot_ues(x)) for x in surv}
            for u in ues:
                dst = next((x for x in surv if cnt[x] < s.p["pack_cap"]), None)
                if dst is None: dst = min(surv, key=lambda x: (cnt[x], TIE_ORDER.index(x)))
                cnt[dst] += 1; mv.append(dict(ue=u, src=o, dst=dst, dgen=s.slots[dst]["gen"], kind="drain"))
            s.new_job(mv)
        s.events.append((s.t, "in", "up", o)); return True
    def cancel_drain(s):
        o = next((x for x in SLOT_ORDER if s.slots[x]["state"] == "drain"), None)
        if o is None: return False
        sl = s.slots[o]; sl["state"] = "ready"; sl["drain_t"] = None; sl["drain_empty"] = None; sl["ann_on"] = None   # retract
        s.moves = [m for m in s.moves if not (m["kind"] == "drain" and m["src"] == o)]      # pending moves dropped; completed moves stay
        s.events.append((s.t, "cancel-drain", "up", o)); return True
    def deploy_vy(s):
        for i in range(3):
            if s.vyos[i]["state"] == "off":
                v = s.vyos[i]; v.update(state="boot", gen=v["gen"] + 1, disp=s.t, adm=s.t + s.p["vy_admit_s"], gone=None, appear=s.t + s.p["vm_appear_s"])
                s.events.append((s.t, "out", "vy", i)); return True
        return False
    def delete_vy(s):
        act = [i for i in range(1, 3) if s.vyos[i]["state"] in ("adm", "boot")]
        if not act: return False
        i = max(act); s.vyos[i]["state"] = "deleting"; s.vyos[i]["gone"] = s.t + s.p["vm_gone_s"]; s.events.append((s.t, "in", "vy", i)); return True
    def create_wk(s):
        for i in range(1, 4):
            if s.workers[i]["state"] == "off":
                w = s.workers[i]; w.update(state="boot", gen=w["gen"] + 1, disp=s.t, ready=s.t + s.p["wk_ready_s"], gone=None, appear=s.t + s.p["vm_appear_s"])
                s.events.append((s.t, "out", "wk", i)); return True
        return False
    def delete_wk(s, i=None):
        if i is None: i = s.idle_worker()
        if i is None: return False
        if s.workers[i]["state"] != "ready": return False
        if any(s.slots[o]["state"] != "off" for o in SLOT_ORDER if SLOT_WK[o] == i): return False
        s.workers[i]["state"] = "deleting"; s.workers[i]["gone"] = s.t + s.p["vm_gone_s"]; s.events.append((s.t, "in", "wk", i)); return True
    # ---------------- relief / moves
    def in_move(s, u): return (s.cur_move is not None and s.cur_move["ue"] == u) or any(m["ue"] == u for m in s.moves)
    def new_job(s, moves):
        s.job_seq += 1
        for m in moves: m["job"] = s.job_seq
        s.moves.extend(moves); s.jobs[s.job_seq] = list(moves)
    def job_occ(s, o):
        """agent occupancy for arrival steering: live UEs + every move (incl. finished) of a still-active job targeting the slot"""
        n = 0
        for jid, ms in s.jobs.items():
            if any((m is s.cur_move) or (m in s.moves) for m in ms): n += sum(1 for m in ms if m["dst"] == o)
        return n
    def enqueue_pool_relief(s):
        cnt = s.counts(); cand = {o: c for o, c in cnt.items() if s.slots[o]["state"] == "ready"}
        if len(cand) < 2: return
        for _ in range(2):
            hot = max(cand, key=lambda o: (cand[o], -TIE_ORDER.index(o))); cold = min(cand, key=lambda o: (cand[o], TIE_ORDER.index(o)))
            if not (cand[hot] > s.p["donor_min"] and cand[cold] < s.p["donor_min"] and cand[hot] - cand[cold] >= 2): break
            el = [i for i in s.slot_ues(hot) if s.t - s.ues[i]["arr"] >= s.p["age_min_s"] and not s.in_move(i)]
            if not el: break
            u = max(el); s.new_job([dict(ue=u, src=hot, dst=cold, dgen=s.slots[cold]["gen"], kind="pool")]); cand[hot] -= 1; cand[cold] += 1
    def enqueue_scaleout_relief(s, o):
        cnt = s.counts(); n_new = cnt.get(o, 0); mv = []
        while n_new < s.p["recv_max"]:
            donors = [x for x in cnt if x != o and s.slots[x]["state"] == "ready" and cnt[x] > s.p["donor_min"]]
            if not donors: break
            d = max(donors, key=lambda x: (cnt[x], -TIE_ORDER.index(x)))
            el = sorted([i for i in s.slot_ues(d) if s.t - s.ues[i]["arr"] >= s.p["age_min_s"] and not s.in_move(i)], key=lambda i: (s.ues[i]["arr"], -i))
            if not el: cnt[d] = 0; continue
            mv.append(dict(ue=el[0], src=d, dst=o, dgen=s.slots[o]["gen"], kind="relief")); cnt[d] -= 1; n_new += 1
        if mv: s.new_job(mv)
    def hot_relief(s, over):
        cnt = s.counts()
        for o in SLOT_ORDER:
            sl = s.slots[o]
            if sl["state"] != "ready": continue
            sl["hot"] = sl["hot"] + 1 if over.get(o) else 0
            if sl["hot"] >= s.p["hot_ticks"] and s.t - sl["hot_cool"] >= s.p["hot_cooldown_s"]:
                cold = min([x for x in cnt if s.slots[x]["state"] == "ready" and x != o], key=lambda x: (cnt[x], TIE_ORDER.index(x)), default=None)
                if cold is not None and cnt[cold] + 1 <= s.p["recv_max"]:
                    el = [i for i in s.slot_ues(o) if s.t - s.ues[i]["arr"] >= s.p["age_min_s"] and not s.in_move(i)]
                    if el: s.new_job([dict(ue=min(el), src=o, dst=cold, dgen=s.slots[cold]["gen"], kind="hot")]); sl["hot_cool"] = s.t; sl["hot"] = 0; return
    def place_arrival(s):
        cands = s.arrival_cands()
        if not cands: return False
        cnt = s.counts(); occ = {o: cnt.get(o, 0) + s.job_occ(o) for o in cands}
        o = min(cands, key=lambda x: (occ[x], TIE_ORDER.index(x)))
        s.ues[s.next_id] = dict(slot=o, arr=s.t); s.active.append(s.next_id); s.next_id += 1; return True
    # ---------------- one second
    def phase_demand(s):
        """(1)+(2): minute-boundary departures (LIFO) and arrival schedule; arrivals due this second are placed"""
        t = s.t; p = s.p
        if t % 60 == 0 and t // 60 < len(s.ue):
            target = s.ue[t // 60]; cur = len(s.ues) + len(s.arrivals)
            if target < cur:
                drop = cur - target
                k = min(drop, len(s.arrivals)); s.arrivals = s.arrivals[:len(s.arrivals) - k]; drop -= k   # unplaced arrivals cancelled first
                for _ in range(drop):
                    u = s.active.pop(); s.ues.pop(u, None)
                    s.moves = [x for x in s.moves if x["ue"] != u]
                    if s.cur_move is not None and s.cur_move["ue"] == u: s.cur_move = None
            n = max(0, target - cur)
            carried = len(s.arrivals)            # leftovers of the previous minute go first
            new = [t + p["arr_first_s"] + j * p["arr_gap_s"] for j in range(carried + n)]
            s.arrivals = [x for x in new if x <= t + p["arr_cutoff_s"]] + [None] * sum(1 for x in new if x > t + p["arr_cutoff_s"])
        placed = 0
        while s.arrivals and s.arrivals[0] is not None and s.arrivals[0] <= t:
            s.arrivals.pop(0); placed += s.place_arrival()
        return placed
    def phase_ready(s):
        """(3) ready / gone transitions due at t"""
        t = s.t
        for i, w in s.workers.items():
            if w["state"] == "boot" and w["ready"] <= t: w["state"] = "ready"
            if w["state"] == "deleting" and w["gone"] <= t: w["state"] = "off"
        for i, v in s.vyos.items():
            if v["state"] == "boot" and v["adm"] <= t: v["state"] = "adm"
            if v["state"] == "deleting" and v["gone"] <= t: v["state"] = "off"
        for o in SLOT_ORDER:
            sl = s.slots[o]
            if sl["state"] == "boot" and sl["api"] <= t: sl["state"] = "ready"
    def phase_relief(s):
        """(4) scale-out relief trigger, drain completion/deletion (+ retract), serial make-before-break moves"""
        t = s.t; p = s.p
        for o in SLOT_ORDER:
            sl = s.slots[o]
            if sl["state"] == "ready" and sl["relief"] is not None and sl["relief"] <= t and not sl["relief_done"]:
                sl["relief_done"] = True; s.enqueue_scaleout_relief(o)
            if sl["state"] == "drain":
                mine = s.slot_ues(o); pend = any(x["src"] == o for x in s.moves) or (s.cur_move is not None and s.cur_move["src"] == o)
                if sl["drain_empty"] is None and not mine and not pend: sl["drain_empty"] = t + p["release_delay_s"] + p["release_tail_s"]
                if sl["drain_empty"] is not None and sl["drain_empty"] <= t and not mine:
                    sl.update(state="off", drain_t=None, drain_empty=None, ann_on=None)
                    s.workers[SLOT_WK[o]]["last_pod_gone"] = t
        if s.cur_move is not None and s.cur_move["end"] <= t:
            mv = s.cur_move; s.cur_move = None; d = s.slots[mv["dst"]]
            if mv["ue"] in s.ues and d["gen"] == mv["dgen"] and d["state"] in ("ready", "boot"):
                s.ues[mv["ue"]]["slot"] = mv["dst"]; s.ues[mv["ue"]]["arr"] = t
        if s.cur_move is None and s.moves:
            mv = s.moves.pop(0)
            if mv["ue"] in s.ues: mv["start"] = t; mv["end"] = t + p["move_s"]; s.cur_move = mv
        for jid in [j for j, ms in s.jobs.items() if not any((m is s.cur_move) or (m in s.moves) for m in ms)]: del s.jobs[jid]
    def measure(s):
        """(6) [t, t+1): loss (traffic weighted), per-unit overflow seconds, alloc_vm"""
        t = s.t; p = s.p; m = t // 60
        if m >= len(s.lossmin): return
        D = len(s.ues); cnt = s.counts(); over = {}; loss = 0.0
        for o, n in cnt.items():
            if s.slots[o]["state"] in ("ready", "drain", "boot") and n > p["knee"]:
                over[o] = True; loss += n * min(0.5, p["over_frac"] * (n - p["knee"]))
        adm = s.vy_admitted(); nv = max(1, len(adm))
        if D > 0:
            per = [D // nv + (1 if i < D % nv else 0) for i in range(nv)]
            for j, c in enumerate(per):
                if c > p["vy_knee"]:
                    over[f"vy{j}"] = True; loss += c * min(0.5, p["vy_over_frac"] * (c - p["vy_knee"]))
        s.lossmin[m] += loss * DT; s.offmin[m] += D * DT
        for u in over: s.unit_over[m][u] = s.unit_over[m].get(u, 0) + DT
        ex = lambda st, ap, gone: st in ("boot", "ready", "adm", "deleting", "failed") and ap is not None and ap <= t and (gone is None or gone > t)
        bwk = CORES["wk"] * sum(1 for w in s.workers.values() if ex(w["state"], w["appear"], w["gone"]))
        bvy = CORES["vy"] * sum(1 for v in s.vyos.values() if ex(v["state"], v["appear"], v["gone"]))
        bup = CORES["up"] * sum(1 for o in SLOT_ORDER if s.slots[o]["state"] != "off")
        s.alloc_by["wk"] += bwk * DT / 60; s.alloc_by["vy"] += bvy * DT / 60; s.alloc_by["up"] += bup * DT / 60
        c = (bwk + bvy + bup) * DT / 60; s.alloc += c; s.permin[m] += c
        if t % 60 == 0: s.slot_hist.append((m, D, dict(cnt), len(adm), len(s.wk_ready())))
        s._over = over
    def minute_bad(s, m):
        lf = s.lossmin[m] / max(s.offmin[m], 1e-9)
        ov = max(s.unit_over[m].values()) if s.unit_over[m] else 0
        return (lf > LOSS_BAD) or (ov >= s.p["p99_over_s"]), lf > LOSS_BAD, ov >= s.p["p99_over_s"]
    def result(s, nmin=None):
        nmin = nmin or len(s.lossmin)
        bad = [s.minute_bad(m) for m in range(nmin)]
        return dict(slo=nmin - sum(b[0] for b in bad), viol=[m for m in range(nmin) if bad[m][0]], viol_loss=[m for m in range(nmin) if bad[m][1]],
                    viol_over=[m for m in range(nmin) if bad[m][2]], alloc_vm=s.alloc, alloc_by=dict(s.alloc_by), permin=s.permin.copy(),
                    pct=100 * s.lossmin / np.maximum(s.offmin, 1e-9), events=list(s.events), slot_hist=list(s.slot_hist))
    def snapshot(s):
        """immutable, JSON-serialisable view of the full state (no future demand)"""
        d = dict(t=s.t, ues={str(k): dict(v) for k, v in s.ues.items()}, active=list(s.active), next_id=s.next_id,
                 slots={str(o): dict(v) for o, v in s.slots.items()}, workers={str(i): dict(v) for i, v in s.workers.items()},
                 vyos={str(i): dict(v) for i, v in s.vyos.items()}, moves=[dict(m) for m in s.moves], cur_move=(dict(s.cur_move) if s.cur_move else None),
                 arrivals=list(s.arrivals), last_pool_relief=s.last_pool_relief)
        return json.loads(json.dumps(d))
    def clone(s, future_ue=None, horizon_s=None):
        """independent copy for a rollout; future_ue replaces the per-minute target list from the next minute boundary on"""
        c = copy.deepcopy(s)
        if future_ue is not None: c.ue = list(future_ue)
        return c

def run(ue, ctl=None, start=None, phys=None, horizon_s=3600, on_tick=None):
    """closed loop on the event physics; ctl.tick(ph, ob) -> bool decided (v8sim11 controllers)"""
    ph = Phys(ue, start=start, p=phys, horizon_s=horizon_s)
    for _ in range(horizon_s):
        ph.phase_demand(); ph.phase_ready(); ph.phase_relief()
        if ph.t % TICK == 0:
            decided = False
            if ctl is not None:
                ob = ph.observe(); decided = ctl.tick(ph, ob)
                if on_tick: on_tick(ph, decided)
            ph.hot_relief(ph._over)
            if not decided and ph.t - ph.last_pool_relief >= ph.p["pool_relief_s"]:
                ph.enqueue_pool_relief(); ph.last_pool_relief = ph.t
        ph.measure(); ph.t += DT
    return ph.result()
