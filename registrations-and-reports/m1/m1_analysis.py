#!/usr/bin/env python3
"""m1_analysis.py — spec §4.99 A.2-A.4: rise10-percentile deciles of the library, per-decile simulated risk per arm,
pre-registered rule (A.3) for t3/t4, effective sample size (A.4), figs/fig_m1_risk_vs_burst.pdf (single column),
and m1/REPORT.md.  Inputs: m1/features.csv, m1/risk_per_trace.csv (both produced here), prior_traces.json (start field)."""
import csv, json, sys, time, re, os, collections
import numpy as np
sys.path.insert(0, "/home/user/experiment/qsim/m1"); sys.path.insert(0, "/home/user/docs/paper/figs/scripts")
from m1_common import *
import common
import matplotlib.pyplot as plt

t0 = time.time()
F = list(csv.DictReader(open(f"{M1}/features.csv"))); R = list(csv.DictReader(open(f"{M1}/risk_per_trace.csv")))
Fl = [r for r in F if r["loc"] != ""]; Rl = [r for r in R if r["loc"] != ""]
Ft = {r["index"]: r for r in F if r["loc"] == ""}; Rt = {r["index"]: r for r in R if r["loc"] == ""}
assert [r["index"] for r in Fl] == [r["index"] for r in Rl]
N = len(Fl)
rise = np.array([float(r["rise10"]) for r in Fl])
risk = {a: np.array([float(r[f"{a}_risk"]) for r in Rl]) for a in ARMS}
alloc = {a: np.array([float(r[f"{a}_alloc"]) for r in Rl]) for a in ARMS}
pr = np.array([prank(rise, x) for x in rise]); dec = np.array([decile_of_prank(p) for p in pr])
tdec = {t: decile_of_prank(prank(rise, float(Ft[t]["rise10"]))) for t in TRACES}
tpr = {t: prank(rise, float(Ft[t]["rise10"])) for t in TRACES}

out = []; P = out.append
P("## A.2 Library deciles by rise10 percentile rank (mid-rank for ties; ties share a decile)")
P("")
P("| decile | rise10 range | n windows | " + " | ".join(f"{a} mean risk (%)" for a in ARMS) + " | " +
  " | ".join(f"{a} frac. windows with >=1 viol. min (%)" for a in ARMS) + " | " + " | ".join(f"{a} mean alloc" for a in ARMS) + " | traces |")
P("|---|---|---|" + "---|" * (3 * len(ARMS)) + "---|")
D = {}
for d in range(10):
    m = dec == d
    D[d] = {"n": int(m.sum()), "lo": float(rise[m].min()) if m.any() else float("nan"), "hi": float(rise[m].max()) if m.any() else float("nan"),
            "risk": {a: float(risk[a][m].mean()) if m.any() else float("nan") for a in ARMS},
            "frac": {a: float((risk[a][m] > 0).mean()) if m.any() else float("nan") for a in ARMS},
            "alloc": {a: float(alloc[a][m].mean()) if m.any() else float("nan") for a in ARMS}}
    tl = ",".join(t for t in TRACES if tdec[t] == d)
    P(f"| D{d+1} (P{10*d}-P{10*d+10}) | {D[d]['lo']:.0f}-{D[d]['hi']:.0f} | {D[d]['n']} | " +
      " | ".join(f"{100*D[d]['risk'][a]:.2f}" for a in ARMS) + " | " + " | ".join(f"{100*D[d]['frac'][a]:.1f}" for a in ARMS) + " | " +
      " | ".join(f"{D[d]['alloc'][a]:.0f}" for a in ARMS) + f" | {tl} |")
