#!/usr/bin/env python3
"""mad_features.py — spec §4.99 B1 item 6 / task step 4: seven features (m1_common.features) for Melbourne (prior_traces.json),
Madrid 1:1 kept (madrid_lib.json), Madrid compressed kept (madrid_compressed_lib.json); P10/P50/P90 (numpy linear) per library;
two-sample KS distance (scipy.stats.ks_2samp statistic, asymptotic p) Madrid-1:1 vs Melbourne, Madrid-compressed vs Madrid-1:1
(and compressed vs Melbourne, reference).  Figure figs/fig_madrid_features.pdf: 2x4 small multiples, density histograms of the three
libraries overlaid, serif 8 pt (figs/scripts/common.py), 7.0 in double column.  Outputs: features_<lib>.csv, features_table.md, features_ks.json."""
import csv, json, os, sys, time
import numpy as np
from scipy.stats import ks_2samp
sys.path.insert(0, "/home/user/experiment/qsim/m1"); sys.path.insert(0, "/home/user/docs/paper/figs/scripts")
from m1_common import features, FEATS, FEAT_LABEL
import common, matplotlib.pyplot as plt
D = os.path.dirname(os.path.abspath(__file__)); t0 = time.time()
LIBS = {"Melbourne": "/home/user/experiment/qsim/prior_traces.json", "Madrid 1:1": f"{D}/madrid_lib.json", "Madrid compressed": f"{D}/madrid_compressed_lib.json"}
F = {}
for name, fn in LIBS.items():
    lib = json.load(open(fn)); rows = [features(e["ue"][:60]) for e in lib]
    F[name] = {k: np.array([r[k] for r in rows]) for k in FEATS}
    with open(f"{D}/features_{name.replace(' ', '_').replace(':', '')}.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["index", "loc/bs", "date", "start"] + FEATS)
        for i, (e, r) in enumerate(zip(lib, rows)): w.writerow([i, e.get("bs", e.get("loc")), e["date"], e.get("start_epoch", e.get("start"))] + [f"{r[k]:.6f}" for k in FEATS])
    print(f"{name}: n={len(lib)}", flush=True)
L = ["| feature | " + " | ".join(f"{n} (n={len(F[n]['mp'])}) P10 / P50 / P90" for n in LIBS) + " | KS 1:1 vs Melb (p) | KS compr vs 1:1 (p) | KS compr vs Melb (p) |", "|---|" + "---|" * (len(LIBS) + 3)]
KS = {}
for k in FEATS:
    cells = []
    for n in LIBS:
        v = F[n][k]; p = np.percentile(v, [10, 50, 90], method="linear"); cells.append(f"{p[0]:.3f} / {p[1]:.3f} / {p[2]:.3f}")
    ks = {}
    for a, b, key in (("Madrid 1:1", "Melbourne", "1to1_vs_melb"), ("Madrid compressed", "Madrid 1:1", "compr_vs_1to1"), ("Madrid compressed", "Melbourne", "compr_vs_melb")):
        r = ks_2samp(F[a][k], F[b][k]); ks[key] = {"D": float(r.statistic), "p": float(r.pvalue)}; cells.append(f"{r.statistic:.3f} ({r.pvalue:.2g})")
    KS[k] = ks; L.append(f"| {k} | " + " | ".join(cells) + " |")
json.dump({"ks": KS, "percentiles": {n: {k: [float(x) for x in np.percentile(F[n][k], [10, 50, 90], method='linear')] for k in FEATS} for n in LIBS},
           "means": {n: {k: float(F[n][k].mean()) for k in FEATS} for n in LIBS}, "n": {n: int(len(F[n]["mp"])) for n in LIBS}}, open(f"{D}/features_ks.json", "w"), indent=1)
open(f"{D}/features_table.md", "w").write("\n".join(L) + "\n"); print("\n".join(L))
# ---- figure
common.set_style()
COL = {"Melbourne": "#555555", "Madrid 1:1": "#0072B2", "Madrid compressed": "#E69F00"}   # common.py palette (Okabe-Ito); validated with dataviz validator
TITLE = {"mp": "mp = mean/max", "f36": "f36 = frac. minutes UE $\\geq$ 36", "minUE": "min UE", "rise10": "rise10 (UE)", "rise1": "rise1 (UE)", "lag1": "lag-1 autocorrelation", "stat": "stationarity (UE)"}
def bins(k):
    allv = np.concatenate([F[n][k] for n in LIBS])
    if k == "f36": return (np.arange(0, round(allv.max() * 60) + 2) - 0.5) / 60
    if k in ("rise10", "rise1", "minUE"): return np.arange(allv.min(), allv.max() + 2) - 0.5
    return np.linspace(allv.min(), allv.max(), 31)
fig, axes = plt.subplots(2, 4, figsize=(7.0, 3.4))
for ax, k in zip(axes.flat, FEATS):
    b = bins(k)
    for n in LIBS:
        ax.hist(F[n][k], bins=b, density=True, histtype="stepfilled", color=COL[n], alpha=0.28, edgecolor="none")
        ax.hist(F[n][k], bins=b, density=True, histtype="step", color=COL[n], linewidth=0.9)
    ax.set_xlabel(TITLE[k]); ax.grid(False); ax.set_yticks([])
    for s in ("top", "right", "left"): ax.spines[s].set_visible(False)
axes[1, 3].axis("off")
from matplotlib.patches import Patch
axes[1, 3].legend(handles=[Patch(facecolor=COL[n], edgecolor=COL[n], alpha=0.6, label=f"{n} (n = {len(F[n]['mp'])})") for n in LIBS], loc="center", frameon=False, fontsize=7.5)
axes[0, 0].set_ylabel("density"); axes[1, 0].set_ylabel("density")
fig.tight_layout(w_pad=0.8, h_pad=0.8)
common.save(fig, "fig_madrid_features.pdf"); fig.savefig(f"{D}/fig_madrid_features_preview.png", dpi=150)
print(f"runtime {time.time()-t0:.1f} s")
