#!/usr/bin/env python3
"""(docstring removed)"""
import json, sys, time
sys.path.insert(0, '/home/user/experiment/qsim'); E = '/home/user/experiment'
TR = {t: json.load(open(f"{E}/trace_ue_60min_v3_{t}.json"))["ue"][:60] for t in ("t3", "t6")}
print(f"=== H 登記預測 {time.strftime('%F %T')}  B6 u=0.775 (offline ε=2 %, R38-off recalibration r62cf) vs deployed 0.70")
import v8sim7 as M, v8sim_b6 as B6, v8sim11 as V
cfg = M.cfg_measured(); mk = B6.load_models(); V.cfg_prior()
for u in (0.775, 0.70):
    for tn in ("t3", "t6"):
        r = B6.sim_b6(TR[tn], cfg, u, mk); print(f" sim_b6   u={u} {tn}  SLO {r['slo']:2d}/60 viol {60-r['slo']}  alloc(dispatch) {r['alloc']:.0f}", flush=True)
        for tag, ph in (("R38 on ", None), ("R38 off", {"knee38": 5})):
            r = V.run(TR[tn], "B6", u=u, phys=ph); print(f" v8sim11 {tag} u={u} {tn}  SLO {r['slo']:2d}/60 viol {60-r['slo']} (min {r['viol']})  alloc_vm {r['alloc_vm']:.0f}", flush=True)
print("判讀 §4.116:(a) |Δ alloc_vm| ≤ 2 % 且 |Δ 違規/場| ≤ 2 對 S4b 同 trace 均值(t3 S4b 4.67 min @1137.0;t6 0 @1390.3)")
