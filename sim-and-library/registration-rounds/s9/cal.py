#!/usr/bin/env python3
"""qsim/s9/cal.py (spec §4.132 item 2): six-split conditional calibration of S9, leakage-free (r63r procedure).
Job = (split, target in 0.02 / 0.005 / eps_v6). S9Prior from the split's calibration groups (thr from s9/out/thresholds.json); cal = first 300.
  init: three buckets = S4 lambda of the split/target (s5/out/cal.jsonl), w = S7 w of the split (s7/out/cal.jsonl; eps_v6 uses 0.02's).
  A (nest2 sim_s9, vmexist): calm then normal: 42-point grid (others fixed) -> cheapest with that bucket's conditional cal risk <= target,
     refine +-0.25; then w (5 points): cheapest with calm and normal conditional risks <= target.
  B (per-slot run_s9, alloc_vm): burst 42-point grid + refine on the cal traces that have >= 1 burst minute -> cheapest with per-slot burst
     conditional risk <= target.
  C: nest2 recheck of calm/normal; if one > target, redo A once with the new burst lambda; stop.
  infeasible bucket -> its lowest-risk point, flagged.
Held-out (all held-out traces of the split, nest2): AB.trace_metrics + per-bucket conditional risk; per-slot held-out burst conditional risk if --ps-ho.
Conditional risk = violating minutes among minutes whose regime (first tick of the minute) is b, pooled over traces.
Run: nohup nice -n 19 python3 s9/cal.py 4 > s9/out/run.log 2>&1 &"""
import os, sys, json, time, itertools, datetime as dt, numpy as np
Q="/home/user/experiment/qsim"; R=f"{Q}/s9"; sys.path.insert(0,Q); sys.path.insert(0,R); os.chdir(Q)
_argv=sys.argv; sys.argv=[sys.argv[0]]
import v8sim10_ablation as AB
sys.argv=_argv
import v8sim2 as S, v8sim11 as V
import s9core as C, v8sim11_s9 as W
from v8sim3 import grouped_split
from concurrent.futures import ProcessPoolExecutor
lib=AB.lib; cfg=AB.cfg; BK=C.BUCKETS; WS=[0,25,100,400,1600]
TH=json.load(open(f"{R}/out/thresholds.json")); THR=(TH['T50'],TH['T85'])
S4={}; S7={}
for l in open(f"{Q}/s5/out/cal.jsonl"):
    r=json.loads(l)
    if r['arm']=='S4': S4[r['seed']]=r
for l in open(f"{Q}/s7/out/cal.jsonl"):
    r=json.loads(l); S7[(r['seed'],r['target_name'])]=r
def log(m):
    line=f"[{dt.datetime.now():%F %T}] {m}"; print(line,flush=True); open(f"{R}/out/progress.log","a").write(line+"\n")
def regmin(ue):
    d=S.expand(ue)*cfg.scale; rg=C.Regime(THR); regs=[rg.step(float(d[i])) for i in range(0,len(d),C.STEP)]
    return [regs[m*2] for m in range(60)]   # first tick of each minute (TICK 30 s)
