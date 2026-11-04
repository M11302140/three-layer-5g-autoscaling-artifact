#!/usr/bin/env python3
"""qsim/s6/equiv.py (spec §4.127 item 7): equivalence checks that must pass before calibration.
(1) sim_s6(margin='sigma') == frozen v8sim10.sim_nest2 on 20 random library traces x 3 lambda sets x 2 accountings (slo/alloc/ev/traj/pct/permin).
(2) trend code path with slope forced to 0 and sigma_res tables replaced by sigma(win) == frozen v8sim10.sim_nest2 (same grid).
(3) v8sim11_s6.CtlS6 trend=False == v8sim11.run('S') on 6 traces x 2 lambda sets (slo/viol/alloc_vm/events); and (2)-style patch for the trend path.
(4) trend on (ws 3 and 5, Lr = L) differs from S4 on some traces (flag effective).  Output: s6/out/equiv.txt"""
import sys, os, json, random, numpy as np, copy
Q='/home/user/experiment/qsim'; sys.path.insert(0,Q); sys.path.insert(0,Q+'/s6'); os.chdir(Q)
import v8sim2 as S, v8sim7 as M, v8sim10 as Q2, v8sim11 as V
import s6core as C, v8sim11_s6 as W
lib=json.load(open(f'{Q}/prior_traces.json')); cfg=M.cfg_measured(); pr=S.Prior(lib,cfg); tp=C.TPrior(lib,cfg)
rnd=random.Random(20261020); idx=rnd.sample(range(len(lib)),20)
LS=({"vy":1.83,"wk":1.83,"up":2.00},{"vy":2.83,"wk":2.83,"up":3.08},{"vy":1.0,"wk":1.0,"up":1.5})
def same(a,b): return a['slo']==b['slo'] and a['alloc']==b['alloc'] and a['ev']==b['ev'] and a['traj']==b['traj'] and np.array_equal(a['pct'],b['pct']) and np.array_equal(a['permin'],b['permin'])
# patched prior: residual tables := sigma(win) tables
tz=copy.copy(tp); tz.sig=dict(tp.sig)
for W_ in (3,5):
    for k in cfg.h: tz.sig[(f"res{W_}",k)]=tp.sig[("win",k)]; tz.sig[(f"res{W_}",k,'all')]=tp.sig[("win",k,'all')]
lines=[]; n1=n2=0; ok1=ok2=True
for L in LS:
    for acct in ('dispatch','vmexist'):
        for i in idx:
            ue=lib[i]["ue"][:60]; r0=Q2.sim_nest2(ue,cfg,pr,L,acct=acct)
            r1=C.sim_s6(ue,cfg,tp,L,acct=acct,margin='sigma'); s1=same(r0,r1); ok1&=s1; n1+=1
            if not s1: lines.append(f"(1) MISMATCH trace {i} L {L} {acct}")
            orig=C.slope; C.slope=lambda v: 0.0
            try: r2=C.sim_s6(ue,cfg,tz,L,acct=acct,margin='trend',ws=3)
            finally: C.slope=orig
            s2=same(r0,r2); ok2&=s2; n2+=1
            if not s2: lines.append(f"(2) MISMATCH trace {i} L {L} {acct}")
V.cfg_prior(); ok3=ok3b=True; n3=0
for L in LS[:2]:
    for i in idx[:6]:
        ue=lib[i]["ue"][:60]; a=V.run(ue,"S",L=L)
        b=W.run_s6(ue,L,trend=False,prior=V.cfg_prior()[1])
        f=lambda r:(r['slo'],r['viol'],r['alloc_vm'],r['events'])
        s3=f(a)==f(b); ok3&=s3; n3+=1
        if not s3: lines.append(f"(3) MISMATCH trace {i} L {L}")
        orig=C.slope; C.slope=lambda v: 0.0
        try: c=W.run_s6(ue,L,trend=True,ws=3,prior=tz,start=V.initial_fleet("S",ue[0],L=L))
        finally: C.slope=orig
        s3b=f(a)==f(c); ok3b&=s3b
        if not s3b: lines.append(f"(3b) MISMATCH trace {i} L {L}")
diff={}
for W_ in (3,5):
    L=LS[0]; diff[W_]=sum(1 for i in idx if C.sim_s6(lib[i]["ue"][:60],cfg,tp,L,ws=W_)['ev']!=Q2.sim_nest2(lib[i]["ue"][:60],cfg,pr,L)['ev'])
hdr=(f"(1) sim_s6 sigma vs v8sim10.sim_nest2: {n1} cases -> {'IDENTICAL' if ok1 else 'MISMATCH'}\n"
     f"(2) sim_s6 trend path (slope=0, sigma_res:=sigma win) vs v8sim10.sim_nest2: {n2} cases -> {'IDENTICAL' if ok2 else 'MISMATCH'}\n"
     f"(3) CtlS6 trend=False vs v8sim11.run('S'): {n3} cases -> {'IDENTICAL' if ok3 else 'MISMATCH'}; trend path patched -> {'IDENTICAL' if ok3b else 'MISMATCH'}\n"
     f"(4) trend on (Lr=L, lambda 1.83/2.00): traces whose events differ from S4 out of 20: {diff}")
open(f'{Q}/s6/out/equiv.txt','w').write(hdr+'\n'+'\n'.join(lines)+'\n'); print(hdr); [print(l) for l in lines[:10]]
sys.exit(0 if ok1 and ok2 and ok3 and ok3b and all(v>0 for v in diff.values()) else 2)
