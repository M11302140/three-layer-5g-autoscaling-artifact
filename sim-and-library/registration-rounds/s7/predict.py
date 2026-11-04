#!/usr/bin/env python3
"""qsim/s7/predict.py (spec §4.131 G2, G3(ii) + registration): deployed S7a/S7b (s7/out/gates.json; tables from the whole library) on t1-t10:
fleet-level s7core.sim_s7 (vmexist, dispatch) and per-slot v8sim11_s7.run_s7 (frozen v8sim11 physics, its default PHYS), S start = own convergence;
B5c1 per-slot v8sim11.run('B5c1') (no fleet-level simulator).  G2: t4 S7b per-slot violation minutes < 2.33; t6/t7 S7b 60/60 in both simulators
and cost (fleet vmexist, per-slot) <= B5c1 per-slot cost x 1.00.  G3 (ii): S7b with R1 off (B=None, rest unchanged) on t4 per-slot -> violations
higher than with R1.  Output s7/out/predict.json, predict.txt"""
import sys, os, json, time
Q='/home/user/experiment/qsim'; sys.path.insert(0,Q); sys.path.insert(0,Q+'/s7'); os.chdir(Q)
import s7core as C, v8sim11_s7 as W, v8sim7 as M, v8sim11 as V
E='/home/user/experiment'
TR={'t4':'t4','t6':'t6','t7':'t7','t1':'40','t2':'pm','t3':'t3','t5':'t5','t8':'t8','t9':'t9','t10':'t10'}
g=json.load(open(f'{Q}/s7/out/gates.json'))['deployed']
lib=json.load(open(f'{Q}/prior_traces.json')); cfg=M.cfg_measured(); sp=C.S7Prior(lib,cfg); V.cfg_prior()
L=lambda d:{'vy':d['a'],'wk':d['a'],'up':d['b']}
out={'time':time.strftime('%F %T'),'deployed':g,'rows':{}}; lines=[f"=== S7 predictions {out['time']} S7a {g['S7a']} | S7b {g['S7b']}",
 "| trace | arm | fleet SLO | fleet cost (vmexist) | dispatch | per-slot SLO | per-slot viol | per-slot cost |","|---|---|---|---|---|---|---|---|"]
def P_(s): print(s,flush=True); lines.append(s)
for l in lines: print(l)
for tn,f in TR.items():
    ue=json.load(open(f"{E}/trace_ue_60min_v3_{f}.json"))["ue"][:60]
    for arm in ('S7a','S7b'):
        d=g[arm]; rv=C.sim_s7(ue,cfg,sp,L(d),B=d['B'],w=d['w'],acct='vmexist'); rd=C.sim_s7(ue,cfg,sp,L(d),B=d['B'],w=d['w'],acct='dispatch'); rs=W.run_s7(ue,L(d),B=d['B'],w=d['w'],prior=sp)
        out['rows'][f'{tn}|{arm}']=dict(fl_slo=rv['slo'],fl_cost=rv['alloc'],fl_disp=rd['alloc'],ps_slo=rs['slo'],ps_viol=rs['viol'],ps_cost=rs['alloc_vm'])
        P_(f"| {tn} | {arm} | {rv['slo']}/60 | {rv['alloc']:.0f} | {rd['alloc']:.0f} | {rs['slo']}/60 | {rs['viol']} | {rs['alloc_vm']:.0f} |")
    rs=V.run(ue,'B5c1'); out['rows'][f'{tn}|B5c1']=dict(ps_slo=rs['slo'],ps_viol=rs['viol'],ps_cost=rs['alloc_vm'])
    P_(f"| {tn} | B5c1 | (none) | | | {rs['slo']}/60 | {rs['viol']} | {rs['alloc_vm']:.0f} |")
r=out['rows']; d=g['S7b']
t4v=60-r['t4|S7b']['ps_slo']; g2a=t4v<2.33
g2b={tn:(r[f'{tn}|S7b']['fl_slo']==60 and r[f'{tn}|S7b']['ps_slo']==60 and r[f'{tn}|S7b']['fl_cost']<=r[f'{tn}|B5c1']['ps_cost'] and r[f'{tn}|S7b']['ps_cost']<=r[f'{tn}|B5c1']['ps_cost']) for tn in ('t6','t7')}
ue4=json.load(open(f"{E}/trace_ue_60min_v3_t4.json"))["ue"][:60]; abl=W.run_s7(ue4,L(d),B=None,w=d['w'],prior=sp); g3b=(60-abl['slo'])>t4v
P_(""); P_(f"G2 t4: S7b per-slot violation minutes {t4v} < 2.33 -> {'PASS' if g2a else 'FAIL'}")
for tn in ('t6','t7'): P_(f"G2 {tn}: S7b fleet {r[f'{tn}|S7b']['fl_slo']}/60 cost {r[f'{tn}|S7b']['fl_cost']:.0f}, per-slot {r[f'{tn}|S7b']['ps_slo']}/60 cost {r[f'{tn}|S7b']['ps_cost']:.0f} vs B5c1 per-slot {r[f'{tn}|B5c1']['ps_cost']:.0f} -> {'PASS' if g2b[tn] else 'FAIL'}")
P_(f"G2: {'PASS' if (g2a and all(g2b.values())) else 'FAIL'}")
P_(f"G3 (ii) ablation R1 off on t4 per-slot: violations {60-abl['slo']} vs {t4v} with R1 -> {'PASS (rises)' if g3b else 'FAIL (does not rise)'}")
out['g2']=dict(t4=g2a,t6t7=g2b); out['g3_ii']=dict(passed=g3b,off=60-abl['slo'],on=t4v)
json.dump(out,open(f'{Q}/s7/out/predict.json','w'),indent=1,default=str); open(f'{Q}/s7/out/predict.txt','w').write("\n".join(lines)+"\n")
