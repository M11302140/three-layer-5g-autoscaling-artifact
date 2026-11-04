#!/usr/bin/env python3
"""r62cf F2 supplement: whole-library (1615) effect of the emergency rule, R38 on, emerg=True; emerg=False reference = frozen v8sim11_lib_<arm>_r38on.json (bit-identical runner shown on t3-t7)."""
import timeit
import sys, os, json, time
os.chdir('/home/user/experiment/qsim'); sys.path.insert(0, '/home/user/experiment/qsim/r62cf'); sys.path.insert(0, '/home/user/experiment/qsim')
import v8sim11_emerg as VE
import numpy as np
LIB = json.load(open('prior_traces.json'))
ARMS = [("S4a", {}, "S4a"), ("S4b", {}, "S4b"), ("v6", {}, "v6"), ("B4c2", {}, "B4c2"), ("B5c1", {}, "B5c1"), ("B6", {"u": 0.70}, "B6u70")]
out = {}
for arm, kw, ref in ARMS:
    t0 = time.time(); rv, cv, nf, nok = [], [], 0, 0
    for tr in LIB:
        r = VE.run(tr["ue"][:60], arm, emerg=True, **kw); rv.append((60 - r["slo"]) / 60); cv.append(r["alloc_vm"])
        nf += len(r["emerg_fires"]); nok += sum(1 for f in r["emerg_fires"] if f[2])
    b = json.load(open(f'v8sim11_lib_{ref}_r38on.json'))
    ch = sum(1 for x, y, c, d in zip(rv, b["risk_vec"], cv, b["cost_vec"]) if x != y or abs(c - d) > 1e-9)
    out[arm] = dict(risk_on=float(np.mean(rv)), cost_on=float(np.mean(cv)), risk_off=b["risk"], cost_off=b["cost"], fires=nf, fires_dispatched=nok, traces_changed=ch)
    print(arm, out[arm], f"{time.time()-t0:.0f}s", flush=True)
json.dump(out, open('/home/user/experiment/qsim/r62cf/f2_lib.json', 'w'), indent=1)
