#!/usr/bin/env python3
"""mad_recal2.py — spec §4.101 R′: identical to mad_recal.py (R) except the grid:
GRID_VM = {0.5, 0.75, ..., 3.5} (13), GRID_UP = {0.5, 0.75, ..., 4.5} (17) = 221 points (R: 6 x 7 = 42).
Same: madrid_lib.json (556), Prior = v8sim2.Prior(madrid_lib, v8sim7.cfg_measured()), grouped split key (bs,date) frac 0.6 seeds 0-5,
cal = first 300, feasible (cal risk <= target) then cheapest cal alloc (dispatch), ±0.25 refinement, held-out risk + alloc (vmexist, dispatch).
Targets 0.02, 0.005, 0.00396.  Execution change only (results identical to running each target separately): for a given seed the coarse-grid
table on the calibration set does not depend on the target, so it is computed once per seed (seed outer loop, targets inner); each target then
gets its own copy of that table, and its ±0.25 refinement points are added only to its own copy (evaluations memoised per seed), exactly as a
separate run would build it.  Verdict: mean ho risk within ε ± SE (std/√6).  Also counts splits whose chosen λ touches 0.5 on either axis.
Run from /home/user/experiment/qsim: nohup nice -n 19 taskset -c 13,14 python3 madrid/mad_recal2.py > madrid/recal2_run.log 2>&1 &"""
import json, os, sys, time, random, itertools
import numpy as np
from concurrent.futures import ProcessPoolExecutor
sys.path.insert(0, "/home/user/experiment/qsim")
D = os.path.dirname(os.path.abspath(__file__))
import v8sim2 as S, v8sim7 as M, v8sim10 as Q2
GRID_VM = [round(0.5 + 0.25 * i, 2) for i in range(13)]; GRID_UP = [round(0.5 + 0.25 * i, 2) for i in range(17)]
assert GRID_VM[-1] == 3.5 and GRID_UP[-1] == 4.5
NSEED = 6; NCAL = 300; FLOOR = 0.5
lib = json.load(open(f"{D}/madrid_lib.json")); cfg = M.cfg_measured(); pr = S.Prior(lib, cfg)
TARGETS = [0.02, 0.005, 0.00396]
LOG = open(f"{D}/recal2_progress.log", "a")
def P(*a):
    s = " ".join(str(x) for x in a); print(s, flush=True); LOG.write(s + "\n"); LOG.flush()
def grouped_split(seed, frac_cal=0.6):
    groups = {}
    for i, tr in enumerate(lib): groups.setdefault((tr["bs"], tr["date"]), []).append(i)
    keys = sorted(groups); rnd = random.Random(seed); rnd.shuffle(keys)
    ncal = int(frac_cal * len(keys)); cal = [i for k in keys[:ncal] for i in groups[k]]; ho = [i for k in keys[ncal:] for i in groups[k]]
    return cal, ho, keys[:ncal]
def run_one(args):
    idx, lv, lu, acct = args; L = {"vy": lv, "wk": lv, "up": lu}
    rs = [Q2.sim_nest2(lib[i]["ue"][:60], cfg, pr, L, acct=acct) for i in idx]
    return (lv, lu, float(np.mean([(60 - r["slo"]) / 60.0 for r in rs])), float(np.mean([r["alloc"] for r in rs])), len(idx))
def evaluate(pool, idx, grid):
    if not grid: return {}
    h = len(idx) // 2; jobs = [(idx[:h], lv, lu, "dispatch") for lv, lu in grid] + [(idx[h:], lv, lu, "dispatch") for lv, lu in grid]
    acc = {}; out = {}
    for lv, lu, risk, al, n in pool.map(run_one, jobs): acc.setdefault((lv, lu), []).append((risk, al, n))
    for k, v in acc.items():
        n = sum(x[2] for x in v); out[k] = (sum(x[0] * x[2] for x in v) / n, sum(x[1] * x[2] for x in v) / n)
    return out
def calibrate(pool, cal_idx, target, base, memo):      # = mad_recal.calibrate with the coarse table supplied
    table = dict(base)
    feas = [(k, v) for k, v in table.items() if v[0] <= target]
    if not feas: return None, table
    (lv, lu), _ = min(feas, key=lambda kv: kv[1][1])
    refine = [(round(lv + dv, 2), round(lu + du, 2)) for dv, du in itertools.product((-0.25, 0, 0.25), (-0.25, 0, 0.25)) if (round(lv + dv, 2), round(lu + du, 2)) not in table and lv + dv > 0 and lu + du > 0]
    memo.update(evaluate(pool, cal_idx, [k for k in refine if k not in memo]))
    table.update({k: memo[k] for k in refine})
    feas = [(k, v) for k, v in table.items() if v[0] <= target]
    (lv, lu), (risk, al) = min(feas, key=lambda kv: kv[1][1])
    return dict(lam_vm=lv, lam_up=lu, cal_risk=risk, cal_alloc_dispatch=al, refine_added=len(refine)), table
