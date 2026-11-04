#!/usr/bin/env python3
"""qsim/s4t/equiv.py (spec §4.133 item 2): k3 = None == frozen S4: sim_s4t vs v8sim10.sim_nest2 (40 traces x 3 lambda x 2 accountings = 240)
and run_s4t vs v8sim11.run('S') (6 x 2 = 12); k3 = 4/5/6 change some traces. Output s4t/out/equiv.txt"""
import sys, os, json, random, numpy as np, time
Q='/home/user/experiment/qsim'; sys.path.insert(0,Q); sys.path.insert(0,Q+'/s4t'); os.chdir(Q)
import v8sim2 as S, v8sim7 as M, v8sim10 as Q2, v8sim11 as V
import s4tcore as C, v8sim11_s4t as W
t0=time.time(); lib=json.load(open(f'{Q}/prior_traces.json')); cfg=M.cfg_measured(); pr=S.Prior(lib,cfg)
rnd=random.Random(20261027); idx=rnd.sample(range(len(lib)),40)
LS=({"vy":1.83,"wk":1.83,"up":2.00},{"vy":2.83,"wk":2.83,"up":3.08},{"vy":1.0,"wk":1.0,"up":1.5})
def same(a,b): return a['slo']==b['slo'] and a['alloc']==b['alloc'] and a['ev']==b['ev'] and a['traj']==b['traj'] and np.array_equal(a['pct'],b['pct']) and np.array_equal(a['permin'],b['permin'])
f=lambda r:(r['slo'],r['viol'],r['alloc_vm'],r['events'])
lines=[]; ok1=True; n1=0
for L in LS:
    for acct in ('dispatch','vmexist'):
        for i in idx:
            ue=lib[i]["ue"][:60]; s=same(Q2.sim_nest2(ue,cfg,pr,L,acct=acct),C.sim_s4t(ue,cfg,pr,L,acct=acct)); ok1&=s; n1+=1
            if not s: lines.append(f"(1) MISMATCH {i} {L} {acct}")
V.cfg_prior(); ok2=True; n2=0
for L in LS[:2]:
    for i in idx[:6]:
        ue=lib[i]["ue"][:60]; s=f(V.run(ue,"S",L=L))==f(W.run_s4t(ue,L,prior=pr)); ok2&=s; n2+=1
        if not s: lines.append(f"(2) MISMATCH {i} {L}")
L=LS[0]; ch={}
for k in (4,5,6):
    ch[k]=(sum(1 for i in idx if C.sim_s4t(lib[i]["ue"][:60],cfg,pr,L,k3=k)['ev']!=Q2.sim_nest2(lib[i]["ue"][:60],cfg,pr,L)['ev']),
           sum(1 for i in idx[:6] if f(W.run_s4t(lib[i]["ue"][:60],L,k3=k,prior=pr))!=f(V.run(lib[i]["ue"][:60],"S",L=L))))
hdr=(f"(1) sim_s4t (k3=None) vs v8sim10.sim_nest2: {n1} cases -> {'IDENTICAL' if ok1 else 'MISMATCH'}\n"
     f"(2) CtlS4T (k3=None) vs v8sim11.run('S'): {n2} cases -> {'IDENTICAL' if ok2 else 'MISMATCH'}\n"
     f"(3) traces changed with R3 on (fleet of 40, per-slot of 6): {ch}; {time.time()-t0:.0f}s")
open(f'{Q}/s4t/out/equiv.txt','w').write(hdr+'\n'+'\n'.join(lines)+'\n'); print(hdr); [print(l) for l in lines[:10]]
sys.exit(0 if ok1 and ok2 and any(v[0]>0 for v in ch.values()) else 2)
