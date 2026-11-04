#!/usr/bin/env python3
"""spec §4.136 item 3 equivalence: (1) nest2gen.sim_s7 variants full / independent_full / fixed_dwell (B=None, w=None) == frozen v8sim10_abl.sim_nest2
on 20 library traces (slo/alloc/ev/traj/pct/permin, dispatch and vmexist); (2) CtlGen all flags off == v8sim11.CtlSigma, R38 off, 20 traces (slo/viol/alloc_vm/events);
CtlGen(w=1600) == s7 CtlS7(B=None, w=1600) on 6 traces; (3) 'apl' changes some traces in both. Output out/equiv.txt"""
import timeit  # noqa
import sys, os, json, random, numpy as np
Q='/home/user/experiment/qsim'; sys.path.insert(0,Q); sys.path.insert(0,Q+'/r68unif'); sys.path.insert(0,Q+'/s7'); sys.path.insert(0,Q+'/r67band'); os.chdir(Q)
import v8sim2 as S, v8sim7 as M, v8sim10_abl as A, v8sim11 as V
import nest2gen as G, ctlgen as CG, s7core as C7, v8sim11_s7 as W7, run as RB
lib=json.load(open(f'{Q}/prior_traces.json')); cfg=M.cfg_measured(); pr=S.Prior(lib,cfg); idx=random.Random(20261027).sample(range(len(lib)),20)
L={"vy":1.83,"wk":1.83,"up":2.00}
def same(a,b): return a['slo']==b['slo'] and a['alloc']==b['alloc'] and a['ev']==b['ev'] and a['traj']==b['traj'] and np.array_equal(a['pct'],b['pct']) and np.array_equal(a['permin'],b['permin'])
ok1=True; n1=0
for var in ('full','independent_full','fixed_dwell'):
    for acct in ('dispatch','vmexist'):
        for i in idx:
            ue=lib[i]["ue"][:60]; s_=same(A.sim_nest2(ue,cfg,pr,L,variant=var,acct=acct),G.sim_s7(ue,cfg,pr,L,variant=var,acct=acct)); ok1&=s_; n1+=1
d_apl=sum(1 for i in idx if G.sim_s7(lib[i]["ue"][:60],cfg,pr,L,variant='apl')['ev']!=A.sim_nest2(lib[i]["ue"][:60],cfg,pr,L,variant='independent_full')['ev'])
cfgV,prV=V.cfg_prior(); f=lambda r:(r['slo'],r['viol'],r['alloc_vm'],r['events']); ok2=True; n2=0
for i in idx:
    ue=lib[i]["ue"][:60]; st=V.initial_fleet("S",ue[0],L=L)
    a=RB.run_ctl(ue,V.CtlSigma(cfgV,prV,L),st); b=RB.run_ctl(ue,CG.CtlGen(cfgV,prV,L),st); s_=f(a)==f(b); ok2&=s_; n2+=1
sp=C7.S7Prior(lib,cfgV); ok3=True
for i in idx[:6]:
    ue=lib[i]["ue"][:60]; st=V.initial_fleet("S",ue[0],L=L)
    a=RB.run_ctl(ue,W7.CtlS7(cfgV,sp,L,B=None,w=1600),st); b=RB.run_ctl(ue,CG.CtlGen(cfgV,sp,L,w=1600),st); ok3&=f(a)==f(b)
d_ps=sum(1 for i in idx if f(RB.run_ctl(lib[i]["ue"][:60],CG.CtlGen(cfgV,prV,L,indep=True,indep_rel=True,plain=True),V.initial_fleet("S",lib[i]["ue"][0],L=L)))!=f(RB.run_ctl(lib[i]["ue"][:60],V.CtlSigma(cfgV,prV,L),V.initial_fleet("S",lib[i]["ue"][0],L=L))))
txt=(f"(1) nest2gen variants full/independent_full/fixed_dwell vs frozen v8sim10_abl.sim_nest2: {n1} cases -> {'IDENTICAL' if ok1 else 'MISMATCH'}; 'apl' differs from independent_full on {d_apl}/20\n"
     f"(2) CtlGen (flags off) vs v8sim11.CtlSigma, R38 off: {n2} cases -> {'IDENTICAL' if ok2 else 'MISMATCH'}; CtlGen(w=1600) vs CtlS7(B=None, w=1600): 6 cases -> {'IDENTICAL' if ok3 else 'MISMATCH'}; per-slot A-PL differs on {d_ps}/20")
print(txt); open(f'{Q}/r68unif/out/equiv.txt','w').write(txt+"\n"); sys.exit(0 if ok1 and ok2 and ok3 and d_apl>0 and d_ps>0 else 2)
