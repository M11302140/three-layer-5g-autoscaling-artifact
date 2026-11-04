#!/usr/bin/env python3
"""fig_cost_viol_t3t8.pdf (double column, 7.0 x 2.35 in) -- 2026-10-24 R68 (spec §4.116, section 2): cost (alloc_vm) vs violating
minutes, two panels: t3 (surge, main experiment, rq_metrics.csv groups) and t8 (independent stress trace, G block, provisional).
Drawing identical to fig_cost_viol_t3t6.py (one large marker per arm at the mean over valid runs, min..max bars, label
"ARM <mean alloc_vm> / <mean violating minutes>", voided runs as hollow black circles).

t8 runs are not in rq_metrics.csv; their per-run alloc_vm and SLO are computed here with the per-run functions of
/home/user/experiment/paper_out_new/rq_metrics.py (daemon(run) -> eupf pod count per minute; alloc_vm_of(run, eupf) -> alloc_vm from
the host sampler), executed from the module text up to `def metrics` (the module has no __main__ guard). SLO per run = number of
minutes with e2e_pct <= 0.1 and lat_p99_us <= 1000 in trace_v7_<run>.csv (rq_metrics.py rule), checked against g_ledger.tsv.
t8 valid runs (g_ledger.tsv / rr_ledger.tsv, flag ok): S4a r471 r478; S4b r476 r500; v6 (HHRO) r475 r479; B6 (B6c4_slo) r474 r504.
Voided: r480 r481 (S4b, ng-dead) and r477 (B6, drain-residue rule); drawn hollow. No B1 run on t8. r470/r472/r473 have no scored data.
Run: cd figs/scripts && nice -n 19 taskset -c 13 python3 fig_cost_viol_t3t8.py [preview.png]
"""
import os, sys, csv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.text import Text
import common as C

RQ = "/home/user/experiment/paper_out_new/rq_metrics.py"
src = open(RQ, encoding="utf-8").read(); ns = {}
exec(compile(src[:src.index("def metrics(")], RQ, "exec"), ns)
daemon, alloc_vm_of = ns["daemon"], ns["alloc_vm_of"]
def slo_of(run):
    n = 0
    for r in csv.DictReader(open(f"{C.P2}/trace_v7_{run}.csv")):
        loss = float(r["e2e_pct"]) if r["e2e_pct"] not in ("", "?") else 1e9
        p99 = float(r["lat_p99_us"]) if r["lat_p99_us"] not in ("", "?") else 1e9
        n += (loss <= 0.1 and p99 <= 1000)
    return n
LEDGER = {}
for line in list(open(f"{C.P2}/g_ledger.tsv")) + list(open(f"{C.P2}/rr_ledger.tsv")):
    f = line.rstrip("\n").split("\t")
    if len(f) >= 6 and f[0].startswith("r"): LEDGER[f[0]] = f
T8 = {"S4a": ["r471", "r478"], "S4b": ["r476", "r500"], "v6": ["r475", "r479"], "B6": ["r474", "r504"]}   # 2026-10-25 spec §4.121
T8_VOID = {"r480": "S4b", "r481": "S4b", "r477": "B6"}   # r477 voided by the drain-residue rule (replaced by r504)
t8rows = []
for arm, runs in list(T8.items()) + [("void", list(T8_VOID))]:
    for run in runs:
        eupf, _ = daemon(run); av = alloc_vm_of(run, eupf); slo = slo_of(run)
        led = LEDGER.get(run); led_slo = int(led[3].split("/")[0]) if led and "/" in led[3] else None
        if led_slo is not None and led_slo != slo: print(f"WARNING {run}: SLO from CSV {slo} != ledger {led_slo}")
        t8rows.append(dict(arm=arm if arm != "void" else T8_VOID[run], run=run, slo=slo, alloc_vm=av, void=(arm == "void")))
        print(f"t8 {run} {arm}: SLO {slo}/60 alloc_vm {av} (ledger {led[3] if led else '?'}, burned {led[4] if led else '?'}, flag {led[5] if led else '?'})")
