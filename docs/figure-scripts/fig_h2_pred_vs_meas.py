#!/usr/bin/env python3
"""fig_h2_pred_vs_meas.pdf (single column, 3.4 x 3.5 in) -- rev. 4.1 (2026-11-01): residual plot of measured cost against the registered
prediction. x = registered prediction alloc_vm (core-min), y = measured / predicted - 1 (%), grey band +/-2 %, y range -5..+6.5.
Points: every valid run (small marker) and every cell mean (large marker, the +/-2 % decision quantity) of
 - CR on t1..t7 (registered alloc_vmexist, hollow; t1/t2 development cells drawn like the others),
 - v6 on t3..t7, B6 (u 0.70) on t6/t7 and the same-target B6 (u 0.775) on t3/t6 (black edge),
 - the pre-registered planner block: planner on t4/t6/t8 (both points), planner / CR / same-target B4, B5, B6 on t11/t12, prediction = version (a)
   (qsim/r71fin/out/predict.json), measured from rq_metrics.csv groups "R72 ...",
 - the fill-in block (rev. 4.2): planner on t3/t5/t7 (both points), same-target B4 / B6 on t4/t8 (qsim/r73fill/out/predict.json (a); groups "R73 ...").
Annotated: the two cells outside the band (v6 t3, B6 t11) and the planner's eight cells (trace name). Legend: 8 entries, two columns, below the axes.
Colours/markers: figs/scripts/palette.py. Run: cd figs/scripts && nice -n 19 taskset -c 13 python3 fig_h2_pred_vs_meas.py [preview.png]"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import common as C, palette as P

C.set_style()
rows = C.load_rq(); pred = C.load_predictions()
pts = []   # (arm, trace, run, x_pred, y_meas, same_target)
for arm, trace, g in C.DEV_GROUPS:
    for r in C.rows_of(rows, g): pts.append((arm, trace, r["run"], pred[(arm, trace)], C.alloc(r), False))
for trace in ["t3", "t4", "t5", "t6", "t7"]:
    for arm in ["S4a", "S4b"]:
        rr = C.rows_of(rows, C.main_group(trace, arm))
        if not rr: print("WARNING: no rows for", trace, arm)
        for r in rr: pts.append((arm, trace, r["run"], pred[(arm, trace)], C.alloc(r), False))
OTHER = [("v6", "t3", 1104.5, "MAIN t3 v6"), ("v6", "t4", 1387.2, "MAIN t4 v6"), ("v6", "t5", 1451.2, "MAIN t5 v6"),
         ("v6", "t6", 1363.0, "MAIN t6 v6"), ("v6", "t7", 1380.0, "MAIN t7 v6"),
         ("B6", "t6", 1449.0, "MAIN t6 B6 u=0.70"), ("B6", "t7", 1445.0, "MAIN t7 B6 u=0.70")]
for arm, trace, pr_, g in OTHER:
    for r in C.rows_of(rows, g): pts.append((arm, trace, r["run"], pr_, C.alloc(r), False))
for trace, pr_, rr_ in (("t3", 1175.0, [1174, 1184]), ("t6", 1431.0, [1434, 1453])):   # B6 u = 0.775 (same-target knob): r493/r505, r498/r499
    for k, y in enumerate(rr_): pts.append(("B6", trace, f"H{k}", pr_, float(y), True))
PR = json.load(open("/home/user/experiment/qsim/r71fin/out/predict.json"))
R72 = [("S4p2", "t4", PR["s4p"]["t4|2|S4p"]["a"]["alloc_vm"], "R72 t4 S4p2", False), ("S4p05", "t4", PR["s4p"]["t4|05|S4p"]["a"]["alloc_vm"], "R72 t4 S4p05", False),
       ("S4p2", "t6", PR["s4p"]["t6|2|S4p"]["a"]["alloc_vm"], "R72 t6 S4p2", False), ("S4p05", "t6", PR["s4p"]["t6|05|S4p"]["a"]["alloc_vm"], "R72 t6 S4p05", False),
       ("S4p2", "t8", PR["s4p"]["t8|2|S4p"]["a"]["alloc_vm"], "R72 t8 S4p2", False), ("S4p05", "t8", PR["s4p"]["t8|05|S4p"]["a"]["alloc_vm"], "R72 t8 S4p05", False)]
A = {"S4p2": ("S4p", "S4p2", False), "S4b": ("S4b", "S4b", False), "B4c2": ("A:B4_3.75_300", "A:B4 3.75/300", True), "B5c1": ("A:B5_4.0_L2", "A:B5 4.0/L2", True), "B6": ("A:B6_0.775", "A:B6 0.775", True)}
for t in ("t11", "t12"):
    for arm, (k, g, st) in A.items(): R72.append((arm, t, PR["t1112"][t]["arms"][k]["alloc_vm"], f"R72 {t} {g}", st))
PR73 = json.load(open("/home/user/experiment/qsim/r73fill/out/predict.json"))   # rev. 4.2 (2026-11-02): fill-in block, prediction (a)
R72 += [("S4p2", t, PR73[f"{t}|S4p2"]["a"]["alloc_vm"], f"R73 {t} S4p2", False) for t in ("t3", "t5", "t7")]
R72 += [("S4p05", t, PR73[f"{t}|S4p05"]["a"]["alloc_vm"], f"R73 {t} S4p05", False) for t in ("t3", "t5", "t7")]
R72 += [("B4c2", t, PR73[f"{t}|B4A_375_300"]["a"]["alloc_vm"], f"R73 {t} A:B4 3.75/300", True) for t in ("t4", "t8")]
R72 += [("B6", t, PR73[f"{t}|B6c5_h"]["a"]["alloc_vm"], f"R73 {t} A:B6 0.775", True) for t in ("t4", "t8")]
for arm, trace, pr_, g, st in R72:
    rr = C.rows_of(rows, g)
    if not rr: print("WARNING: no rows for", g)
    for r in rr: pts.append((arm, trace, r["run"], pr_, C.alloc(r), st))
print(f"{len(pts)} runs")

fig, ax = plt.subplots(figsize=(3.4, 2.75))   # rev. 4.5 (A3): rendered at 0.88 columnwidth; height chosen to keep the former printed height
xs = [p[3] for p in pts]; lo, hi = min(xs) - 40, max(xs) + 40
ax.axhspan(-2, 2, color="#bbbbbb", alpha=0.35, lw=0, zorder=0); ax.axhline(0, color="#444444", lw=0.7, ls="--", zorder=1)
cells = {}
for p in pts: cells.setdefault((p[0], p[1], p[3], p[5]), []).append(p[4])
for arm, trace, run, x, y, st in pts:
    ax.plot([x], [100 * (y / x - 1)], **P.style(arm, same_target=st, cell=False), alpha=0.8, zorder=3)
res = {}
for (arm, trace, x, st), ys in cells.items():
    e = 100 * (np.mean(ys) / x - 1); res[(arm, trace, st)] = (x, e)
    ax.plot([x], [e], **P.style(arm, same_target=st, cell=True), zorder=4)
# annotations: the two cells outside the band and the planner's eight cells
for (arm, trace, st), (x, e) in sorted(res.items(), key=lambda kv: kv[1][0]):
    if abs(e) > 2 or arm in ("S4p2", "S4p05"):
        lab = trace if arm.startswith("S4p") else f"{ {'v6': 'v6', 'B4c2': 'HPA', 'B5c1': 'Holt-forecast HPA'}.get(arm, 'multi-predictor') } {trace}"
        dy = 8 if e >= 0 else -10
        if arm == "S4p05": dy = -10                                  # 0.5 % cells labelled below, 2 % cells above
        if arm == "S4p2": dy = 8
        ax.annotate(lab, (x, e), textcoords="offset points", xytext=(0, dy), fontsize=6, color="#333333", ha="center", va="bottom" if dy > 0 else "top")
ax.set_xlim(lo, hi); ax.set_ylim(-5, 6.5)   # rev. 4.2: same-target B4 on t8 at +5.7 % (measured / predicted - 1)
ax.set_xlabel("Registered prediction $\\hat{C}$ (core-min)"); ax.set_ylabel("Measured / predicted $-$ 1 (%)"); ax.grid(True, axis="y")
h = [Line2D([], [], **P.style(a, cell=True, ms=5.5), label=P.ARMS[a][0]) for a in ("S4p2", "S4p05", "S4b", "S4a", "v6", "B4c2", "B5c1", "B6")]
ax.legend(handles=h, loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=2, fontsize=6.5, frameon=False, handletextpad=0.4, columnspacing=1.2)
fig.tight_layout(pad=0.3)
C.save(fig, "fig_h2_pred_vs_meas.pdf")
if len(sys.argv) > 1: fig.savefig(sys.argv[1], dpi=160, bbox_inches="tight")
for (arm, trace, st), (x, e) in sorted(res.items(), key=lambda kv: (kv[0][1], kv[0][0])): print(f"{trace} {arm}{' (same-target)' if st else ''} pred={x:.0f} err={e:+.2f}%")
print("cells", len(res), "outside +/-2 %:", [(a, t) for (a, t, s), (x, e) in res.items() if abs(e) > 2])
