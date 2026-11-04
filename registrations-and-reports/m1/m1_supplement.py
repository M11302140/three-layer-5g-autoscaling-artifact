#!/usr/bin/env python3
"""m1_supplement.py — spec §4.99 A supplement (5) and (6), R58-2.
(5) three-level prediction table for t3/t4/t6/t7 x S4a/S4b/v6: rise10-decile mean risk (from m1/analysis.json),
    registered per-trace prediction (nest2 exact trace, deployed λ, vmexist; v6 = sim_v6; from m1/risk_per_trace.csv,
    identical to the registered files), per-slot simulator v8sim11 exact trace (V.cfg_prior(); V.run(tr, arm) with arm in
    {"S4a","S4b","v6"}, default start/phys/kwargs), measured hardware violating minutes per run (3-run total / 3).
(6) re-bucket the library by rise1 deciles, decile mean risk per arm, t3/t4/t6/t7 placement and ratios,
    figs/fig_m1_risk_vs_burst_rise1.pdf.  Appends '## Supplement R58-2' to m1/REPORT.md."""
import csv, json, sys, time, os, collections, re
import timeit  # pre-load the stdlib module: qsim/timeit.py shadows it once v8sim11 inserts qsim at sys.path[0] (breaks the PDF backend)
import numpy as np
sys.path.insert(0, "/home/user/experiment/qsim"); sys.path.insert(0, "/home/user/experiment/qsim/m1"); sys.path.insert(0, "/home/user/docs/paper/figs/scripts")
from m1_common import *
import common
import matplotlib.pyplot as plt

t0 = time.time()
TT = ("t3", "t4", "t6", "t7")
tr = load_traces()
F = list(csv.DictReader(open(f"{M1}/features.csv"))); R = list(csv.DictReader(open(f"{M1}/risk_per_trace.csv")))
Fl = [r for r in F if r["loc"] != ""]; Rl = [r for r in R if r["loc"] != ""]
Ft = {r["index"]: r for r in F if r["loc"] == ""}; Rt = {r["index"]: r for r in R if r["loc"] == ""}
AN = json.load(open(f"{M1}/analysis.json"))
risk = {a: np.array([float(r[f"{a}_risk"]) for r in Rl]) for a in ARMS}
N = len(Rl)

# ---- (5) v8sim11 per-slot exact-trace predictions ----
import v8sim11 as V
V.cfg_prior()
r38 = {k: V.PHYS[k] for k in ("knee", "knee38", "a38", "churn38_s", "hold38_s")}; r38["PHYS_OVERRIDE env"] = os.environ.get("PHYS_OVERRIDE")
t1 = time.time()
P11 = {}
for t in TT:
    for a in ARMS:
        r = V.run(tr[t], a)
        assert 60 - r["slo"] == len(r["viol"]), (t, a, r["slo"], r["viol"])
        P11[(t, a)] = (60 - int(r["slo"]), list(r["viol"]), float(r["alloc_vm"]), {int(k): v for k, v in r["viol_src"].items()})
# determinism check
rr = V.run(tr["t3"], "S4b"); assert 60 - rr["slo"] == P11[("t3", "S4b")][0]
t11 = time.time() - t1
out = []; P = out.append
P("## Supplement R58-2 (spec §4.99 A (5) and (6), added 10-20)")
P("")
P(f"Generated {time.strftime('%Y-%m-%d %H:%M:%S')} by /home/user/experiment/qsim/m1/m1_supplement.py "
  f"(`cd /home/user/experiment/qsim && nice -n 19 taskset -c 13,14 python3 m1/m1_supplement.py | tee m1/supplement_run.log`).")
P("")
P("### (5) Three-level prediction table: rise10-decile mean vs registered per-trace vs per-slot (v8sim11) per-trace vs measured")
P("")
P("Units: violating minutes per 60-minute run. Registered = nest2 exact trace at deployed λ, acct = vmexist (S4a/S4b), v8sim2.sim_v6 (v6); "
  "values are those in m1/risk_per_trace.csv, which were verified equal to the registered prediction files. "
  "v8sim11 = `import v8sim11 as V; V.cfg_prior(); r = V.run(tr, arm)` with arm names exactly \"S4a\", \"S4b\", \"v6\" (v8sim11.make_ctl: "
  "S4a/S4b -> CtlSigma with its own LAM table = deployed λ, v6 -> CtlV6), start = None (initial_fleet), phys = None, no kwargs; "
  f"R38 (slot .38 overflow rule) is on by default via v8sim11.PHYS and was left at its defaults: {r38}; violating minutes = 60 - slo = len(viol). "
  "Decile mean = rise10 decile mean risk x 60 (from §A.2 table). Measured = 3-run total / 3. Ratios are measured / prediction; n/a when the prediction is 0.")
