#!/usr/bin/env python3
"""qsim/s7r/replay.py (S7R protocol P1, registered in protocol.json P1_replay): hardware-run replays on event_phys.

causal replay: start = observed fleet and per-slot UE counts at formal t0 (prom upf_sessions nearest t0, trimmed/padded to the minute-0
target); injected = the controller's observed dispatches at their own second (daemon log: hbo scale_out_up/scale_in_up (eupf) with the slot
identity, deploy/delete_vyos, create/delete_worker; 'scale_out_up ... cancelled in-flight drain' = drain cancel); everything else
(ready events, arrival placement, relief, drains, loss, cost) comes from event_phys with the fixed profiling constants. Pool relief runs at
ticks with no dispatch in [t, t+30), as in the daemon. No hardware outcome after t is read by the simulation.
Outputs per run: model bad minutes (loss / overflow parts), hardware SLO minutes and classes (classify_b2), model vs hardware alloc_vm.
Usage: python3 s7r/replay.py causal [run ...]  -> s7r/out/P1/causal/<run>.json and summary"""
import sys, os, re, json, csv, math, datetime as dt, collections
S7 = os.path.dirname(os.path.abspath(__file__)); Q = os.path.dirname(S7); P = "/home/user/experiment/p2"
sys.path.insert(0, S7); sys.path.insert(0, Q); sys.path.insert(0, "/home/user/experiment/paper_out_new"); sys.path.insert(0, f"{Q}/r66rr/hit")
import event_phys as E
DNN2OCT = {"internet": 38, "internet2": 31, "internet3": 32, "internet4": 33, "internet5": 34, "internet6": 35, "internet7": 36, "internet8": 37}

def local_hms(line):
    m = re.match(r"\[(\d\d):(\d\d):(\d\d)\]", line); return (int(m[1]), int(m[2]), int(m[3])) if m else None
def run_epoch_t0(run):
    """epoch seconds of the harness 'start:' line (log times are Asia/Taipei)"""
    first = None
    for line in open(f"{P}/v7{run}_daemon.log"):
        if '"time"' in line:
            try: first = json.loads(line)["time"]; break
            except Exception: pass
    d_utc = dt.datetime.fromisoformat(first[:19]).replace(tzinfo=dt.timezone.utc)
    tz = dt.timezone(dt.timedelta(hours=8)); d_loc = d_utc.astimezone(tz)
    for line in open(f"{P}/trace_v7_{run}.log"):
        if re.match(r"\[\d\d:\d\d:\d\d\] start:", line):
            h, mi, s = local_hms(line); t = d_loc.replace(hour=h, minute=mi, second=s, microsecond=0)
            if t < d_loc - dt.timedelta(hours=1): t += dt.timedelta(days=1)
            return int(t.timestamp())
    raise SystemExit(f"{run}: no start line")
def daemon_events(run, t0):
    ev = []
    for line in open(f"{P}/v7{run}_daemon.log"):
        if '"msg":"hbo ' not in line: continue
        try: d = json.loads(line)
        except Exception: continue
        t = int(dt.datetime.fromisoformat(d["time"][:19]).replace(tzinfo=dt.timezone.utc).timestamp()) - t0
        if t < 0 or t >= 3600: continue
        msg = d["msg"]
        if msg == "hbo scale_out_up (eupf)": ev.append((t, "out_up", int(d["slot"].split("-")[1])))
        elif msg.startswith("hbo scale_out_up (eupf): cancelled in-flight drain"): ev.append((t, "cancel", None))
        elif msg == "hbo scale_in_up (eupf)": ev.append((t, "in_up", int(d["slot"].split("-")[1])))
        elif msg == "hbo deploy_vyos": ev.append((t, "out_vy", int(d["name"].split("-")[1])))
        elif msg == "hbo delete_vyos": ev.append((t, "in_vy", int(d["name"].split("-")[1])))
        elif msg == "hbo create_worker": ev.append((t, "out_wk", int(d["name"].split("-")[1])))
        elif msg == "hbo delete_worker": ev.append((t, "in_wk", int(d["name"].split("-")[1])))
    return sorted(ev)
def start_state(run, t0):
    rows = list(csv.DictReader(open(f"{P}/trace_v7_{run}.csv")))
    r0 = rows[0]; nvy = int(r0["vyos_n"]); nwk = int(r0["worker_n"]); target = [int(r["target_ue"]) for r in rows][:60]
    sess = collections.defaultdict(list)
    for r in csv.DictReader(open(f"{P}/prom/v7{run}_upf_sessions.csv")):
        try: ts = int(r["ts"]); o = int(r["label"].split(":")[0].split(".")[-1]); v = float(r["value"])
        except Exception: continue
        sess[o].append((abs(ts - t0), ts, v))
    cnt = {}
    for o, xs in sess.items():
        best = min(xs)
        if best[0] <= 30: cnt[o] = int(round(best[2]))
    return target, nvy, nwk, cnt
