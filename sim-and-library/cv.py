#!/usr/bin/env python3
"""(docstring removed)"""
import json, math, sys, random, bisect
import numpy as np
import qsim as Q
from qsim import DT, TICK, HS, NEED, H_OUT, W_IN, DWELL, T, CORES, SPW, FMAX, FMIN, CAP_VY, CAP_UP, expand, oracle_alloc
LMIN=8.0
def ctx_of(d,i):
    j=max(0,i-120//DT); tr=d[i]-d[j]
    return 0 if tr<-1 else (2 if tr>1 else 1)
def samples(d,h):
    """(docstring removed)"""
    n=len(d); k=h//DT; out=[]
    for i in range(0,n-k,TICK//DT): out.append((ctx_of(d,i), d[i], d[i+1:i+k+1].max()-d[i]))
    return out
class Prior:
    """(docstring removed)"""
    def __init__(s, prior):
        s.tab={}
        for h in HS:
            a=np.array(prior[h],float)   # (ctx, level, rise)
            for rel in (False,True):
                v=a[:,2]/np.maximum(a[:,1],LMIN) if rel else a[:,2]
                if rel: v=np.round(v,3)
                for c in (None,0,1,2):
                    vv=v if c is None else v[a[:,0]==c]
                    u,cnt=np.unique(vv,return_counts=True)
                    s.tab[(h,c,rel)]=(u,np.cumsum(cnt))
class QModel:
    def __init__(s, P, eps, rel=False, ctx=False, aci=True, gamma=None, amin=None):
        s.P=P; s.rel=rel; s.ctx=ctx; s.aci=aci; s.eps=eps
        s.gamma=gamma if gamma is not None else max(0.005, eps/5)
        s.amin=amin if amin is not None else eps/4
        s.on={}
        s.alpha={h:eps for h in HS}; s.pending={h:[] for h in HS}; s.err={h:[] for h in HS}
    def margin(s,h,level,c):
        key=(h,c if s.ctx else None,s.rel); u,cum=s.P.tab[key]
        on=s.on.get(key[:2],[])
        a=min(max(s.alpha[h],s.amin),1.0)
        n=cum[-1]+len(on); k=max(1, math.ceil((1-a)*n))
        cand=np.union1d(u,on) if on else u
        cp=np.searchsorted(u,cand,side="right"); cp=np.where(cp>0,cum[np.maximum(cp-1,0)],0)
        if on:
            o=np.sort(on); cp=cp+np.searchsorted(o,cand,side="right")
        i=int(np.searchsorted(cp,k,side="left")); i=min(i,len(cand)-1); m=float(cand[i])
        return m*max(level,LMIN) if s.rel else m
    def tick(s,t,d,i):
        c=ctx_of(d,i)
        for h in HS:
            k=h//DT
            while s.pending[h] and s.pending[h][0][0]+h<=t:
                t0,base,m,c0=s.pending[h].pop(0); i0=t0//DT
                real=d[i0+1:i0+k+1].max()-base
                e=1.0 if real>m+1e-9 else 0.0; s.err[h].append(e)
                if s.aci: s.alpha[h]=min(1.0,max(-0.5,s.alpha[h]+s.gamma*(s.eps-e)))
                v=round(real/max(base,LMIN),3) if s.rel else real
                s.on.setdefault((h,c0 if s.ctx else None),[]).append(v)
            s.pending[h].append((t,d[i],s.margin(h,d[i],c),c))
        return c
def simulate(ue, qm=None, batch=5.0, m0_hold=True):
    d=expand(ue); n=len(d)
    up0=lambda x: x+batch
    cur={k:NEED[k](up0(d[0])) for k in ("vy","up","wk")}
    infl=[]; dying=[]; burn=dict(cur); last_out={k:-1e9 for k in cur}; red={k:None for k in cur}
    alloc=0.0; acts=0; flaps=0; last_dir={k:(None,-1e9) for k in cur}
    lossmin=np.zeros(60); offmin=np.zeros(60)
    for i in range(n):
        t=i*DT
        for x in [x for x in infl if x[0]<=t]: cur[x[1]]+=1; infl.remove(x)
        for x in [x for x in dying if x[0]<=t]: burn[x[1]]-=1; dying.remove(x)
        capv=cur["vy"]*CAP_VY; capu=cur["up"]*CAP_UP; l=0.0
        if d[i]>capv: l=1-capv/d[i]
        x=d[i]*(1-l)
        if x>capu: l=1-(1-l)*capu/x
        lossmin[i*DT//60]+=l*d[i]*DT; offmin[i*DT//60]+=d[i]*DT
        alloc+=sum(CORES[k]*burn[k] for k in burn)*DT/60
        if t%TICK: continue
        c=qm.tick(t,d,i) if qm else None
        pend={k:sum(1 for x in infl if x[1]==k) for k in cur}
        U=(lambda h: d[i]+qm.margin(h,d[i],c)) if qm else (lambda h: d[i]+batch)
        for k in ("vy","wk","up"):
            want=NEED[k](U(H_OUT[k]))
            if want>cur[k]+pend[k] and cur[k]+pend[k]<FMAX[k]:
                if k=="up" and cur["up"]+pend["up"]+1>(cur["wk"]+pend["wk"])*SPW: continue
                teff=t+T[k+"_out"]
                if k=="up" and cur["up"]+pend["up"]+1>cur["wk"]*SPW:
                    teff=max(teff, max(x[0] for x in infl if x[1]=="wk")+T["up_out"])
                infl.append((teff,k)); burn[k]+=1; acts+=1; last_out[k]=t
                if last_dir[k][0]==-1 and t-last_dir[k][1]<=600: flaps+=1
                last_dir[k]=(+1,t)
        for k in ("up","vy","wk"):
            if cur[k]<=FMIN[k] or pend[k]>0: red[k]=None; continue
            if k=="wk" and (cur["wk"]-1)*SPW<cur["up"]+pend["up"]: red[k]=None; continue
            if qm:
                ok=NEED[k](U(W_IN[k]))<=cur[k]-1; dwell=DWELL[k]; vmdw=0
            else:
                w={"up":300,"vy":115,"wk":145}[k]; j0=max(0,i-w//DT)
                ok=NEED[k](d[j0:i+1].max()+batch)<=cur[k]-1; dwell=0; vmdw=(600 if k in ("vy","wk") else 300) if m0_hold else 0
            if not ok: red[k]=None; continue
            if red[k] is None: red[k]=t
            if t-red[k]>=dwell and t-last_out[k]>=vmdw:
                cur[k]-=1; dying.append((t+T[k+"_in"],k)); acts+=1; red[k]=None
                if last_dir[k][0]==+1 and t-last_dir[k][1]<=600: flaps+=1
                last_dir[k]=(-1,t)
    pct=100*lossmin/np.maximum(offmin,1e-9)
    cov=np.mean([np.mean(qm.err[h]) for h in set(H_OUT.values()) if qm.err[h]]) if qm else float("nan")
    return dict(slo=int((pct<=0.1).sum()), worst=float(pct.max()), lost=float(lossmin.sum()*250e3/1e6), alloc=alloc, acts=acts, flaps=flaps, miss=cov)
if __name__=="__main__":
    random.seed(7)
    lib=json.load(open("prior_traces.json"))
    locs=sorted({t["loc"] for t in lib}); random.shuffle(locs)
    K=6; folds=[locs[i::K] for i in range(K)]
    NTEST=int(sys.argv[1]) if len(sys.argv)>1 else 30
    EPS=(0.2,0.1,0.05,0.02,0.01)
    VAR=[("abs",dict(rel=False,ctx=False,aci=False)),("abs+aci",dict(rel=False,ctx=False,aci=True)),
         ("abs+ctx",dict(rel=False,ctx=True,aci=False)),("abs+ctx+aci",dict(rel=False,ctx=True,aci=True)),
         ("rel+ctx+aci",dict(rel=True,ctx=True,aci=True)),("rel+aci",dict(rel=True,ctx=False,aci=True))]
    agg={}
    def add(key,r,fl):
        a=agg.setdefault(key,dict(slo=[],full=[],over=[],flaps=[],acts=[],lost=[],miss=[]))
        a["slo"].append(r["slo"]); a["full"].append(r["slo"]==60); a["over"].append(100*(r["alloc"]-fl)/fl); a["flaps"].append(r["flaps"]); a["acts"].append(r["acts"]); a["lost"].append(r["lost"]); a["miss"].append(r["miss"])
    for fi,fold in enumerate(folds):
        train=[t for t in lib if t["loc"] not in fold]; test=[t for t in lib if t["loc"] in fold]
        test=random.sample(test,min(NTEST,len(test)))
        prior={h:[] for h in HS}
        for tr in train:
            d=expand(tr["ue"])
            for h in HS: prior[h]+=samples(d,h)
        PR=Prior(prior)
        for tr in test:
            ue=tr["ue"]; fl=oracle_alloc(ue,5)
            add(("M0 batch5",None),simulate(ue),fl)
            add(("M0 batch5 nohold",None),simulate(ue,m0_hold=False),fl)
            for b in (3.0,8.0): add((f"M0 batch{b:.0f}",None),simulate(ue,batch=b),fl)
            for name,kw in VAR:
                for e in EPS: add((name,e),simulate(ue,QModel(PR,e,**kw)),fl)
        print("fold",fi,"done",len(test),file=sys.stderr)
    print(f"{'variant':18s} {'eps':>5s} {'n':>4s} {'SLO/60':>7s} {'P(60/60)':>8s} {'lostM':>7s} {'over_floor%':>11s} {'acts':>5s} {'flaps':>5s} {'miss(out)':>9s}")
    for (name,e),a in agg.items():
        print(f"{name:18s} {str(e) if e else '':>5s} {len(a['slo']):4d} {np.mean(a['slo']):7.2f} {np.mean(a['full']):8.2f} {np.mean(a['lost']):7.1f} {np.mean(a['over']):+11.1f} {np.mean(a['acts']):5.1f} {np.mean(a['flaps']):5.2f} {np.nanmean(a['miss']):9.3f}")
    json.dump({f"{k[0]}|{k[1]}":{m:float(np.nanmean(v)) for m,v in a.items()} for k,a in agg.items()},open("cv_result.json","w"),indent=1)