P("")
P("| trace | arm | rise10 decile | decile mean (min/run, %) | registered (min/run) | v8sim11 (min/run; minutes; alloc_vm) | measured (min/run) | measured / registered | measured / v8sim11 | measured / decile mean |")
P("|---|---|---|---|---|---|---|---|---|---|")
def ratio(m, p): return f"{m/p:.2f}" if p > 0 else ("n/a (pred 0)" if m == 0 else "∞ (pred 0)")
tab5 = {}
for t in TT:
    d = AN["t_decile"][t]
    for a in ARMS:
        dm = AN["deciles"][str(d)]["risk"][a] * 60
        reg = 60 - int(Rt[t][f"{a}_slo"])
        v11, vm, al, src = P11[(t, a)]
        meas = MEASURED_VIOL[a][t] / 3
        tab5[(t, a)] = (dm, reg, v11, meas)
        P(f"| {t} | {a} | D{d+1} | {dm:.2f} ({dm/60*100:.2f}%) | {reg} | {v11}; {vm if vm else '-'}; {al:.0f} | {meas:.2f} ({MEASURED_VIOL[a][t]}/3) | {ratio(meas, reg)} | {ratio(meas, v11)} | {ratio(meas, dm)} |")
P("")
P("v8sim11 violation sources (viol_src per violating minute): " + "; ".join(f"{t}/{a}: {P11[(t,a)][3]}" for t in TT for a in ARMS if P11[(t,a)][3]))
P("")

# ---- (6) rise1 deciles ----
def deciles(feat):
    v = np.array([float(r[feat]) for r in Fl]); pr = np.array([prank(v, x) for x in v]); dec = np.array([decile_of_prank(p) for p in pr])
    D = {}
    for d in range(10):
        m = dec == d
        D[d] = {"n": int(m.sum()), "lo": float(v[m].min()) if m.any() else float("nan"), "hi": float(v[m].max()) if m.any() else float("nan"),
                "risk": {a: float(risk[a][m].mean()) if m.any() else float("nan") for a in ARMS}}
    tdec = {t: decile_of_prank(prank(v, float(Ft[t][feat]))) for t in TRACES}; tpr = {t: prank(v, float(Ft[t][feat])) for t in TRACES}
    return D, tdec, tpr
D1, tdec1, tpr1 = deciles("rise1")
P("### (6) Re-bucketing by rise1 (max one-minute rise), same decile method (percentile rank, mid-rank ties)")
P("")
P("rise1 is integer-valued with heavy ties (library P10/P50/P90 = 7/9/14), so some deciles are empty and others wide; empty deciles are shown as '-' and omitted from the figure.")
P("")
P("| decile | rise1 range | n windows | " + " | ".join(f"{a} mean risk (%)" for a in ARMS) + " | traces |")
P("|---|---|---|---|---|---|---|")
for d in range(10):
    tl = ",".join(t for t in TRACES if tdec1[t] == d)
    if D1[d]["n"] == 0: P(f"| D{d+1} (P{10*d}-P{10*d+10}) | - | 0 | - | - | - | {tl} |"); continue
    P(f"| D{d+1} (P{10*d}-P{10*d+10}) | {D1[d]['lo']:.0f}-{D1[d]['hi']:.0f} | {D1[d]['n']} | " + " | ".join(f"{100*D1[d]['risk'][a]:.2f}" for a in ARMS) + f" | {tl} |")
P("")
P("Trace placement by rise1: " + "; ".join(f"{t}: rise1 = {float(Ft[t]['rise1']):.0f}, percentile rank {tpr1[t]:.1f} -> D{tdec1[t]+1}" for t in TRACES)
  + ". By rise10 the same traces were: " + "; ".join(f"{t} -> D{AN['t_decile'][t]+1}" for t in TRACES) + ".")
P("")
P("| trace | rise1 decile | arm | decile mean sim. risk (%) | measured (%) | ratio = decile mean / measured | verdict (rule A.3, t3/t4) | rise10 decile mean (%) / ratio |")
P("|---|---|---|---|---|---|---|---|")
verd1 = {}
for t in TT:
    for a in ("S4b", "S4a", "v6"):
        d = tdec1[t]; dm = D1[d]["risk"][a]; meas = MEASURED_VIOL[a][t] / MEASURED_DEN
        d10 = AN["t_decile"][t]; dm10 = AN["deciles"][str(d10)]["risk"][a]
        if t in ("t3", "t4"):
            rt_ = dm / meas
            v = "within [0.5, 2]" if 0.5 <= rt_ <= 2 else f"simulator {'under' if rt_ < 1 else 'over'}-estimates tail risk by factor {(1/rt_ if rt_ < 1 else rt_):.2f}"
            verd1[(t, a)] = (rt_, v); rs = f"{rt_:.2f}"
        else:
            rs = f"{dm/meas:.2f}" if meas > 0 else "n/a (measured 0)"; v = "(reference only)"
        P(f"| {t} | D{d+1} ({D1[d]['lo']:.0f}-{D1[d]['hi']:.0f}) | {a} | {100*dm:.2f} | {100*meas:.2f} ({MEASURED_VIOL[a][t]}/{MEASURED_DEN}) | {rs} | {v} | {100*dm10:.2f} / {(dm10/meas if meas>0 else float('nan')):.2f} |")