P("")
P("Library-wide mean risk: " + ", ".join(f"{a} {100*risk[a].mean():.3f}%" for a in ARMS) + f" (n = {N}).")
P("")
P("Trace placement: " + "; ".join(f"{t}: rise10 = {float(Ft[t]['rise10']):.0f}, percentile rank {tpr[t]:.1f} -> D{tdec[t]+1}" for t in TRACES))
P("")
P("## A.3 Pre-registered rule: decile mean simulated risk vs measured hardware risk (3 runs x 60 min)")
P("")
P("| trace | decile | arm | sim. risk of the exact trace (%) | decile mean sim. risk (%) | measured risk (%) | ratio = decile mean / measured | verdict |")
P("|---|---|---|---|---|---|---|---|")
verdicts = {}
for t in ("t3", "t4", "t6", "t7"):
    for a in ("S4b", "S4a", "v6"):
        d = tdec[t]; dm = D[d]["risk"][a]; ex = float(Rt[t][f"{a}_risk"])
        mv = MEASURED_VIOL[a][t]; meas = mv / MEASURED_DEN
        if t in ("t3", "t4"):
            ratio = dm / meas if meas > 0 else float("inf")
            if 0.5 <= ratio <= 2:
                v = "within [0.5, 2]: epsilon is a library-average target and the tail risk is correctly anticipated by the simulator"
            else:
                v = f"simulator {'under' if ratio < 1 else 'over'}-estimates tail risk by factor {1/ratio if ratio < 1 else ratio:.2f}"
            verdicts[(t, a)] = (ratio, v)
            rs = f"{ratio:.2f}"
        else:
            rs = f"{dm/meas:.2f}" if meas > 0 else "n/a (measured 0)"; v = "(rule pre-registered for t3/t4 only; shown for reference)"
        P(f"| {t} | D{d+1} ({D[d]['lo']:.0f}-{D[d]['hi']:.0f}) | {a} | {100*ex:.2f} | {100*dm:.2f} | {100*meas:.2f} ({mv}/{MEASURED_DEN}) | {rs} | {v} |")
P("")
P("## A.4 Effective sample size")
lib = load_lib()
groups = collections.defaultdict(list)
for t in lib: groups[(t["loc"], t["date"])].append(t["start"])
cnt = collections.Counter(len(v) for v in groups.values())
ov = []; dstart = collections.Counter()
for k, v in groups.items():
    v = sorted(v)
    for a, b in zip(v, v[1:]):
        dstart[b - a] += 1; ov.append(max(0, 240 - (b - a)) / 240)
ov = np.array(ov)
P("")
P(f"- library windows: {N}; distinct sensors (loc): {len({k[0] for k in groups})}; distinct dates: {len({k[1] for k in groups})}")
P(f"- (loc, date) groups = **effective n = {len(groups)}**")
P(f"- windows per group: mean {N/len(groups):.2f}, min {min(cnt)}, max {max(cnt)}; distribution {{windows: groups}} = " +
  ", ".join(f"{k}: {cnt[k]}" for k in sorted(cnt)))
P(f"- start field is in real minutes of day (values {min(t['start'] for t in lib)}..{max(t['start'] for t in lib)}); each window covers 240 real minutes (4 real min = 1 trace min)")
P(f"- consecutive-window start gaps within a group: " + ", ".join(f"delta={k} min: {dstart[k]} pairs" for k in sorted(dstart)) +
  f" ({len(ov)} consecutive pairs)")
P(f"- overlap = max(0, 240 - delta_start)/240: mean {ov.mean():.3f}, median {np.median(ov):.3f}, min {ov.min():.3f}, max {ov.max():.3f}; "
  f"fraction of pairs with overlap 0.75: {np.mean(np.isclose(ov, 0.75))*100:.1f}%")
P(f"- for reference, non-overlapping 240-min windows per group would be at most {(max(t['start'] for t in lib)+240-min(t['start'] for t in lib))//240} -> "
  f"about {len(groups)*((max(t['start'] for t in lib)+240-min(t['start'] for t in lib))//240)} independent windows if every group were fully covered "
  f"(actual coverage is lower, see distribution above)")
P("")
json.dump({"deciles": D, "t_decile": tdec, "t_prank": tpr, "verdicts": {f"{t}/{a}": v for (t, a), v in verdicts.items()},
           "eff_n": {"groups": len(groups), "windows": N, "overlap_mean": float(ov.mean()), "dstart": dict(dstart), "windows_per_group": dict(cnt)}},
          open(f"{M1}/analysis.json", "w"), indent=1)