def heldout(pool, ho_idx, lv, lu):
    out = {}
    for acct in ("vmexist", "dispatch"):
        ch = [ho_idx[j:j + 60] for j in range(0, len(ho_idx), 60)]
        rs = list(pool.map(run_one, [(c, lv, lu, acct) for c in ch]))
        n = sum(r[4] for r in rs); out[acct] = (sum(r[2] * r[4] for r in rs) / n, sum(r[3] * r[4] for r in rs) / n, n)
    return out
if __name__ == "__main__":
    t0 = time.time(); P(f"# mad_recal2.py start {time.strftime('%F %T')} lib n={len(lib)} grid {len(GRID_VM)}x{len(GRID_UP)}={len(GRID_VM)*len(GRID_UP)} targets={TARGETS} affinity={sorted(os.sched_getaffinity(0))}")
    results = {"generated": time.strftime("%F %T"), "lib": "madrid_lib.json", "n": len(lib), "grid_vm": GRID_VM, "grid_up": GRID_UP, "ncal": NCAL, "nseed": NSEED, "targets": {str(t): {"rows": []} for t in TARGETS}}
    with ProcessPoolExecutor(2) as pool:
        for seed in range(NSEED):
            cal_idx, ho_idx, cal_keys = grouped_split(seed); ncal_avail = len(cal_idx); cal_idx = cal_idx[:NCAL]
            ts = time.time(); base = evaluate(pool, cal_idx, list(itertools.product(GRID_VM, GRID_UP))); memo = {}
            P(f"seed {seed}: coarse grid {len(base)} points in {time.time()-ts:.0f} s  [{time.time()-t0:.0f}s]")
            for target in TARGETS:
                res, table = calibrate(pool, cal_idx, target, base, memo)
                if res is None: P(f"  target {target} split{seed}: infeasible"); results["targets"][str(target)]["rows"].append(dict(seed=seed, infeasible=True)); continue
                ho = heldout(pool, ho_idx, res["lam_vm"], res["lam_up"])
                row = dict(seed=seed, cal_groups=len(cal_keys), cal_avail=ncal_avail, ncal=len(cal_idx), nho=len(ho_idx), **res,
                           floor_touch=bool(res["lam_vm"] <= FLOOR or res["lam_up"] <= FLOOR),
                           ho_risk=ho["vmexist"][0], ho_alloc_vmexist=ho["vmexist"][1], ho_alloc_dispatch=ho["dispatch"][1],
                           table={f"{k[0]}/{k[1]}": v for k, v in table.items()})
                results["targets"][str(target)]["rows"].append(row)
                P(f"  target {target} split{seed}: cal groups {len(cal_keys)} (avail {ncal_avail}, used {len(cal_idx)}) ho n {len(ho_idx)} | λ {res['lam_vm']}/{res['lam_up']}{' FLOOR' if row['floor_touch'] else ''} cal risk {res['cal_risk']:.4f} alloc(dispatch) {res['cal_alloc_dispatch']:.1f} | ho risk {row['ho_risk']:.4f} alloc vmexist {row['ho_alloc_vmexist']:.1f} dispatch {row['ho_alloc_dispatch']:.1f}  [{time.time()-t0:.0f}s]")
            json.dump(results, open(f"{D}/recal2_results.json", "w"), indent=1)
            if seed == 0: P(f"ESTIMATE total runtime ≈ {(time.time()-t0)*NSEED/60:.0f} min (from seed 0)")
        for target in TARGETS:
            rows = results["targets"][str(target)]["rows"]; ok = [r for r in rows if not r.get("infeasible")]
            hr = np.array([r["ho_risk"] for r in ok]); ha = np.array([r["ho_alloc_vmexist"] for r in ok]); lv = np.array([r["lam_vm"] for r in ok]); lu = np.array([r["lam_up"] for r in ok])
            se = float(hr.std(ddof=1) / np.sqrt(len(hr)))
            summ = dict(lam_vm_mean=float(lv.mean()), lam_vm_std=float(lv.std(ddof=1)), lam_up_mean=float(lu.mean()), lam_up_std=float(lu.std(ddof=1)),
                        ho_risk_mean=float(hr.mean()), ho_risk_std=float(hr.std(ddof=1)), ho_risk_se=se, ho_alloc_mean=float(ha.mean()), ho_alloc_std=float(ha.std(ddof=1)),
                        n_splits_in_band=int(np.sum(np.abs(hr - target) <= se)), n_floor_touch=int(sum(r["floor_touch"] for r in ok)),
                        verdict=("automatic recalibration recovers" if abs(hr.mean() - target) <= se else ("below ε-SE (conservative)" if hr.mean() < target else "above ε+SE")))
            results["targets"][str(target)]["summary"] = summ
            P(f"  target {target} summary: λ {summ['lam_vm_mean']:.2f}±{summ['lam_vm_std']:.2f} / {summ['lam_up_mean']:.2f}±{summ['lam_up_std']:.2f}  ho risk {hr.mean():.4f}±{hr.std(ddof=1):.4f} (SE {se:.4f})  alloc {ha.mean():.1f}±{ha.std(ddof=1):.1f}  floor-touch {summ['n_floor_touch']}/6 -> {summ['verdict']}")
    results["runtime_s"] = time.time() - t0; json.dump(results, open(f"{D}/recal2_results.json", "w"), indent=1)
    L = ["| target ε | split | cal groups (avail/used) | ho n | λ_vm / λ_up | cal risk | ho risk | ho alloc vmexist | ho alloc dispatch |", "|---|---|---|---|---|---|---|---|---|"]
    for t, v in results["targets"].items():
        for r in v["rows"]:
            if r.get("infeasible"): L.append(f"| {t} | {r['seed']} | infeasible |||||||"); continue
            L.append(f"| {t} | {r['seed']} | {r['cal_groups']} ({r['cal_avail']}/{r['ncal']}) | {r['nho']} | {r['lam_vm']} / {r['lam_up']}{' (floor)' if r['floor_touch'] else ''} | {r['cal_risk']:.4f} | {r['ho_risk']:.4f} | {r['ho_alloc_vmexist']:.1f} | {r['ho_alloc_dispatch']:.1f} |")
        s = v["summary"]
        L.append(f"| {t} | **mean ± std** | | | {s['lam_vm_mean']:.2f}±{s['lam_vm_std']:.2f} / {s['lam_up_mean']:.2f}±{s['lam_up_std']:.2f} | | {s['ho_risk_mean']:.4f}±{s['ho_risk_std']:.4f} (SE {s['ho_risk_se']:.4f}; {s['n_splits_in_band']}/{len(v['rows'])} splits in ε±SE; floor-touch {s['n_floor_touch']}/6) | {s['ho_alloc_mean']:.1f}±{s['ho_alloc_std']:.1f} | **{s['verdict']}** |")
    R1 = json.load(open(f"{D}/recal_results.json"))
    L += ["", "### R (grid 6x7, floor 1.0/1.5) vs R′ (grid 13x17, step 0.25, floor 0.5/0.5), same splits", "",
          "| target ε | run | λ_vm mean ± std | λ_up mean ± std | ho risk mean ± SE (std) | ho alloc vmexist mean ± std | floor-touch | verdict (ε ± SE) |", "|---|---|---|---|---|---|---|---|"]
    for t in TARGETS:
        for name, res, fl in (("R", R1, None), ("R′", results, True)):
            s = res["targets"][str(t)]["summary"]
            ft = f"{s['n_floor_touch']}/6 (at 0.5)" if fl else f"{sum(1 for r in res['targets'][str(t)]['rows'] if r['lam_vm'] <= 1.0 or r['lam_up'] <= 1.5)}/6 (at old floor 1.0/1.5, incl. refinement below)"
            L.append(f"| {t} | {name} | {s['lam_vm_mean']:.2f} ± {s['lam_vm_std']:.2f} | {s['lam_up_mean']:.2f} ± {s['lam_up_std']:.2f} | {s['ho_risk_mean']:.4f} ± {s['ho_risk_se']:.4f} ({s['ho_risk_std']:.4f}) | {s['ho_alloc_mean']:.1f} ± {s['ho_alloc_std']:.1f} | {ft} | {s['verdict']} |")
    open(f"{D}/recal2_table.md", "w").write("\n".join(L) + "\n"); P("\n".join(L)); P(f"runtime {time.time()-t0:.0f} s")
