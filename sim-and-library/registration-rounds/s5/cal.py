#!/usr/bin/env python3
"""qsim/s5/cal.py (10-26, spec §4.124): six-split calibration of S5 (quantile margin) and S4 recomputation, leakage-free (r63r method).
Context = (arm, split): Prior/QPrior from the split's calibration groups; cal = first 300 cal traces; held-out = all held-out traces.
Targets: 0.02, 0.005 and eps_v6 = v6's realised held-out risk on the same split (sim_v6, fixed constants).
Calibration: coarse grid -> feasible (cal risk <= target) cheapest cal alloc (dispatch) -> refine 8 neighbours -> re-select.
  S5: p grid {0.80,0.85,0.90,0.925,0.95,0.965,0.975,0.985,0.99,0.995}^2, refine +-0.005 within [0.80,0.995]; variants b' (independent_full) and b (independent).
  S4: lambda grid of v8sim10_cal (6x7), refine +-0.25 (= r63r 'full').
Held-out per target: risk, alloc (vmexist), alloc_dispatch, flaps, acts (AB.trace_metrics) on every held-out trace.
Output: out/cal.jsonl (one line per context; resumable), out/progress.log.
Run: cd /home/user/experiment/qsim && nohup nice -n 19 python3 s5/cal.py 4 > s5/out/run.log 2>&1 &"""
import os, sys, json, time, itertools, datetime as dt, numpy as np
Q="/home/user/experiment/qsim"; R=f"{Q}/s5"; sys.path.insert(0,Q); sys.path.insert(0,R); os.chdir(Q)
_argv=sys.argv; sys.argv=[sys.argv[0]]
import v8sim10_ablation as AB
sys.argv=_argv
import s5core as C, v8sim2 as S
from v8sim3 import grouped_split
from concurrent.futures import ProcessPoolExecutor
lib=AB.lib; cfg=AB.cfg; FN=f"{R}/out/cal.jsonl"
PG=[0.80,0.85,0.90,0.925,0.95,0.965,0.975,0.985,0.99,0.995]
def log(m):
    line=f"[{dt.datetime.now():%F %T}] {m}"; print(line,flush=True); open(f"{R}/out/progress.log","a").write(line+"\n")
