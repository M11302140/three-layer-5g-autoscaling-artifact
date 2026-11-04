#!/usr/bin/env python3
"""qsim/s7/equiv.py (spec §4.131 item 6): equivalence checks before calibration.
(1) sim_s7(B=None, w=None) == frozen v8sim10.sim_nest2 on 20 random library traces x 3 lambda x 2 accountings (slo/alloc/ev/traj/pct/permin).
(2) CtlS7(B=None, w=None) == v8sim11.run('S') on 6 traces x 2 lambda (slo/viol/alloc_vm/events).
(3) R1 alone (B=5) and R2 alone (w=1600) each change events on some traces (flags effective).  Output: s7/out/equiv.txt"""
import sys, os, json, random, numpy as np, time
Q='/home/user/experiment/qsim'; sys.path.insert(0,Q); sys.path.insert(0,Q+'/s7'); os.chdir(Q)
import v8sim2 as S, v8sim7 as M, v8sim10 as Q2, v8sim11 as V
import s7core as C, v8sim11_s7 as W
t0=time.time()
lib=json.load(open(f'{Q}/prior_traces.json')); cfg=M.cfg_measured(); pr=S.Prior(lib,cfg); sp=C.S7Prior(lib,cfg)
print(f"S7Prior built {time.time()-t0:.0f}s",flush=True)
rnd=random.Random(20261020); idx=rnd.sample(range(len(lib)),20)
LS=({"vy":1.83,"wk":1.83,"up":2.00},{"vy":2.83,"wk":2.83,"up":3.08},{"vy":1.0,"wk":1.0,"up":1.5})
def same(a,b): return a['slo']==b['slo'] and a['alloc']==b['alloc'] and a['ev']==b['ev'] and a['traj']==b['traj'] and np.array_equal(a['pct'],b['pct']) and np.array_equal(a['permin'],b['permin'])
ok1=True; n1=0; lines=[]
for L in LS:
    for acct in ('dispatch','vmexist'):
        for i in idx:
            ue=lib[i]["ue"][:60]; r0=Q2.sim_nest2(ue,cfg,pr,L,acct=acct); r1=C.sim_s7(ue,cfg,sp,L,acct=acct); s=same(r0,r1); ok1&=s; n1+=1
            if not s: lines.append(f"(1) MISMATCH {i} {L} {acct}")
V.cfg_prior(); ok2=True; n2=0
f=lambda r:(r['slo'],r['viol'],r['alloc_vm'],r['events'])
for L in LS[:2]:
    for i in idx[:6]:
        ue=lib[i]["ue"][:60]; a=V.run(ue,"S",L=L); b=W.run_s7(ue,L,prior=sp); s=f(a)==f(b); ok2&=s; n2+=1
        if not s: lines.append(f"(2) MISMATCH {i} {L}")
L=LS[0]
d1=sum(1 for i in idx if C.sim_s7(lib[i]["ue"][:60],cfg,sp,L,B=5)['ev']!=Q2.sim_nest2(lib[i]["ue"][:60],cfg,pr,L)['ev'])
d2=sum(1 for i in idx if C.sim_s7(lib[i]["ue"][:60],cfg,sp,L,w=1600)['ev']!=Q2.sim_nest2(lib[i]["ue"][:60],cfg,pr,L)['ev'])
d3=sum(1 for i in idx[:6] if f(W.run_s7(lib[i]["ue"][:60],L,B=5,w=100,prior=sp))!=f(V.run(lib[i]["ue"][:60],"S",L=L)))
hdr=(f"(1) sim_s7 (rules off) vs v8sim10.sim_nest2: {n1} cases -> {'IDENTICAL' if ok1 else 'MISMATCH'}\n"
     f"(2) CtlS7 (rules off) vs v8sim11.run('S'): {n2} cases -> {'IDENTICAL' if ok2 else 'MISMATCH'}\n"
     f"(3) traces changed (of 20): R1 B=5 {d1}, R2 w=1600 {d2}; per-slot B=5,w=100 (of 6) {d3}\n"
     f"sanity: P(R_up>2 | D=20) {sp.p_exceed('up',20,2):.3f}, P(R_wk>2 | D=20) {sp.p_exceed('wk',20,2):.3f}, E_T(D=20,h=2) {sp.e_t(20,2):.0f}s, E_T(D=20,h=10) {sp.e_t(20,10):.0f}s")
open(f'{Q}/s7/out/equiv.txt','w').write(hdr+'\n'+'\n'.join(lines)+'\n'); print(hdr); [print(l) for l in lines[:10]]
sys.exit(0 if ok1 and ok2 and d1>0 and d2>0 else 2)