def Lof(a,b): return {"vy":a,"wk":a,"up":b}
def key(Lb,w): return (tuple((Lb[b]["vy"],Lb[b]["up"]) for b in BK),w)
class Job:
    def __init__(s,seed,tname):
        s.seed=seed; s.tname=tname; c,h=grouped_split(seed); s.h=h; s.cal=c[:AB.NCAL]
        s.sp=C.S9Prior([lib[i] for i in c],cfg,thr=THR); V.cfg_prior()
        s.target={'0.02':0.02,'0.005':0.005,'eps_v6':S4[seed]['v6']['risk']}[tname]
        s.regs={i:regmin(lib[i]["ue"][:60]) for i in s.cal}; s.bt=[i for i in s.cal if 'burst' in s.regs[i]]
        s.cn={}; s.cp={}; s.nn=0; s.np=0
    def evN(s,Lb,w):
        k=key(Lb,w)
        if k in s.cn: return s.cn[k]
        viol={b:0 for b in BK}; mins={b:0 for b in BK}; risk=[]; cost=[]
        for i in s.cal:
            r=C.sim_s9(lib[i]["ue"][:60],cfg,s.sp,None,Lb=Lb,thr=THR,trend=True,w=w,acct="vmexist"); s.nn+=1
            v=r['pct']>0.1; risk.append(float(v.mean())); cost.append(r['alloc'])
            for m,b in enumerate(r['reg']): mins[b]+=1; viol[b]+=int(v[m])
        out=dict(cond={b:(viol[b]/mins[b] if mins[b] else 0.0) for b in BK},mins=mins,risk=float(np.mean(risk)),cost=float(np.mean(cost)))
        s.cn[k]=out; return out
    def evP(s,Lb,w):
        k=key(Lb,w)
        if k in s.cp: return s.cp[k]
        vb=0; mb=0; cost=[]
        for i in s.bt:
            r=W.run_s9(lib[i]["ue"][:60],None,Lb=Lb,thr=THR,trend=True,w=w,prior=s.sp); s.np+=1
            vs=set(r['viol']); cost.append(r['alloc_vm'])
            for m,b in enumerate(r['reg']):
                if b=='burst': mb+=1; vb+=int(m in vs)
        out=dict(cond_burst=(vb/mb if mb else 0.0),mins=mb,cost=float(np.mean(cost)) if cost else 0.0)
        s.cp[k]=out; return out
    def sweep(s,Lb,w,b,ev,riskf,flags):
        pts=list(itertools.product(AB.GRID_VM,AB.GRID_UP)); res={}
        def try_(a,u):
            L2=dict(Lb); L2[b]=Lof(a,u); res[(a,u)]=ev(L2,w)
        for a,u in pts: try_(a,u)
        feas=[(p,v) for p,v in res.items() if riskf(v)<=s.target]
        if feas:
            (a,u),_=min(feas,key=lambda kv:kv[1]['cost'])
            for da,du in itertools.product((-0.25,0,0.25),(-0.25,0,0.25)):
                p=(round(a+da,4),round(u+du,4))
                if p not in res and p[0]>0 and p[1]>0: try_(*p)
            feas=[(p,v) for p,v in res.items() if riskf(v)<=s.target]; (a,u),_=min(feas,key=lambda kv:kv[1]['cost'])
        else:
            (a,u),_=min(res.items(),key=lambda kv:(riskf(kv[1]),kv[1]['cost'])); flags.append(f"infeasible-{b}")
        L2=dict(Lb); L2[b]=Lof(a,u); return L2
    def stageA(s,Lb,w,flags):
        for b in ("calm","normal"): Lb=s.sweep(Lb,w,b,s.evN,lambda v,b=b:v['cond'][b],flags)
        res={x:s.evN(Lb,x) for x in WS}
        feas=[(x,v) for x,v in res.items() if max(v['cond']['calm'],v['cond']['normal'])<=s.target]
        if feas: w,_=min(feas,key=lambda kv:kv[1]['cost'])
        else: w,_=min(res.items(),key=lambda kv:(max(kv[1]['cond']['calm'],kv[1]['cond']['normal']),kv[1]['cost'])); flags.append("infeasible-w")
        return Lb,w
    def run(s,ps_ho=False):
        t0=time.time(); flags=[]
        r4=S4[s.seed]['rows'][s.tname]; Lb={b:Lof(r4['a'],r4['b']) for b in BK}
        w=S7[(s.seed,'0.02' if s.tname=='eps_v6' else s.tname)]['w']
        Lb,w=s.stageA(Lb,w,flags); tA=time.time()-t0
        Lb=s.sweep(Lb,w,"burst",s.evP,lambda v:v['cond_burst'],flags); tB=time.time()-t0-tA
        c=s.evN(Lb,w); redo=False
        if c['cond']['calm']>s.target or c['cond']['normal']>s.target:
            redo=True; Lb,w=s.stageA(Lb,w,flags); c=s.evN(Lb,w)
        p=s.evP(Lb,w)
        ms=[]; hv={b:0 for b in BK}; hm={b:0 for b in BK}
        for i in s.h:
            r=C.sim_s9(lib[i]["ue"][:60],cfg,s.sp,None,Lb=Lb,thr=THR,trend=True,w=w,acct="vmexist"); m=AB.trace_metrics(r)
            v=r['pct']>0.1
            for mm,b in enumerate(r['reg']): hm[b]+=1; hv[b]+=int(v[mm])
            m["alloc_dispatch"]=C.sim_s9(lib[i]["ue"][:60],cfg,s.sp,None,Lb=Lb,thr=THR,trend=True,w=w,acct="dispatch")["alloc"]; ms.append(m)
        keys=['risk','alloc','alloc_dispatch','flaps','flaps_cd','acts','acts_vy','acts_wk','acts_up']
        risks=[m['risk'] for m in ms]
        out=dict(seed=s.seed,target_name=s.tname,target=s.target,Lb={b:[Lb[b]['vy'],Lb[b]['up']] for b in BK},w=w,flags=flags,redoA=redo,
                 cal_cond=c['cond'],cal_mins=c['mins'],cal_risk=c['risk'],cal_cost=c['cost'],cal_ps_burst=p['cond_burst'],cal_ps_burst_mins=p['mins'],n_burst_traces=len(s.bt),
                 ho={k:float(np.mean([m[k] for m in ms])) for k in keys},ho_se=float(np.std(risks,ddof=1)/np.sqrt(len(risks))),ho_n=len(risks),
                 ho_cond={b:(hv[b]/hm[b] if hm[b] else 0.0) for b in BK},ho_mins=hm,nsim_nest2=s.nn,nsim_ps=s.np,tA=tA,tB=tB,t=time.time()-t0)
        if ps_ho:
            vb=0; mb=0
            for i in s.h:
                rg=regmin(lib[i]["ue"][:60])
                if 'burst' not in rg: continue
                r=W.run_s9(lib[i]["ue"][:60],None,Lb=Lb,thr=THR,trend=True,w=w,prior=s.sp); vs=set(r['viol'])
                for mm,b in enumerate(r['reg']):
                    if b=='burst': mb+=1; vb+=int(mm in vs)
            out['ho_ps_burst']=vb/mb if mb else 0.0; out['ho_ps_burst_mins']=mb
        return out
