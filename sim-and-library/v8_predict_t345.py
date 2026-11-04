#!/usr/bin/env python3
"""(docstring removed)"""
import json, sys, time
sys.path.insert(0, '/home/user/experiment/qsim')
import v8sim10 as M10
E = '/home/user/experiment'
LAM = {"S4a": {"vy": 2.83, "wk": 2.83, "up": 3.08}, "S4b": {"vy": 1.83, "wk": 1.83, "up": 2.00}}
TR = {t: json.load(open(f"{E}/trace_ue_60min_v3_{f}.json"))["ue"][:60] for t, f in (("t1", "40"), ("t2", "pm"), ("t3", "t3"), ("t4", "t4"), ("t5", "t5"))}
lib = json.load(open(f"{E}/qsim/prior_traces.json")); cfg = M10.M.cfg_measured(); pr = M10.S.Prior(lib, cfg)
print(f"=== 凍結版預測 {time.strftime('%F %T')} nest2 (v8sim10.sim_nest2) λ={LAM}")
print(" grp  trace  peakUE  SLO(dispatch)  alloc_dispatch  alloc_vmexist  events(min:action:layer)")
for grp in ("S4a", "S4b"):
    for tn in ("t1", "t2", "t3", "t4", "t5"):
        r = M10.sim_nest2(TR[tn], cfg, pr, LAM[grp])
        rv = M10.sim_nest2(TR[tn], cfg, pr, LAM[grp], acct='vmexist')
        ev = ' '.join(f"{int(t)//60}:{a}:{k}" for t, a, k in r["ev"])
        print(f" {grp}  {tn}    {max(TR[tn]):3d}     {r['slo']:2d}/60        {r['alloc']:7.0f}        {rv['alloc']:7.0f}      {ev[:160]}", flush=True)
