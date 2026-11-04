#!/usr/bin/env python3
"""v8sim11.py(10-11,審查第三十五輪 A「模擬忠實度」):逐槽/逐 VyOS 的物理引擎 + 六套控制律(S sigma、v6 batch、B4c2、B5c1、B6)。
與 v8sim10(nest2)/v8sim2(sim_v6)/v8sim_b6 的差別只在**物理層**(控制律逐句移植,不改決策邏輯):
  - UE 是個體:每分鐘到達(序列、散在分鐘前 ~40 s)/離開(LIFO,分鐘起點);到達導流 = 就緒、有 association、非 drain 槽中取最空(平手 .38,.31,…,.37)
  - 槽有身分:啟動序 eupf-0 .38(w0)、.33(w0)、.31(w1)、.32(w1)、.34(w2)、.35(w2)、.37(w3)、.36(w3);擴容取序列中第一個未啟用且 worker 就緒者;縮容取最後啟用的非 drain 槽
  - 搬遷:scale-out relief(新槽 API 後 +20 s 起,從 >DONOR_MIN 的最滿槽搬最老 UE 到新槽至 RECV_MAX)、PoolRelief(每 150 s、無決策 tick、最多 2 顆 hot>5/cold<5/差≥2)、
    hot-slot relief(連續 2 tick 溢位 → 搬 1 顆到最冷槽,冷卻 120 s)、縮容 drain(victim 的 UE 依 idx 塞進存活槽至 5、否則最空;全搬完 +75 s 釋放延遲 → 刪 pod;空槽 30 s)
    每次搬遷 17 s、序列執行;make-before-break(搬完才算到新槽)
  - 違規逐槽判:槽 n 顆 > 膝點 K(一般 5;**.38 在總 UE ≥ T38 時 K=4**)→ 該槽流量損失 over_frac×(n−K);逐 VyOS:公平分配(最大差 1),count×250k > CapVY×0.93 → 溢位
    分鐘違規 = 彙總損失 > 0.1% **或** 任一槽/VyOS 溢位秒數 ≥ P99_OVER_S(p99>1 ms 的代理)
  - 計費 = alloc_vm 口徑:worker 3 核 × VM 存在(派出 +15 s 出現、刪除 +20 s 消失)、VyOS 2 核同法、槽 0.8 × pod 存在(建立→刪除)
  - T_ready 實測:槽 API +15 s、VyOS 入池 +80 s、worker Ready +85 s(53 開機 + 30 provisioning)
物理參數全部集中在 PHYS(關卡一前寫死;只允許用 t1/t2/t4 的既有場次校驗)。
用法:import v8sim11 as V; V.run(ue, arm, start=(slots,vy,wk), **kw)  → dict(slo, viol_min, alloc_vm, permin, events, slot_hist)
"""
import sys, math, json, os
import numpy as np
Q = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, Q)
import v8sim2 as S, v8sim7 as M
DT = 5; TICK = 30
PER_UE = 250e3; CAP_UP = 1.35e6 * 0.93; CAP_VY = 4.45e6 * 0.93
SLOT_ORDER = [38, 33, 31, 32, 34, 35, 37, 36]; SLOT_WK = {38: 0, 33: 0, 31: 1, 32: 1, 34: 2, 35: 2, 37: 3, 36: 3}
TIE_ORDER = [38, 31, 32, 33, 34, 35, 36, 37]
FMAX = dict(up=8, vy=3, wk=4); FMIN = dict(up=2, vy=1, wk=1)
CORES = dict(wk=3.0, vy=2.0, up=0.8)
PHYS = dict(knee=5, knee38=4, a38=7, churn38_s=300, hold38_s=60, over_frac=0.01, p99_over_s=10, vy_knee=18, vy_over_frac=0.003,
            slot_api_s=15, relief_delay_s=20, move_s=17, release_delay_s=75, release_tail_s=10, empty_delete_s=30,
            vy_admit_s=80, vm_appear_s=15, vm_gone_s=20, wk_ready_s=90,
            age_min_s=90, donor_min=5, recv_max=5, pool_relief_s=150, hot_ticks=2, hot_cooldown_s=120, pack_cap=5,
            arr_first_s=2, arr_span_s=38, arr_min_gap_s=3, idle_nopod_s=120, idle_age_s=300)
if os.environ.get("PHYS_OVERRIDE"): PHYS.update(json.loads(os.environ["PHYS_OVERRIDE"]))   # 反事實(例:'{"knee38":5}' = 關閉 R38)

