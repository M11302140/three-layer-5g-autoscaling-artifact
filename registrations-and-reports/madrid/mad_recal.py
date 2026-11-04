#!/usr/bin/env python3
"""mad_recal.py — spec §4.99 B1 item 7 R: recalibrate λ on the Madrid 1:1 kept library (madrid_lib.json) with the Melbourne procedure
(v8sim10_cal.py logic): grouped splits by (bs, date) (v8sim3.grouped_split logic, frac_cal 0.6, cal = first 300 traces of the
calibration groups), seeds 0-5, grid GRID_VM x GRID_UP, feasible (cal risk <= target) then cheapest (cal alloc, dispatch accounting as in
v8sim10_cal.py), ±0.25 refinement, held-out evaluation.  Simulator = frozen v8sim10.sim_nest2 with cfg = v8sim7.cfg_measured() and
Prior = v8sim2.Prior(madrid_lib, cfg) (the Madrid library's own prior, since R = 'calibrate on Madrid').
Held-out: risk = mean (60-slo)/60; alloc reported with acct='vmexist' (slo is acct-independent) and 'dispatch'.
Targets: 0.02, 0.005 (pre-registered) + supplementary target = v6's realised Madrid risk from T2 (equal-risk cost comparison).
Verdict: mean held-out risk within ε ± SE (SE = std over 6 splits / sqrt(6)) -> 'automatic recalibration recovers'.
Outputs: recal_results.json, recal_table.md, recal_progress.log.  Run from /home/user/experiment/qsim:
  nohup nice -n 19 taskset -c 13,14 python3 madrid/mad_recal.py > madrid/recal_run.log 2>&1 &"""
import json, os, sys, time, random, itertools
import numpy as np
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0, "/home/user/experiment/qsim")
D = os.path.dirname(os.path.abspath(__file__))
import v8sim2 as S, v8sim7 as M, v8sim10 as Q2
GRID_VM = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5]; GRID_UP = [1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5]
NSEED = 6; NCAL = 300
lib = json.load(open(f"{D}/madrid_lib.json")); cfg = M.cfg_measured(); pr = S.Prior(lib, cfg)
t12 = json.load(open(f"{D}/t12_summary.json")); V6_MADRID = t12["libs"]["madrid_1to1"]["arms"]["v6"]
TARGETS = [0.02, 0.005, round(V6_MADRID["risk"], 5)]
LOG = open(f"{D}/recal_progress.log", "a")
def P(*a):
    s = " ".join(str(x) for x in a); print(s, flush=True); LOG.write(s + "\n"); LOG.flush()
def grouped_split(seed, frac_cal=0.6):                 # v8sim3.grouped_split, key (bs, date)
    groups = {}
    for i, tr in enumerate(lib): groups.setdefault((tr["bs"], tr["date"]), []).append(i)
    keys = sorted(groups); rnd = random.Random(seed); rnd.shuffle(keys)
    ncal = int(frac_cal * len(keys)); cal = [i for k in keys[:ncal] for i in groups[k]]; ho = [i for k in keys[ncal:] for i in groups[k]]
    return cal, ho, keys[:ncal]
def risk_vec(rs): return [(60 - r["slo"]) / 60.0 for r in rs]
def run_one(args):
    idx, lv, lu, acct = args; L = {"vy": lv, "wk": lv, "up": lu}
    rs = [Q2.sim_nest2(lib[i]["ue"][:60], cfg, pr, L, acct=acct) for i in idx]
    return (lv, lu, float(np.mean(risk_vec(rs))), float(np.mean([r["alloc"] for r in rs])), len(idx))
def evaluate(pool, idx, grid):
    out = {}
    # split the 300-trace cal set in two halves per grid point so both workers stay busy; recombine by weighted mean
    h = len(idx) // 2; jobs = [(idx[:h], lv, lu, "dispatch") for lv, lu in grid] + [(idx[h:], lv, lu, "dispatch") for lv, lu in grid]
    acc = {}
    for lv, lu, risk, al, n in pool.map(run_one, jobs): acc.setdefault((lv, lu), []).append((risk, al, n))
    for k, v in acc.items():
        n = sum(x[2] for x in v); out[k] = (sum(x[0] * x[2] for x in v) / n, sum(x[1] * x[2] for x in v) / n)
    return out
def calibrate(pool, cal_idx, target):                   # v8sim10_cal.calibrate, verbatim logic
    table = evaluate(pool, cal_idx, list(itertools.product(GRID_VM, GRID_UP)))
    feas = [(k, v) for k, v in table.items() if v[0] <= target]
    if not feas: return None, table
    (lv, lu), _ = min(feas, key=lambda kv: kv[1][1])
    refine = [(round(lv + dv, 2), round(lu + du, 2)) for dv, du in itertools.product((-0.25, 0, 0.25), (-0.25, 0, 0.25)) if (round(lv + dv, 2), round(lu + du, 2)) not in table and lv + dv > 0 and lu + du > 0]
    table.update(evaluate(pool, cal_idx, refine))
    feas = [(k, v) for k, v in table.items() if v[0] <= target]
    (lv, lu), (risk, al) = min(feas, key=lambda kv: kv[1][1])
    return dict(lam_vm=lv, lam_up=lu, cal_risk=risk, cal_alloc_dispatch=al), table
def heldout(pool, ho_idx, lv, lu):
    out = {}
    for acct in ("vmexist", "dispatch"):
        ch = [ho_idx[j:j + 60] for j in range(0, len(ho_idx), 60)]
        rs = list(pool.map(run_one, [(c, lv, lu, acct) for c in ch]))
        n = sum(r[4] for r in rs); out[acct] = (sum(r[2] * r[4] for r in rs) / n, sum(r[3] * r[4] for r in rs) / n, n)
    return out
