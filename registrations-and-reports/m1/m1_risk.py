#!/usr/bin/env python3
"""m1_risk.py — spec §4.99 A.2: frozen simulators over the whole prior library and t1..t7.
S4a/S4b = v8sim10.sim_nest2(ue, cfg_measured, Prior(lib), deployed λ, acct='vmexist');
v6 = v8sim2.sim_v6(ue, v8sim7.cfg_measured()).  risk = (60 - slo)/60.  Writes m1/risk_per_trace.csv.
Cross-checks t3..t7 against the registered prediction files (v8_predict_t345_2026-10-07.txt,
v8_predict_v6_t345_2026-10-07.txt, v8_predict_t67_2026-10-15.txt)."""
import csv, json, sys, time, os
from multiprocessing import Pool
sys.path.insert(0, "/home/user/experiment/qsim"); sys.path.insert(0, "/home/user/experiment/qsim/m1")
from m1_common import *
import v8sim10 as M10
import v8sim2 as S, v8sim7 as M

t0 = time.time()
lib = load_lib(); tr = load_traces()
cfg = M10.M.cfg_measured(); pr = M10.S.Prior(lib, cfg); cfg2 = M.cfg_measured()
print(f"prior built {time.time()-t0:.1f} s; affinity {sorted(os.sched_getaffinity(0))}", flush=True)

def one(ue):
    out = {}
    for arm in ("S4a", "S4b"):
        r = M10.sim_nest2(ue, cfg, pr, LAM[arm], acct="vmexist")
        out[arm] = (int(r["slo"]), float(r["alloc"]))
    r = S.sim_v6(ue, cfg2)
    out["v6"] = (int(r["slo"]), float(r["alloc"]))
    return out

jobs = [t["ue"] for t in lib] + [tr[t] for t in TRACES] + [tr["t6"]]   # last = determinism re-run of t6
nw = min(8, len(os.sched_getaffinity(0)))
t1 = time.time()
with Pool(nw) as p:
    res = p.map(one, jobs, chunksize=20)
print(f"simulated {len(jobs)} traces x 3 arms with {nw} workers in {time.time()-t1:.1f} s", flush=True)
assert res[-1] == res[len(lib) + list(TRACES).index("t6")], "sim not deterministic on t6 re-run"
print("determinism check OK (t6 simulated twice, identical)")

with open(f"{M1}/risk_per_trace.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["index", "loc", "date", "start"] + [f"{a}_{m}" for a in ARMS for m in ("slo", "risk", "alloc")])
    for i, t in enumerate(lib):
        r = res[i]
        w.writerow([i, t["loc"], t["date"], t["start"]] + sum(([r[a][0], f"{(60-r[a][0])/60:.6f}", f"{r[a][1]:.2f}"] for a in ARMS), []))
    for j, t in enumerate(TRACES):
        r = res[len(lib) + j]
        w.writerow([t, "", "", ""] + sum(([r[a][0], f"{(60-r[a][0])/60:.6f}", f"{r[a][1]:.2f}"] for a in ARMS), []))
print(f"wrote {M1}/risk_per_trace.csv")

# registered predictions (slo, alloc_vmexist) to cross-check
REG = {"S4a": {"t1": (60, 1149), "t2": (60, 1413), "t3": (57, 1257), "t4": (60, 1454), "t5": (60, 1464), "t6": (60, 1449), "t7": (60, 1430)},
       "S4b": {"t1": (59, 1080), "t2": (60, 1338), "t3": (57, 1129), "t4": (59, 1427), "t5": (60, 1454), "t6": (60, 1393), "t7": (60, 1395)},
       "v6":  {"t1": (58, 1081), "t2": (59, 1296), "t3": (57, 1104), "t4": (57, 1387), "t5": (60, 1451), "t6": (58, 1363), "t7": (60, 1380)}}
lines = ["| trace | " + " | ".join(f"{a} slo / risk / alloc (registered slo/alloc)" for a in ARMS) + " |", "|---|---|---|---|"]
ok = True
for j, t in enumerate(TRACES):
    r = res[len(lib) + j]; cells = []
    for a in ARMS:
        slo, al = r[a]; rs, ra = REG[a][t]
        match = (slo == rs and abs(round(al) - ra) <= 1)
        ok &= match
        cells.append(f"{slo}/60 / {(60-slo)/60*100:.1f}% / {al:.0f} ({rs}/{ra}{'' if match else ' MISMATCH'})")
    lines.append(f"| {t} | " + " | ".join(cells) + " |")
txt = "\n".join(lines); print(txt)
print("registered-prediction cross-check:", "ALL MATCH" if ok else "MISMATCH (see table)")
open(f"{M1}/risk_t_table.md", "w").write(txt + f"\n\nregistered-prediction cross-check: {'ALL MATCH' if ok else 'MISMATCH'}\n")
# library summary
import numpy as np
for a in ARMS:
    rk = np.array([(60 - r[a][0]) / 60 for r in res[:len(lib)]]); al = np.array([r[a][1] for r in res[:len(lib)]])
    print(f"library {a}: mean risk {rk.mean()*100:.3f}%  frac traces with >=1 violating min {np.mean(rk>0)*100:.1f}%  mean alloc {al.mean():.1f}")
print(f"total runtime {time.time()-t0:.1f} s")
