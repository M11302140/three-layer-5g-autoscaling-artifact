#!/usr/bin/env python3
"""qsim/r67band/run.py (spec §4.135): whole-library per-slot (v8sim11, R38 off = knee38 5) runs of seven arms x two targets with per-layer VM-minutes.
Runner = r62cf/calib_c.run_ctl (identical to v8sim11.run with an explicit controller). Frozen files are imported, never modified.
  python3 run.py check   -> 20 random traces vs r62cf cache (risk, alloc_vm per trace), exit 2 on any mismatch
  python3 run.py all     -> out/<config>.json for every config (per-trace slo, viol, alloc_vm, alloc_by, vm-min, flaps)
Run with: nice -n 19 taskset -c 13,14 python3 run.py ..."""
import timeit  # noqa: stdlib first (qsim/timeit.py shadow, as r62cf)
import sys, os, json, math, time, random
Q='/home/user/experiment/qsim'; R=f'{Q}/r67band'; os.chdir(Q); sys.path.insert(0,Q)
import v8sim11 as V
from concurrent.futures import ProcessPoolExecutor
LIB=json.load(open(f'{Q}/prior_traces.json')); PH={"knee38":5}
LEADS={"L1":(1,3,3),"L2":(2,5,5),"L4":(4,10,10)}
def mu_of(fam,T): return (12.0/3.5 if fam=="B4" else 14.0/4.0)*T
CFG={  # name -> (family, key)
 "S4b":("S2",(1.83,2.00)), "S1_2.25":("S1",(2.25,)), "B4_3.75_300":("B4",(3.75,300)), "B5_4.0_L2":("B5",(4.0,"L2")), "B6_0.775":("B6",(0.775,)),
 "S4a":("S2",(2.83,3.08)), "S1_3.25":("S1",(3.25,)), "B4_3.0_300":("B4",(3.0,300)), "B5_3.5_L1":("B5",(3.5,"L1")), "B6_0.7":("B6",(0.7,)),
 "v6":("v6",()), "B1":("B1",()), "B5_3.25_L1":("B5",(3.25,"L1")), "B6_0.675":("B6",(0.675,))}
def run_ctl(ue,ctl,start):
    ph=V.Phys(ue,start=start,p=PH)
    for i in range(60*60//V.DT):
        ph.advance_units()
        if ph.t%V.TICK==0:
            if ctl is not None:
                ob=ph.observe(); decided=ctl.tick(ph,ob)
            else: decided=False
            ph.hot_relief(getattr(ph,"_over",{}))
            if not decided and ph.t-ph.last_pool_relief>=ph.p["pool_relief_s"]:
                ph.enqueue_pool_relief(); ph.last_pool_relief=ph.t
        ph.step()
    return ph.result()
def make(fam,key,ue):
    cfg,pr=V.cfg_prior()
    if fam in ("B4","B5"):
        T,x=key; mu=mu_of(fam,T)
        ctl=V.CtlB4(predictive=False,mu=mu,target=T,tol=0.05,down=int(x),margin=0.8) if fam=="B4" else V.CtlB4(predictive=True,mu=mu,target=T,tol=0.05,down=600,margin=0.8,lead=LEADS[x])
        return ctl,V.initial_fleet("B4",ue[0],target=T,mu=mu)
    if fam=="B6": u=key[0]; return V.CtlB6(cfg,u=u),V.initial_fleet("B6",ue[0],u=u)
    if fam=="S1": l=key[0]; L={"vy":l,"wk":l,"up":l}; return V.CtlSigma(cfg,pr,L),V.initial_fleet("S",ue[0],L=L)
    if fam=="S2": a,b=key; L={"vy":a,"wk":a,"up":b}; return V.CtlSigma(cfg,pr,L),V.initial_fleet("S",ue[0],L=L)
    if fam=="v6": return V.CtlV6(cfg),V.initial_fleet("v6",ue[0])
    if fam=="B1": return None,(8,3,4)
def flaps(events):
    ev=sorted((t/60.0,k,(+1 if a=='out' else -1)) for (t,a,k,*_) in events if a in ('out','in'))
    n=0
    for i,(t,l,dr) in enumerate(ev):
        for t2,l2,d2 in ev[i+1:]:
            if l2==l and t2-t<=10 and d2==-dr: n+=1; break
    return n
def one(args):
    name,i=args; fam,key=CFG[name]; ue=LIB[i]["ue"][:60]; ctl,st=make(fam,key,ue); r=run_ctl(ue,ctl,st); ab=r['alloc_by']
    return i,dict(slo=int(r['slo']),viol=[int(x) for x in r['viol']],alloc_vm=r['alloc_vm'],wk_core=ab['wk'],vy_core=ab['vy'],up_core=ab['up'],wk_min=ab['wk']/3.0,vy_min=ab['vy']/2.0,slot_min=ab['up']/0.8,flaps=int(flaps(r['events'])))
def cache_name(name):
    fam,key=CFG[name]; f={"S1":"S"}.get(fam,fam); return f"{Q}/r62cf/cache/{f}_off_"+"_".join(str(k) for k in key)+".json"
if __name__=="__main__":
    mode=sys.argv[1]; t0=time.time()
    if mode=="check":
        idx=random.Random(20261027).sample(range(len(LIB)),20); bad=0; lines=[]
        names=["B4_3.75_300","B5_4.0_L2","B6_0.775","S1_2.25","B4_3.0_300","B5_3.5_L1","B6_0.7","S1_3.25"]
        with ProcessPoolExecutor(2) as pool:
            for name in names:
                c=json.load(open(cache_name(name))); res=dict(pool.map(one,[(name,i) for i in idx]))
                mm=[i for i in idx if abs((60-res[i]['slo'])/60.0-c['risk_vec'][i])>1e-12 or abs(res[i]['alloc_vm']-c['cost_vec'][i])>1e-9]
                bad+=len(mm); lines.append(f"{name}: {20-len(mm)}/20 identical"+(f" MISMATCH {mm}" if mm else ""))
        lines.append(f"consistency vs r62cf cache: {'ALL IDENTICAL' if bad==0 else f'{bad} MISMATCHES'} ({time.time()-t0:.0f}s)")
        print("\n".join(lines)); open(f"{R}/out/check.txt","w").write("\n".join(lines)+"\n"); sys.exit(0 if bad==0 else 2)
    if mode=="all":
        names=[n for n in CFG if not os.path.exists(f"{R}/out/{n}.json")]
        with ProcessPoolExecutor(2) as pool:
            for name in names:
                t1=time.time(); res=dict(pool.map(one,[(name,i) for i in range(len(LIB))],chunksize=8))
                json.dump(dict(name=name,fam=CFG[name][0],key=list(CFG[name][1]),phys=PH,rows=[res[i] for i in range(len(LIB))]),open(f"{R}/out/{name}.json","w"))
                print(f"[{time.strftime('%T')}] {name} done {time.time()-t1:.0f}s",flush=True)
        print(f"ALL DONE {time.time()-t0:.0f}s")
