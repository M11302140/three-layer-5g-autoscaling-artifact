#!/usr/bin/env python3
"""qsim/s9/predict.py (spec §4.132 G2, G4 + registration): deployed S9a/S9b (s9/out/gates.json; tables from the whole library) on t1-t10:
fleet-level s9core.sim_s9 (vmexist, dispatch) and per-slot v8sim11_s9.run_s9 (frozen v8sim11 physics), S start = own convergence.
G2 (S9b, each simulator): violation minutes t3 <= 4.0, t4 <= 1.8, t8 <= 1.5; t6/t7 60/60 and cost <= B5c1 hardware alloc_vm (1433 / 1413); t1/t2 >= 58/60.
G4 (S9b): (a) burst trend off -> t4 per-slot violations higher; (b) regime off (force normal, normal lambda and conditional sigma, no trend)
-> in either simulator t3 or t8 violations higher, or t6 or t7 cost higher.  t9/t10 are listed (development-like, not in any gate).
Output s9/out/predict.json, predict.txt"""
import sys, os, json, time
Q='/home/user/experiment/qsim'; sys.path.insert(0,Q); sys.path.insert(0,Q+'/s9'); os.chdir(Q)
import s9core as C, v8sim11_s9 as W, v8sim7 as M, v8sim11 as V
E='/home/user/experiment'
TR={'t1':'40','t2':'pm','t3':'t3','t4':'t4','t5':'t5','t6':'t6','t7':'t7','t8':'t8','t9':'t9','t10':'t10'}
B5HW={'t6':1433,'t7':1413}; VMAX={'t3':4.0,'t4':1.8,'t8':1.5}
g=json.load(open(f'{Q}/s9/out/gates.json'))['deployed']; th=json.load(open(f'{Q}/s9/out/thresholds.json')); thr=(th['T50'],th['T85'])
lib=json.load(open(f'{Q}/prior_traces.json')); cfg=M.cfg_measured(); sp=C.S9Prior(lib,cfg,thr=thr); V.cfg_prior()
LB=lambda d:{b:{'vy':d['Lb'][b][0],'wk':d['Lb'][b][0],'up':d['Lb'][b][1]} for b in C.BUCKETS}
ue_of=lambda tn: json.load(open(f"{E}/trace_ue_60min_v3_{TR[tn]}.json"))["ue"][:60]
def fl(ue,d,**kw):
    rv=C.sim_s9(ue,cfg,sp,None,Lb=LB(d),thr=thr,trend=kw.get('trend',True),w=d['w'],acct='vmexist',force_reg=kw.get('force')); rd=C.sim_s9(ue,cfg,sp,None,Lb=LB(d),thr=thr,trend=kw.get('trend',True),w=d['w'],acct='dispatch',force_reg=kw.get('force'))
    return rv,rd
def ps(ue,d,**kw): return W.run_s9(ue,None,Lb=LB(d),thr=thr,trend=kw.get('trend',True),w=d['w'],force_reg=kw.get('force'),prior=sp)
out={'time':time.strftime('%F %T'),'deployed':g,'rows':{}}
lines=[f"=== S9 predictions {out['time']} S9a {g['S9a']} | S9b {g['S9b']}","| trace | arm | fleet SLO | fleet vmexist | dispatch | per-slot SLO | per-slot viol minutes | per-slot cost | burst minutes |","|---|---|---|---|---|---|---|---|---|"]
def P_(s): print(s,flush=True); lines.append(s)
for l in lines: print(l)
for tn in TR:
    ue=ue_of(tn)
    for arm in ('S9a','S9b'):
        d=g[arm]; rv,rd=fl(ue,d); rs=ps(ue,d)
        out['rows'][f'{tn}|{arm}']=dict(fl_slo=rv['slo'],fl_cost=rv['alloc'],fl_disp=rd['alloc'],ps_slo=rs['slo'],ps_viol=rs['viol'],ps_cost=rs['alloc_vm'],burst=rv['reg'].count('burst'))
        P_(f"| {tn} | {arm} | {rv['slo']}/60 | {rv['alloc']:.0f} | {rd['alloc']:.0f} | {rs['slo']}/60 | {rs['viol']} | {rs['alloc_vm']:.0f} | {rv['reg'].count('burst')} |")
r=out['rows']; v=lambda tn,s: 60-r[f'{tn}|S9b'][s]
g2={}
for tn,mx in VMAX.items(): g2[tn]=v(tn,'fl_slo')<=mx and v(tn,'ps_slo')<=mx
for tn in ('t6','t7'): g2[tn]=r[f'{tn}|S9b']['fl_slo']==60 and r[f'{tn}|S9b']['ps_slo']==60 and r[f'{tn}|S9b']['fl_cost']<=B5HW[tn] and r[f'{tn}|S9b']['ps_cost']<=B5HW[tn]
for tn in ('t1','t2'): g2[tn]=r[f'{tn}|S9b']['fl_slo']>=58 and r[f'{tn}|S9b']['ps_slo']>=58
P_("")
for tn,ok in g2.items(): P_(f"G2 {tn}: fleet {r[f'{tn}|S9b']['fl_slo']}/60 cost {r[f'{tn}|S9b']['fl_cost']:.0f}, per-slot {r[f'{tn}|S9b']['ps_slo']}/60 cost {r[f'{tn}|S9b']['ps_cost']:.0f} -> {'PASS' if ok else 'FAIL'}")
P_(f"G2: {'PASS' if all(g2.values()) else 'FAIL'}")
d=g['S9b']; a=ps(ue_of('t4'),d,trend=False); g4a=(60-a['slo'])>v('t4','ps_slo')
P_(f"G4 (a) trend off, t4 per-slot: violations {60-a['slo']} {a['viol']} vs {v('t4','ps_slo')} with trend -> {'PASS (rises)' if g4a else 'FAIL'}")
dN=dict(d); dN['Lb']={b:d['Lb']['normal'] for b in C.BUCKETS}; b4={}
for tn in ('t3','t8','t6','t7'):
    rv,_=fl(ue_of(tn),dN,trend=False,force='normal'); rs=ps(ue_of(tn),dN,trend=False,force='normal')
    b4[tn]=dict(fl_viol=60-rv['slo'],fl_cost=rv['alloc'],ps_viol=60-rs['slo'],ps_cost=rs['alloc_vm'])
    P_(f"G4 (b) regime off, {tn}: fleet viol {60-rv['slo']} cost {rv['alloc']:.0f} | per-slot viol {60-rs['slo']} cost {rs['alloc_vm']:.0f}  (S9b: fleet {v(tn,'fl_slo')} / {r[f'{tn}|S9b']['fl_cost']:.0f}, per-slot {v(tn,'ps_slo')} / {r[f'{tn}|S9b']['ps_cost']:.0f})")
g4b=any(b4[tn]['fl_viol']>v(tn,'fl_slo') or b4[tn]['ps_viol']>v(tn,'ps_slo') for tn in ('t3','t8')) or any(b4[tn]['fl_cost']>r[f'{tn}|S9b']['fl_cost'] or b4[tn]['ps_cost']>r[f'{tn}|S9b']['ps_cost'] for tn in ('t6','t7'))
P_(f"G4 (b): {'PASS' if g4b else 'FAIL'}; G4: {'PASS' if (g4a and g4b) else 'FAIL'}")
out['g2']=g2; out['g4']=dict(a=g4a,b=g4b,abl_a=dict(viol=60-a['slo']),abl_b=b4)
json.dump(out,open(f'{Q}/s9/out/predict.json','w'),indent=1,default=str); open(f'{Q}/s9/out/predict.txt','w').write("\n".join(lines)+"\n")