open(os.path.join(C.FIGS, "fig_cost_viol_t3t8_t8runs.csv"), "w").write("run,arm,slo,alloc_vm,void\n" + "\n".join(f"{r['run']},{r['arm']},{r['slo']},{r['alloc_vm']},{int(r['void'])}" for r in t8rows) + "\n")

C.set_style()
rows = C.load_rq()
ALL_PANELS = [("t3", "t3 (surge)"), ("t8", "t8 (independent stress)")]
# rev. 4.5 (A2): CV_PANELS=t8 renders the paper's single-column figure (3.5 x 2.4 in, fonts >= 7 pt) as fig_cost_viol_t8.pdf;
# CV_PANELS=t3 renders the t3 panel for the TR (fig_cost_viol_t3.pdf); unset = the former two-panel fig_cost_viol_t3t8.pdf.
SEL = os.environ.get("CV_PANELS", "t3,t8").split(",")
PANELS = [pn for pn in ALL_PANELS if pn[0] in SEL]
SINGLE = len(PANELS) == 1
FS = 7.0 if SINGLE else 6.3
OUTNAME = "fig_cost_viol_t3t8.pdf" if not SINGLE else f"fig_cost_viol_{PANELS[0][0]}.pdf"
XMAX = 9.5; XCLAMP = 9.0
if os.environ.get("CV_PANELS", "") == "t8": XMAX = 10.6   # rev. 4.5 single t8 panel: every label on a leader slot column at x = 5.9 (crossing-free search)
if os.environ.get("CV_PANELS", "") == "t3": XMAX = 11.8   # rev. 4.5 single t3 panel (TR): room for the 7 pt labels at x = 7.2
T8_ALL_SLOTS = [(5.9, y) for y in (1205, 1167, 1129, 1091, 1053, 1015, 977, 939)]
SHORT = {"S4a": "CR 0.5%", "S4b": "CR 2%", "S4p2": "planner 2%", "S4p05": "planner 0.5%", "v6": "v6", "B4c2": "HPA", "B5c1": "Holt-forecast HPA", "B6": "multi-predictor", "B1": "B1"}
fig, axes = plt.subplots(1, len(PANELS), figsize=((3.5, 2.4) if SINGLE else (7.0, 2.35)), sharey=True, squeeze=False)
fig.canvas.draw(); rend = fig.canvas.get_renderer()
CANDS = [(8, 5), (8, -8), (6, 9), (6, -12), (-8, 5), (-8, -8), (10, 0), (-10, 0), (0, 10), (0, -11)]
CANDS += [(dx, dy) for dx in (18, 26, 34, 44, 56, 70, 86, 104, 124, 146) for dy in (0, 8, -10, 18, -20, 28, -30)]
CANDS += [(dx, dy) for dx in (-18, -26) for dy in (0, 10, -10, 20, -20)] + [(0, 18), (0, -20), (0, 28), (0, -30)]
LEADER_FROM = 14
# rev. 4.1 item 4: on the t3 panel every label gets a leader line to a staggered position in the empty upper-right area
# (x 5.5..9, y 1300..1480), so the cluster at 2-6 min / 1130-1240 core-min stays readable and the planner's two future points
# (rq groups "R72 t3 S4p2" / "R72 t3 S4p05", drawn automatically once present) have room.
T3_SLOTS = [(7.2, 1510), (7.2, 1470), (7.2, 1430), (7.2, 1390), (7.2, 1350), (7.2, 1310), (7.2, 1270), (7.2, 1230), (7.2, 1190)]   # rev. 4.2: one column at x = 7.2 (right of the voided-run markers), 40 core-min apart (nine labels with the planner on t3)
# rev. 4.4 (item A6): the t3 labels are split into a left column (points with x < 3, slots in the empty area above the 2-min cluster)
# and the right column; within each column the slot order is chosen by exhaustive search so that no two leader lines cross and no
# leader passes within 0.25 label-heights of another cell marker; ties by total leader length.
T3_LEFT_SLOTS = [(0.25, 1355), (0.25, 1315)]
def t3_assign(pts, columns=None):
    """pts: list of (key, mx, my). Returns {key: (tx, ty)} with crossing-free leaders per column.
    columns: optional [(name, predicate(mx), slots)]; default = t3 left/right split."""
    import itertools
    SX, SY = 9.0, 500.0   # normalisation of the data units for the geometry tests
    def seg_cross(a, b, c, d):
        def o(p, q, r): return (q[0]-p[0])*(r[1]-p[1]) - (q[1]-p[1])*(r[0]-p[0])
        return (o(a, b, c) * o(a, b, d) < 0) and (o(c, d, a) * o(c, d, b) < 0)
    def seg_pt(a, b, p):
        ax_, ay = a[0]/SX, a[1]/SY; bx, by = b[0]/SX, b[1]/SY; px, py = p[0]/SX, p[1]/SY
        dx, dy = bx-ax_, by-ay; t = max(0.0, min(1.0, ((px-ax_)*dx + (py-ay)*dy) / (dx*dx+dy*dy+1e-12)))
        return ((ax_+t*dx-px)**2 + (ay+t*dy-py)**2) ** 0.5
    out = {}
    cols = columns or [("L", lambda mx: mx < 3, T3_LEFT_SLOTS), ("R", lambda mx: mx >= 3, T3_SLOTS)]
    for col, pred, slots in cols:
        grp = [q for q in pts if pred(q[1])]
        if not grp: continue
        best = None
        for perm in itertools.permutations(range(len(slots)), len(grp)):
            segs = [((q[1], q[2]), slots[j]) for q, j in zip(grp, perm)]
            cross = sum(seg_cross(*segs[i], *segs[k]) for i in range(len(segs)) for k in range(i+1, len(segs)))
            near = sum(1 for i, (a, b) in enumerate(segs) for q in pts if q is not grp[i] and seg_pt(a, b, (q[1], q[2])) < 0.02)
            length = sum(((a[0]-b[0])/SX)**2 + ((a[1]-b[1])/SY)**2 for a, b in segs)
            key = (cross, near, length)
            if best is None or key < best[0]: best = (key, perm)
        for q, j in zip(grp, best[1]): out[q[0]] = slots[j]
        print("t3 labels", col, "crossings/near/len", best[0])
    return out
