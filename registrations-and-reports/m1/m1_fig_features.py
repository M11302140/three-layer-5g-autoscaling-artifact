#!/usr/bin/env python3
"""m1_fig_features.py — figs/fig_m1_features.pdf (double column, 7.0 in, serif): small-multiple histograms of
the library distribution of mp, f36, rise10, rise1, lag-1 and stationarity with vertical marks for t1..t7.
Style: docs/paper/figs/scripts/common.py (8 pt serif, TrueType-embedded).  Values read from m1/features.csv."""
import csv, sys, time
import numpy as np
sys.path.insert(0, "/home/user/experiment/qsim/m1"); sys.path.insert(0, "/home/user/docs/paper/figs/scripts")
from m1_common import *
import common
import matplotlib.pyplot as plt

t0 = time.time()
common.set_style()
rows = list(csv.DictReader(open(f"{M1}/features.csv")))
lib = [r for r in rows if r["loc"] != ""]; tr = {r["index"]: r for r in rows if r["loc"] == ""}
PANELS = ["mp", "f36", "rise10", "rise1", "lag1", "stat"]
TITLE = {"mp": "mp = mean/max", "f36": "f36 = frac. minutes UE $\\geq$ 36", "rise10": "rise10 (UE)",
         "rise1": "rise1 (UE)", "lag1": "lag-1 autocorrelation", "stat": "stationarity (UE)"}
def bins(k, v):
    if k == "f36": return (np.arange(0, round(v.max() * 60) + 2) - 0.5) / 60
    if k in ("rise10", "rise1", "minUE"): return np.arange(v.min(), v.max() + 2) - 0.5
    return np.linspace(v.min(), v.max(), 31)

fig, axes = plt.subplots(2, 3, figsize=(7.0, 3.5))
DEV, TEST = ("t1", "t2"), ("t3", "t4", "t5", "t6", "t7")
for ax, k in zip(axes.flat, PANELS):
    v = np.array([float(r[k]) for r in lib])
    ax.hist(v, bins=bins(k, v), color="#C8C8C8", edgecolor="white", linewidth=0.3)
    ax.set_xlabel(TITLE[k]); ax.grid(False)
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    y0, y1 = ax.get_ylim(); ax.set_ylim(0, y1 * 1.38)
    xs, xe = ax.get_xlim(); span = xe - xs
    marks = sorted([(float(tr[t][k]), t) for t in DEV + TEST])
    prev_x, level = None, -1
    for x, t in marks:
        dev = t in DEV
        ax.axvline(x, color="#888888" if dev else "#222222", lw=0.7, ls=(0, (2, 1.5)) if dev else "-", zorder=3)
        level = (level + 1) % 3 if (prev_x is not None and x - prev_x < 0.09 * span) else 0
        prev_x = x
        ax.text(x, y1 * (1.34 - 0.11 * level), t, ha="center", va="top", fontsize=6.5,
                color="#555555" if dev else "#000000", bbox=dict(boxstyle="square,pad=0.1", fc="white", ec="none", alpha=0.85), zorder=4)
axes[0, 0].set_ylabel("library windows (n = %d)" % len(lib)); axes[1, 0].set_ylabel("library windows (n = %d)" % len(lib))
from matplotlib.lines import Line2D
fig.legend(handles=[Line2D([], [], color="#888888", lw=0.7, ls=(0, (2, 1.5)), label="development traces t1, t2"),
                    Line2D([], [], color="#222222", lw=0.7, label="test traces t3-t7")],
           loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.01), frameon=False)
fig.tight_layout(rect=(0, 0.05, 1, 1), w_pad=1.2, h_pad=0.8)
common.save(fig, "fig_m1_features.pdf")
if len(sys.argv) > 1: fig.savefig(sys.argv[1], dpi=160)
print(f"runtime {time.time()-t0:.1f} s")
