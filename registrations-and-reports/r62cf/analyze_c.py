#!/usr/bin/env python3
"""r62cf Task C tables from calib_results.json + cache/ (pure lookup)."""
import json, os, math, glob, statistics as st
import numpy as np
R = '/home/user/experiment/qsim/r62cf'
res = json.load(open(f'{R}/calib_results.json'))
out = []; P = lambda s="": (print(s), out.append(s))
NAME = {("B4", "on"): "B4c2-family (v8sim11, R38 on)", ("B5", "on"): "B5c1-family (v8sim11, R38 on)", ("B6b6", "-"): "B6 (v8sim_b6.sim_b6, aggregate physics)",
        ("B6", "on"): "B6 (v8sim11 CtlB6, R38 on)", ("S", "on"): "S single-λ (v8sim11, R38 on)",
        ("B4", "off"): "B4c2-family (v8sim11, R38 off)", ("B5", "off"): "B5c1-family (v8sim11, R38 off)", ("B6", "off"): "B6 (v8sim11 CtlB6, R38 off)", ("S", "off"): "S single-λ (v8sim11, R38 off)"}
ACCT = {"B6b6": "dispatch"}
def agg(fam, phys, target):
    s = [r for r in res if r["fam"] == fam and r["phys"] == phys and r["target"] == target]
    if len(s) < 6: return None
    f = lambda k: (st.mean(r[k] for r in s), st.pstdev(r[k] for r in s))
    return dict(n=len(s), keys=[tuple(r["key"]) for r in s], cal=f("cal_risk"), ho=f("ho_risk"), cost=f("ho_cost"), ninf=sum(r["infeasible"] for r in s), rows=s)
# S reference values (given): nest2, vmexist (dispatch in brackets)
S_REF = {0.02: dict(dep=("S4b deployed λ 1.83/2.00, whole library", 0.01886, None, 1281.3, None), rec=("S4 recalibrated (ablation (e)), six-split held-out", 0.0194, 0.0017, 1282.5, 1290.1)),
         0.005: dict(dep=("S4a deployed λ 2.83/3.08, whole library", 0.00467, None, 1338.2, None), rec=("S4 recalibrated (ablation (e)), six-split held-out", 0.0051, 0.0007, 1338.6, 1344.0))}
P("## C.3 Per-split picks\n\n| baseline | target | seed | pick | cal risk | cal cost | held-out risk | held-out cost | feasible |\n|---|---|---|---|---|---|---|---|---|")
for (fam, phys), nm in NAME.items():
    for target in (0.02, 0.005):
        for r in sorted([r for r in res if r["fam"] == fam and r["phys"] == phys and r["target"] == target], key=lambda r: r["seed"]):
            P(f"| {nm} | {target} | {r['seed']} | {r['key']} | {r['cal_risk']:.4f} | {r['cal_cost']:.1f} | {r['ho_risk']:.4f} | {r['ho_cost']:.1f} | {'no (lowest achievable)' if r['infeasible'] else 'yes'} |")
P("\n## C.4 Summary per baseline (mean ± population std over 6 splits; SE = std/√6)\n\n| baseline | accounting | target | picks (6 splits) | cal risk | held-out risk (SE) | held-out cost | infeasible splits |\n|---|---|---|---|---|---|---|---|")
A = {}
for (fam, phys), nm in NAME.items():
    for target in (0.02, 0.005):
        a = agg(fam, phys, target)
        if a is None: P(f"| {nm} | | {target} | not run (budget) | | | | |"); continue
        A[(fam, phys, target)] = a
        P(f"| {nm} | {ACCT.get(fam, 'alloc_vm (VM existence)')} | {target} | {', '.join(str(k[0]) if len(k)==1 else f'{k[0]}/{k[1]}' for k in a['keys'])} | {a['cal'][0]:.4f} ± {a['cal'][1]:.4f} | {a['ho'][0]:.4f} ± {a['ho'][1]:.4f} ({a['ho'][1]/math.sqrt(6):.4f}) | {a['cost'][0]:.1f} ± {a['cost'][1]:.1f} | {a['ninf']}/6 |")