T8_SLOTS = {"B4 3.75/300": (6.6, 928), "B6 0.775": (6.6, 985)}   # rev. 4.2: same-target labels with leaders into the empty lower-right area of the t8 panel   # one column, 45 core-min apart
def overlaps(b, boxes): return any(b.overlaps(o) for o in boxes)
EXTRA_T8 = [("B4c2", "R73 t8 A:B4 3.75/300", "B4 3.75/300"), ("B6", "R73 t8 A:B6 0.775", "B6 0.775")]   # rev. 4.2: same-target knobs on t8 (fill-in block), black-edged markers
def arm_runs(trace, arm, group=None):
    if group: return [(C.viol(r), C.alloc(r), r["run"]) for r in C.rows_of(rows, group)]
    if arm in ("S4p2", "S4p05"):   # rev. 4: planner block cells from rq_metrics.csv (groups "R72 t8 ..." and, since rev. 4.2, "R73 t3 ...")
        return [(C.viol(r), C.alloc(r), r["run"]) for r in C.rows_of(rows, f"R72 {trace} {arm}") + C.rows_of(rows, f"R73 {trace} {arm}")]
    if trace == "t3":
        return [(C.viol(r), C.alloc(r), r["run"]) for r in C.rows_of(rows, C.main_group(trace, arm))]
    return [(60 - r["slo"], float(r["alloc_vm"]), r["run"]) for r in t8rows if r["arm"] == arm and not r["void"]]
def void_runs(trace):
    if trace == "t3":
        out = []
        for r in rows:
            g = r["group"]
            if g.startswith("MAIN t3 ") and ("VOID" in g or "replaced by" in g) and r["slo"] not in ("", "?"): out.append((C.viol(r), C.alloc(r), r["run"]))
        return out
    return [(60 - r["slo"], float(r["alloc_vm"]), r["run"]) for r in t8rows if r["void"]]
