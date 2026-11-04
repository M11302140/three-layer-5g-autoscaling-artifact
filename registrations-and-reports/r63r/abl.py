#!/usr/bin/env python3
"""r63r task 1: equal-risk ablation (spec §4.99 C) with split-specific, leakage-free σ̂ (spec §4.107 A consequence).
Identical to v8sim10_ablation.py (imported for VARIANTS, grids, trace_metrics; simulator = v8sim10_abl.sim_nest2 with the variant flag)
except: the Prior of split s = v8sim2.Prior(all traces of the calibration groups of grouped_split(s), cfg_measured) (= r63a task 1),
used for calibration AND held-out evaluation of that split; held-out groups never enter σ̂.
Calibration (= v8sim10_ablation.calibrate): coarse grid GRID_VM×GRID_UP (1-D GRID_1D for single_lambda) on cal = first 300 cal traces,
acct dispatch -> feasible (mean cal risk ≤ target) cheapest mean cal alloc -> ±0.25 refine -> re-select; infeasible -> recorded, no fallback.
Held-out: every held-out trace with acct vmexist (risk, metrics) and acct dispatch (alloc_dispatch).  Simulations are cached per
(trace, λ) inside a (variant, split) context so both targets share the coarse grid (pure caching; the arithmetic is unchanged).
One job = one (variant, split) context, ≤ 2 worker processes; results appended to out/abl.jsonl (resumable).
Run: cd /home/user/experiment/qsim/r63r && nohup nice -n 19 taskset -c 13,14 python3 abl.py > out/abl_run.log 2>&1 &"""
import os, sys, json, time, itertools, datetime as dt, numpy as np
Q = "/home/user/experiment/qsim"; R = f"{Q}/r63r"; sys.path.insert(0, Q); os.chdir(Q)
_argv = sys.argv; sys.argv = [sys.argv[0]]
import v8sim10_ablation as AB          # module-level: loads lib/cfg/full-library pr (unused here), defines helpers; main guarded
sys.argv = _argv
import v8sim10_abl as A, v8sim2 as S
from v8sim3 import grouped_split, risk_vec
from concurrent.futures import ProcessPoolExecutor
lib = AB.lib; cfg = AB.cfg
FN = f"{R}/out/abl.jsonl"
def log(m):
    line = f"[{dt.datetime.now():%F %T}] {m}"; print(line, flush=True); open(f"{R}/out/abl_progress.log", "a").write(line + "\n")
def context(job):
    tag, variant, seed = job; t0 = time.time(); one_d = (variant == "single_lambda")
    c, h = grouped_split(seed); pr = S.Prior([lib[i] for i in c], cfg); cal = c[:AB.NCAL]
    cache = {}; ns = [0]
    def calres(i, lv, lu):
        k = (i, lv, lu); r = cache.get(k)
        if r is None:
            x = A.sim_nest2(lib[i]["ue"][:60], cfg, pr, {"vy": lv, "wk": lv, "up": lu}, variant=variant); r = cache[k] = (x["slo"], x["alloc"]); ns[0] += 1
        return r
    def ev(lv, lu):
        rs = [calres(i, lv, lu) for i in cal]
        return (float(np.mean([(60 - s) / 60.0 for s, _ in rs])), float(np.mean([a for _, a in rs])))
    out = dict(variant=variant, tag=tag, seed=seed, n_prior=len(c), n_cal=len(cal), n_ho=len(h), rows={})
    for target in AB.TARGETS:
        grid = [(l, l) for l in AB.GRID_1D] if one_d else list(itertools.product(AB.GRID_VM, AB.GRID_UP))
        table = {k: ev(*k) for k in grid}
        feas = [(k, v) for k, v in table.items() if v[0] <= target]
        if not feas:
            out["rows"][str(target)] = dict(infeasible=True, min_cal_risk=min(v[0] for v in table.values())); continue
        (lv, lu), _ = min(feas, key=lambda kv: kv[1][1])
        if one_d: refine = [(round(lv + dv, 2), round(lv + dv, 2)) for dv in (-0.25, 0.25) if (round(lv + dv, 2), round(lv + dv, 2)) not in table and lv + dv > 0]
        else: refine = [(round(lv + dv, 2), round(lu + du, 2)) for dv, du in itertools.product((-0.25, 0, 0.25), (-0.25, 0, 0.25)) if (round(lv + dv, 2), round(lu + du, 2)) not in table and lv + dv > 0 and lu + du > 0]
        for k in refine: table[k] = ev(*k)
        feas = [(k, v) for k, v in table.items() if v[0] <= target]
        (lv, lu), (risk, al) = min(feas, key=lambda kv: kv[1][1])
        L = {"vy": lv, "wk": lv, "up": lu}; ms = []
        for i in h:
            r = A.sim_nest2(lib[i]["ue"][:60], cfg, pr, L, variant=variant, acct="vmexist"); m = AB.trace_metrics(r)
            r2 = A.sim_nest2(lib[i]["ue"][:60], cfg, pr, L, variant=variant, acct="dispatch"); m["alloc_dispatch"] = r2["alloc"]
            assert r2["slo"] == r["slo"] and r2["ev"] == r["ev"]; ms.append(m); ns[0] += 2
        keys = ['risk', 'alloc', 'alloc_dispatch', 'flaps', 'flaps_cd', 'acts', 'acts_vy', 'acts_wk', 'acts_up', 'under_vy', 'under_up', 'over_vy', 'over_up']
        ho = {k: float(np.mean([m[k] for m in ms])) for k in keys} | {"n": len(ms)}
        out["rows"][str(target)] = dict(infeasible=False, lam_vm=lv, lam_up=lu, cal_risk=risk, cal_alloc=al, n_eval=len(table), ho=ho)
    out.update(t=time.time() - t0, nsim=ns[0]); return out
if __name__ == "__main__":
    nproc = 2
    done = set()
    if os.path.exists(FN):
        for l in open(FN): done.add(json.loads(l)["tag"])
    # long 2-D contexts first, 1-D last; e first so the r63a check is available early
    order = ["full", "independent", "independent_full", "fixed_dwell", "lock_only", "single_lambda"]
    jobs = [(f"{v}|s{s}", v, s) for v in order for s in AB.SEEDS]; todo = [j for j in jobs if j[0] not in done]
    log(f"=== r63r ablation: {len(jobs)} contexts, {len(done)} done, {len(todo)} to run, nproc {nproc}, affinity {sorted(os.sched_getaffinity(0))}, pid {os.getpid()}")
    T0 = time.time(); k = 0
    with ProcessPoolExecutor(nproc) as pool:
        for r in pool.map(context, todo):
            k += 1; open(FN, "a").write(json.dumps(r) + "\n"); el = time.time() - T0
            rs = "; ".join(f"{tg}: " + ("INFEASIBLE" if x["infeasible"] else f"λ {x['lam_vm']}/{x['lam_up']} cal {x['cal_risk']:.4f} ho {x['ho']['risk']:.4f} vm {x['ho']['alloc']:.1f} fl {x['ho']['flaps']:.2f}") for tg, x in r["rows"].items())
            log(f"{r['tag']} ({k}/{len(todo)}) nprior {r['n_prior']} nho {r['n_ho']} sims {r['nsim']} {r['t']:.0f}s | {rs} | elapsed {el:.0f}s eta {el/k*(len(todo)-k):.0f}s")
    log(f"=== DONE {time.time()-T0:.0f}s")