def job(args):
    seed,tname,ps_ho=args; return Job(seed,tname).run(ps_ho)
if __name__=="__main__":
    nproc=int(sys.argv[1]) if len(sys.argv)>1 else 4; ps_ho='--ps-ho' in sys.argv
    only=[a.split('=',1)[1] for a in sys.argv if a.startswith('--only=')]
    CF=f"{R}/out/cal.jsonl"
    done={(json.loads(l)['seed'],json.loads(l)['target_name']) for l in open(CF)} if os.path.exists(CF) else set()
    jobs=[(s,t,ps_ho) for t in ('0.02','0.005','eps_v6') for s in AB.SEEDS if (s,t) not in done]
    if only: jobs=[j for j in jobs if f"{j[0]}:{j[1]}" in only[0].split(',')]
    log(f"=== S9 calibration: {len(jobs)} jobs, thr {THR}, nproc {nproc}, ps_ho {ps_ho}, affinity {sorted(os.sched_getaffinity(0))}, pid {os.getpid()}")
    T0=time.time(); k=0
    with ProcessPoolExecutor(nproc) as pool:
        for r in pool.map(job,jobs):
            k+=1; open(CF,"a").write(json.dumps(r)+"\n")
            log(f"split{r['seed']} {r['target_name']} ({k}/{len(jobs)}) {r['t']:.0f}s (A {r['tA']:.0f} B {r['tB']:.0f}; nest2 {r['nsim_nest2']} ps {r['nsim_ps']}) | Lb {r['Lb']} w {r['w']} flags {r['flags']} redo {r['redoA']} | cal cond {r['cal_cond']} ps-burst {r['cal_ps_burst']:.4f} | ho risk {r['ho']['risk']:.4f}±{r['ho_se']:.4f} vm {r['ho']['alloc']:.1f} disp {r['ho']['alloc_dispatch']:.1f} fl {r['ho']['flaps']:.2f}")
    log(f"=== DONE {time.time()-T0:.0f}s")
