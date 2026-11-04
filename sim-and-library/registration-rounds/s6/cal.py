#!/usr/bin/env python3
"""qsim/s6/cal.py (10-26, spec §4.127 item 6): six-split calibration of S6 (trend term), leakage-free (r63r / §4.124 method).
Job = (split seed, target). Prior: TPrior from the split's calibration groups; cal = first 300 cal traces; held-out = all held-out traces.
Release multipliers Lr = S4's pick for the same split and target (s5/out/cal.jsonl, S4|full rows; bit-identical to r63r).
Targets 0.02 (S6b), 0.005 (S6a), eps_v6 (= v6 realised held-out risk on the split, from the same file).
Coarse grid GRID_VM x GRID_UP x ws{3,5} -> feasible (cal risk <= target) cheapest cal dispatch cost -> refine +-0.25 (8 neighbours, ws fixed) -> re-select.
Held-out: risk, alloc (vmexist), alloc_dispatch, flaps, acts (v8sim10_ablation.trace_metrics).
Output: s6/out/cal.jsonl (resumable), s6/out/progress.log.  Run: nohup nice -n 19 python3 s6/cal.py 4 > s6/out/run.log 2>&1 &"""
import os, sys, json, time, itertools, datetime as dt, numpy as np
Q="/home/user/experiment/qsim"; R=f"{Q}/s6"; sys.path.insert(0,Q); sys.path.insert(0,R); os.chdir(Q)
_argv=sys.argv; sys.argv=[sys.argv[0]]
import v8sim10_ablation as AB
sys.argv=_argv
import s6core as C
from v8sim3 import grouped_split
from concurrent.futures import ProcessPoolExecutor
lib=AB.lib; cfg=AB.cfg; FN=f"{R}/out/cal.jsonl"; WS=(3,5)
S4={}
for l in open(f"{Q}/s5/out/cal.jsonl"):
    r=json.loads(l)
    if r['arm']=='S4': S4[r['seed']]=r
def log(m):
    line=f"[{dt.datetime.now():%F %T}] {m}"; print(line,flush=True); open(f"{R}/out/progress.log","a").write(line+"\n")
def job(args):
    seed,tname=args; t0=time.time(); s4=S4[seed]; row4=s4['rows'][tname]
    target={'0.02':0.02,'0.005':0.005,'eps_v6':s4['v6']['risk']}[tname]
    Lr={"vy":row4['a'],"wk":row4['a'],"up":row4['b']}
    c,h=grouped_split(seed); tp=C.TPrior([lib[i] for i in c],cfg,ws=WS); cal=c[:AB.NCAL]; ns=[0]
    def L_of(a,b): return {"vy":a,"wk":a,"up":b}
    def ev(a,b,w):
        rs=[C.sim_s6(lib[i]["ue"][:60],cfg,tp,L_of(a,b),Lr=Lr,ws=w) for i in cal]; ns[0]+=len(rs)
        return (float(np.mean([(60-r["slo"])/60.0 for r in rs])), float(np.mean([r["alloc"] for r in rs])))
    tab={(a,b,w):ev(a,b,w) for a,b,w in itertools.product(AB.GRID_VM,AB.GRID_UP,WS)}
    out=dict(seed=seed,target_name=tname,target=target,Lr=Lr,n_prior=len(c),n_cal=len(cal),n_ho=len(h))
    feas=[(k,v) for k,v in tab.items() if v[0]<=target]
    if not feas:
        out.update(infeasible=True,min_cal_risk=min(v[0] for v in tab.values()),t=time.time()-t0,nsim=ns[0]); return out
    (a,b,w),_=min(feas,key=lambda kv:kv[1][1])
    for da,db in itertools.product((-0.25,0,0.25),(-0.25,0,0.25)):
        k=(round(a+da,4),round(b+db,4),w)
        if k not in tab and k[0]>0 and k[1]>0: tab[k]=ev(*k)
    feas=[(k,v) for k,v in tab.items() if v[0]<=target]
    (a,b,w),(risk,al)=min(feas,key=lambda kv:kv[1][1])
    ms=[]
    for i in h:
        r=C.sim_s6(lib[i]["ue"][:60],cfg,tp,L_of(a,b),Lr=Lr,ws=w,acct="vmexist"); m=AB.trace_metrics(r)
        r2=C.sim_s6(lib[i]["ue"][:60],cfg,tp,L_of(a,b),Lr=Lr,ws=w,acct="dispatch"); m["alloc_dispatch"]=r2["alloc"]
        assert r2["slo"]==r["slo"] and r2["ev"]==r["ev"]; ms.append(m); ns[0]+=2
    keys=['risk','alloc','alloc_dispatch','flaps','flaps_cd','acts','acts_vy','acts_wk','acts_up','under_vy','under_up','over_vy','over_up']
    best_other=min(((k,v) for k,v in tab.items() if v[0]<=target and k[2]!=w),key=lambda kv:kv[1][1],default=None)
    out.update(infeasible=False,a=a,b=b,ws=w,cal_risk=risk,cal_alloc=al,n_eval=len(tab),
               other_ws=(None if best_other is None else dict(a=best_other[0][0],b=best_other[0][1],ws=best_other[0][2],cal_risk=best_other[1][0],cal_alloc=best_other[1][1])),
               ho={k:float(np.mean([m[k] for m in ms])) for k in keys},t=time.time()-t0,nsim=ns[0])
    return out
if __name__=="__main__":
    nproc=int(sys.argv[1]) if len(sys.argv)>1 else 4
    done=set()
    if os.path.exists(FN):
        for l in open(FN): r=json.loads(l); done.add((r['seed'],r['target_name']))
    jobs=[(s,t) for t in ('0.02','0.005','eps_v6') for s in AB.SEEDS]; todo=[j for j in jobs if j not in done]
    log(f"=== S6 calibration: {len(jobs)} jobs, {len(done)} done, {len(todo)} to run, nproc {nproc}, affinity {sorted(os.sched_getaffinity(0))}, pid {os.getpid()}")
    T0=time.time(); k=0
    with ProcessPoolExecutor(nproc) as pool:
        for r in pool.map(job,todo):
            k+=1; open(FN,"a").write(json.dumps(r)+"\n"); el=time.time()-T0
            s=("INFEASIBLE min cal risk %.4f"%r['min_cal_risk']) if r['infeasible'] else f"lam {r['a']}/{r['b']} ws {r['ws']} cal {r['cal_risk']:.4f}/{r['cal_alloc']:.1f} | ho risk {r['ho']['risk']:.4f} vm {r['ho']['alloc']:.1f} disp {r['ho']['alloc_dispatch']:.1f} fl {r['ho']['flaps']:.2f}"
            log(f"split{r['seed']} target {r['target_name']} ({k}/{len(todo)}) {r['t']:.0f}s sims {r['nsim']} | Lr {r['Lr']['vy']}/{r['Lr']['up']} | {s} | eta {el/k*(len(todo)-k):.0f}s")
    log(f"=== DONE {time.time()-T0:.0f}s")
