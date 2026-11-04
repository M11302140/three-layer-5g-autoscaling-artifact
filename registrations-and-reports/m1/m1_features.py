#!/usr/bin/env python3
"""m1_features.py — spec §4.99 A.1: load features for the prior library (1615) and t1..t7,
library percentile ranks of each t-value, write m1/features.csv and print the t-table.
Cross-checks mp/f36/minUE/rise10 of t1..t5 against the frozen t6t7_thresholds.json."""
import csv, json, sys, time
import numpy as np
sys.path.insert(0, "/home/user/experiment/qsim/m1")
from m1_common import *

t0 = time.time()
lib = load_lib(); tr = load_traces()
L = [features(t["ue"]) for t in lib]
N = len(L)
col = {k: np.array([l[k] for l in L]) for k in FEATS}
T = {t: features(u) for t, u in tr.items()}

# cross-check against frozen stats (t1..t5)
froz = json.load(open(f"{Q}/t6t7_thresholds.json"))["t1_t5_stats"]
for t in ("t1", "t2", "t3", "t4", "t5"):
    for a, b in (("mp", "mp"), ("f36", "f36"), ("minUE", "minue"), ("rise10", "rise10")):
        assert abs(T[t][a] - froz[t][b]) < 1e-9, (t, a, T[t][a], froz[t][b])
print(f"cross-check OK: t1..t5 mp/f36/minUE/rise10 equal the frozen t6t7_thresholds.json values")

with open(f"{M1}/features.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["index", "loc", "date", "start"] + FEATS + [f"pct_{k}" for k in FEATS])
    for i, (t, l) in enumerate(zip(lib, L)):
        w.writerow([i, t["loc"], t["date"], t["start"]] + [f"{l[k]:.6g}" for k in FEATS] + [""] * len(FEATS))
    for t in TRACES:
        w.writerow([t, "", "", ""] + [f"{T[t][k]:.6g}" for k in FEATS] + [f"{prank(col[k], T[t][k]):.1f}" for k in FEATS])
print(f"wrote {M1}/features.csv ({N} library rows + {len(TRACES)} t rows)")

QS = [10, 25, 50, 75, 90]
lines = []
lines.append("| feature | P10 | P25 | P50 | P75 | P90 | mean |")
lines.append("|---|---|---|---|---|---|---|")
for k in FEATS:
    lines.append(f"| {k} | " + " | ".join(f"{np.percentile(col[k], q, method='linear'):.3f}" for q in QS) + f" | {col[k].mean():.3f} |")
lines.append("")
lines.append("| trace | " + " | ".join(f"{k} (pct)" for k in FEATS) + " |")
lines.append("|---|" + "---|" * len(FEATS))
for t in TRACES:
    lines.append(f"| {t} | " + " | ".join(f"{T[t][k]:.3f} ({prank(col[k], T[t][k]):.0f})" for k in FEATS) + " |")
txt = "\n".join(lines)
print(txt)
open(f"{M1}/features_table.md", "w").write(f"library n={N}; percentile = numpy linear; (pct) = library percentile rank, mid-rank for ties\n\n" + txt + "\n")
json.dump({"t": T, "lib_pct": {k: {str(q): float(np.percentile(col[k], q, method='linear')) for q in QS} for k in FEATS},
           "t_prank": {t: {k: prank(col[k], T[t][k]) for k in FEATS} for t in TRACES}}, open(f"{M1}/features_t.json", "w"), indent=1)
print(f"runtime {time.time()-t0:.1f} s")
