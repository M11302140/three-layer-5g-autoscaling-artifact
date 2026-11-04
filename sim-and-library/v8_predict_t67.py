#!/usr/bin/env python3
"""(docstring removed)"""
import json, sys, time, os
sys.path.insert(0, '/home/user/experiment/qsim')
E = '/home/user/experiment'
TR = {t: json.load(open(f"{E}/trace_ue_60min_v3_{t}.json"))["ue"][:60] for t in ("t6", "t7")}
print(f"=== t6/t7 登記預測 {time.strftime('%F %T')}  peakUE t6={max(TR['t6'])} t7={max(TR['t7'])}")
import v8sim10 as M10
LAM = {"S4a": {"vy": 2.83, "wk": 2.83, "up": 3.08}, "S4b": {"vy": 1.83, "wk": 1.83, "up": 2.00}}
lib = json.load(open(f"{E}/qsim/prior_traces.json")); cfg = M10.M.cfg_measured(); pr = M10.S.Prior(lib, cfg)
print(" grp  trace  SLO(dispatch)  alloc_dispatch  alloc_vmexist(登記)")
for grp in ("S4a", "S4b"):
    for tn in ("t6", "t7"):
        r = M10.sim_nest2(TR[tn], cfg, pr, LAM[grp]); rv = M10.sim_nest2(TR[tn], cfg, pr, LAM[grp], acct='vmexist')
        print(f" {grp}  {tn}    {r['slo']:2d}/60        {r['alloc']:7.0f}        {rv['alloc']:7.0f}", flush=True)
import v8sim2 as S, v8sim7 as M
cfg2 = M.cfg_measured()
for tn in ("t6", "t7"):
    r = S.sim_v6(TR[tn], cfg2); print(f" v6   {tn}    {r['slo']:2d}/60  alloc {r['alloc']:.0f}", flush=True)
import v8sim_b6 as B6
mk = B6.load_models()
for tn in ("t6", "t7"):
    r = B6.sim_b6(TR[tn], cfg2, 0.70, mk); print(f" B6u70 {tn}   {r['slo']:2d}/60  alloc {r['alloc']:.0f}  worst {r['worst']:.2f}%", flush=True)
try:
    import v8sim11 as V
    V.cfg_prior()
    for arm in ("B4c2", "B5c1", "B1"):
        for tn in ("t6", "t7"):
            r = V.run(TR[tn], arm); print(f" [補充 v8sim11] {arm} {tn}  {r['slo']:2d}/60  alloc_vm {r['alloc_vm']:.0f}", flush=True)
except Exception as e:
    print(f" [補充 v8sim11] 略過: {e}")