class ReplayPhys(E.Phys):
    def init_observed(s, nvy, nwk, cnt, d0):
        for i in range(4): s.workers[i].update(state="off", gen=0, appear=None, ready=None, gone=None)
        for i in range(nwk): s.workers[i].update(state="ready", gen=1, disp=-1e9, ready=-1e9, appear=-1e9)
        for i in range(3): s.vyos[i].update(state="off", gen=0, appear=None, adm=None, gone=None)
        for i in range(nvy): s.vyos[i].update(state="adm", gen=1, disp=-1e9, adm=-1e9, appear=-1e9)
        for o in E.SLOT_ORDER: s.slots[o].update(state="off")
        s.ues = {}; s.active = []; s.next_id = 0
        for o in E.SLOT_ORDER:
            if o in cnt: s.slots[o].update(state="ready", gen=1, disp=-1e9, api=-1e9, relief=-1e9, relief_done=True)
        live = [o for o in E.TIE_ORDER if o in cnt]
        want = {o: cnt[o] for o in live}; tot = sum(want.values())
        while tot > d0: o = max(live, key=lambda x: (want[x], -E.TIE_ORDER.index(x))); want[o] -= 1; tot -= 1
        for o in live:
            for _ in range(want[o]): s.ues[s.next_id] = dict(slot=o, arr=-1e9); s.active.append(s.next_id); s.next_id += 1
        while tot < d0: s.place_arrival(); s.ues[s.next_id - 1]["arr"] = -1e9; tot += 1
    def do(s, kind, idx):
        t = s.t; p = s.p
        if kind == "out_up":
            o = E.SLOT_ORDER[idx]; sl = s.slots[o]
            if sl["state"] != "off" or s.workers[E.SLOT_WK[o]]["state"] != "ready": return "skip"
            sl.update(state="boot", gen=sl["gen"] + 1, disp=t, api=t + p["slot_api_s"], relief=t + p["slot_api_s"] + p["relief_delay_s"], relief_done=False, drain_t=None, drain_empty=None, ann_on=None)
            s.events.append((t, "out", "up", o)); return "ok"
        if kind == "cancel": return "ok" if s.cancel_drain() else "skip"
        if kind == "in_up":
            o = E.SLOT_ORDER[idx]
            if s.slots[o]["state"] != "ready": return "skip"
            save = E.SLOT_ORDER; order = [x for x in save if x != o] + [o]
            act = [x for x in order if s.slots[x]["state"] == "ready"]
            if act[-1] != o: return "skip"
            E.SLOT_ORDER = order
            try: ok = s.scale_in_up()
            finally: E.SLOT_ORDER = save
            return "ok" if ok else "skip"
        if kind == "out_vy":
            v = s.vyos[idx]
            if v["state"] != "off": return "skip"
            v.update(state="boot", gen=v["gen"] + 1, disp=t, adm=t + p["vy_admit_s"], gone=None, appear=t + p["vm_appear_s"]); s.events.append((t, "out", "vy", idx)); return "ok"
        if kind == "in_vy":
            v = s.vyos[idx]
            if v["state"] not in ("adm", "boot"): return "skip"
            v["state"] = "deleting"; v["gone"] = t + p["vm_gone_s"]; s.events.append((t, "in", "vy", idx)); return "ok"
        if kind == "out_wk":
            w = s.workers[idx]
            if w["state"] != "off": return "skip"
            w.update(state="boot", gen=w["gen"] + 1, disp=t, ready=t + p["wk_ready_s"], gone=None, appear=t + p["vm_appear_s"]); s.events.append((t, "out", "wk", idx)); return "ok"
        if kind == "in_wk":
            return "ok" if s.delete_wk(idx) else "skip"
        raise ValueError(kind)
