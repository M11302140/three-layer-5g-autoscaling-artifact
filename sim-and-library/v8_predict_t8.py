#!/usr/bin/env python3
"""(docstring removed)"""
import json, sys, time
sys.path.insert(0, '/home/user/experiment/qsim')
E = '/home/user/experiment'
ue = json.load(open(f"{E}/trace_ue_60min_v3_t8.json"))["ue"][:60]
print(f"=== t8 登記預測 {time.strftime('%F %T')}  peakUE={max(ue)} UE0={ue[0]}")
import v8sim10 as M10
LAM = {"S4a": {"vy": 2.83, "wk": 2.83, "up": 3.08}, "S4b": {"vy": 1.83, "wk": 1.83, "up": 2.00}}
lib = json.load(open(f"{E}/qsim/prior_traces.json")); cfg = M10.M.cfg_measured(); pr = M10.S.Prior(lib, cfg)
print("[fleet-level]")
for grp in ("S4a", "S4b"):
    r = M10.sim_nest2(ue, cfg, pr, LAM[grp]); rv = M10.sim_nest2(ue, cfg, pr, LAM[grp], acct='vmexist')
    print(f" {grp} nest2  SLO {r['slo']:2d}/60  viol {60-r['slo']}  alloc_vmexist(登記) {rv['alloc']:.0f}  dispatch {r['alloc']:.0f}", flush=True)
import v8sim2 as S, v8sim7 as M
cfg2 = M.cfg_measured()
r = S.sim_v6(ue, cfg2); print(f" v6 sim_v6  SLO {r['slo']:2d}/60  viol {60-r['slo']}  alloc {r['alloc']:.0f}", flush=True)
import v8sim_b6 as B6
mk = B6.load_models(); r = B6.sim_b6(ue, cfg2, 0.70, mk); print(f" B6u70 sim_b6  SLO {r['slo']:2d}/60  viol {60-r['slo']}  alloc {r['alloc']:.0f}", flush=True)
print("[per-slot v8sim11]")
import v8sim11 as V
V.cfg_prior()
for arm in ("S4a", "S4b", "v6", "B6"):
    r = V.run(ue, arm); print(f" {arm} v8sim11  SLO {r['slo']:2d}/60  viol {60-r['slo']} (min {r['viol']})  alloc_vm {r['alloc_vm']:.0f}", flush=True)
print("違規閘(§4.17 比率換算 2 場 = 120 分):S4a ≤ 1/120、S4b ≤ 4/120;無同事件連續 ≥3 分鐘(僅報告)")