# ---- figure: simulated risk vs rise10 decile, single column ----
common.set_style()
fig, ax = plt.subplots(figsize=(3.4, 3.0))
x = np.arange(10)
for a in ARMS:
    lab, c, mk = common.ARMS[a]
    ax.plot(x, [100 * D[d]["risk"][a] for d in range(10)], color=c, marker=mk, ms=4, lw=1.0, label=f"{lab.split(' (')[0]} simulated (decile mean)", zorder=3)
OFF = {"S4a": -0.2, "S4b": 0.0, "v6": 0.2}
for t in ("t3", "t4", "t6", "t7"):
    for a in ARMS:
        lab, c, mk = common.ARMS[a]
        ax.plot(tdec[t] + OFF[a], 100 * MEASURED_VIOL[a][t] / MEASURED_DEN, marker=mk, ms=5.5, mfc="white", mec=c, mew=1.0, ls="none", zorder=4)
ymax = max(100 * D[d]["risk"][a] for d in range(10) for a in ARMS)
ymax = max(ymax, max(100 * MEASURED_VIOL[a][t] / MEASURED_DEN for a in ARMS for t in MEASURED_VIOL[a]))
ax.set_ylim(-0.3, ymax * 1.14)
lab_at = collections.defaultdict(list)
for t in ("t3", "t4", "t6", "t7"): lab_at[tdec[t]].append(t)
for d, ts in lab_at.items():
    ax.axvline(d, color="#AAAAAA", lw=0.6, ls=(0, (1, 2)), zorder=1)
    ax.text(d, ymax * 1.12, ", ".join(ts), ha="center", va="top", fontsize=7, color="#333333")
ax.set_xticks(x); ax.set_xticklabels([f"D{d+1}\n{D[d]['lo']:.0f}-{D[d]['hi']:.0f}" for d in range(10)], fontsize=6)
ax.set_xlabel("rise10 decile of the prior library (rise10 range, UE)")
ax.set_ylabel("violating minutes (%)")
for s in ("top", "right"): ax.spines[s].set_visible(False)
ax.grid(axis="y", lw=0.4, alpha=0.3)
from matplotlib.lines import Line2D
h, l = ax.get_legend_handles_labels()
h.append(Line2D([], [], marker="o", ms=5.5, mfc="white", mec="#333333", mew=1.0, ls="none")); l.append("measured, 3 runs x 60 min (hollow)")
fig.legend(h, l, loc="lower center", ncol=2, fontsize=6, frameon=False, bbox_to_anchor=(0.5, -0.005), columnspacing=1.0, handletextpad=0.4)
fig.tight_layout(rect=(0, 0.1, 1, 1))
common.save(fig, "fig_m1_risk_vs_burst.pdf")
if len(sys.argv) > 1: fig.savefig(sys.argv[1], dpi=160)

# ---- REPORT.md ----
def rt(log, pat):
    try:
        m = re.findall(pat, open(log).read()); return m[-1] if m else "?"
    except FileNotFoundError: return "?"
