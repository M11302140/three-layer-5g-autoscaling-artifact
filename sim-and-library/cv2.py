#!/usr/bin/env python3
"""(docstring removed)"""
import json, math, sys, random
import numpy as np
import qsim
from qsim import DT, TICK, HS, NEED, H_OUT, W_IN, DWELL, T, CORES, SPW, FMAX, FMIN, CAP_VY, CAP_UP, expand, oracle_alloc
import cv
BINS=(10,20,30)
def lbin(l): return sum(l>=b for b in BINS)
class Prior2:
    def __init__(s, prior, lmin=8.0):
        s.lmin=lmin; s.tab={}
        for h in HS:
            a=np.array(prior[h],float)   # (ctx, level, rise)
            rel=np.round(a[:,2]/np.maximum(a[:,1],lmin),3); ab=a[:,2]
            s.tab[(h,"rel",None)]=np.unique(rel,return_counts=True)
            s.tab[(h,"abs",None)]=np.unique(ab,return_counts=True)
            lb=np.array([lbin(x) for x in a[:,1]])
            for b in range(len(BINS)+1):
                s.tab[(h,"lvl",b)]=np.unique(ab[lb==b],return_counts=True)
class QM:
    def __init__(s,P,eps,scale="rel",adapt="aci",n0=2000,gamma=None):
        s.P=P; s.eps=eps; s.scale=scale; s.adapt=adapt; s.n0=n0
        s.gamma=gamma if gamma is not None else max(0.005,eps/5)
        s.alpha={h:eps for h in HS}; s.pending={h:[] for h in HS}; s.err={h:[] for h in HS}; s.on={}
    def key(s,h,level): return (h,s.scale,lbin(level) if s.scale=="lvl" else None)
    def margin(s,h,level,c=None):
        k=s.key(h,level); u,cnt=s.P.tab[k]; on=s.on.get(k,[])
        a=s.alpha[h]
        if s.adapt=="aci": a=min(max(a,s.eps/4),1.0)
        elif s.adapt=="aci_b": a=min(max(a,s.eps/2),2*s.eps)
        else: a=s.eps
        w=cnt.astype(float)
        if s.adapt=="mix": w=w*(s.n0/w.sum())
        vals=np.concatenate([u,np.array(on,float)]) if on else u
        ws=np.concatenate([w,np.ones(len(on))]) if on else w
        o=np.argsort(vals,kind="stable"); vals=vals[o]; cw=np.cumsum(ws[o])
        i=int(np.searchsorted(cw,(1-a)*cw[-1]-1e-9,side="left")); i=min(i,len(vals)-1)
        m=float(vals[i])
        return m*max(level,s.P.lmin) if s.scale=="rel" else m
    def tick(s,t,d,i):
        for h in HS:
            k=h//DT
            while s.pending[h] and s.pending[h][0][0]+h<=t:
                t0,base,m=s.pending[h].pop(0); i0=t0//DT
                real=d[i0+1:i0+k+1].max()-base
                e=1.0 if real>m+1e-9 else 0.0; s.err[h].append(e)
                if s.adapt in("aci","aci_b"): s.alpha[h]=min(1.0,max(-0.5,s.alpha[h]+s.gamma*(s.eps-e)))
                v=round(real/max(base,s.P.lmin),3) if s.scale=="rel" else real
                s.on.setdefault(s.key(h,base),[]).append(v)
            s.pending[h].append((t,d[i],s.margin(h,d[i])))
        return None
def run_set(traces, prior, variants, EPS, agg):
    Ps={}
    for tr in traces:
        ue=tr["ue"]; fl=oracle_alloc(ue,5)
        for name,kw in variants:
            lm=kw.get("lmin",8.0)
            if lm not in Ps: Ps[lm]=Prior2(prior,lm)
            for e in EPS:
                q=QM(Ps[lm],e,**{k:v for k,v in kw.items() if k!="lmin"})
                r=cv.simulate(ue,q)
                a=agg.setdefault((name,e),dict(slo=[],full=[],over=[],flaps=[],lost=[],miss=[]))
                a["slo"].append(r["slo"]); a["full"].append(r["slo"]==60); a["over"].append(100*(r["alloc"]-fl)/fl); a["flaps"].append(r["flaps"]); a["lost"].append(r["lost"]); a["miss"].append(r["miss"])
VARIANTS=[("rel aci L8",dict(scale="rel",adapt="aci")),("rel none L8",dict(scale="rel",adapt="none")),
          ("rel aci_b L8",dict(scale="rel",adapt="aci_b")),("rel mix2000 L8",dict(scale="rel",adapt="mix",n0=2000)),("rel mix500 L8",dict(scale="rel",adapt="mix",n0=500)),
          ("rel none L16",dict(scale="rel",adapt="none",lmin=16.0)),("rel aci_b L16",dict(scale="rel",adapt="aci_b",lmin=16.0)),
          ("abs none",dict(scale="abs",adapt="none")),("abs aci_b",dict(scale="abs",adapt="aci_b")),("abs mix500",dict(scale="abs",adapt="mix",n0=500)),
          ("lvl none",dict(scale="lvl",adapt="none")),("lvl aci_b",dict(scale="lvl",adapt="aci_b")),("lvl mix500",dict(scale="lvl",adapt="mix",n0=500))]
if __name__=="__main__":
    random.seed(7)
    lib=json.load(open("prior_traces.json"))
    locs=sorted({t["loc"] for t in lib}); random.shuffle(locs)
    K=6; folds=[locs[i::K] for i in range(K)]
    NTEST=int(sys.argv[1]) if len(sys.argv)>1 else 25
    EPS=(0.1,0.05,0.02)
    agg={}; dev={}
    full_prior={h:[] for h in HS}
    for fi,fold in enumerate(folds):
        train=[t for t in lib if t["loc"] not in fold]; test=[t for t in lib if t["loc"] in fold]
        test=random.sample(test,min(NTEST,len(test)))
        prior={h:[] for h in HS}
        for tr in train:
            d=expand(tr["ue"])
            for h in HS: prior[h]+=cv.samples(d,h)
        run_set(test,prior,VARIANTS,EPS,agg)
        print("fold",fi,file=sys.stderr)
    for tr in lib:
        d=expand(tr["ue"])
        for h in HS: full_prior[h]+=cv.samples(d,h)
    E="/home/user/experiment"
    for nm,f in (("t1","trace_ue_60min_v3_40.json"),("t2","trace_ue_60min_v3_pm.json")):
        a={}; ue=json.load(open(f"{E}/{f}"))["ue"][:60]
        run_set([dict(ue=ue)],full_prior,VARIANTS,EPS,a); dev[nm]=a
    print(f"{'variant':16s} {'eps':>5s} | {'CV SLO':>6s} {'P60':>5s} {'over%':>6s} {'flaps':>5s} {'miss':>5s} | {'t1 SLO':>6s} {'over%':>6s} | {'t2 SLO':>6s} {'over%':>6s}")
    for (name,e),a in agg.items():
        d1=dev["t1"][(name,e)]; d2=dev["t2"][(name,e)]
        print(f"{name:16s} {e:5.2f} | {np.mean(a['slo']):6.2f} {np.mean(a['full']):5.2f} {np.mean(a['over']):+6.1f} {np.mean(a['flaps']):5.2f} {np.nanmean(a['miss']):5.3f} | {d1['slo'][0]:6d} {d1['over'][0]:+6.1f} | {d2['slo'][0]:6d} {d2['over'][0]:+6.1f}")
