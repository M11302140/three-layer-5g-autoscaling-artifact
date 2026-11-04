#!/usr/bin/env python3
"""spec §4.138 item 2 (library): r62cf equal-risk six-split calibration (GRIDS, coarse -> +-1 fine step -> feasible cheapest; R38 off; per-slot)
re-run for B4, B5, B6 (CtlB6) and S single-lambda under two unified start rules: 's4b' = every arm starts at v8sim11.initial_fleet('S4b', ue0),
'b1' = every arm starts at 8 / 3 / 4. Grid points cached with full per-trace rows in out/libcal/<rule>/; S4b and S4a deployed rows too.
Prefill off. Output out/libcal/<rule>/calib.json"""
import timeit  # noqa
import sys, os, json, time, numpy as np
Q='/home/user/experiment/qsim'; R=f'{Q}/r70eq'
for p in (Q,Q+'/r67band'): sys.path.insert(0,p)
os.chdir(Q)
import v8sim11 as V, run as RB
from v8sim3 import grouped_split
from concurrent.futures import ProcessPoolExecutor
LIB=RB.LIB; N=len(LIB)
GRIDS={"B4":([2.0,2.5,3.0,3.5,4.0,4.5,5.0],0.25,1.75,5.25,[300,600,900]),"B5":([2.0,2.5,3.0,3.5,4.0,4.5,5.0],0.25,1.75,5.25,["L1","L2","L4"]),
       "B6":([0.40,0.45,0.50,0.55,0.60,0.65,0.70,0.75,0.80,0.85,0.90,0.95],0.025,0.375,0.975,[None]),"S":([1.5,2.0,2.5,3.0,3.5,4.0,5.0,6.0],0.25,1.0,7.0,[None])}
def r2(x): return round(x,4)
def mk_key(fam,c,x): return (r2(c),x) if fam in ("B4","B5") else (r2(c),)
def start_of(rule,ue): return tuple(V.initial_fleet("S4b",ue[0])) if rule=="s4b" else (8,3,4)
def make(fam,key):
    cfg,pr=V.cfg_prior()
    if fam=="B4": T,x=key; return V.CtlB4(predictive=False,mu=RB.mu_of("B4",T),target=T,tol=0.05,down=int(x),margin=0.8)
    if fam=="B5": T,x=key; return V.CtlB4(predictive=True,mu=RB.mu_of("B5",T),target=T,tol=0.05,down=600,margin=0.8,lead=RB.LEADS[x])
    if fam=="B6": return V.CtlB6(cfg,u=key[0])
    if fam=="S": l=key[0]; return V.CtlSigma(cfg,pr,{"vy":l,"wk":l,"up":l})
    if fam=="S2": a,b=key; return V.CtlSigma(cfg,pr,{"vy":a,"wk":a,"up":b})
def one(args):
    rule,fam,key,i=args; ue=LIB[i]["ue"][:60]; r=RB.run_ctl(ue,make(fam,key),start_of(rule,ue)); ab=r['alloc_by']
    return i,dict(slo=int(r['slo']),alloc_vm=r['alloc_vm'],wk_min=ab['wk']/3,vy_min=ab['vy']/2,slot_min=ab['up']/0.8,flaps=int(RB.flaps(r['events'])))
CACHE={}
def get(pool,rule,fam,key):
    nm=f"{fam}_"+"_".join(str(k) for k in key); fn=f'{R}/out/libcal/{rule}/{nm}.json'
    if nm in CACHE.get(rule,{}): return CACHE[rule][nm]
    if os.path.exists(fn): d=json.load(open(fn))
    else:
        res=dict(pool.map(one,[(rule,fam,tuple(key),i) for i in range(N)],chunksize=8)); rows=[res[i] for i in range(N)]
        d=dict(fam=fam,key=list(key),rows=rows,risk_vec=[(60-r['slo'])/60 for r in rows],cost_vec=[r['alloc_vm'] for r in rows])
        json.dump(d,open(fn,'w')); print(f"[{time.strftime('%T')}] {rule} {nm}: risk {100*np.mean(d['risk_vec']):.3f} % cost {np.mean(d['cost_vec']):.1f}",flush=True)
    CACHE.setdefault(rule,{})[nm]=d; return d
def calibrate(pool,rule,fam,target,seed):
    cal,ho=grouped_split(seed); cal=cal[:300]; coarse,step,lo,hi,disc=GRIDS[fam]
    def stat(key,idx): d=get(pool,rule,fam,key); return float(np.mean([d["risk_vec"][i] for i in idx])),float(np.mean([d["cost_vec"][i] for i in idx]))
    table={mk_key(fam,c,x):stat(mk_key(fam,c,x),cal) for c in coarse for x in disc}
    feas=[(k,v) for k,v in table.items() if v[0]<=target+1e-12]
    k0=min(feas,key=lambda kv:kv[1][1])[0] if feas else min(table.items(),key=lambda kv:(kv[1][0],kv[1][1]))[0]
    for dc in (-step,step):
        c=r2(k0[0]+dc)
        if lo-1e-9<=c<=hi+1e-9:
            k=(c,)+tuple(k0[1:])
            if k not in table: table[k]=stat(k,cal)
    feas=[(k,v) for k,v in table.items() if v[0]<=target+1e-12]
    if feas: kb,(cr,cc)=min(feas,key=lambda kv:kv[1][1]); inf=False
    else: kb,(cr,cc)=min(table.items(),key=lambda kv:(kv[1][0],kv[1][1])); inf=True
    hr,hc=stat(kb,ho); return dict(fam=fam,target=target,seed=seed,key=list(kb),cal_risk=cr,ho_risk=hr,ho_cost=hc,infeasible=inf)
if __name__=="__main__":
    with ProcessPoolExecutor(2) as pool:
        for rule in ("s4b","b1"):
            os.makedirs(f'{R}/out/libcal/{rule}',exist_ok=True); res=[]
            for fam in ("B4","B5","B6","S"):
                for tg in (0.02,0.005):
                    for sd in range(6): r=calibrate(pool,rule,fam,tg,sd); res.append(r); print(rule,fam,tg,sd,r['key'],f"ho {r['ho_risk']:.4f}/{r['ho_cost']:.1f}",flush=True)
            for key in ((1.83,2.00),(2.83,3.08)): get(pool,rule,"S2",key)
            json.dump(res,open(f'{R}/out/libcal/{rule}/calib.json','w'),indent=1)
    print("DONE",flush=True)
