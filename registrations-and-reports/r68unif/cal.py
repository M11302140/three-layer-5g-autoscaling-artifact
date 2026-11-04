#!/usr/bin/env python3
"""qsim/r68unif/cal.py (spec §4.136 items 3-4): nest2 equal-risk six-split calibration of A-PL (variant 'apl') and S4' (variant independent_full + R2 w=1600).
Job = (arm, split): split prior from the calibration groups (S7Prior for S4', which adds the R2 tables), cal = first 300; table over GRID_VM x GRID_UP
(dispatch cost); per target (0.02, 0.005): feasible (cal risk <= target) cheapest -> refine +-0.25 -> feasible cheapest; infeasible -> lowest cal risk.
Held-out (all held-out traces): AB.trace_metrics on vmexist + dispatch cost. Output out/cal.jsonl"""
import os, sys, json, time, itertools, numpy as np
Q="/home/user/experiment/qsim"; R=f"{Q}/r68unif"; sys.path.insert(0,Q); sys.path.insert(0,R); sys.path.insert(0,Q+"/s7"); os.chdir(Q)
_argv=sys.argv; sys.argv=[sys.argv[0]]
import v8sim10_ablation as AB
sys.argv=_argv
import v8sim2 as S, nest2gen as G, s7core as C7
from v8sim3 import grouped_split
from concurrent.futures import ProcessPoolExecutor
lib=AB.lib; cfg=AB.cfg
ARMS={"APL":dict(variant="apl",w=None),"S4p":dict(variant="independent_full",w=1600)}
def Lof(a,b): return {"vy":a,"wk":a,"up":b}
def job(args):
    arm,seed=args; t0=time.time(); c,h=grouped_split(seed); A=ARMS[arm]
    pr=(C7.S7Prior if A["w"] is not None else S.Prior)([lib[i] for i in c],cfg); cal=c[:AB.NCAL]
    ev=lambda a,b: (lambda rs:(float(np.mean([(60-r["slo"])/60 for r in rs])),float(np.mean([r["alloc"] for r in rs]))))([G.sim_s7(lib[i]["ue"][:60],cfg,pr,Lof(a,b),variant=A["variant"],w=A["w"]) for i in cal])
    tab={(a,b):ev(a,b) for a,b in itertools.product(AB.GRID_VM,AB.GRID_UP)}; out=[]
    for tg in (0.02,0.005):
        T=dict(tab); feas=[(k,v) for k,v in T.items() if v[0]<=tg]; inf=not feas
        (a,b),_=min(feas,key=lambda kv:kv[1][1]) if feas else min(T.items(),key=lambda kv:(kv[1][0],kv[1][1]))
        for da,db in itertools.product((-0.25,0,0.25),(-0.25,0,0.25)):
            k=(round(a+da,4),round(b+db,4))
            if k not in T and k[0]>0 and k[1]>0: T[k]=ev(*k)
        feas=[(k,v) for k,v in T.items() if v[0]<=tg]
        (a,b),(cr,cc)=min(feas,key=lambda kv:kv[1][1]) if feas else min(T.items(),key=lambda kv:(kv[1][0],kv[1][1]))
        ms=[]
        for i in h:
            r=G.sim_s7(lib[i]["ue"][:60],cfg,pr,Lof(a,b),variant=A["variant"],w=A["w"],acct="vmexist"); m=AB.trace_metrics(r)
            m["alloc_dispatch"]=G.sim_s7(lib[i]["ue"][:60],cfg,pr,Lof(a,b),variant=A["variant"],w=A["w"],acct="dispatch")["alloc"]; ms.append(m)
        out.append(dict(arm=arm,seed=seed,target=tg,a=a,b=b,infeasible=(not feas),cal_risk=cr,cal_cost=cc,ho={k:float(np.mean([m[k] for m in ms])) for k in ('risk','alloc','alloc_dispatch','flaps')},t=time.time()-t0))
    return out
if __name__=="__main__":
    t0=time.time(); jobs=[(a,s) for a in ARMS for s in range(6)]
    with ProcessPoolExecutor(2) as pool:
        for rows in pool.map(job,jobs):
            for r in rows:
                open(f"{R}/out/cal.jsonl","a").write(json.dumps(r)+"\n")
                print(f"[{time.strftime('%T')}] {r['arm']} split{r['seed']} {r['target']}: lam {r['a']}/{r['b']} inf {r['infeasible']} cal {r['cal_risk']:.4f}/{r['cal_cost']:.1f} | ho risk {r['ho']['risk']:.4f} vm {r['ho']['alloc']:.1f} disp {r['ho']['alloc_dispatch']:.1f} fl {r['ho']['flaps']:.2f} ({r['t']:.0f}s)",flush=True)
    print(f"DONE {time.time()-t0:.0f}s")