PRESENT = set()
for ax, (trace, title) in zip(axes.flat, PANELS):
    ax.set_title(title, pad=3); ax.grid(True); ax.set_xlim(-0.5, XMAX); ax.set_xlabel("Violating minutes (of 60)")
    placed = []; means = []; bars = []; extra_pts = []
    specs = [(arm, None, SHORT[arm], False) for arm in C.ARM_ORDER] + ([(a, g, lab, True) for a, g, lab in EXTRA_T8] if trace == "t8" else [])
    for arm, group, short, st in specs:
        label, col, mk = C.ARMS[arm]; rr = arm_runs(trace, arm, group)
        if not rr: print("note: no rows for", trace, arm, group); continue
        x = np.array([v for v, _, _ in rr], float); y = np.array([a for _, a, _ in rr], float); mx, my = x.mean(), y.mean()
        if len(rr) > 1:
            ax.errorbar([mx], [my], xerr=[[mx - x.min()], [x.max() - mx]], yerr=[[my - y.min()], [y.max() - my]], fmt="none", ecolor=col, elinewidth=0.8, capsize=2, capthick=0.8, alpha=0.9, zorder=3)
            bars += [(x.min(), my, x.max(), my), (mx, y.min(), mx, y.max())]
        import palette as P
        ax.plot([mx], [my], **P.style(arm, same_target=st, cell=True, ms=8), zorder=5)
        means.append((arm, mx, my, col, short)); PRESENT.add(arm)
        print(trace, arm, [r for _, _, r in rr], "mean viol=%.2f alloc=%.1f  x[%g,%g] y[%g,%g]" % (mx, my, x.min(), x.max(), y.min(), y.max()))
    for v, a, run in void_runs(trace):
        vv = min(v, XCLAMP)
        ax.scatter([vv], [a], s=26, facecolors="none", edgecolors="k", marker="o", linewidths=0.7, zorder=4); extra_pts.append((vv, a))
        if v > XCLAMP: ax.annotate(f"{run} void:\n{v} min (off-scale)", (vv, a), textcoords="offset points", xytext=(-5, -5), fontsize=FS, color="k", ha="right", va="top")
        print(trace, "void/replaced", run, "viol", v, "alloc", a)
    fig.canvas.draw()
    for arm, mx, my, col, _s in means:
        px, py = ax.transData.transform((mx, my)); placed.append(plt.matplotlib.transforms.Bbox([[px - 6, py - 6], [px + 6, py + 6]]))
    for ex, ey in extra_pts:
        px, py = ax.transData.transform((ex, ey)); placed.append(plt.matplotlib.transforms.Bbox([[px - 5, py - 5], [px + 5, py + 5]]))
    for x0, y0, x1, y1 in bars:
        (px0, py0), (px1, py1) = ax.transData.transform([(x0, y0), (x1, y1)])
        placed.append(plt.matplotlib.transforms.Bbox([[min(px0, px1) - 1.5, min(py0, py1) - 1.5], [max(px0, px1) + 1.5, max(py0, py1) + 1.5]]))
    t3map = t3_assign([(arm, mx, my) for arm, mx, my, _c, _s in means if arm != "B1"]) if trace == "t3" else {}
    if SINGLE and trace == "t8": t3map = t3_assign([(sh, mx, my) for arm, mx, my, _c, sh in means], [("R", lambda mx: True, T8_ALL_SLOTS)])   # keyed by the short label (B6 and B6 0.775 share the arm key)
    for k_, (arm, mx, my, col, short) in enumerate(sorted(means, key=lambda t: -t[2])):
        txt = f"{short} {my:.0f} / {mx:.1f}"
        if SINGLE and trace == "t8": txt = f"{ {'B4 3.75/300': 'HPA*', 'B6 0.775': 'multi-pred.*'}.get(short, short) } {my:.0f} / {mx:.1f}"
        if (trace == "t3" and arm != "B1") or (trace == "t8" and (short in T8_SLOTS or SINGLE)):
            tx, ty = t3map[arm] if trace == "t3" else (t3map[short] if SINGLE else T8_SLOTS[short])
            ax.annotate(txt, (mx, my), xytext=(tx, ty), textcoords="data", fontsize=FS, color=col, ha="left", va="center", zorder=6,
                        arrowprops=dict(arrowstyle="-", color=col, lw=0.4, alpha=0.7, shrinkA=0, shrinkB=4)); continue
        for dx, dy in CANDS:
            ha = "left" if dx > 0 else ("right" if dx < 0 else "center"); va = "bottom" if dy > 0 else ("top" if dy < 0 else "center")
            far = max(abs(dx), abs(dy)) > LEADER_FROM
            a = ax.annotate(txt, (mx, my), textcoords="offset points", xytext=(dx, dy), fontsize=FS, color=col, ha=ha, va=va, zorder=6,
                            arrowprops=dict(arrowstyle="-", color=col, lw=0.4, alpha=0.7, shrinkA=0, shrinkB=4) if far else None)
            a.update_positions(rend); b = Text.get_window_extent(a, rend).expanded(1.12, 1.35); axb = ax.get_window_extent(rend)
            if not overlaps(b, placed) and axb.contains(b.x0, b.y0) and axb.contains(b.x1, b.y1): placed.append(b); break
            a.remove()
        else:
            a = ax.annotate(txt, (mx, my), textcoords="offset points", xytext=CANDS[0], fontsize=FS, color=col, ha="left", va="bottom", zorder=6)
            a.update_positions(rend); placed.append(Text.get_window_extent(a, rend)); print("NOTE: label fallback (overlap) for", trace, arm)