if __name__ == "__main__":
    t0 = time.time(); P(f"# mad_recal.py start {time.strftime('%F %T')} lib n={len(lib)} groups={len({(e['bs'],e['date']) for e in lib})} targets={TARGETS} affinity={sorted(os.sched_getaffinity(0))}")
    results = {"generated": time.strftime("%F %T"), "lib": "madrid_lib.json", "n": len(lib), "grid_vm": GRID_VM, "grid_up": GRID_UP, "ncal": NCAL, "nseed": NSEED, "v6_madrid": V6_MADRID, "targets": {}}
    with ProcessPoolExecutor(2) as pool:
        for target in TARGETS:
            rows = []
            for seed in range(NSEED):
                cal_idx, ho_idx, cal_keys = grouped_split(seed); ncal_avail = len(cal_idx); cal_idx = cal_idx[:NCAL]
                res, table = calibrate(pool, cal_idx, target)
                if res is None: P(f"  target {target} split{seed}: infeasible"); rows.append(dict(seed=seed, infeasible=True)); continue
                ho = heldout(pool, ho_idx, res["lam_vm"], res["lam_up"])
                row = dict(seed=seed, cal_groups=len(cal_keys), cal_avail=ncal_avail, ncal=len(cal_idx), nho=len(ho_idx), **res,
                           ho_risk=ho["vmexist"][0], ho_alloc_vmexist=ho["vmexist"][1], ho_alloc_dispatch=ho["dispatch"][1],
                           table={f"{k[0]}/{k[1]}": v for k, v in table.items()})
                rows.append(row)
                P(f"  target {target} split{seed}: cal groups {len(cal_keys)} (avail {ncal_avail}, used {len(cal_idx)}) ho n {len(ho_idx)} | λ {res['lam_vm']}/{res['lam_up']} cal risk {res['cal_risk']:.4f} alloc(dispatch) {res['cal_alloc_dispatch']:.1f} | ho risk {row['ho_risk']:.4f} alloc vmexist {row['ho_alloc_vmexist']:.1f} dispatch {row['ho_alloc_dispatch']:.1f}  [{time.time()-t0:.0f}s]")
            ok = [r for r in rows if not r.get("infeasible")]
            if ok:
                hr = np.array([r["ho_risk"] for r in ok]); ha = np.array([r["ho_alloc_vmexist"] for r in ok]); lv = np.array([r["lam_vm"] for r in ok]); lu = np.array([r["lam_up"] for r in ok])
                se = float(hr.std(ddof=1) / np.sqrt(len(hr))) if len(hr) > 1 else float("nan")
                summ = dict(lam_vm_mean=float(lv.mean()), lam_vm_std=float(lv.std(ddof=1)), lam_up_mean=float(lu.mean()), lam_up_std=float(lu.std(ddof=1)),
                            ho_risk_mean=float(hr.mean()), ho_risk_std=float(hr.std(ddof=1)), ho_risk_se=se, ho_alloc_mean=float(ha.mean()), ho_alloc_std=float(ha.std(ddof=1)),
                            n_splits_in_band=int(np.sum(np.abs(hr - target) <= se)),
                            verdict=("automatic recalibration recovers" if abs(hr.mean() - target) <= se else ("below ε-SE (conservative)" if hr.mean() < target else "above ε+SE")))
                P(f"  target {target} summary: λ {summ['lam_vm_mean']:.2f}±{summ['lam_vm_std']:.2f} / {summ['lam_up_mean']:.2f}±{summ['lam_up_std']:.2f}  ho risk {hr.mean():.4f}±{hr.std(ddof=1):.4f} (SE {se:.4f})  alloc {ha.mean():.1f}±{ha.std(ddof=1):.1f}  -> {summ['verdict']}")
            else: summ = {}
            results["targets"][str(target)] = {"rows": rows, "summary": summ}
            json.dump(results, open(f"{D}/recal_results.json", "w"), indent=1)
    results["runtime_s"] = time.time() - t0; json.dump(results, open(f"{D}/recal_results.json", "w"), indent=1)
    L = ["| target ε | split | cal groups (avail/used) | ho n | λ_vm / λ_up | cal risk | ho risk | ho alloc vmexist | ho alloc dispatch |", "|---|---|---|---|---|---|---|---|---|"]
    for t, v in results["targets"].items():
        for r in v["rows"]:
            if r.get("infeasible"): L.append(f"| {t} | {r['seed']} | infeasible |||||||"); continue
            L.append(f"| {t} | {r['seed']} | {r['cal_groups']} ({r['cal_avail']}/{r['ncal']}) | {r['nho']} | {r['lam_vm']} / {r['lam_up']} | {r['cal_risk']:.4f} | {r['ho_risk']:.4f} | {r['ho_alloc_vmexist']:.1f} | {r['ho_alloc_dispatch']:.1f} |")
        s = v["summary"]
        if s: L.append(f"| {t} | **mean ± std** | | | {s['lam_vm_mean']:.2f}±{s['lam_vm_std']:.2f} / {s['lam_up_mean']:.2f}±{s['lam_up_std']:.2f} | | {s['ho_risk_mean']:.4f}±{s['ho_risk_std']:.4f} (SE {s['ho_risk_se']:.4f}; {s['n_splits_in_band']}/{len(v['rows'])} splits in ε±SE) | {s['ho_alloc_mean']:.1f}±{s['ho_alloc_std']:.1f} | **{s['verdict']}** |")
    open(f"{D}/recal_table.md", "w").write("\n".join(L) + "\n"); P("\n".join(L)); P(f"runtime {time.time()-t0:.0f} s")