# deployed-knob library points
P("\n## C.5 Deployed knobs, whole library (from the cached grid points)\n\n| baseline | knob | library risk | library cost |\n|---|---|---|---|")
for fam, phys, key, lab in (("B4", "on", "3.5_600", "B4c2 T3.5/μ12/down600"), ("B5", "on", "4.0_L2", "B5c1 T4.0/μ14/lead(2,5,5)"), ("B6b6", "-", "0.7", "B6 u0.70 (sim_b6)"), ("B6", "on", "0.7", "B6 u0.70 (v8sim11)"),
                            ("B4", "off", "3.5_600", "B4c2 (R38 off)"), ("B5", "off", "4.0_L2", "B5c1 (R38 off)"), ("B6", "off", "0.7", "B6 u0.70 (v8sim11, R38 off)")):
    fn = f"{R}/cache/{fam}_{phys}_{key}.json"
    if os.path.exists(fn): d = json.load(open(fn)); P(f"| {lab} | {key} | {d['risk']:.4f} | {d['cost']:.1f} |")
P("\n## C.6 Equal-risk cost table and verdicts\nRule: S 'cheaper' iff its equal-risk cost is lower by > 2 % of the baseline's; 'more expensive' iff higher by > 2 %; otherwise 'same level'. Risk-difference flag: |Δrisk| > combined SE √(SE_S² + SE_B²) (6-split SE = std/√6).\n")
def verdict(cs, cb):
    d = (cb - cs) / cb
    return ("S cheaper" if d > 0.02 else ("S more expensive" if d < -0.02 else "same level")) + f" ({100*d:+.2f} %)"
for target in (0.02, 0.005):
    sd, sr = S_REF[target]["dep"], S_REF[target]["rec"]
    P(f"\n### target ε = {target}\n\n| row | simulator / accounting | risk (SE) | cost | S4-recal vs row: verdict | risk differs > 1 SE? |\n|---|---|---|---|---|---|")
    P(f"| {sd[0]} | nest2 / vmexist | {sd[1]:.4f} | {sd[3]:.1f} | — | — |")
    P(f"| {sr[0]} | nest2 / vmexist (dispatch) | {sr[1]:.4f} ({sr[2]/math.sqrt(6):.4f}) | {sr[3]:.1f} ({sr[4]:.1f}) | — | — |")
    P(f"| v6 fixed constants, whole library | v8sim2.sim_v6 / dispatch | 0.0239 | 1262.3 | {verdict(sr[4], 1262.3)} (dispatch vs dispatch) | v6 is not at ε (realised 0.0239) |")
    seS = sr[2] / math.sqrt(6)
    for (fam, phys), nm in NAME.items():
        a = A.get((fam, phys, target))
        if a is None or fam == "S": continue
        cs = sr[4] if fam == "B6b6" else sr[3]
        seB = a["ho"][1] / math.sqrt(6); dr = sr[1] - a["ho"][0]; flag = abs(dr) > math.sqrt(seS ** 2 + seB ** 2)
        tag = "" if a["ninf"] == 0 else f" [{a['ninf']}/6 splits infeasible: lowest achievable]"
        P(f"| {nm}{tag} | {ACCT.get(fam, 'alloc_vm')} | {a['ho'][0]:.4f} ({seB:.4f}) | {a['cost'][0]:.1f} | {verdict(cs, a['cost'][0])} | {'YES' if flag else 'no'} (Δ = {dr:+.4f}) |")
    # within-v8sim11 comparison: S single-λ calibrated in the same physics
    for phys in ("on", "off"):
        s = A.get(("S", phys, target))
        if s is None: continue
        inf_s = '' if s['ninf'] == 0 else f" [{s['ninf']}/6 splits infeasible: lowest achievable]"
        P(f"\n*Within v8sim11 (R38 {phys}): S single-λ calibrated in the same physics = held-out risk {s['ho'][0]:.4f} ({s['ho'][1]/math.sqrt(6):.4f}), cost {s['cost'][0]:.1f}{inf_s}.*\n\n| baseline (same physics) | risk (SE) | cost | S-v8sim11 vs baseline | risk differs > 1 SE? |\n|---|---|---|---|---|")
        for fam in ("B4", "B5", "B6"):
            a = A.get((fam, phys, target))
            if a is None: continue
            seB = a["ho"][1] / math.sqrt(6); seS2 = s["ho"][1] / math.sqrt(6); dr = s["ho"][0] - a["ho"][0]
            P(f"| {NAME[(fam, phys)]} | {a['ho'][0]:.4f} ({seB:.4f}) | {a['cost'][0]:.1f} | {verdict(s['cost'][0], a['cost'][0])} | {'YES' if abs(dr) > math.sqrt(seS2**2+seB**2) else 'no'} (Δ = {dr:+.4f}) |")
# runtime
secs = [json.load(open(f))["secs"] for f in glob.glob(f"{R}/cache/*.json")]
P(f"\nGrid points simulated: {len(secs)}, total simulation time {sum(secs)/3600:.2f} h (single process).")
open(f'{R}/c_tables.md', 'w').write("\n".join(out) + "\n")