ally = [a for tr, _t in PANELS for arm in C.ARM_ORDER for _, a, _ in arm_runs(tr, arm)] + [a for tr, _t in PANELS for _, a, _ in void_runs(tr)]
axes[0, 0].set_ylim(min(ally) - 60, (max(ally) + 90 if SINGLE and PANELS[0][0] == "t8" else 1525))
for ax in axes[:, 0]: ax.set_ylabel("Cost $C$ (core-min)")
import palette as P
h = [Line2D([], [], **P.style(a, cell=True, ms=6), label=C.ARMS[a][0]) for a in C.ARM_ORDER if (not SINGLE or a in PRESENT)]
h += [Line2D([], [], **P.style("B6", same_target=True, cell=True, ms=6), label=("same-target knob (*)" if SINGLE and PANELS[0][0] == "t8" else "same-target knob (t8: B4 3.75/300, B6 0.775)" if not SINGLE else "same-target knob"))]
h += [Line2D([], [], color="#777777", lw=0.8, marker="|", ms=4, label=("bars: min–max of runs" if SINGLE else "bars: min–max of the valid runs")), Line2D([], [], marker="o", mfc="none", mec="k", ls="", ms=5, label="voided / replaced run")]
if SINGLE: axes[0, 0].legend(handles=h, loc="lower center", bbox_to_anchor=(0.5, 0.0), bbox_transform=fig.transFigure, ncol=3, fontsize=7.0, frameon=False, columnspacing=0.6, handlelength=1.1, handletextpad=0.35, labelspacing=0.25, borderaxespad=0.0)   # rev. 4.7: anchored to the figure width (the axes-centred legend clipped its right column)   # rev. 4.5: legend below the single panel, 7 pt
else: axes[0, -1].legend(handles=h, loc="upper right", fontsize=6.0, ncol=2, columnspacing=0.5, handlelength=1.2, borderaxespad=0.15, labelspacing=0.2)   # rev. 4.1: legend in the t8 panel (upper right empty); t3 labels use the leader slots
if SINGLE: fig.subplots_adjust(left=0.15, right=0.985, top=0.90, bottom=0.42)
else: fig.tight_layout(h_pad=1.0, w_pad=1.0)
C.save(fig, OUTNAME)
if len(sys.argv) > 1: fig.savefig(sys.argv[1], dpi=160)