def context(job):
    tag,arm,variant,seed=job; t0=time.time()
    c,h=grouped_split(seed); qp=C.QPrior([lib[i] for i in c],cfg); cal=c[:AB.NCAL]
    # v6 on the held-out set (target eps_v6) -- identical for every arm of this split
    v6=[S.sim_v6(lib[i]["ue"][:60],cfg) for i in h]
    v6_risk=float(np.mean([(60-r["slo"])/60.0 for r in v6])); v6_alloc=float(np.mean([r["alloc"] for r in v6])); v6_flaps=float(np.mean([r["flaps"] for r in v6]))
    margin='quantile' if arm=='S5' else 'sigma'
    def L_of(a,b): return {"vy":a,"wk":a,"up":b}
    cache={}; ns=[0]
    def calres(i,a,b):
        k=(i,a,b); r=cache.get(k)
        if r is None:
            x=C.sim_s5(lib[i]["ue"][:60],cfg,qp,L_of(a,b),variant=variant,margin=margin); r=cache[k]=(x["slo"],x["alloc"]); ns[0]+=1
        return r
    def ev(a,b):
        rs=[calres(i,a,b) for i in cal]
        return (float(np.mean([(60-s)/60.0 for s,_ in rs])), float(np.mean([al for _,al in rs])))
    if arm=='S5':
        grid=list(itertools.product(PG,PG)); step=0.005; lo,hi=0.80,0.995
    else:
        grid=list(itertools.product(AB.GRID_VM,AB.GRID_UP)); step=0.25; lo,hi=1e-9,99
    out=dict(tag=tag,arm=arm,variant=variant,seed=seed,n_prior=len(c),n_cal=len(cal),n_ho=len(h),v6=dict(risk=v6_risk,alloc_dispatch=v6_alloc,flaps=v6_flaps),rows={})
    table={k:ev(*k) for k in grid}
    for tname,target in (("0.02",0.02),("0.005",0.005),("eps_v6",v6_risk)):
        tab=dict(table)
        feas=[(k,v) for k,v in tab.items() if v[0]<=target]
        if not feas: out["rows"][tname]=dict(infeasible=True,target=target,min_cal_risk=min(v[0] for v in tab.values())); continue
        (a,b),_=min(feas,key=lambda kv:kv[1][1])
        ref=[(round(a+da,4),round(b+db,4)) for da,db in itertools.product((-step,0,step),(-step,0,step))]
        ref=[k for k in ref if k not in tab and lo-1e-9<=k[0]<=hi+1e-9 and lo-1e-9<=k[1]<=hi+1e-9]
        for k in ref: tab[k]=ev(*k)
        feas=[(k,v) for k,v in tab.items() if v[0]<=target]
        (a,b),(risk,al)=min(feas,key=lambda kv:kv[1][1])
        ms=[]
        for i in h:
            r=C.sim_s5(lib[i]["ue"][:60],cfg,qp,L_of(a,b),variant=variant,margin=margin,acct="vmexist"); m=AB.trace_metrics(r)
            r2=C.sim_s5(lib[i]["ue"][:60],cfg,qp,L_of(a,b),variant=variant,margin=margin,acct="dispatch"); m["alloc_dispatch"]=r2["alloc"]
            assert r2["slo"]==r["slo"] and r2["ev"]==r["ev"]; ms.append(m); ns[0]+=2
        keys=['risk','alloc','alloc_dispatch','flaps','flaps_cd','acts','acts_vy','acts_wk','acts_up','under_vy','under_up','over_vy','over_up']
        out["rows"][tname]=dict(infeasible=False,target=target,a=a,b=b,cal_risk=risk,cal_alloc=al,n_eval=len(tab),ho={k:float(np.mean([m[k] for m in ms])) for k in keys})
    out.update(t=time.time()-t0,nsim=ns[0]); return out
if __name__=="__main__":
    nproc=int(sys.argv[1]) if len(sys.argv)>1 else 4
    done=set()
    if os.path.exists(FN):
        for l in open(FN): done.add(json.loads(l)["tag"])
    jobs=[(f"S5|{v}|s{s}","S5",v,s) for v in ("independent_full","independent") for s in AB.SEEDS]+[(f"S4|full|s{s}","S4","full",s) for s in AB.SEEDS]
    todo=[j for j in jobs if j[0] not in done]
    log(f"=== S5 calibration: {len(jobs)} contexts, {len(done)} done, {len(todo)} to run, nproc {nproc}, affinity {sorted(os.sched_getaffinity(0))}, pid {os.getpid()}")
    T0=time.time(); k=0
    with ProcessPoolExecutor(nproc) as pool:
        for r in pool.map(context,todo):
            k+=1; open(FN,"a").write(json.dumps(r)+"\n"); el=time.time()-T0
            rs="; ".join(f"{tg}: "+("INFEASIBLE" if x["infeasible"] else f"{x['a']}/{x['b']} cal {x['cal_risk']:.4f} ho {x['ho']['risk']:.4f} vm {x['ho']['alloc']:.1f} disp {x['ho']['alloc_dispatch']:.1f} fl {x['ho']['flaps']:.2f}") for tg,x in r["rows"].items())
            log(f"{r['tag']} ({k}/{len(todo)}) {r['t']:.0f}s sims {r['nsim']} | v6 risk {r['v6']['risk']:.4f} disp {r['v6']['alloc_dispatch']:.1f} | {rs} | eta {el/k*(len(todo)-k):.0f}s")
    log(f"=== DONE {time.time()-T0:.0f}s")
