#!/usr/bin/env python3
"""(docstring removed)"""
import sys, json, time
sys.path.insert(0, '/home/user/experiment/qsim')
import v8sim2 as S, v8sim7 as M
E = '/home/user/experiment'
TR = {t: json.load(open(f"{E}/trace_ue_60min_v3_{f}.json"))["ue"][:60] for t, f in (("t1", "40"), ("t2", "pm"), ("t3", "t3"), ("t4", "t4"), ("t5", "t5"))}
cfg = M.cfg_measured()
print(f"=== v6 模擬預測 {time.strftime('%F %T')} (v8sim2.sim_v6, cfg_measured; 口徑 = 該模擬的 alloc)")
for tn in ("t1", "t2", "t3", "t4", "t5"):
    r = S.sim_v6(TR[tn], cfg)
    keys = {k: r[k] for k in r if k in ('slo', 'alloc', 'lostfrac')}
    print(f" v6  {tn}  peakUE {max(TR[tn]):3d}  {keys}", flush=True)