def causal(run):
    t0 = run_epoch_t0(run); target, nvy, nwk, cnt = start_state(run, t0); ev = daemon_events(run, t0)
    ph = ReplayPhys(target, start=(2, 1, 1)); ph.init_observed(nvy, nwk, cnt, target[0])
    applied = []; i = 0; pend = []
    for _ in range(3600):
        ph.phase_demand(); ph.phase_ready(); ph.phase_relief()
        while i < len(ev) and ev[i][0] <= ph.t:
            pend.append(ev[i]); i += 1
        keep = []
        for e in pend:                     # infeasible in the model at this second -> deferred (hardware state was ahead), max 120 s
            st = ph.do(e[1], e[2])
            if st == "ok": applied.append((e[0], e[1], e[2], "ok" if ph.t == e[0] else f"deferred {ph.t - e[0]} s"))
            elif ph.t - e[0] >= 120: applied.append((e[0], e[1], e[2], "skip"))
            else: keep.append(e)
        pend = keep
        if ph.t % E.TICK == 0:
            decided = any(ph.t <= e[0] < ph.t + E.TICK for e in ev)
            ph.hot_relief(ph._over)
            if not decided and ph.t - ph.last_pool_relief >= ph.p["pool_relief_s"]: ph.enqueue_pool_relief(); ph.last_pool_relief = ph.t
        ph.measure(); ph.t += 1
    r = ph.result()
    rows = list(csv.DictReader(open(f"{P}/trace_v7_{run}.csv")))
    hw_bad = [int(rw["min"]) for rw in rows if float(rw["e2e_pct"] or 0) > 0.1 or float(rw["lat_p99_us"] or 0) > 1000]
    import classify_b2 as CB
    try: cls = {int(k): v for k, v in CB.classify(run).items()}
    except Exception as e: cls = {m: "unclassified" for m in hw_bad}
    import rq_metrics as RQ
    eupf, _ = RQ.daemon(run); hw_cost = RQ.alloc_vm_of(run, eupf)
    out = dict(run=run, t0=t0, start=dict(nvy=nvy, nwk=nwk, slots=cnt, d0=target[0]), events=ev, applied=applied,
               model=dict(viol=r["viol"], viol_loss=r["viol_loss"], viol_over=r["viol_over"], alloc_vm=r["alloc_vm"], alloc_by=r["alloc_by"]),
               hw=dict(viol=hw_bad, classes=cls, alloc_vm=hw_cost), skipped=[a for a in applied if a[3] == "skip"], deferred=[a for a in applied if a[3].startswith("deferred")])
    os.makedirs(f"{S7}/out/P1/causal", exist_ok=True); json.dump(out, open(f"{S7}/out/P1/causal/{run}.json", "w"), indent=1, default=str)
    return out
def summarize(outs):
    eps = []; fa_num = 0; fa_den = 0; apes = []; lines = []
    for o in outs:
        cls = o["hw"]["classes"]; hwbad = set(o["hw"]["viol"]); mb = set(o["model"]["viol"])
        fp = sorted(m for m in range(60) if m in cls and cls[m] in ("fleet", "placement"))
        cur = []
        for m in fp:
            if cur and m == cur[-1] + 1: cur.append(m)
            else:
                if cur: eps.append((o["run"], cur))
                cur = [m]
        if cur: eps.append((o["run"], cur))
        clean = [m for m in range(60) if m not in hwbad]; fa = [m for m in clean if m in mb]
        fa_num += len(fa); fa_den += len(clean)
        ape = abs(o["model"]["alloc_vm"] - o["hw"]["alloc_vm"]) / o["hw"]["alloc_vm"] if o["hw"]["alloc_vm"] else None
        if ape is not None: apes.append(ape)
        lines.append(f"| {o['run']} | {sorted(hwbad)} | {dict(sorted((k, v) for k, v in cls.items()))} | {sorted(mb)} | {fa} | {o['model']['alloc_vm']:.0f} | {o['hw']['alloc_vm']} | {100*ape if ape is not None else float('nan'):.1f} | {len(o['skipped'])} |")
    rec = []
    for run, ep in eps:
        o = next(x for x in outs if x["run"] == run); mb = set(o["model"]["viol"])
        rec.append(any(m in mb for m in range(ep[0] - 1, ep[-1] + 2)))
    runs_with = len({r for r, _ in eps})
    summ = dict(episodes=len(eps), runs_with_episodes=runs_with, recalled=sum(rec), recall=(sum(rec) / len(eps) if eps else None),
                false_alarm=fa_num / fa_den if fa_den else None, fa_minutes=fa_num, clean_minutes=fa_den,
                cost_mape=(sum(apes) / len(apes) if apes else None), n_runs=len(outs), episode_list=[(r, e, ok) for (r, e), ok in zip(eps, rec)])
    gate = dict(recall=(summ["recall"] is not None and summ["recall"] >= 0.8 and len(eps) >= 5 and runs_with >= 3),
                support=(len(eps) >= 5 and runs_with >= 3), false_alarm=(summ["false_alarm"] is not None and summ["false_alarm"] <= 0.05),
                cost=(summ["cost_mape"] is not None and summ["cost_mape"] <= 0.03))
    return summ, gate, lines
if __name__ == "__main__":
    mode = sys.argv[1]; runs = sys.argv[2:] or json.load(open(f"{S7}/protocol.json"))["P1_replay"]["model_validation_runs"]
    assert mode == "causal"
    outs = []
    for run in runs:
        o = causal(run); outs.append(o)
        print(f"{run}: hw viol {o['hw']['viol']} classes {o['hw']['classes']} | model viol {o['model']['viol']} | cost model {o['model']['alloc_vm']:.0f} hw {o['hw']['alloc_vm']} | skipped {len(o['skipped'])}", flush=True)
    summ, gate, lines = summarize(outs)
    hdr = "| run | hw viol minutes | hw classes | model bad minutes | false alarms (model bad, hw clean) | model alloc_vm | hw alloc_vm | APE % | skipped injections |\n|---|---|---|---|---|---|---|---|---|"
    txt = hdr + "\n" + "\n".join(lines) + "\n\n" + json.dumps(summ, indent=1, default=str) + "\nGATE " + json.dumps(gate)
    open(f"{S7}/out/P1/causal_summary.md", "w").write(txt); print(txt)
