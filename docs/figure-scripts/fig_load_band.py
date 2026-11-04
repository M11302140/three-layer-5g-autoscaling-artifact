#!/usr/bin/env python3
"""fig_load_band.pdf (single column, 3.4 x 4.0 in) -- rev. 4 (2026-10-31), Simulation IV-E "Load-band analysis".
Two stacked panels over the mp deciles of the prior library (thresholds from qsim/r67band/out/tables.json, the m1 rule):
 (a) realized risk (% of violating minutes) per decile, 2 % group: CR (S4b 1.83/2.00), planner (S4' 1.5/1.92), A-PL (2.00/2.83),
     B4c2 3.75/300, B5c1 4.0/L2, B6 0.775 and v6 -- per-trace rows of qsim/r67band/out/*.json and qsim/r68unif/out/{S4p_2,APL_2}.json
     (v8sim11 per-slot, R38 off, own initial fleet); B1 (all zero) omitted;
 (b) cost difference per decile, % of the baseline: CR minus B4 / B5 / B6 (solid) and planner minus B4 / B5 / B6 (dashed).
Test traces are marked at their decile (t8 D1, t3 D2, t1 D3, t11 D5, t2 D7, t6/t7 D8, t12 D9, t4/t5 D10; tables.json 'tb' plus
t11/t12 from their mp 0.608 / 0.741). Nothing is typed in: every value is recomputed from the per-trace rows.
Run: cd figs/scripts && nice -n 19 taskset -c 13 python3 fig_load_band.py [preview.png]"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import common as C

Q = "/home/user/experiment/qsim"
LIB = json.load(open(f"{Q}/prior_traces.json"))
mp = np.array([np.mean(t["ue"][:60]) / max(t["ue"][:60]) for t in LIB])
T = json.load(open(f"{Q}/r67band/out/tables.json"))["mp"]; thr = T["thr"]
dec = np.array([int(np.searchsorted(thr, v, side="left")) for v in mp])   # 0..9 ; m1 rule: first threshold >= value
assert len(set(dec)) == 10 and T["merge"] == {str(i): i for i in range(1, 11)}
def rows(fn): return json.load(open(fn))["rows"]
SRC = {"S4b": f"{Q}/r67band/out/S4b.json", "S4p2": f"{Q}/r68unif/out/S4p_2.json", "APL": f"{Q}/r68unif/out/APL_2.json",
       "B4c2": f"{Q}/r67band/out/B4_3.75_300.json", "B5c1": f"{Q}/r67band/out/B5_4.0_L2.json", "B6": f"{Q}/r67band/out/B6_0.775.json", "v6": f"{Q}/r67band/out/v6.json"}
R = {a: rows(f) for a, f in SRC.items()}
for a, r in R.items(): assert len(r) == len(LIB), a
risk = {a: np.array([(60 - x["slo"]) / 60 * 100 for x in r]) for a, r in R.items()}
cost = {a: np.array([x["alloc_vm"] for x in r]) for a, r in R.items()}
def per_dec(v): return np.array([v[dec == d].mean() for d in range(10)])
tb = dict(T["tb"]); tb["t11"] = int(np.searchsorted(thr, 0.608, side="left")) + 1; tb["t12"] = int(np.searchsorted(thr, 0.741, side="left")) + 1

C.set_style()
fig, (ax, bx) = plt.subplots(2, 1, figsize=(3.4, 4.0), sharex=True, gridspec_kw={"hspace": 0.12})
x = np.arange(10)
import palette as P
for a in ("B4c2", "B5c1", "B6", "v6", "APL", "S4b", "S4p2"):
    lab, col, mk = C.ARMS[a]; hollow = P.ARMS[a][3]; lab = {"B4c2": "HPA 3.75/300", "B5c1": "Holt-forecast HPA 4.0/L2", "B6": "multi-predictor 0.775"}.get(a, lab)   # rev. 4.6: same-target knobs named (the legend had said u = 0.70)
    ax.plot(x, per_dec(risk[a]), color=col, marker=mk, ms=3.8, mfc="white" if hollow else col, mew=0.9, lw=1.0, ls="-" if a != "APL" else (0, (3, 1.5)), label=lab, zorder=3 if a in ("S4b", "S4p2") else 2)
ax.set_ylabel("realized risk (% of minutes)"); ax.grid(True, axis="y")
ax.legend(fontsize=5.8, ncol=2, loc="upper right", bbox_to_anchor=(1.0, 0.93), handlelength=1.6)
ax.set_title("(a) ε = 2 % group, equal library-average risk target", pad=3, fontsize=7.5)
for s_arm, ls_ in (("S4b", "-"), ("S4p2", (0, (3, 1.5)))):
    for b in ("B4c2", "B5c1", "B6"):
        lab, col, mk = C.ARMS[b]
        d = np.array([100 * (cost[s_arm][dec == k].mean() - cost[b][dec == k].mean()) / cost[b][dec == k].mean() for k in range(10)])
        bx.plot(x, d, color=col, marker=C.ARMS[s_arm][2], ms=3.5, mfc="white" if P.ARMS[s_arm][3] else col, mew=0.9, lw=1.0, ls=ls_, zorder=3)
bx.axhline(0, color="#444444", lw=0.6); bx.axhspan(-2, 2, color="#bbbbbb", alpha=0.25, lw=0)
bx.set_ylabel("Δcost vs. baseline (%)"); bx.grid(True, axis="y")
bx.set_xticks(x); bx.set_xticklabels([f"D{d+1}" for d in range(10)], fontsize=6.5)
bx.set_xlabel("mean-to-peak decile of the prior library (D1 = burstiest)")
h = [Line2D([], [], color=C.ARMS[b][1], lw=1.0, label=f"vs. { {'B4c2': 'HPA', 'B5c1': 'Holt-forecast HPA', 'B6': 'multi-predictor'}[b] }") for b in ("B4c2", "B5c1", "B6")]
h += [Line2D([], [], color="#333333", marker="o", ms=3.5, mfc="white", lw=1.0, ls="-", label="CR, ε = 2 %"), Line2D([], [], color="#333333", marker="o", ms=3.5, lw=1.0, ls=(0, (3, 1.5)), label="planner, ε = 2 %")]
bx.legend(handles=h, fontsize=5.8, ncol=2, loc="upper right", handlelength=1.8)
bx.set_title("(b) cost difference per decile (band: ±2 %)", pad=3, fontsize=7.5)
# trace markers on top panel
lab_at = {}
for t, d in tb.items(): lab_at.setdefault(d - 1, []).append(t)
ytop = ax.get_ylim()[1]
for d, ts in sorted(lab_at.items()):
    ax.axvline(d, color="#AAAAAA", lw=0.5, ls=(0, (1, 2)), zorder=1); bx.axvline(d, color="#AAAAAA", lw=0.5, ls=(0, (1, 2)), zorder=1)
    bx.text(d, bx.get_ylim()[0] + 0.12, ",".join(ts), ha="center", va="bottom", fontsize=5.5, color="#333333")
ax.set_ylim(top=ytop * 1.08); bx.set_ylim(bottom=bx.get_ylim()[0] - 0.5)
fig.tight_layout(pad=0.3)
C.save(fig, "fig_load_band.pdf")
if len(sys.argv) > 1: fig.savefig(sys.argv[1], dpi=160, bbox_inches="tight")
# print the plotted values for numbers-rev. 4 / FIGS.md
for a in SRC: print(a, "risk per decile", np.round(per_dec(risk[a]), 2).tolist(), "library", round(risk[a].mean(), 3), "cost", round(cost[a].mean(), 1))
for s_arm in ("S4b", "S4p2"):
    for b in ("B4c2", "B5c1", "B6"):
        print(s_arm, "vs", b, [round(100 * (cost[s_arm][dec == k].mean() - cost[b][dec == k].mean()) / cost[b][dec == k].mean(), 2) for k in range(10)], "library %+.2f" % (100 * (cost[s_arm].mean() - cost[b].mean()) / cost[b].mean()))
print("trace deciles", tb)
