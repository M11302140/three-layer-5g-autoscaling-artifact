#!/usr/bin/env python3
"""qsim/s6/predict.py (spec §4.127 §2 G2 + registration): predictions on t9/t10 (and t1-t8 for reference) for
 S6a/S6b (deployed lambda/ws from s6/gates.py; sigma_res from the whole library; release Lr = deployed S4a/S4b):
   fleet-level s6core.sim_s6 (vmexist = alloc_vm, and dispatch) and per-slot v8sim11_s6.run_s6, start = own convergence;
 v6: v8sim2.sim_v6 (fleet) and v8sim11.run('v6'); B6 u=0.70: v8sim_b6.sim_b6 (fleet) and v8sim11.run('B6');
 B4c2, B5c1: v8sim11.run only (no fleet-level simulator exists).  Same conventions as the t6/t7 and t8 registrations.
Usage: python3 s6/predict.py <lamVM_a> <lamUP_a> <ws_a> <lamVM_b> <lamUP_b> <ws_b>  -> s6/out/predict.json, predict.txt (G2 verdict)"""
import sys, os, json, time
Q='/home/user/experiment/qsim'; sys.path.insert(0,Q); sys.path.insert(0,Q+'/s6'); os.chdir(Q)
import s6core as C, v8sim11_s6 as W, v8sim7 as M, v8sim2 as S, v8sim11 as V, v8sim_b6 as B6
E='/home/user/experiment'
TR={'t9':'t9','t10':'t10','t1':'40','t2':'pm','t3':'t3','t4':'t4','t5':'t5','t6':'t6','t7':'t7','t8':'t8'}
a=[float(x) for x in sys.argv[1:7]]
P={'S6a':({'vy':a[0],'wk':a[0],'up':a[1]},int(a[2]),V.LAM['S4a']),'S6b':({'vy':a[3],'wk':a[3],'up':a[4]},int(a[5]),V.LAM['S4b'])}
lib=json.load(open(f'{Q}/prior_traces.json')); cfg=M.cfg_measured(); tp=C.TPrior(lib,cfg); V.cfg_prior(); mk=B6.load_models()
out={'time':time.strftime('%F %T'),'params':{k:dict(L=v[0],ws=v[1],Lr=v[2]) for k,v in P.items()},'rows':{}}
lines=[f"=== S6 predictions {out['time']}  S6a L {P['S6a'][0]['vy']}/{P['S6a'][0]['up']} ws {P['S6a'][1]} (Lr 2.83/3.08)  S6b L {P['S6b'][0]['vy']}/{P['S6b'][0]['up']} ws {P['S6b'][1]} (Lr 1.83/2.00)",
       "| trace | arm | fleet-level SLO | fleet viol | fleet cost (alloc_vm; S6 vmexist) | S6 dispatch | per-slot SLO | per-slot viol | per-slot alloc_vm |","|---|---|---|---|---|---|---|---|---|"]
