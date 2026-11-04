#!/usr/bin/env python3
"""fig_eps_guarantee.pdf (double column, 7.0 in): what epsilon guarantees (spec §4.106, Results "What ε guarantees").
Left: simulated SLO-violation risk per rise10 decile of the prior library under the deployed full-library lambda
(filled markers, lines: S4a, S4b, v6), with the measured hardware risk of t3, t4, t6 and t7 (hollow markers, 3 runs x 60 min)
placed at the trace's decile; dotted verticals mark the trace deciles. Same data and drawing as the retired
fig_m1_risk_vs_burst.pdf (qsim/m1/m1_analysis.py), read here from qsim/m1/analysis.json and m1_common.MEASURED_VIOL.
Right: per rise1 bucket (8 non-empty buckets; empty deciles merged) the held-out risk after conditional calibration,
six-split mean with error bars = +- std over the six splits, for the 0.5 % (S4a) and 2 % (S4b) targets; dashed lines at
epsilon. Data: qsim/r62ab/results.json key "A" (ho_mean, ho_std); bucket rise1 ranges from qsim/r62ab/REPORT.md Task A.
Run: nice -n 19 taskset -c 13 python3 fig_eps_guarantee.py"""
import os, sys, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, "/home/user/experiment/qsim/m1")
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import common as C
from m1_common import MEASURED_VIOL, MEASURED_DEN

C.set_style()
M = json.load(open("/home/user/experiment/qsim/m1/analysis.json"))
D = {int(k): v for k, v in M["deciles"].items()}; tdec = M["t_decile"]
A = json.load(open("/home/user/experiment/qsim/r62ab/results.json"))["A"]
ARMS = ["S4a", "S4b", "v6"]
fig, (ax, bx) = plt.subplots(1, 2, figsize=(7.0, 2.3), gridspec_kw={"width_ratios": [1.1, 1.0]})

# ---- left: rise10 decile curve (full-library lambda) + hardware markers ----
x = np.arange(10)
for a in ARMS:
    lab, c, mk = C.ARMS[a]
    ax.plot(x, [100 * D[d]["risk"][a] for d in range(10)], color=c, marker=mk, ms=3.5, lw=1.0, label=f"{lab.split(' (')[0]} simulated", zorder=3)
OFF = {"S4a": -0.2, "S4b": 0.0, "v6": 0.2}
for t in ("t3", "t4", "t6", "t7"):
    for a in ARMS:
        lab, c, mk = C.ARMS[a]
        ax.plot(tdec[t] + OFF[a], 100 * MEASURED_VIOL[a][t] / MEASURED_DEN, marker=mk, ms=5, mfc="white", mec=c, mew=1.0, ls="none", zorder=4)
ymax = max(max(100 * D[d]["risk"][a] for d in range(10) for a in ARMS),
           max(100 * MEASURED_VIOL[a][t] / MEASURED_DEN for a in ARMS for t in MEASURED_VIOL[a]))
ax.set_ylim(-0.3, ymax * 1.16)
lab_at = collections.defaultdict(list)
for t in ("t3", "t4", "t6", "t7"): lab_at[tdec[t]].append(t)
for d, ts in lab_at.items():
    ax.axvline(d, color="#AAAAAA", lw=0.6, ls=(0, (1, 2)), zorder=1)
    ax.text(d, ymax * 1.15, ", ".join(ts), ha="center", va="top", fontsize=6.5, color="#333333")
ax.set_xticks(x); ax.set_xticklabels([f"D{d+1}\n{D[d]['lo']:.0f}-{D[d]['hi']:.0f}" for d in range(10)], fontsize=6)
ax.set_xlabel("rise10 decile of the prior library (rise10 range, UE)")
ax.set_ylabel("violating minutes (%)")
ax.set_title("(a) full-library $\\lambda$: risk per rise10 decile", pad=3)
h, l = ax.get_legend_handles_labels()
h.append(Line2D([], [], marker="o", ms=5, mfc="white", mec="#333333", mew=1.0, ls="none")); l.append("measured (hollow)")
ax.legend(h, l, loc="upper center", bbox_to_anchor=(0.6, 0.93), fontsize=6, ncol=2)

# ---- right: conditional calibration per rise1 bucket ----
RANGE = {"D1": "4-7", "D2+3": "8", "D4": "9", "D5+6": "10", "D7": "11", "D8": "12", "D9": "13-14", "D10": "15-22"}
ks = sorted({k.split("|")[0] for k in A}, key=lambda n: int(n[1:].split("+")[0]))
assert ks == list(RANGE), ks
xb = np.arange(len(ks))
for tg, arm, dx in ((0.005, "S4a", -0.1), (0.02, "S4b", 0.1)):
    lab, c, mk = C.ARMS[arm]
    ho = np.array([A[f"{k}|{tg}"]["ho_mean"] for k in ks]) * 100
    sd = np.array([A[f"{k}|{tg}"]["ho_std"] for k in ks]) * 100
    bx.errorbar(xb + dx, ho, yerr=sd, fmt=mk, color=c, ms=3.5, capsize=2, lw=0.8, label=f"target {tg*100:g} % (held-out, $\\pm$ std)")
    bx.axhline(tg * 100, ls="--", color=c, lw=0.7)
    bx.text(-0.45, tg * 100 + 0.03, f"$\\varepsilon$ = {tg*100:g} %", fontsize=6, color=c, va="bottom", ha="left")
bx.set_xticks(xb); bx.set_xticklabels([f"{k}\n{RANGE[k]}" for k in ks], fontsize=6)
bx.set_xlabel("rise1 bucket (rise1 range, UE/min)")
bx.set_ylabel("held-out violating minutes (%)")
bx.set_ylim(0, None)
bx.set_title("(b) bucket-calibrated $\\lambda$: held-out risk per rise1 bucket", pad=3)
bx.legend(loc="center left", fontsize=6)
for a_ in (ax, bx):
    for s in ("top", "right"): a_.spines[s].set_visible(False)
    a_.grid(axis="y", lw=0.4, alpha=0.3)
fig.tight_layout(pad=0.4, w_pad=1.2)
C.save(fig, "fig_eps_guarantee.pdf")
if len(sys.argv) > 1: fig.savefig(sys.argv[1], dpi=160)
