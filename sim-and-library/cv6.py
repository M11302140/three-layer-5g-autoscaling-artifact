#!/usr/bin/env python3
"""(docstring removed)"""
import json, math, sys, random
import numpy as np
import qsim, cv, cv2
from qsim import DT, TICK, HS, NEED, H_OUT, W_IN, DWELL, T, CORES, SPW, FMAX, FMIN, CAP_VY, CAP_UP, expand, oracle_alloc
HS2=sorted(set(HS+[int(round((DWELL[k]+W_IN[k])/15)*15) for k in ("up","vy","wk")]))
def samples(d,h):
    n=len(d); k=h//DT; out=[]
    for i in range(0,n-k,TICK//DT): out.append((0, d[i], d[i+1:i+k+1].max()-d[i]))
    return out
class P2(cv2.Prior2):
    def __init__(s,prior,lmin=8.0):
        s.lmin=lmin; s.tab={}
        for h in prior:
            a=np.array(prior[h],float); rel=np.round(a[:,2]/np.maximum(a[:,1],lmin),3)
            s.tab[(h,"rel",None)]=np.unique(rel,return_counts=True)
ONE_SIDED=True
class QM(cv2.QM):
    def margin(s,h,level,c=None,a_override=None):
        k=s.key(h,level); u,cnt=s.P.tab[k]; on=s.on.get(k,[])
        a=min(max(s.alpha[h],s.eps/4),s.eps if ONE_SIDED else 1.0)
        if a_override is not None: a=a_override
        vals=np.concatenate([u,np.array(on,float)]) if on else u
        ws=np.concatenate([cnt.astype(float),np.ones(len(on))]) if on else cnt.astype(float)
        o=np.argsort(vals,kind="stable"); vals=vals[o]; cw=np.cumsum(ws[o])
        i=int(np.searchsorted(cw,(1-a)*cw[-1]-1e-9,side="left")); i=min(i,len(vals)-1)
        return float(vals[i])*max(level,s.P.lmin)
    def __init__(s,P,eps,hs):
        s.P=P; s.eps=eps; s.scale="rel"; s.adapt="aci"; s.n0=0; s.gamma=max(0.005,eps/5); s.hs=hs
        s.alpha={h:eps for h in hs}; s.pending={h:[] for h in hs}; s.err={h:[] for h in hs}; s.on={}
    def tick(s,t,d,i):
        for h in s.hs:
            k=h//DT
            while s.pending[h] and s.pending[h][0][0]+h<=t:
                t0,base,m=s.pending[h].pop(0); i0=t0//DT
                real=d[i0+1:i0+k+1].max()-base
                e=1.0 if real>m+1e-9 else 0.0; s.err[h].append(e)
                s.alpha[h]=min(s.eps if ONE_SIDED else 1.0,max(-0.5,s.alpha[h]+s.gamma*(s.eps-e)))
                s.on.setdefault(s.key(h,base),[]).append(round(real/max(base,s.P.lmin),3))
            s.pending[h].append((t,d[i],s.margin(h,d[i])))
def simulate(ue, q, rule="R0", k=1.0):
    d=expand(ue); n=len(d)
    cur={x:NEED[x](d[0]+q.margin(H_OUT[x],d[0])) for x in ("vy","up","wk")}
    if cur["wk"]*SPW<cur["up"]: cur["wk"]=math.ceil(cur["up"]/SPW)
    infl=[]; dying=[]; burn=dict(cur); last_out={x:-1e9 for x in cur}
    alloc=0.0; acts=0; flaps=0; last_dir={x:(None,-1e9) for x in cur}
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
        alloc+=sum(CORES[z]*burn[z] for z in burn)*DT/60
        if t%TICK: continue
        q.tick(t,d,i)
        pend={z:sum(1 for x in infl if x[1]==z) for z in cur}
        for z in ("vy","wk","up"):
            want=NEED[z](d[i]+q.margin(H_OUT[z],d[i]))
            if want>cur[z]+pend[z] and cur[z]+pend[z]<FMAX[z]:
                if z=="up" and cur["up"]+pend["up"]+1>(cur["wk"]+pend["wk"])*SPW: continue
                teff=t+T[z+"_out"]
                if z=="up" and cur["up"]+pend["up"]+1>cur["wk"]*SPW:
                    teff=max(teff, max(x[0] for x in infl if x[1]=="wk")+T["up_out"])
                infl.append((teff,z)); burn[z]+=1; acts+=1; last_out[z]=t
                if last_dir[z][0]==-1 and t-last_dir[z][1]<=600: flaps+=1
                last_dir[z]=(+1,t)
        for z in ("up","vy","wk"):
            if cur[z]<=FMIN[z] or pend[z]>0: continue
            if z=="wk" and (cur["wk"]-1)*SPW<cur["up"]+pend["up"]: continue
            dw=DWELL[z]*(k if rule=="R2" else 1.0)
            if t<dw+W_IN[z] or t-last_out[z]<dw: continue
            j0=max(0,i-int(dw)//DT); base=d[j0:i+1].max()
            if rule.startswith("R1"):
                H=int(round((DWELL[z]+W_IN[z])/15)*15)
                rho=float(rule[3:]) if len(rule)>2 else None
                X=base+q.margin(H,base,a_override=rho)
                x=X+q.margin(H_OUT[z],X)
            else:
                x=base+q.margin(W_IN[z],base)
            if NEED[z](x)<=cur[z]-1:
                cur[z]-=1; dying.append((t+T[z+"_in"],z)); acts+=1
                if last_dir[z][0]==+1 and t-last_dir[z][1]<=600: flaps+=1
                last_dir[z]=(-1,t)
    pct=100*lossmin/np.maximum(offmin,1e-9)
    return dict(slo=int((pct<=0.1).sum()), alloc=alloc, acts=acts, flaps=flaps)
if __name__=="__main__":
    random.seed(7)
    lib=json.load(open("prior_traces.json"))
    locs=sorted({t["loc"] for t in lib}); random.shuffle(locs)
    K=6; folds=[locs[i::K] for i in range(K)]
    NTEST=int(sys.argv[1]) if len(sys.argv)>1 else 25
    RULES=[("R0",1.0),("R1",1.0),("R1p0.5",1.0),("R1p0.25",1.0),("R2",2.0)]
    agg={}; dev={}
    def add(A,key,r,fl):
        a=A.setdefault(key,dict(slo=[],full=[],over=[],flaps=[],acts=[]))
        a["slo"].append(r["slo"]); a["full"].append(r["slo"]==60); a["over"].append(100*(r["alloc"]-fl)/fl); a["flaps"].append(r["flaps"]); a["acts"].append(r["acts"])
    allp={h:[] for h in HS2}
    for fi,fold in enumerate(folds):
        train=[t for t in lib if t["loc"] not in fold]; test=[t for t in lib if t["loc"] in fold]
        test=random.sample(test,min(NTEST,len(test)))
        prior={h:[] for h in HS2}
        for tr in train:
            d=expand(tr["ue"])
            for h in HS2: prior[h]+=samples(d,h)
        P=P2(prior)
        for tr in test:
            ue=tr["ue"]; fl=oracle_alloc(ue,5)
            for e in (0.1,0.05):
                for rule,k in RULES: add(agg,(rule,k,e),simulate(ue,QM(P,e,HS2),rule,k),fl)
        print("fold",fi,file=sys.stderr)
    for tr in lib:
        d=expand(tr["ue"])
        for h in HS2: allp[h]+=samples(d,h)
    P=P2(allp); E="/home/user/experiment"
    for nm,f in (("t1","trace_ue_60min_v3_40.json"),("t2","trace_ue_60min_v3_pm.json")):
        ue=json.load(open(f"{E}/{f}"))["ue"][:60]; fl=oracle_alloc(ue,5); A={}
        for e in (0.1,0.05):
            for rule,k in RULES: add(A,(rule,k,e),simulate(ue,QM(P,e,HS2),rule,k),fl)
        dev[nm]=A
    print(f"{'rule':8s} {'eps':>5s} | {'CV SLO':>6s} {'P60':>5s} {'over%':>6s} {'acts':>5s} {'flaps':>5s} | t1 SLO over% flaps | t2 SLO over% flaps")
    for (rule,k,e),a in agg.items():
        d1=dev["t1"][(rule,k,e)]; d2=dev["t2"][(rule,k,e)]
        nm=rule+(f" k={k:.0f}" if rule=="R2" else "")
        print(f"{nm:8s} {e:5.2f} | {np.mean(a['slo']):6.2f} {np.mean(a['full']):5.2f} {np.mean(a['over']):+6.1f} {np.mean(a['acts']):5.1f} {np.mean(a['flaps']):5.2f} | {d1['slo'][0]:4d} {d1['over'][0]:+6.1f} {d1['flaps'][0]:4d}  | {d2['slo'][0]:4d} {d2['over'][0]:+6.1f} {d2['flaps'][0]:4d}")
