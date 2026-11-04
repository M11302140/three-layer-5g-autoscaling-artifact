#!/usr/bin/env python3
"""qsim/s9/equiv.py (spec §4.132 item 1.6): equivalence checks before calibration.
(1) sim_s9(thr=None, w=None) == frozen v8sim10.sim_nest2: 40 random library traces x 3 lambda x 2 accountings = 240 (slo/alloc/ev/traj/pct/permin).
(2) run_s9(thr=None) == v8sim11.run('S'): 6 traces x 2 lambda = 12 (slo/viol/alloc_vm/events).
(3) regime on, three equal lambdas, cond=False, trend off == S4 (nest2 40 x 1 lambda x dispatch; per-slot 6 x 1).
(4) each switch alone changes some traces: per-bucket lambda, conditional sigma, burst trend, R2 (w=1600).  Output s9/out/equiv.txt"""
import sys, os, json, random, numpy as np, time
Q='/home/user/experiment/qsim'; sys.path.insert(0,Q); sys.path.insert(0,Q+'/s9'); os.chdir(Q)
import v8sim2 as S, v8sim7 as M, v8sim10 as Q2, v8sim11 as V
import s9core as C, v8sim11_s9 as W
t0=time.time()
th=json.load(open(f'{Q}/s9/out/thresholds.json')); thr=(th['T50'],th['T85'])
lib=json.load(open(f'{Q}/prior_traces.json')); cfg=M.cfg_measured(); pr=S.Prior(lib,cfg); sp=C.S9Prior(lib,cfg,thr=thr)
print(f"S9Prior built {time.time()-t0:.0f}s thr {thr}",flush=True)
rnd=random.Random(20261027); idx=rnd.sample(range(len(lib)),40)
LS=({"vy":1.83,"wk":1.83,"up":2.00},{"vy":2.83,"wk":2.83,"up":3.08},{"vy":1.0,"wk":1.0,"up":1.5})
def same(a,b): return a['slo']==b['slo'] and a['alloc']==b['alloc'] and a['ev']==b['ev'] and a['traj']==b['traj'] and np.array_equal(a['pct'],b['pct']) and np.array_equal(a['permin'],b['permin'])
f=lambda r:(r['slo'],r['viol'],r['alloc_vm'],r['events'])
lines=[]; ok1=True; n1=0
for L in LS:
    for acct in ('dispatch','vmexist'):
        for i in idx:
            ue=lib[i]["ue"][:60]; s=same(Q2.sim_nest2(ue,cfg,pr,L,acct=acct),C.sim_s9(ue,cfg,sp,L,acct=acct)); ok1&=s; n1+=1
            if not s: lines.append(f"(1) MISMATCH {i} {L} {acct}")
print(f"(1) done {time.time()-t0:.0f}s",flush=True)
V.cfg_prior(); ok2=True; n2=0
for L in LS[:2]:
    for i in idx[:6]:
        ue=lib[i]["ue"][:60]; s=f(V.run(ue,"S",L=L))==f(W.run_s9(ue,L,prior=sp)); ok2&=s; n2+=1
        if not s: lines.append(f"(2) MISMATCH {i} {L}")
L=LS[0]; LB={b:L for b in C.BUCKETS}; ok3=True; n3=0
for i in idx:
    ue=lib[i]["ue"][:60]; s=same(Q2.sim_nest2(ue,cfg,pr,L),C.sim_s9(ue,cfg,sp,None,Lb=LB,thr=thr,cond=False)); ok3&=s; n3+=1
    if not s: lines.append(f"(3) MISMATCH nest2 {i}")
for i in idx[:6]:
    ue=lib[i]["ue"][:60]; s=f(V.run(ue,"S",L=L))==f(W.run_s9(ue,None,Lb=LB,thr=thr,cond=False,prior=sp)); ok3&=s; n3+=1
    if not s: lines.append(f"(3) MISMATCH per-slot {i}")
print(f"(2)(3) done {time.time()-t0:.0f}s",flush=True)
base=lambda i: Q2.sim_nest2(lib[i]["ue"][:60],cfg,pr,L)['ev']
LB2={"calm":{"vy":1.0,"wk":1.0,"up":1.5},"normal":L,"burst":{"vy":3.0,"wk":3.0,"up":3.5}}
d_lb=sum(1 for i in idx if C.sim_s9(lib[i]["ue"][:60],cfg,sp,None,Lb=LB2,thr=thr,cond=False)['ev']!=base(i))
d_c=sum(1 for i in idx if C.sim_s9(lib[i]["ue"][:60],cfg,sp,None,Lb=LB,thr=thr,cond=True)['ev']!=base(i))
d_t=sum(1 for i in idx if C.sim_s9(lib[i]["ue"][:60],cfg,sp,None,Lb=LB,thr=thr,cond=False,trend=True)['ev']!=base(i))
d_w=sum(1 for i in idx if C.sim_s9(lib[i]["ue"][:60],cfg,sp,L,w=1600)['ev']!=base(i))
d_ps=sum(1 for i in idx[:6] if f(W.run_s9(lib[i]["ue"][:60],None,Lb=LB2,thr=thr,trend=True,w=100,prior=sp))!=f(V.run(lib[i]["ue"][:60],"S",L=L)))
regs=[C.sim_s9(lib[i]["ue"][:60],cfg,sp,None,Lb=LB,thr=thr)['reg'] for i in idx]
share={b:sum(r.count(b) for r in regs)/sum(len(r) for r in regs) for b in C.BUCKETS}
hdr=(f"thr T50/T85 = {thr}\n(1) sim_s9 (all off) vs v8sim10.sim_nest2: {n1} cases -> {'IDENTICAL' if ok1 else 'MISMATCH'}\n"
     f"(2) CtlS9 (all off) vs v8sim11.run('S'): {n2} cases -> {'IDENTICAL' if ok2 else 'MISMATCH'}\n"
     f"(3) regime on, equal lambdas, cond off, trend off vs S4: {n3} cases (40 nest2 + 6 per-slot) -> {'IDENTICAL' if ok3 else 'MISMATCH'}\n"
     f"(4) traces changed (of 40): per-bucket lambda {d_lb}, conditional sigma {d_c}, burst trend {d_t}, R2 w=1600 {d_w}; per-slot all on (of 6) {d_ps}\n"
     f"minute regime share on the 40 traces: {share}; total {time.time()-t0:.0f}s")
open(f'{Q}/s9/out/equiv.txt','w').write(hdr+'\n'+'\n'.join(lines)+'\n'); print(hdr); [print(l) for l in lines[:10]]
sys.exit(0 if ok1 and ok2 and ok3 and min(d_lb,d_c,d_t,d_w)>0 else 2)