class Phys:
    def __init__(s, ue, start=None, p=None):
        s.p = dict(PHYS); s.p.update(p or {}); s.ue = list(ue)[:60]; s.t = 0
        s.ues = {}            # id -> dict(slot, arr, vy)
        s.next_id = 0; s.active = []   # arrival order (for LIFO departures)
        s.slots = {o: dict(state="off", disp=None, api=None, delete=None, relief=None, drain_t=None, hot=0, hot_cool=-1e9, drain_empty=None) for o in SLOT_ORDER}
        s.workers = {i: dict(state=("ready" if i == 0 else "off"), disp=-1e9, ready=-1e9, gone=None, appear=-1e9) for i in range(4)}
        s.vyos = {i: dict(state=("adm" if i == 0 else "off"), disp=-1e9, adm=-1e9, gone=None, appear=-1e9) for i in range(3)}
        s.moves = []          # queue of dict(ue, src, dst, kind, start=None)
        s.cur_move = None
        s.arrivals = []       # scheduled (t, ) arrivals
        s.alloc = 0.0; s.permin = np.zeros(60); s.lossmin = np.zeros(60); s.offmin = np.zeros(60); s.overs = np.zeros(60)
        s.events = []; s.slot_hist = []; s.last_pool_relief = -1e9
        s.last_scale_in_up = -1e9; s.last_scale_out_up = -1e9
        s.drain_victim = None; s.last_slot_change = -1e9; s.arr_this_min = 0; s.burst_until = -1e9; s.job_seq = 0
        n_up, n_vy, n_wk = start if start else (2, 1, 1)
        for i in range(1, n_wk): s.workers[i] = dict(state="ready", disp=-1e9, ready=-1e9, gone=None, appear=-1e9)
        for i in range(1, n_vy): s.vyos[i] = dict(state="adm", disp=-1e9, adm=-1e9, gone=None, appear=-1e9)
        k = 0
        for o in SLOT_ORDER:
            if k >= n_up: break
            if s.workers[SLOT_WK[o]]["state"] == "ready":
                s.slots[o].update(state="ready", disp=-1e9, api=-1e9, relief=-1e9); k += 1
        s.total_ue_target = 0
        for _ in range(s.ue[0]): s.place_arrival(); s.ues[s.next_id - 1]["arr"] = -1e9   # 起跑時 UE 已就位(warm-in 已收斂)
    # ---------- helpers
    def slot_ues(s, o): return [i for i, u in s.ues.items() if u["slot"] == o]
    def counts(s): return {o: sum(1 for u in s.ues.values() if u["slot"] == o) for o in SLOT_ORDER if s.slots[o]["state"] != "off"}
    def D(s): return len(s.ues)
    def ready_slots(s): return [o for o in SLOT_ORDER if s.slots[o]["state"] == "ready"]
    def arrival_cands(s):
        return [o for o in SLOT_ORDER if s.slots[o]["state"] == "ready" or (s.slots[o]["state"] == "boot" and s.slots[o]["api"] is not None and s.slots[o]["api"] <= s.t)]
    def vy_admitted(s): return [i for i, v in s.vyos.items() if v["state"] == "adm"]
    def wk_ready(s): return [i for i, w in s.workers.items() if w["state"] == "ready"]
    def observe(s):
        rep = sum(1 for o in SLOT_ORDER if s.slots[o]["state"] in ("boot", "ready", "drain"))
        ready = sum(1 for o in SLOT_ORDER if s.slots[o]["state"] in ("ready", "drain"))
        drn = sum(1 for o in SLOT_ORDER if s.slots[o]["state"] == "drain")
        vy_vm = sum(1 for v in s.vyos.values() if v["state"] in ("boot", "adm")); vy_adm = len(s.vy_admitted())
        wk_vm = sum(1 for w in s.workers.values() if w["state"] in ("boot", "ready")); wk_rdy = len(s.wk_ready())
        idle = s.idle_worker()
        return dict(D=s.D(), rep_up=rep, ready_up=ready, drain_up=drn, boot_up=rep - ready, vy_vm=vy_vm, vy_adm=vy_adm, vy_boot=vy_vm - vy_adm,
                    wk_vm=wk_vm, wk_ready=wk_rdy, wk_boot=wk_vm - wk_rdy, idle_wk=idle, counts=s.counts(),
                    positions_ready=wk_rdy * 2, free_positions=wk_rdy * 2 - sum(1 for o in SLOT_ORDER if s.slots[o]["state"] != "off" and s.workers[SLOT_WK[o]]["state"] == "ready"))
    def idle_worker(s):
        best = None
        for i in sorted(s.workers, reverse=True):
            w = s.workers[i]
            if i == 0 or w["state"] != "ready" or s.t - w["ready"] < s.p["idle_age_s"]: continue
            pods = [o for o in SLOT_ORDER if SLOT_WK[o] == i and s.slots[o]["state"] != "off"]
            if pods: continue
            if s.t - w.get("last_pod_gone", -1e9) < s.p["idle_nopod_s"]: continue
            best = i; break
        return best
    # ---------- actions (return True if dispatched)
    def scale_out_up(s):
        for o in SLOT_ORDER:
            if s.slots[o]["state"] == "off":
                w = s.workers[SLOT_WK[o]]
                if w["state"] != "ready": return ("noworker", SLOT_WK[o])
                s.slots[o].update(state="boot", disp=s.t, api=s.t + s.p["slot_api_s"], relief=s.t + s.p["slot_api_s"] + s.p["relief_delay_s"], delete=None, drain_t=None, relief_done=False)
                s.events.append((s.t, "out", "up", o)); s.last_scale_out_up = s.t; return ("ok", o)
        return ("none", None)
    def scale_in_up(s):
        act = [o for o in SLOT_ORDER if s.slots[o]["state"] == "ready"]
        if len(act) <= 1: return False
        o = act[-1]; sl = s.slots[o]; sl["state"] = "drain"; sl["drain_t"] = s.t; s.drain_victim = o
        ues = sorted(s.slot_ues(o))
        if not ues: sl["drain_empty"] = s.t + s.p["empty_delete_s"]
        else:
            sl["drain_empty"] = None; mv = []
            # planScaleInCap: victims' UEs (idx order) packed into survivors in activation order up to pack_cap, else least loaded
            surv = [x for x in SLOT_ORDER if s.slots[x]["state"] == "ready"]
            cnt = {x: len(s.slot_ues(x)) for x in surv}
            for u in ues:
                dst = next((x for x in surv if cnt[x] < s.p["pack_cap"]), None)
                if dst is None: dst = min(surv, key=lambda x: (cnt[x], TIE_ORDER.index(x)))
                cnt[dst] += 1; mv.append(dict(ue=u, src=o, dst=dst, kind="drain"))
            s.new_job(mv)
        s.last_slot_change = s.t; s.events.append((s.t, "in", "up", o)); s.last_scale_in_up = s.t; return True
    def cancel_drain(s):
        o = next((x for x in SLOT_ORDER if s.slots[x]["state"] == "drain"), None)
        if o is None: return False
        s.slots[o]["state"] = "ready"; s.slots[o]["drain_t"] = None; s.slots[o]["drain_empty"] = None
        s.moves = [m for m in s.moves if not (m["kind"] == "drain" and m["src"] == o)]
        s.last_slot_change = s.t; s.events.append((s.t, "cancel-drain", "up", o)); return True
    def deploy_vy(s):
        for i in range(3):
            if s.vyos[i]["state"] == "off":
                s.vyos[i] = dict(state="boot", disp=s.t, adm=s.t + s.p["vy_admit_s"], gone=None, appear=s.t + s.p["vm_appear_s"]); s.events.append((s.t, "out", "vy", i)); return True
        return False
    def delete_vy(s):
        act = [i for i in range(1, 3) if s.vyos[i]["state"] in ("adm", "boot")]
        if not act: return False
        i = max(act); s.vyos[i]["state"] = "deleting"; s.vyos[i]["gone"] = s.t + s.p["vm_gone_s"]; s.events.append((s.t, "in", "vy", i)); return True
    def create_wk(s):
        for i in range(1, 4):
            if s.workers[i]["state"] == "off":
                s.workers[i] = dict(state="boot", disp=s.t, ready=s.t + s.p["wk_ready_s"], gone=None, appear=s.t + s.p["vm_appear_s"]); s.events.append((s.t, "out", "wk", i)); return True
        return False
    def delete_wk(s, i=None):
        if i is None: i = s.idle_worker()
        if i is None: return False
        if any(s.slots[o]["state"] != "off" for o in SLOT_ORDER if SLOT_WK[o] == i): return False
        s.workers[i]["state"] = "deleting"; s.workers[i]["gone"] = s.t + s.p["vm_gone_s"]; s.events.append((s.t, "in", "wk", i)); return True
    # ---------- relief / moves
    def enqueue_pool_relief(s):
        cnt = s.counts(); cand = {o: c for o, c in cnt.items() if s.slots[o]["state"] == "ready"}
        if len(cand) < 2: return
        for _ in range(2):
            hot = max(cand, key=lambda o: (cand[o], -TIE_ORDER.index(o))); cold = min(cand, key=lambda o: (cand[o], TIE_ORDER.index(o)))
            if not (cand[hot] > 5 and cand[cold] < 5 and cand[hot] - cand[cold] >= 2): break
            el = [i for i in s.slot_ues(hot) if s.t - s.ues[i]["arr"] >= s.p["age_min_s"] and not s.in_move(i)]
            if not el: break
            u = max(el); s.new_job([dict(ue=u, src=hot, dst=cold, kind="pool")]); cand[hot] -= 1; cand[cold] += 1
    def in_move(s, u): return (s.cur_move and s.cur_move["ue"] == u) or any(m["ue"] == u for m in s.moves)
    def enqueue_scaleout_relief(s, o):
        cnt = s.counts(); n_new = cnt.get(o, 0); mv = []
        while n_new < s.p["recv_max"]:
            donors = [x for x in cnt if x != o and s.slots[x]["state"] == "ready" and cnt[x] > s.p["donor_min"]]
            if not donors: break
            d = max(donors, key=lambda x: cnt[x])
            el = sorted([i for i in s.slot_ues(d) if s.t - s.ues[i]["arr"] >= s.p["age_min_s"] and not s.in_move(i)], key=lambda i: s.ues[i]["arr"])
            if not el: cnt[d] = 0; continue
            mv.append(dict(ue=el[0], src=d, dst=o, kind="relief")); cnt[d] -= 1; n_new += 1
        if mv: s.new_job(mv)
    def hot_relief(s, over):
        cnt = s.counts()
        for o in SLOT_ORDER:
            sl = s.slots[o]
            if sl["state"] != "ready": continue
            sl["hot"] = sl["hot"] + 1 if over.get(o) else 0
            if sl["hot"] >= s.p["hot_ticks"] and s.t - sl["hot_cool"] >= s.p["hot_cooldown_s"]:
                cold = min([x for x in cnt if s.slots[x]["state"] == "ready" and x != o], key=lambda x: (cnt[x], TIE_ORDER.index(x)), default=None)
                if cold is not None and cnt[cold] + 1 <= 5:
                    el = [i for i in s.slot_ues(o) if s.t - s.ues[i]["arr"] >= s.p["age_min_s"] and not s.in_move(i)]
                    if el: s.new_job([dict(ue=min(el), src=o, dst=cold, kind="hot")]); sl["hot_cool"] = s.t; sl["hot"] = 0; return
    # ---------- per-step physics
    def new_job(s, moves):
        s.job_seq += 1
        for m in moves: m["job"] = s.job_seq
        s.moves.extend(moves); s.jobs = getattr(s, "jobs", {}); s.jobs[s.job_seq] = list(moves)
    def job_occ(s, o):
        """實機 agent:到達導流的占用數 = 活 UE + 執行中 job 的所有搬遷(含已完成)指向該槽者"""
        n = 0
        for jid, ms in getattr(s, "jobs", {}).items():
            active = any((m is s.cur_move) or (m in s.moves) for m in ms)
            if active: n += sum(1 for m in ms if m["dst"] == o)
        return n
    def advance_units(s):
        t = s.t
        for i, w in s.workers.items():
            if w["state"] == "boot" and w["ready"] <= t: w["state"] = "ready"
            if w["state"] == "deleting" and w["gone"] <= t: w["state"] = "off"
        for i, v in s.vyos.items():
            if v["state"] == "boot" and v["adm"] <= t: v["state"] = "adm"
            if v["state"] == "deleting" and v["gone"] <= t: v["state"] = "off"
        for o in SLOT_ORDER:
            sl = s.slots[o]
            if sl["state"] == "boot" and sl["api"] <= t: sl["state"] = "ready"; s.last_slot_change = t
    def place_arrival(s):
        cands = [o for o in s.arrival_cands()]
        if not cands: return
        cnt = s.counts(); occ = {o: cnt.get(o, 0) + s.job_occ(o) for o in cands}
        o = min(cands, key=lambda x: (occ[x], TIE_ORDER.index(x)))
        s.ues[s.next_id] = dict(slot=o, arr=s.t); s.active.append(s.next_id); s.next_id += 1
    def step(s):
        t = s.t; p = s.p; m = t // 60
        if t % 60 == 0 and m < 60:
            target = s.ue[m]; cur = len(s.ues); s.total_ue_target = target
            if target < cur:
                for _ in range(cur - target):
                    u = s.active.pop(); s.ues.pop(u, None)
                    s.moves = [x for x in s.moves if x["ue"] != u]
                    if s.cur_move and s.cur_move["ue"] == u: s.cur_move = None
            s.arr_this_min = max(0, target - cur)
            if target > cur:
                n = target - cur; gap = max(p["arr_min_gap_s"], p["arr_span_s"] / n)
                s.arrivals = [t + p["arr_first_s"] + j * gap for j in range(n)]
                # R38 [推測,t1/t2/t4 證據]:到達爆量(≥a38 顆/分)且槽層剛變動(<churn38_s)或未開滿 → .38 在 5 顆就溢位;效應延續 hold38_s
                ready8 = sum(1 for o in SLOT_ORDER if s.slots[o]["state"] == "ready")
                if n >= p["a38"] and (ready8 < 8 or t - s.last_slot_change < p["churn38_s"]): s.burst_until = t + 60 + p["hold38_s"]
        while s.arrivals and s.arrivals[0] <= t + DT - 1e-9:
            s.arrivals.pop(0); s.place_arrival()
        s.advance_units()
        for o in SLOT_ORDER:
            sl = s.slots[o]
            if sl["state"] == "ready" and sl.get("relief") is not None and sl["relief"] <= t and not sl.get("relief_done", True):
                sl["relief_done"] = True; s.enqueue_scaleout_relief(o)
            if sl["state"] == "drain":
                mine = s.slot_ues(o); pend = any(x["src"] == o for x in s.moves) or (s.cur_move and s.cur_move["src"] == o)
                if sl["drain_empty"] is None and not mine and not pend: sl["drain_empty"] = t + p["release_delay_s"] + p["release_tail_s"]
                if sl["drain_empty"] is not None and sl["drain_empty"] <= t and not mine:
                    sl["state"] = "off"; sl["delete"] = t; s.workers[SLOT_WK[o]]["last_pod_gone"] = t; s.drain_victim = None; s.last_slot_change = t
        # moves (serial, make-before-break)
        if s.cur_move and s.cur_move["end"] <= t:
            mv = s.cur_move; s.cur_move = None
            if mv["ue"] in s.ues and s.slots[mv["dst"]]["state"] in ("ready", "boot"): s.ues[mv["ue"]]["slot"] = mv["dst"]; s.ues[mv["ue"]]["arr"] = t
        if s.cur_move is None and s.moves:
            mv = s.moves.pop(0)
            if mv["ue"] in s.ues: mv["start"] = t; mv["end"] = t + p["move_s"]; s.cur_move = mv
        # loss
        D = len(s.ues); cnt = s.counts(); over = {}; loss = 0.0
        if not hasattr(s, "src"): s.src = [set() for _ in range(60)]
        nready = sum(1 for o in SLOT_ORDER if s.slots[o]["state"] in ("ready", "drain"))
        for o, n in cnt.items():
            K = p["knee"]
            if o == 38 and t < s.burst_until: K = p["knee38"]
            if n > K:
                over[o] = True; loss += n * min(0.5, p["over_frac"] * (n - K))
                if m < 60:
                    if n > p["knee"]: s.src[m].add("slot"); 
                    else: s.src[m].add("R38")
                    if D > p["knee"] * max(1, nready): s.src[m].add("capacity")
        adm = s.vy_admitted(); nv = max(1, len(adm))
        if D > 0:
            per = [D // nv + (1 if i < D % nv else 0) for i in range(nv)]
            for c in per:
                if c > p["vy_knee"]:
                    over["vy"] = True; loss += c * min(0.5, p["vy_over_frac"] * (c - p["vy_knee"]))
                    if m < 60: s.src[m].add("vy")
        if m < 60:
            s.lossmin[m] += loss * DT; s.offmin[m] += D * DT
            if over: s.overs[m] += DT
            bwk = CORES["wk"] * sum(1 for w in s.workers.values() if (w["state"] in ("boot", "ready", "deleting") and w["appear"] <= t) and (w["gone"] is None or w["gone"] > t))
            bvy = CORES["vy"] * sum(1 for v in s.vyos.values() if (v["state"] in ("boot", "adm", "deleting") and v["appear"] <= t) and (v["gone"] is None or v["gone"] > t))
            bup = CORES["up"] * sum(1 for o in SLOT_ORDER if s.slots[o]["state"] != "off")
            burn = bwk + bvy + bup
            if not hasattr(s, "alloc_by"): s.alloc_by = {"wk": 0.0, "vy": 0.0, "up": 0.0}
            s.alloc_by["wk"] += bwk * DT / 60; s.alloc_by["vy"] += bvy * DT / 60; s.alloc_by["up"] += bup * DT / 60
            s.alloc += burn * DT / 60; s.permin[m] += burn * DT / 60
            if t % 60 == 0: s.slot_hist.append((m, D, dict(cnt), len(adm), len(s.wk_ready())))
        s._over = over
        s.t += DT
    def result(s):
        pct = 100 * s.lossmin / np.maximum(s.offmin, 1e-9)
        viol = [(pct[m] > 0.1) or (s.overs[m] >= s.p["p99_over_s"]) for m in range(60)]
        return dict(slo=60 - sum(viol), viol=[m for m in range(60) if viol[m]], viol_src={m: sorted(getattr(s, 'src', [set()]*60)[m]) for m in range(60) if viol[m]}, alloc_vm=s.alloc, alloc_by=getattr(s, 'alloc_by', {}), pct=pct, overs=s.overs, permin=s.permin, events=s.events, slot_hist=s.slot_hist)

# ======================= controllers (decision logic ported verbatim; only the physics is new) =======================
class CtlSigma:
    """v8sim10.sim_nest2 的決策碼(S4a/S4b;λ·σ̂ + k 餘裕,k 預設 0)"""
    def __init__(s, cfg, prior, L, K=None, lock_up=300, lock_vm=600, idle_min=600):
        s.cfg, s.pr, s.L = cfg, prior, L; s.K = K or {"up": 0, "vy": 0, "wk": 0}
        s.W = {k: int(round(cfg.win[k])) for k in cfg.h}; s.LOCK = {"up": lock_up, "vy": lock_vm, "wk": lock_vm}; s.Dd = dict(cfg.d)
        s.last_out = {k: -1e9 for k in cfg.h}; s.last_in = {k: -1e9 for k in cfg.h}; s.idle_min = idle_min; s.hist = []
    def need(s, k, x): return float(s.cfg.need(k, x))
    def mg(s, kind, k, D): return s.L[k] * s.pr.sigma(kind, k, D) + s.K[k]
    def want_wk(s, D): return max(s.need("wk", D + s.mg("win", "wk", D)), math.ceil(s.need("up", D + s.L["up"] * s.pr.sigma("win", "wk", D) + s.K["up"]) / s.cfg.spw))
    def tick(s, ph, ob):
        t = ph.t; D = float(ob["D"]); s.hist.append((t, D))
        wants = {"up": s.need("up", D + s.mg("win", "up", D)), "vy": s.need("vy", D + s.mg("win", "vy", D)), "wk": s.want_wk(D)}
        decided = False
        for k in ("vy", "wk", "up"):
            ob = ph.observe()
            eff = {"up": ob["rep_up"] - ob["drain_up"], "vy": ob["vy_vm"], "wk": ob["wk_vm"]}
            boot = {"up": ob["boot_up"], "vy": ob["vy_boot"], "wk": ob["wk_boot"]}
            if not (wants[k] > eff[k] and eff[k] < FMAX[k]): continue
            if k == "wk" and boot["wk"] > 0: continue
            if k == "up":
                if ob["drain_up"] > 0: ph.cancel_drain(); decided = True; continue
                if boot["up"] > 0: continue
                if ob["rep_up"] >= ob["wk_ready"] * s.cfg.spw: continue   # position_wait(sigma 模式 worker 層負責建)
                r = ph.scale_out_up()
                if r[0] == "ok": s.last_out[k] = t; decided = True
                continue
            ok = ph.deploy_vy() if k == "vy" else ph.create_wk()
            if ok: s.last_out[k] = t; decided = True
        for k in ("up", "vy", "wk"):
            ob = ph.observe()
            eff = {"up": ob["rep_up"] - ob["drain_up"], "vy": ob["vy_vm"], "wk": ob["wk_vm"]}
            boot = {"up": ob["boot_up"], "vy": ob["vy_boot"], "wk": ob["wk_boot"]}; drn = {"up": ob["drain_up"], "vy": 0, "wk": 0}
            if eff[k] <= FMIN[k] + 1e-9 or boot[k] > 0: continue
            if drn[k] > 0 or t - s.last_in[k] < s.Dd[k]: continue
            if k == "wk" and (drn["up"] > 0 or t - s.last_in["up"] < s.Dd["up"]): continue
            if t - s.last_out[k] < s.LOCK[k]: continue
            if t < 2 * s.W[k]: continue
            peak = max(d for (tt, d) in s.hist if tt >= t - s.W[k])
            def rel_need(level):
                x = level + s.L[k] * s.pr.sigma("run", k, level) + s.K[k]
                if k == "wk":
                    nn = max(s.need("up", x), math.ceil(s.need("up", level + s.L["up"] * s.pr.sigma("run", "wk", level) + s.K["up"]) / s.cfg.spw) * s.cfg.spw)
                    return max(nn, eff["up"])
                return s.need(k, x)
            if k == "wk":
                if not (rel_need(D) <= (eff["wk"] - 1) * s.cfg.spw and rel_need(peak) <= (eff["wk"] - 1) * s.cfg.spw): continue
                if eff["up"] > (eff["wk"] - 1) * s.cfg.spw: continue
                i = ob["idle_wk"]
                if i is None or ph.t - ph.workers[i]["ready"] < s.idle_min: continue
                if ph.delete_wk(i): s.last_in[k] = t; decided = True
            else:
                if not (rel_need(D) <= eff[k] - 1 and rel_need(peak) <= eff[k] - 1): continue
                ok = ph.scale_in_up() if k == "up" else ph.delete_vy()
                if ok: s.last_in[k] = t; decided = True
        return decided

class CtlV6:
    """v8sim2.sim_v6(batch 先驗:need(D+5);縮容 need(窗內峰值+5) ≤ cur−1 + dwell 300/600)"""
    def __init__(s, cfg, b=5):
        s.cfg, s.b = cfg, b; s.W6 = {"up": 300, "vy": 115, "wk": 145}; s.VMDW = {"up": 300, "vy": 600, "wk": 600}
        s.last_out = {k: -1e9 for k in cfg.h}; s.hist = []
    def tick(s, ph, ob):
        t = ph.t; D = float(ob["D"]); s.hist.append((t, D)); decided = False
        cur = {"up": ob["ready_up"] - ob["drain_up"], "vy": ob["vy_adm"], "wk": ob["wk_ready"]}
        pend = {"up": ob["boot_up"], "vy": ob["vy_boot"], "wk": ob["wk_boot"]}
        for k in ("vy", "wk", "up"):
            want = s.cfg.need(k, D + s.b)
            if want > cur[k] + pend[k] and cur[k] + pend[k] < FMAX[k]:
                if k == "up":
                    if cur["up"] + pend["up"] + 1 > (cur["wk"] + pend["wk"]) * s.cfg.spw: continue
                    if ob["drain_up"] > 0: ph.cancel_drain(); decided = True; continue
                    r = ph.scale_out_up()
                    if r[0] == "ok": s.last_out[k] = t; decided = True; pend["up"] += 1
                    continue
                ok = ph.deploy_vy() if k == "vy" else ph.create_wk()
                if ok: s.last_out[k] = t; decided = True; pend[k] += 1
        for k in ("up", "vy", "wk"):
            if cur[k] <= FMIN[k] or pend[k] > 0: continue
            if k == "up" and ob["drain_up"] > 0: continue
            if k == "wk" and (cur["wk"] - 1) * s.cfg.spw < cur["up"] + pend["up"]: continue
            peak = max(d for (tt, d) in s.hist if tt >= t - s.W6[k])
            if not (s.cfg.need(k, peak + s.b) <= cur[k] - 1): continue
            if t - s.last_out[k] < s.VMDW[k]: continue
            if k == "up": ok = ph.scale_in_up()
            elif k == "vy": ok = ph.delete_vy()
            else: ok = ph.delete_wk()
            if ok: decided = True
        return decided

class HPA:
    def __init__(s, tol, target, mn, mx, down_window):
        s.tol, s.target, s.mn, s.mx, s.dw = tol, target, mn, mx, down_window; s.hist = []
    def step(s, now, cur, avg):
        cur = max(1, cur); raw = cur; ratio = avg / s.target if s.target > 0 else 0
        if abs(ratio - 1) > s.tol: raw = int(math.ceil(cur * ratio - 1e-12))
        raw = min(s.mx, max(s.mn, raw)); s.hist.append((now, raw)); s.hist = [h for h in s.hist if h[0] >= now - s.dw]
        eff = raw
        if raw < cur:
            eff = max(eff, max(h[1] for h in s.hist)); eff = min(eff, cur)
        return eff

class CtlB4:
    """baseline.go b4(DASA+HPA)/b5(Holt 預測 + 同控制律 + 預測式 worker 預建,q11 位置封頂)"""
    def __init__(s, predictive=False, mu=12.0, n0=1, kmax=2, margin=0.8, target=3.5, tol=0.05, hmin=2, hmax=8, down=600, maxbatch=3,
                 holt=(0.3, 0.05), lead=(2, 5, 5), min_wk=1, max_wk=4):
        s.pred = predictive; s.mu, s.n0, s.kmax, s.margin = mu, n0, kmax, margin; s.hpa = HPA(tol, target, hmin, hmax, down); s.target = target
        s.maxbatch = maxbatch; s.a, s.be = holt; s.lead = dict(up=lead[0], vy=lead[1], wk=lead[2]); s.min_wk, s.max_wk = min_wk, max_wk
        s.L = s.T = 0.0; s.init = False; s.last = {}; s.base = {}
    def inflight(s, a, cur, maxage, t):
        if a not in s.last: return False
        if cur != s.base[a] or t - s.last[a] > maxage: s.last.pop(a); s.base.pop(a); return False
        return True
    def note(s, a, cur, t): s.last[a] = t; s.base[a] = cur
    def tick(s, ph, ob):
        t = ph.t; total = float(ob["D"]); decided = False
        pred = lambda ticks: total
        if s.pred:
            x = total
            if not s.init: s.L, s.T, s.init = x, 0.0, True
            else: lp = s.L; s.L = s.a * x + (1 - s.a) * (s.L + s.T); s.T = s.be * (s.L - lp) + (1 - s.be) * s.T
            pred = lambda ticks: max(x, s.L + ticks * s.T)
        # DASA (VyOS)
        cur = ob["vy_vm"]; sessVY = pred(s.lead["vy"])
        desired = max(s.n0, min(s.n0 + s.kmax, int(math.ceil(sessVY / s.mu - 1e-9)))) if s.mu > 0 else s.n0
        if desired > cur and not s.inflight("deploy_vy", cur, 240, t):
            if ph.deploy_vy(): s.note("deploy_vy", cur, t); decided = True
        elif desired < cur and cur > s.n0 and sessVY <= (cur - 1) * s.mu * s.margin and not s.inflight("delete_vy", cur, 240, t):
            if ph.delete_vy(): s.note("delete_vy", cur, t); decided = True
        # HPA (slots)
        curW = max(ob["wk_ready"], ob["wk_vm"]); positions = curW * 2; needWorker = False; scaledOut = False
        cur_up = ob["ready_up"]   # active slots (pods with association; draining pods still answer)
        if cur_up > 0:
            avg = pred(s.lead["up"]) / cur_up
            eff = s.hpa.step(t, cur_up, avg)
            if eff > cur_up and not s.inflight("out_up", cur_up, 90, t):
                n = min(eff - cur_up, s.maxbatch)
                if s.pred:
                    if eff > positions: needWorker = True
                    free = ob["wk_ready"] * 2 - cur_up
                    n = min(n, free)
                if n > 0:
                    for _ in range(n):
                        if ob["drain_up"] > 0 and ph.cancel_drain(): continue
                        r = ph.scale_out_up()
                        if r[0] == "noworker" and not s.pred:
                            # executor fallback (b4): create the slot's worker first (reactive)
                            if not s.inflight("create_wk", curW, 240, t) and ph.create_wk(): s.note("create_wk", curW, t)
                            break
                    s.note("out_up", cur_up, t); scaledOut = True; decided = True
            elif eff < cur_up and not s.inflight("in_up", cur_up, 300, t):
                if ph.scale_in_up(): s.note("in_up", cur_up, t); decided = True
        # b5 predictive worker
        if s.pred and curW < s.max_wk and not s.inflight("create_wk", curW, 240, t):
            needSlots = min(s.hpa.mx, int(math.ceil(pred(s.lead["wk"]) / s.target - 1e-9)))
            if needWorker or needSlots > positions:
                if ph.create_wk(): s.note("create_wk", curW, t); scaledOut = True; decided = True
        # reactive worker reclaim (b4 and b5 both: idle worker)
        if not scaledOut and ob["idle_wk"] is not None and ob["wk_ready"] > s.min_wk and not s.inflight("delete_wk", ob["wk_vm"], 180, t):
            if ph.delete_wk(ob["idle_wk"]): s.note("delete_wk", ob["wk_vm"], t); decided = True
        return decided

class CtlB6:
    """baseline_b6.go decideB6 逐句移植(Toka 型:多預測器 + 回測選用;容量利用目標 u;inflight 計時;q11 位置封頂;winMax 回看)"""
    def __init__(s, cfg, u=0.70, W=10, dwell_up=300, dwell_vm=600, cap_vy=17.8, cap_up=5.0, spw=2, n0=1, kmax=2, up_min=2, up_max=8, wk_min=1, wk_max=4, maxbatch=3):
        import v8sim_b6 as B
        s.u = {k: u for k in ("up", "vy", "wk")}; s.W = W; s.dwell = {"up": dwell_up, "vy": dwell_vm, "wk": dwell_vm}
        s.cap_vy, s.cap_up, s.spw, s.n0, s.kmax, s.up_min, s.up_max, s.wk_min, s.wk_max, s.maxbatch = cap_vy, cap_up, spw, n0, kmax, up_min, up_max, wk_min, wk_max, maxbatch
        s.fcs = B.load_models()(); s.H = dict(B.H_TICKS); s.hist = []; s.pred_log = {f.name: {} for f in s.fcs}; s.ti = 0
        s.last_out = {k: -1e9 for k in s.u}; s.last_in = {k: -1e9 for k in s.u}; s.last = {}; s.base = {}
    def inflight(s, a, cur, maxage, t):
        if a not in s.last: return False
        if cur != s.base[a] or t - s.last[a] > maxage: s.last.pop(a); s.base.pop(a); return False
        return True
    def note(s, a, cur, t): s.last[a] = t; s.base[a] = cur
    def ceildiv(s, v, c): return int(math.ceil(v / c - 1e-9)) if c > 0 else 0
    def needVY(s, v): return min(s.n0 + s.kmax, max(s.n0, s.ceildiv(v, s.cap_vy * s.u["vy"])))
    def needUP(s, v): return min(s.up_max, max(s.up_min, s.ceildiv(v, s.cap_up * s.u["up"])))
    def needWK(s, v): return min(s.wk_max, max(s.wk_min, s.ceildiv(float(s.ceildiv(v, s.cap_up * s.u["wk"])), float(s.spw))))
    def tick(s, ph, ob):
        t = ph.t; x = float(ob["D"]); s.hist.append(x); decided = False
        for f in s.fcs: f.update(x)
        j0 = max(0, s.ti - s.W); winMax = max(s.hist[j0:s.ti + 1])
        fc = {}
        for k in ("up", "vy", "wk"):
            h = s.H[k]; errs = {}
            for f in s.fcs:
                e = [abs(s.pred_log[f.name].get((j, h), s.hist[j]) - s.hist[j]) for j in range(max(0, s.ti - s.W), s.ti)]
                errs[f.name] = sum(e) / len(e) if e else 0.0
            best = min(s.fcs, key=lambda f: errs[f.name]); fc[k] = max(0.0, best.fc(s.hist, h))
            for f in s.fcs: s.pred_log[f.name][(s.ti + h, h)] = f.fc(s.hist, h)
        s.ti += 1
        dwellOK = lambda k: (t - s.last_out[k] >= s.dwell[k]) and (t - s.last_in[k] >= s.dwell[k])
        scaledOut = False
        curW = max(ob["wk_ready"], ob["wk_vm"]); positions = curW * s.spw; needWorker = False
        # VyOS
        cur = ob["vy_vm"]; want = max(s.needVY(fc["vy"]), s.needVY(x))
        if want > cur and not s.inflight("deploy_vy", cur, 240, t):
            if ph.deploy_vy(): s.note("deploy_vy", cur, t); s.last_out["vy"] = t; scaledOut = True; decided = True
        elif cur > s.n0 and s.needVY(max(winMax, fc["vy"])) <= cur - 1 and dwellOK("vy") and not s.inflight("deploy_vy", cur, 240, t) and not s.inflight("delete_vy", cur, 240, t):
            if ph.delete_vy(): s.note("delete_vy", cur, t); s.last_in["vy"] = t; decided = True
        # slots
        cur = ob["ready_up"]
        if cur > 0:
            want = max(s.needUP(fc["up"]), s.needUP(x))
            if want > positions: needWorker = True
            if want > cur and not s.inflight("out_up", cur, 90, t):
                n = min(want - cur, s.maxbatch, ob["wk_ready"] * s.spw - cur)
                if n > 0:
                    for _ in range(n):
                        if ob["drain_up"] > 0 and ph.cancel_drain(): continue
                        ph.scale_out_up()
                    s.note("out_up", cur, t); s.last_out["up"] = t; scaledOut = True; decided = True
            elif cur > s.up_min and s.needUP(max(winMax, fc["up"])) <= cur - 1 and dwellOK("up") and not s.inflight("out_up", cur, 90, t) and not s.inflight("in_up", cur, 300, t):
                if ph.scale_in_up(): s.note("in_up", cur, t); s.last_in["up"] = t; decided = True
        # worker: predictive pre-build
        if curW < s.wk_max and not s.inflight("create_wk", curW, 240, t):
            needW = max(s.needWK(fc["wk"]), s.needWK(x))
            if needWorker and needW < curW + 1: needW = curW + 1
            if needW > curW:
                if ph.create_wk(): s.note("create_wk", curW, t); s.last_out["wk"] = t; scaledOut = True; decided = True
        # worker: reclaim (physical idle + dwell)
        if not scaledOut and ob["idle_wk"] is not None and curW > s.wk_min and dwellOK("wk") and s.needWK(max(winMax, fc["wk"])) <= curW - 1 and not s.inflight("delete_wk", ob["wk_ready"], 180, t):
            if ph.delete_wk(ob["idle_wk"]): s.note("delete_wk", ob["wk_ready"], t); s.last_in["wk"] = t; decided = True
        return decided

# ======================= runner =======================
_CFG = None; _PRIOR = None
def cfg_prior():
    global _CFG, _PRIOR
    if _CFG is None:
        _CFG = M.cfg_measured(); lib = json.load(open(f"{Q}/prior_traces.json")); _PRIOR = S.Prior(lib, _CFG)
    return _CFG, _PRIOR
LAM = {"S4a": {"vy": 2.83, "wk": 2.83, "up": 3.08}, "S4b": {"vy": 1.83, "wk": 1.83, "up": 2.00}}
def make_ctl(arm, **kw):
    cfg, pr = cfg_prior()
    if arm in ("S4a", "S4b"): return CtlSigma(cfg, pr, LAM[arm], K=kw.get("K"))
    if arm == "S": return CtlSigma(cfg, pr, kw["L"], K=kw.get("K"))
    if arm == "v6": return CtlV6(cfg)
    if arm == "B4c2": return CtlB4(predictive=False, mu=12.0, target=3.5)
    if arm == "B5c1": return CtlB4(predictive=True, mu=14.0, target=4.0)
    if arm == "B4": return CtlB4(predictive=False, mu=kw["mu"], target=kw["target"])
    if arm == "B5": return CtlB4(predictive=True, mu=kw["mu"], target=kw["target"])
    if arm == "B6": return CtlB6(cfg, u=kw.get("u", 0.70))
    if arm == "B1": return None
    raise ValueError(arm)
def initial_fleet(arm, d0, **kw):
    """start=None 時各臂自己的收斂起點(與舊模擬同法:S = need(d0+λσ̂(+k));v6 = need(d0+5);B6 = need_u(d0);B4/B5 = ceil(d0/target), ceil(d0/μ))"""
    cfg, pr = cfg_prior(); d0 = float(d0)
    if arm in ("S4a", "S4b", "S"):
        L = LAM[arm] if arm in LAM else kw["L"]; K = kw.get("K") or {"up": 0, "vy": 0, "wk": 0}
        up = cfg.need("up", d0 + L["up"] * pr.sigma("win", "up", d0) + K["up"]); vy = cfg.need("vy", d0 + L["vy"] * pr.sigma("win", "vy", d0) + K["vy"])
    elif arm == "v6": up = cfg.need("up", d0 + 5); vy = cfg.need("vy", d0 + 5)
    elif arm == "B6":
        u = kw.get("u", 0.70); up = min(8, max(2, math.ceil(d0 / (5.0 * u) - 1e-9))); vy = min(3, max(1, math.ceil(d0 / (17.8 * u) - 1e-9)))
    elif arm in ("B4c2", "B5c1", "B4", "B5"):
        tg = {"B4c2": (3.5, 12.0), "B5c1": (4.0, 14.0)}.get(arm, (kw.get("target", 3.5), kw.get("mu", 12.0)))
        up = min(8, max(2, math.ceil(d0 / tg[0] - 1e-9))); vy = min(3, max(1, math.ceil(d0 / tg[1] - 1e-9)))
    else: up, vy = max(2, math.ceil(d0 / 5)), max(1, math.ceil(d0 / 16.5))
    up = int(min(8, max(2, up))); vy = int(min(3, max(1, vy))); wk = int(min(4, max(1, math.ceil(up / 2))))
    return (up, vy, wk)
def run(ue, arm, start=None, phys=None, **kw):
    if start is None: start = initial_fleet(arm, ue[0], **kw)
    ph = Phys(ue, start=start, p=phys); ctl = make_ctl(arm, **kw)
    n = 60 * 60 // DT
    for i in range(n):
        ph.advance_units()   # 就緒/消失轉移先於本 tick 的觀測
        if ph.t % TICK == 0 and ctl is not None:
            ob = ph.observe()
            decided = ctl.tick(ph, ob)
            ph.hot_relief(getattr(ph, "_over", {}))
            if not decided and ph.t - ph.last_pool_relief >= ph.p["pool_relief_s"]:
                ph.enqueue_pool_relief(); ph.last_pool_relief = ph.t
        elif ph.t % TICK == 0 and ctl is None:
            ph.hot_relief(getattr(ph, "_over", {}))
            if ph.t - ph.last_pool_relief >= ph.p["pool_relief_s"]: ph.enqueue_pool_relief(); ph.last_pool_relief = ph.t
        ph.step()
    return ph.result()
if __name__ == "__main__":
    E = "/home/cyy/experiment"
    TR = {"t1": "40", "t2": "pm", "t4": "t4"}
    arm = sys.argv[1] if len(sys.argv) > 1 else "S4a"; tn = sys.argv[2] if len(sys.argv) > 2 else "t4"
    ue = json.load(open(f"{E}/trace_ue_60min_v3_{TR[tn]}.json"))["ue"][:60]
    st = tuple(int(x) for x in sys.argv[3].split("/")) if len(sys.argv) > 3 else None
    r = run(ue, arm, start=st)
    print(f"{arm} {tn} start={st}: SLO {r['slo']}/60 viol {r['viol']} alloc_vm {r['alloc_vm']:.0f}")
    print(" events:", [(int(t) // 60, a, k, o) for t, a, k, o in r["events"]][:40])
    print(" per-minute (m, D, counts, vy, wk):"); [print("  ", h) for h in r["slot_hist"][::5]]