rep = []; A = rep.append
A("# M1 (spec §4.99 Task A): conditional risk of ε — library features, simulated vs measured tail risk, effective n")
A("")
A(f"Generated {time.strftime('%Y-%m-%d %H:%M:%S')} by /home/user/experiment/qsim/m1/m1_analysis.py. Pure simulation; no testbed run, no change to λ/daemon/harness.")
A("Library: /home/user/experiment/qsim/prior_traces.json (1615 windows). Traces: t1 = trace_ue_60min_v3_40.json, t2 = trace_ue_60min_v3_pm.json, t3..t7 = trace_ue_60min_v3_t3..t7.json (key \"ue\", first 60 minutes).")
A("Simulators (frozen): S4a/S4b = v8sim10.sim_nest2(ue, M.cfg_measured(), S.Prior(lib, cfg), λ, acct='vmexist') with λ S4a {vy 2.83, wk 2.83, up 3.08}, S4b {1.83, 1.83, 2.00}; v6 = v8sim2.sim_v6(ue, v8sim7.cfg_measured()). risk = (60 - slo)/60.")
A("")
A("## Commands (run from /home/user/experiment/qsim; v8sim3 opens prior_traces.json relative to the cwd)")
A("```")
A("cd /home/user/experiment/qsim/m1 && nice -n 19 taskset -c 8-15 python3 m1_features.py | tee features_run.log")
A("cd /home/user/experiment/qsim && nice -n 19 taskset -c 8-15 python3 m1/m1_risk.py | tee m1/risk_run.log")
A("cd /home/user/experiment/qsim && nice -n 19 taskset -c 8-15 python3 m1/m1_fig_features.py | tee m1/fig_features_run.log")
A("cd /home/user/experiment/qsim && nice -n 19 taskset -c 8-15 python3 m1/m1_analysis.py | tee m1/analysis_run.log")
A("```")
A(f"`taskset -c 8-15` resolves to the cgroup-allowed CPUs {sorted(os.sched_getaffinity(0))} on this host (16 logical CPUs, user slice cpuset); the pool used {min(8, len(os.sched_getaffinity(0)))} workers.")
A("")
A("## Runtimes")
A(f"- m1_features.py: {rt(f'{M1}/features_run.log', r'runtime ([0-9.]+) s')} s")
A(f"- m1_risk.py: {rt(f'{M1}/risk_run.log', r'total runtime ([0-9.]+) s')} s total (simulation of 1623 traces x 3 arms: {rt(f'{M1}/risk_run.log', r'in ([0-9.]+) s')} s; Prior build {rt(f'{M1}/risk_run.log', r'prior built ([0-9.]+) s')} s)")
A(f"- m1_fig_features.py: {rt(f'{M1}/fig_features_run.log', r'runtime ([0-9.]+) s')} s")
A(f"- m1_analysis.py: {time.time()-t0:.1f} s (up to writing this report)")
A("")
A("## Checks")
A("- t1..t5 mp/f36/minUE/rise10 computed here equal the frozen values in t6t7_thresholds.json (assert in m1_features.py).")
A("- The simulated slo/alloc of t1..t7 for S4a/S4b/v6 equal the registered predictions (v8_predict_t345_2026-10-07.txt, v8_predict_v6_t345_2026-10-07.txt, v8_predict_t67_2026-10-15.txt): see table below (" + rt(f'{M1}/risk_run.log', r'registered-prediction cross-check: (.*)') + ").")
A("- Determinism: t6 simulated twice in the pool, identical results.")
A("")
A("## A.1 Features (m1/features.csv; figs/fig_m1_features.pdf)")
A("")
A(open(f"{M1}/features_table.md").read().rstrip())
A("")
A("## A.2 Simulated risk of t1..t7 (m1/risk_per_trace.csv; registered values in parentheses)")
A("")
A(open(f"{M1}/risk_t_table.md").read().rstrip())
A("")
A("Library-wide (1615 windows): " + "; ".join(re.findall(r"library (S4a|S4b|v6): (mean risk [^\n]*)", open(f"{M1}/risk_run.log").read()).__class__.__name__ and
  [f"{a}: {s}" for a, s in re.findall(r"library (S4a|S4b|v6): (mean risk [^\n]*)", open(f"{M1}/risk_run.log").read())]))
A("")
rep.extend(out)
A("## Figures")
A("- /home/user/docs/paper/figs/fig_m1_features.pdf (double column, 7.0 in): library histograms of mp, f36, rise10, rise1, lag-1, stationarity; dashed grey marks = t1/t2 (development), solid black = t3-t7 (test), labelled.")
A("- /home/user/docs/paper/figs/fig_m1_risk_vs_burst.pdf (single column, 3.4 in): decile mean simulated risk per arm (filled markers, lines; S4a blue circle, S4b orange square, v6 green triangle, as in common.py) vs rise10 decile; hollow markers = measured hardware risk of t3/t4/t6/t7 (3 runs x 60 min) placed at the trace's decile (x offset -0.2/0/+0.2 for S4a/S4b/v6); dotted verticals mark the deciles of t3, t4, t6/t7.")
A("")
A("## Verdict (rule A.3, pre-registered)")
for (t, a), (ratio, v) in verdicts.items():
    A(f"- {t} / {a}: ratio {ratio:.2f} -> {v}")
open(f"{M1}/REPORT.md", "w").write("\n".join(rep) + "\n")
print("\n".join(out)); print("\n".join(rep[-1 - len(verdicts):]))
print(f"wrote {M1}/REPORT.md; runtime {time.time()-t0:.1f} s")
