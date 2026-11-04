#!/usr/bin/env python3
"""spec §4.138 item 1: per-slot (v8sim11 R38 off, r67band runner, own initial_fleet) whole-library scan of a common lambda scale c for S4, A-PL, S8, S4'
at the nest2-deployed lambda ratio; frontier c = 0.70..1.40 step 0.05, then 0.02-grid points between the frontier points that bracket the target.
Rows cached in out/scan/<arm>_<grp>_<c>.json. Targets: S4b 1.83/2.00 per-slot library risk (2 % group), S4a 2.83/3.08 (0.5 % group), from r67band."""
import timeit  # noqa
import sys, os, json, numpy as np
Q='/home/user/experiment/qsim'; R=f'{Q}/r70eq'
for p in (Q,Q+'/r67band',Q+'/r68unif',Q+'/s7'): sys.path.insert(0,p)
os.chdir(Q)
import v8sim11 as V, s7core as C7, ctlgen as CG, run as RB
from concurrent.futures import ProcessPoolExecutor
LIB=RB.LIB; N=len(LIB)
BASE={"2":{"S4":(1.83,2.00),"APL":(2.00,2.83),"S8":(1.54,1.75),"S4p":(1.50,1.92)},"05":{"S4":(2.83,3.08),"APL":(3.08,3.71),"S8":(2.58,2.92),"S4p":(2.33,3.33)}}
FLAGS={"S4":None,"APL":dict(indep=True,indep_rel=True,plain=True,w=None),"S8":dict(w=1600),"S4p":dict(indep=True,indep_rel=True,w=1600)}
TGT={g:float(np.mean([(60-r['slo'])/60 for r in json.load(open(f'{Q}/r67band/out/{n}.json'))['rows']])) for g,n in (("2","S4b"),("05","S4a"))}
_SP=[None]
def prior(arm):
    cfg,pr=V.cfg_prior()
    if arm in ("S8","S4p"):
        if _SP[0] is None: _SP[0]=C7.S7Prior(LIB,cfg)
        return _SP[0]
    return pr
def ctl_of(arm,L,ue=None):
    cfg,_=V.cfg_prior(); pr=prior(arm)
    return V.CtlSigma(cfg,pr,L) if FLAGS[arm] is None else CG.CtlGen(cfg,pr,L,**FLAGS[arm])
def sim_one(arm,L,ue,phys=RB.PH):
    r=RB.run_ctl(ue,ctl_of(arm,L),V.initial_fleet("S",ue[0],L=L)) if phys is RB.PH else None
    if r is None:
        ph=V.Phys(ue,start=V.initial_fleet("S",ue[0],L=L),p=phys); ctl=ctl_of(arm,L)
        for _ in range(3600//V.DT):
            ph.advance_units()
            if ph.t%V.TICK==0:
                ob=ph.observe(); d=ctl.tick(ph,ob); ph.hot_relief(getattr(ph,"_over",{}))
                if not d and ph.t-ph.last_pool_relief>=ph.p["pool_relief_s"]: ph.enqueue_pool_relief(); ph.last_pool_relief=ph.t
            ph.step()
        r=ph.result()
    ab=r['alloc_by']
    return dict(slo=int(r['slo']),viol=[int(x) for x in r['viol']],alloc_vm=r['alloc_vm'],wk_min=ab['wk']/3,vy_min=ab['vy']/2,slot_min=ab['up']/0.8,flaps=int(RB.flaps(r['events'])))
def job(args):
    arm,g,c,i=args; a,b=BASE[g][arm]; L={"vy":round(c*a,4),"wk":round(c*a,4),"up":round(c*b,4)}
    return i,sim_one(arm,L,LIB[i]["ue"][:60])
def point(pool,arm,g,c):
    c=round(c,2); fn=f'{R}/out/scan/{arm}_{g}_{c:.2f}.json'
    if os.path.exists(fn): return json.load(open(fn))
    res=dict(pool.map(job,[(arm,g,c,i) for i in range(N)],chunksize=8)); rows=[res[i] for i in range(N)]
    d=dict(arm=arm,g=g,c=c,risk=float(np.mean([(60-r['slo'])/60 for r in rows])),cost=float(np.mean([r['alloc_vm'] for r in rows])),rows=rows)
    json.dump(d,open(fn,'w')); print(f"[{__import__('time').strftime('%T')}] {arm} {g} c {c:.2f}: risk {100*d['risk']:.3f} % cost {d['cost']:.1f}",flush=True); return d
if __name__=="__main__":
    print("targets",TGT,flush=True)
    with ProcessPoolExecutor(2) as pool:
        for g in ("2","05"):
            for arm in ("S4","APL","S8","S4p"):
                fr=[point(pool,arm,g,0.70+0.05*k) for k in range(15)]
                fr=sorted(fr,key=lambda d:d['c']); t=TGT[g]
                br=[(x,y) for x,y in zip(fr,fr[1:]) if (x['risk']-t)*(y['risk']-t)<=0]
                if not br: print(f"{arm} {g}: target outside frontier",flush=True); continue
                x,y=br[0]; k=1
                while 0.70+0.02*k < y['c']-1e-9:
                    cc=round(0.70+0.02*k,2)
                    if cc> x['c']+1e-9: point(pool,arm,g,cc)
                    k+=1
    print("DONE",flush=True)