def P_(s): print(s,flush=True); lines.append(s)
for l in lines: print(l)
for tn,f in TR.items():
    ue=json.load(open(f"{E}/trace_ue_60min_v3_{f}.json"))["ue"][:60]
    for arm,(L,ws,Lr) in P.items():
        rv=C.sim_s6(ue,cfg,tp,L,Lr=Lr,ws=ws,acct='vmexist'); rd=C.sim_s6(ue,cfg,tp,L,Lr=Lr,ws=ws,acct='dispatch'); rs=W.run_s6(ue,L,Lr=Lr,ws=ws,prior=tp)
        out['rows'][f'{tn}|{arm}']=dict(fl_slo=rv['slo'],fl_cost=rv['alloc'],fl_dispatch=rd['alloc'],ps_slo=rs['slo'],ps_viol=rs['viol'],ps_cost=rs['alloc_vm'])
        P_(f"| {tn} | {arm} | {rv['slo']}/60 | {60-rv['slo']} | {rv['alloc']:.0f} | {rd['alloc']:.0f} | {rs['slo']}/60 | {rs['viol']} | {rs['alloc_vm']:.0f} |")
    r6=S.sim_v6(ue,cfg); rs=V.run(ue,'v6'); out['rows'][f'{tn}|v6']=dict(fl_slo=r6['slo'],fl_cost=r6['alloc'],ps_slo=rs['slo'],ps_viol=rs['viol'],ps_cost=rs['alloc_vm'])
    P_(f"| {tn} | v6 | {r6['slo']}/60 | {60-r6['slo']} | {r6['alloc']:.0f} (sim_v6) | | {rs['slo']}/60 | {rs['viol']} | {rs['alloc_vm']:.0f} |")
    rb=B6.sim_b6(ue,cfg,0.70,mk); rs=V.run(ue,'B6'); out['rows'][f'{tn}|B6']=dict(fl_slo=rb['slo'],fl_cost=rb['alloc'],ps_slo=rs['slo'],ps_viol=rs['viol'],ps_cost=rs['alloc_vm'])
    P_(f"| {tn} | B6 | {rb['slo']}/60 | {60-rb['slo']} | {rb['alloc']:.0f} (sim_b6) | | {rs['slo']}/60 | {rs['viol']} | {rs['alloc_vm']:.0f} |")
    for arm in ('B4c2','B5c1'):
        rs=V.run(ue,arm); out['rows'][f'{tn}|{arm}']=dict(ps_slo=rs['slo'],ps_viol=rs['viol'],ps_cost=rs['alloc_vm'])
        P_(f"| {tn} | {arm} | (none) | | | | {rs['slo']}/60 | {rs['viol']} | {rs['alloc_vm']:.0f} |")
# G2 (registered): per test trace; viol = 60 - SLO minutes
r=out['rows']; g2={}
for tn in ('t9','t10'):
    s6b=r[f'{tn}|S6b']; s6a=r[f'{tn}|S6a']; ok=[]; why=[]
    for base in ('B4c2','B5c1','B6'):
        b=r[f'{tn}|{base}']
        if base=='B6': pairs=[('fleet',60-s6b['fl_slo'],s6b['fl_cost'],60-b['fl_slo'],b['fl_cost']),('per-slot',60-s6b['ps_slo'],s6b['ps_cost'],60-b['ps_slo'],b['ps_cost'])]
        else: pairs=[('fleet vs per-slot',60-s6b['fl_slo'],s6b['fl_cost'],60-b['ps_slo'],b['ps_cost']),('per-slot',60-s6b['ps_slo'],s6b['ps_cost'],60-b['ps_slo'],b['ps_cost'])]
        for nm,sv,sc,bv,bc in pairs:
            o1=sv<=bv; o2=sc<=1.02*bc; ok+= [o1,o2]
            why.append(f"S6b vs {base} [{nm}]: viol {sv} <= {bv} {'ok' if o1 else 'FAIL'}; cost {sc:.0f} <= 1.02x{bc:.0f}={1.02*bc:.0f} {'ok' if o2 else 'FAIL'}")
    b=r[f'{tn}|B6']
    for nm,sv,bv in (('fleet',60-s6a['fl_slo'],60-b['fl_slo']),('per-slot',60-s6a['ps_slo'],60-b['ps_slo'])):
        o=sv<=bv; ok.append(o); why.append(f"S6a vs B6 [{nm}]: viol {sv} <= {bv} {'ok' if o else 'FAIL'}")
    g2[tn]=(all(ok),why)
P_("")
for tn,(o,why) in g2.items():
    P_(f"G2 {tn}: {'PASS' if o else 'FAIL'}"); [P_("  "+w) for w in why]
P_(f"G2 overall: {'PASS' if all(o for o,_ in g2.values()) else 'FAIL'}")
out['g2']={tn:dict(passed=o,detail=why) for tn,(o,why) in g2.items()}
json.dump(out,open(f'{Q}/s6/out/predict.json','w'),indent=1,default=str); open(f'{Q}/s6/out/predict.txt','w').write("\n".join(lines)+"\n")
