#!/usr/bin/env python3
"""out/testtr.json -> out/testtr_table.md (no simulation)"""
import json, numpy as np
R = "/home/user/experiment/qsim/r63r"; d = json.load(open(f"{R}/out/testtr.json"))
L = ["| trace | rise1 | bucket | arm | bucket λ old → new | full λ: nest2 | full λ: v8sim11 | bucket λ: nest2 old → new | bucket λ: v8sim11 old → new | v8sim11 new λ, full-library Prior | six split Priors: nest2 / v8sim11 (mean [min–max]) | hardware |",
     "|---|---|---|---|---|---|---|---|---|---|---|---|"]
for x in d["rows"]:
    o = x["old"]; sp = x["split_priors"]
    f = lambda k: (lambda a: f"{np.mean(a):.2f} [{min(a)}–{max(a)}]")([int(s[k][0]) for s in sp])
    L.append(f"| {x['trace']} | {x['rise1']:g} | {x['bucket']} | {x['arm']} | {o['lam'][0]}/{o['lam'][1]} → **{x['lam'][0]}/{x['lam'][1]}** | {o['full_n2']} ({o['full_n2_alloc']:.0f}) | {o['full_11']} ({o['full_11_alloc']:.0f}) | "
             f"{o['dec_n2']} ({o['dec_n2_alloc']:.0f}) → **{x['n2'][0]} ({x['n2'][1]:.0f})** | {o['dec_11']} ({o['dec_11_alloc']:.0f}) → **{int(x['v11'][0])} ({x['v11'][1]:.0f})** | {int(x['v11_fullprior'][0])} ({x['v11_fullprior'][1]:.0f}) | {f('n2')} / {f('v11')} | {o['hw']} |")
L.append(""); L.append("recheck of the old bucket-λ nest2 column (old λ, full-library Prior): " + ", ".join(f"{x['trace']} {x['arm']} {x['old_recheck_n2'][0]}{'' if x['old_recheck_n2'][0]==x['old']['dec_n2'] else ' DIFF'}" for x in d["rows"]))
open(f"{R}/out/testtr_table.md", "w").write("\n".join(L) + "\n"); print("\n".join(L))