P("")
mv = "moves to a higher decile" if tdec1["t4"] > AN["t_decile"]["t4"] else ("stays in the same decile" if tdec1["t4"] == AN["t_decile"]["t4"] else "moves to a lower decile")
P(f"t4 outcome: rise1 = {float(Ft['t4']['rise1']):.0f} (library percentile rank {tpr1['t4']:.1f}) -> D{tdec1['t4']+1}; by rise10 it was D{AN['t_decile']['t4']+1}: t4 {mv}. "
  f"Decile mean risk at t4's rise1 decile: " + ", ".join(f"{a} {100*D1[tdec1['t4']]['risk'][a]:.2f}%" for a in ARMS) +
  " vs at its rise10 decile: " + ", ".join(f"{a} {100*AN['deciles'][str(AN['t_decile']['t4'])]['risk'][a]:.2f}%" for a in ARMS) + ".")
P("")
P("Verdicts (rule A.3 with rise1 deciles): " + "; ".join(f"{t}/{a}: ratio {r_:.2f} -> {v}" for (t, a), (r_, v) in verd1.items()))
P("")
json.dump({"table5": {f"{t}/{a}": v for (t, a), v in tab5.items()}, "v8sim11": {f"{t}/{a}": v[:3] for (t, a), v in P11.items()}, "r38_consts": {k: str(v) for k, v in r38.items()},
           "rise1_deciles": D1, "rise1_t_decile": tdec1, "rise1_t_prank": tpr1, "rise1_verdicts": {f"{t}/{a}": v for (t, a), v in verd1.items()}},
          open(f"{M1}/supplement.json", "w"), indent=1)

# ---- figure: risk vs rise1 decile (same style as rise10 figure) ----
common.set_style()
fig, ax = plt.subplots(figsize=(3.4, 3.0))
x = np.arange(10); nonempty = [d for d in range(10) if D1[d]["n"] > 0]
for a in ARMS:
    lab, c, mk = common.ARMS[a]
    ax.plot([d for d in nonempty], [100 * D1[d]["risk"][a] for d in nonempty], color=c, marker=mk, ms=4, lw=1.0, label=f"{lab.split(' (')[0]} simulated (decile mean)", zorder=3)
OFF = {"S4a": -0.2, "S4b": 0.0, "v6": 0.2}
for t in TT:
    for a in ARMS:
        lab, c, mk = common.ARMS[a]
        ax.plot(tdec1[t] + OFF[a], 100 * MEASURED_VIOL[a][t] / MEASURED_DEN, marker=mk, ms=5.5, mfc="white", mec=c, mew=1.0, ls="none", zorder=4)
ymax = max(max(100 * D1[d]["risk"][a] for d in nonempty for a in ARMS), max(100 * MEASURED_VIOL[a][t] / MEASURED_DEN for a in ARMS for t in TT))
ax.set_ylim(-0.3, ymax * 1.14)
lab_at = collections.defaultdict(list)
for t in TT: lab_at[tdec1[t]].append(t)
for d, ts in lab_at.items():
    ax.axvline(d, color="#AAAAAA", lw=0.6, ls=(0, (1, 2)), zorder=1)
    ax.text(d, ymax * 1.12, ", ".join(ts), ha="center", va="top", fontsize=7, color="#333333")
ax.set_xticks(x); ax.set_xticklabels([f"D{d+1}\n" + (f"{D1[d]['lo']:.0f}-{D1[d]['hi']:.0f}" if D1[d]["n"] else "(empty)") for d in range(10)], fontsize=6)
ax.set_xlabel("rise1 decile of the prior library (rise1 range, UE)")
ax.set_ylabel("violating minutes (%)")
for s in ("top", "right"): ax.spines[s].set_visible(False)
ax.grid(axis="y", lw=0.4, alpha=0.3)
from matplotlib.lines import Line2D
h, l = ax.get_legend_handles_labels()
h.append(Line2D([], [], marker="o", ms=5.5, mfc="white", mec="#333333", mew=1.0, ls="none")); l.append("measured, 3 runs x 60 min (hollow)")
fig.legend(h, l, loc="lower center", ncol=2, fontsize=6, frameon=False, bbox_to_anchor=(0.5, -0.005), columnspacing=1.0, handletextpad=0.4)
fig.tight_layout(rect=(0, 0.1, 1, 1))
common.save(fig, "fig_m1_risk_vs_burst_rise1.pdf")
if len(sys.argv) > 1: fig.savefig(sys.argv[1], dpi=160)
P("Figure: /home/user/docs/paper/figs/fig_m1_risk_vs_burst_rise1.pdf (single column; same encoding as fig_m1_risk_vs_burst.pdf, x = rise1 decile; empty deciles omitted).")
P("")
P(f"Runtime: v8sim11 12 runs + cfg_prior {t11:.1f} s; whole script {time.time()-t0:.1f} s.")
txt = "\n".join(out)
open(f"{M1}/REPORT.md", "a").write("\n" + txt + "\n")
print(txt)
