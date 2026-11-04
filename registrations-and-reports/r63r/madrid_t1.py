#!/usr/bin/env python3
"""r63r task 2 (spec §4.107 A consequence): Madrid T1 with the leakage-free six-split mean λ.
Same procedure as madrid/mad_t12.py T1: frozen v8sim10.sim_nest2(ue, cfg, pr, L, acct='vmexist'), cfg = cfg_measured(),
Prior = Melbourne FULL library (prior_traces.json) = what the deployed system carries; library = madrid/madrid_lib.json (556 kept 1:1 windows).
λ sets: new mean (r63a): S4b 1.88/1.88/2.00 (ε 0.02), S4a 2.75/2.75/3.12 (ε 0.005); deployed frozen S4b 1.83/2.00, S4a 2.83/3.08 (reference,
must reproduce madrid/REPORT.md 0.213 %/1130.5 and 0.048 %/1224.5); sensitivity: unrounded means 1.875/2.00 and 2.75/3.125.
Verdict (§4.99 B item 7): risk in [ε, 1.5ε] -> 'λ transfers directly'; < ε -> 'conservative, transfers'; > 1.5ε -> 'needs recalibration'.
Run: cd /home/user/experiment/qsim/r63r && nice -n 19 taskset -c 13,14 python3 madrid_t1.py"""
import os, sys, json, time
import numpy as np
from multiprocessing import Pool
Q = "/home/user/experiment/qsim"; R = f"{Q}/r63r"; sys.path.insert(0, Q); os.chdir(Q)
import v8sim10 as M10
SETS = {  # name: (arm, eps, L)
    "S4b new (1.88/2.00)": ("S4b", 0.02, {"vy": 1.88, "wk": 1.88, "up": 2.00}),
    "S4a new (2.75/3.12)": ("S4a", 0.005, {"vy": 2.75, "wk": 2.75, "up": 3.12}),
    "S4b deployed (1.83/2.00)": ("S4b", 0.02, {"vy": 1.83, "wk": 1.83, "up": 2.00}),
    "S4a deployed (2.83/3.08)": ("S4a", 0.005, {"vy": 2.83, "wk": 2.83, "up": 3.08}),
    "S4b new unrounded (1.875/2.00)": ("S4b", 0.02, {"vy": 1.875, "wk": 1.875, "up": 2.00}),
    "S4a new unrounded (2.75/3.125)": ("S4a", 0.005, {"vy": 2.75, "wk": 2.75, "up": 3.125}),
}
OLD = {"S4b": (0.00213, 1130.5), "S4a": (0.00048, 1224.5)}   # madrid/REPORT.md T1 (deployed λ)
t0 = time.time()
cfg = M10.M.cfg_measured(); pr = M10.S.Prior(json.load(open(f"{Q}/prior_traces.json")), cfg)
lib = json.load(open(f"{Q}/madrid/madrid_lib.json")); UE = [e["ue"][:60] for e in lib]; assert len(UE) == 556 and all(len(u) == 60 for u in UE)
def one(ue):
    return {k: (lambda r: (int(r["slo"]), float(r["alloc"])))(M10.sim_nest2(ue, cfg, pr, L, acct="vmexist")) for k, (_, _, L) in SETS.items()}
if __name__ == "__main__":
    with Pool(2) as p: res = p.map(one, UE, chunksize=10)
    out = {"runtime_s": None, "n": len(UE), "sets": {}}
    rows = ["| λ set | arm | ε | mean risk ± SE | frac traces ≥1 viol | mean alloc vmexist ± SE | risk/ε | T1 verdict |", "|---|---|---|---|---|---|---|---|"]
    for k, (arm, e, L) in SETS.items():
        rk = np.array([(60 - r[k][0]) / 60 for r in res]); al = np.array([r[k][1] for r in res])
        risk = float(rk.mean()); v = "λ transfers directly" if e <= risk <= 1.5 * e else ("conservative, transfers" if risk < e else "needs recalibration")
        d = dict(arm=arm, eps=e, L=L, risk=risk, risk_se=float(rk.std(ddof=1) / np.sqrt(len(rk))), frac_viol=float((rk > 0).mean()), alloc=float(al.mean()), alloc_se=float(al.std(ddof=1) / np.sqrt(len(al))), ratio=risk / e, verdict=v)
        out["sets"][k] = d
        rows.append(f"| {k} | {arm} | {e} | {risk*100:.3f}% ± {d['risk_se']*100:.3f} | {d['frac_viol']*100:.1f}% | {d['alloc']:.1f} ± {d['alloc_se']:.1f} | {d['ratio']:.2f} | {v} |")
    for arm in ("S4a", "S4b"):
        k = [x for x in SETS if x.startswith(arm + " deployed")][0]; d = out["sets"][k]
        ok = round(d["risk"], 5) == OLD[arm][0] and round(d["alloc"], 1) == OLD[arm][1]
        out[f"reproduce_{arm}"] = ok; rows.append(f"\nreproduce madrid/REPORT.md T1 {arm} ({OLD[arm][0]*100:.3f}%, {OLD[arm][1]}): {'MATCH' if ok else 'MISMATCH'} (fresh {d['risk']*100:.4f}%, {d['alloc']:.2f})")
    out["runtime_s"] = time.time() - t0
    json.dump(out, open(f"{R}/out/madrid_t1.json", "w"), indent=1)
    open(f"{R}/out/madrid_t1_table.md", "w").write("\n".join(rows) + "\n"); print("\n".join(rows)); print(f"runtime {time.time()-t0:.1f} s")
