#!/usr/bin/env python3
"""qsim/s7/cal.py (spec §4.131 item 5): six-split calibration of S7 (lambda grid x w x P), leakage-free (r63r procedure).
Phase 1 task = (split, P): S7Prior from the split's calibration groups; cal = first 300; table over GRID_VM x GRID_UP x W (210 points),
  dispatch cost, -> out/table.jsonl (one line per task).
Phase 2 job = (split, target in 0.02 / 0.005 / eps_v6): feasible (cal risk <= target) cheapest over the 630 points of the split ->
  refine lambda +-0.25 (w, P fixed) -> held-out (all held-out traces): risk, vmexist, dispatch, flaps (AB.trace_metrics) -> out/cal.jsonl.
eps_v6 = v6's held-out risk of the split (s5/out/cal.jsonl). Run: nohup nice -n 19 python3 s7/cal.py 4 > s7/out/run.log 2>&1 &"""
import os, sys, json, time, itertools, datetime as dt, numpy as np
Q="/home/user/experiment/qsim"; R=f"{Q}/s7"; sys.path.insert(0,Q); sys.path.insert(0,R); os.chdir(Q)
_argv=sys.argv; sys.argv=[sys.argv[0]]
import v8sim10_ablation as AB
sys.argv=_argv
import s7core as C
from v8sim3 import grouped_split
from concurrent.futures import ProcessPoolExecutor
lib=AB.lib; cfg=AB.cfg
PB={"P85":4,"P90":5,"P95":7}; WS=[0,25,100,400,1600]
S4={}
for l in open(f"{Q}/s5/out/cal.jsonl"):
    r=json.loads(l)
    if r['arm']=='S4': S4[r['seed']]=r
def log(m):
    line=f"[{dt.datetime.now():%F %T}] {m}"; print(line,flush=True); open(f"{R}/out/progress.log","a").write(line+"\n")
_PR={}
def prior(seed):
    if seed not in _PR:
        c,h=grouped_split(seed); _PR[seed]=(C.S7Prior([lib[i] for i in c],cfg),c,h)
    return _PR[seed]
def L_of(a,b): return {"vy":a,"wk":a,"up":b}
def ev(sp,cal,a,b,B,w):
    rs=[C.sim_s7(lib[i]["ue"][:60],cfg,sp,L_of(a,b),B=B,w=w) for i in cal]
    return (float(np.mean([(60-r["slo"])/60.0 for r in rs])), float(np.mean([r["alloc"] for r in rs])))
def task(args):
    seed,pn=args; t0=time.time(); sp,c,h=prior(seed); cal=c[:AB.NCAL]; B=PB[pn]
    tab=[[a,b,w,*ev(sp,cal,a,b,B,w)] for a,b,w in itertools.product(AB.GRID_VM,AB.GRID_UP,WS)]
    return dict(seed=seed,P=pn,B=B,rows=tab,t=time.time()-t0)
def job(args):
    seed,tname,rows=args; t0=time.time(); sp,c,h=prior(seed); cal=c[:AB.NCAL]
    target={'0.02':0.02,'0.005':0.005,'eps_v6':S4[seed]['v6']['risk']}[tname]
    tab={(r[0],r[1],r[2],r[3]):(r[4],r[5]) for r in rows}     # (a,b,w,P) -> (risk, cost)
    feas=[(k,v) for k,v in tab.items() if v[0]<=target]
    if not feas: return dict(seed=seed,target_name=tname,target=target,infeasible=True,min_cal_risk=min(v[0] for v in tab.values()))
    (a,b,w,pn),_=min(feas,key=lambda kv:kv[1][1])
    for da,db in itertools.product((-0.25,0,0.25),(-0.25,0,0.25)):
        k=(round(a+da,4),round(b+db,4),w,pn)
        if k not in tab and k[0]>0 and k[1]>0: tab[k]=ev(sp,cal,k[0],k[1],PB[pn],w)
    feas=[(k,v) for k,v in tab.items() if v[0]<=target]
    (a,b,w,pn),(risk,al)=min(feas,key=lambda kv:kv[1][1])
    ms=[]
    for i in h:
        r=C.sim_s7(lib[i]["ue"][:60],cfg,sp,L_of(a,b),B=PB[pn],w=w,acct="vmexist"); m=AB.trace_metrics(r)
        r2=C.sim_s7(lib[i]["ue"][:60],cfg,sp,L_of(a,b),B=PB[pn],w=w,acct="dispatch"); m["alloc_dispatch"]=r2["alloc"]; ms.append(m)
    keys=['risk','alloc','alloc_dispatch','flaps','flaps_cd','acts','acts_vy','acts_wk','acts_up','under_vy','under_up','over_vy','over_up']
    return dict(seed=seed,target_name=tname,target=target,infeasible=False,a=a,b=b,w=w,P=pn,B=PB[pn],cal_risk=risk,cal_alloc=al,
                ho={k:float(np.mean([m[k] for m in ms])) for k in keys},t=time.time()-t0)
if __name__=="__main__":
    nproc=int(sys.argv[1]) if len(sys.argv)>1 else 4
    TF=f"{R}/out/table.jsonl"; CF=f"{R}/out/cal.jsonl"
    done={(json.loads(l)['seed'],json.loads(l)['P']) for l in open(TF)} if os.path.exists(TF) else set()
    tasks=[(s,p) for s in AB.SEEDS for p in PB if (s,p) not in done]
    log(f"=== S7 phase 1: {len(tasks)} table tasks (210 points x 300 cal traces each), nproc {nproc}, affinity {sorted(os.sched_getaffinity(0))}, pid {os.getpid()}")
    T0=time.time(); k=0
    with ProcessPoolExecutor(nproc) as pool:
        for r in pool.map(task,tasks):
            k+=1; open(TF,"a").write(json.dumps(r)+"\n")
            best=min(r['rows'],key=lambda x:(x[3]>0.02,x[4]))
            log(f"table split{r['seed']} {r['P']} ({k}/{len(tasks)}) {r['t']:.0f}s | cheapest <=2%: lam {best[0]}/{best[1]} w {best[2]} risk {best[3]:.4f} cost {best[4]:.1f} | eta {(time.time()-T0)/k*(len(tasks)-k):.0f}s")
    rows={}
    for l in open(TF):
        r=json.loads(l)
        for x in r['rows']: rows.setdefault(r['seed'],[]).append([x[0],x[1],x[2],r['P'],x[3],x[4]])
    done2={(json.loads(l)['seed'],json.loads(l)['target_name']) for l in open(CF)} if os.path.exists(CF) else set()
    jobs=[(s,t,rows[s]) for t in ('0.02','0.005','eps_v6') for s in AB.SEEDS if (s,t) not in done2]
    log(f"=== S7 phase 2: {len(jobs)} selection jobs")
    with ProcessPoolExecutor(nproc) as pool:
        for r in pool.map(job,jobs):
            open(CF,"a").write(json.dumps(r)+"\n")
            s=("INFEASIBLE %.4f"%r['min_cal_risk']) if r['infeasible'] else f"lam {r['a']}/{r['b']} w {r['w']} {r['P']} cal {r['cal_risk']:.4f}/{r['cal_alloc']:.1f} | ho risk {r['ho']['risk']:.4f} vm {r['ho']['alloc']:.1f} disp {r['ho']['alloc_dispatch']:.1f} fl {r['ho']['flaps']:.2f}"
            log(f"split{r['seed']} {r['target_name']}: {s}")
    log(f"=== DONE {time.time()-T0:.0f}s")
