#!/usr/bin/env python3
"""(docstring removed)"""
import json, math, sys, bisect
import numpy as np
DT=5; TICK=30
CAP_VY=4.45e6*0.93/250e3; CAP_UP=5; SPW=2
FMAX=dict(vy=3,wk=4,up=8); FMIN=dict(vy=1,wk=1,up=2)
T=dict(up_out=15, up_in=120, vy_out=85, vy_in=30, wk_out=100, wk_in=60)   # calib T_ready
CORES=dict(wk=3.0, vy=2.0, up=0.8); LAMBDA=0.002; DLOSS=dict(up=0.005, vy=0.0005, wk=0.0)
def need_vy(d): return min(FMAX["vy"], max(FMIN["vy"], math.ceil(d/CAP_VY-1e-9)))
def need_up(d): return min(FMAX["up"], max(FMIN["up"], math.ceil(math.ceil(d-0.25)/CAP_UP)))
def need_wk(d): return min(FMAX["wk"], max(FMIN["wk"], math.ceil(need_up(d)/SPW)))
NEED=dict(vy=need_vy, up=need_up, wk=need_wk)
def expand(ue): return np.repeat(np.array(ue,float), 60//DT)

H_OUT=dict(up=T["up_out"]+TICK, vy=T["vy_out"]+TICK, wk=T["wk_out"]+T["up_out"]+TICK)
W_IN =dict(up=T["up_in"]+T["up_out"]+TICK, vy=T["vy_out"]+TICK, wk=T["wk_in"]+T["wk_out"]+T["up_out"]+TICK)

DWELL={k:(T[k+"_in"]+T[k+"_out"]) + DLOSS[k]/(LAMBDA*CORES[k]) for k in ("up","vy","wk")}
HS=sorted(set(list(H_OUT.values())+list(W_IN.values())))
def scores(d, h):
    """(docstring removed)"""
    n=len(d); k=h//DT; step=TICK//DT; out=[]
    for i in range(0,n-k,step): out.append(d[i+1:i+k+1].max()-d[i])
    return out
class Quant:
    """(docstring removed)"""
    def __init__(s, prior, eps, gamma=0.02, aci=True):
        s.sc={h:sorted(prior[h]) for h in HS}; s.eps=eps; s.gamma=gamma; s.aci=aci
        s.alpha={h:eps for h in HS}; s.pending={h:[] for h in HS}; s.err={h:[] for h in HS}
    def margin(s,h):
        a=min(max(s.alpha[h],0.0),1.0); arr=s.sc[h]
        if a<=0: return arr[-1]
        i=min(len(arr)-1, max(0, math.ceil((1-a)*len(arr))-1)); return arr[i]
    def issue(s,t,base):
        for h in HS: s.pending[h].append((t,base,s.margin(h)))
    def observe(s,t,d,i):
        for h in HS:
            k=h//DT
            while s.pending[h] and s.pending[h][0][0]+h<=t:
                t0,base,m=s.pending[h].pop(0); i0=t0//DT
                real=d[i0+1:i0+k+1].max()-base
                e=1.0 if real>m+1e-9 else 0.0; s.err[h].append(e)
                if s.aci: s.alpha[h]+=s.gamma*(s.eps-e)
                bisect.insort(s.sc[h], real)
def simulate(ue, model, prior=None, eps=0.05, start=None, aci=True):
    d=expand(ue); n=len(d)
    q=Quant(prior,eps,aci=aci) if model=="MQ" else None
    cur=dict(start) if start else {k:NEED[k](d[0]+(5 if model=="M0" else 0)) for k in ("vy","up","wk")}
    if cur["wk"]*SPW<cur["up"]: cur["wk"]=math.ceil(cur["up"]/SPW)
    infl=[]      # (t_eff, layer, +1)
    last_out={k:-1e9 for k in cur}; redundant_since={k:None for k in cur}
    alloc=0.0; hist=[]; acts={k:0 for k in cur}; flaps=0; last_dir={k:(None,-1e9) for k in cur}
    burn=dict(cur)
    dying=[]           # (t_end, layer)
    lossmin=np.zeros(60); offmin=np.zeros(60)
    for i in range(n):
        t=i*DT
        for x in [x for x in infl if x[0]<=t]: cur[x[1]]+=1; infl.remove(x)
        for x in [x for x in dying if x[0]<=t]: burn[x[1]]-=1; dying.remove(x)

        capv=cur["vy"]*CAP_VY; capu=cur["up"]*CAP_UP
        l=0.0
        if d[i]>capv: l=1-capv/d[i]
        x=d[i]*(1-l)
        if x>capu: l=1-(1-l)*capu/x
        lossmin[i*DT//60]+=l*d[i]*DT; offmin[i*DT//60]+=d[i]*DT
        alloc+=sum(CORES[k]*burn[k] for k in burn)*DT/60
        if t%TICK==0:
            if q: q.observe(t,d,i); q.issue(t,d[i])
            pend={k:sum(1 for x in infl if x[1]==k) for k in cur}
            def upper(h, base):
                if model=="MQ": return base+q.margin(h)
                return base+5.0

            for k in ("vy","wk","up"):
                want=NEED[k](upper(H_OUT[k], d[i]))
                if want>cur[k]+pend[k] and cur[k]+pend[k]<FMAX[k]:
                    if k=="up" and cur["up"]+pend["up"]+1>(cur["wk"]+pend["wk"])*SPW: continue
                    teff=t+T[k+"_out"]
                    if k=="up" and cur["up"]+pend["up"]+1>cur["wk"]*SPW:
                        teff=max(teff, max(x[0] for x in infl if x[1]=="wk")+T["up_out"])
                    infl.append((teff,k)); burn[k]+=1; acts[k]+=1; last_out[k]=t
                    if last_dir[k][0]==-1 and t-last_dir[k][1]<=600: flaps+=1
                    last_dir[k]=(+1,t)

            for k in ("up","vy","wk"):
                if cur[k]<=FMIN[k] or pend[k]>0: redundant_since[k]=None; continue
                if k=="wk" and (cur["wk"]-1)*SPW<cur["up"]+pend["up"]: redundant_since[k]=None; continue
                if model=="MQ":
                    ok=NEED[k](upper(W_IN[k], d[i]))<=cur[k]-1
                    dwell=DWELL[k]; vmdw=0
                else:
                    w={"up":300,"vy":115,"wk":145}[k]; j0=max(0,i-w//DT)
                    ok=NEED[k](d[j0:i+1].max()+5.0)<=cur[k]-1
                    dwell=0; vmdw=600 if k in ("vy","wk") else 300
                if not ok: redundant_since[k]=None; continue
                if redundant_since[k] is None: redundant_since[k]=t
                if t-redundant_since[k]>=dwell and t-last_out[k]>=vmdw:
                    cur[k]-=1; dying.append((t+T[k+"_in"],k)); acts[k]+=1; redundant_since[k]=None
                    if last_dir[k][0]==+1 and t-last_dir[k][1]<=600: flaps+=1
                    last_dir[k]=(-1,t)
        hist.append((t,cur["vy"],cur["wk"],cur["up"]))
    pct=100*lossmin/np.maximum(offmin,1e-9)
    res=dict(slo=int((pct<=0.1).sum()), worst=float(pct.max()), lost=float(lossmin.sum()*250e3/1e6), alloc=alloc, acts=sum(acts.values()), flaps=flaps)
    if q: res["cov"]={h:(1-np.mean(q.err[h]) if q.err[h] else None) for h in HS}; res["alpha"]={h:q.alpha[h] for h in HS}; res["margin"]={h:q.margin(h) for h in HS}
    return res, hist
def oracle_alloc(ue, lead=0):
    d=expand(ue); a=0.0
    for i in range(len(d)):
        x=d[i]+lead; a+=(CORES["vy"]*need_vy(x)+CORES["up"]*need_up(x)+CORES["wk"]*need_wk(x))*DT/60
    return a
if __name__=="__main__":
    E="/home/user/experiment"
    TR=dict(t1="trace_ue_60min_v3_40.json", t2="trace_ue_60min_v3_pm.json", t3="trace_ue_60min_v3_t3.json", t4="trace_ue_60min_v3_t4.json", t5="trace_ue_60min_v3_t5.json")
    lib=json.load(open("prior_traces.json"))
    prior={h:[] for h in HS}
    for tr in lib:
        d=expand(tr["ue"])
        for h in HS: prior[h]+=scores(d,h)
    print("horizons out",H_OUT,"in",W_IN,"dwell",{k:round(v) for k,v in DWELL.items()})
    print("prior scores per horizon:",len(prior[HS[0]]))
    for h in HS:
        a=np.array(prior[h]); print(f"  h={h:3d}s  P(rise>0)={np.mean(a>0):.3f}  q80={np.quantile(a,.8):.0f} q90={np.quantile(a,.9):.0f} q95={np.quantile(a,.95):.0f} q99={np.quantile(a,.99):.0f} q999={np.quantile(a,.999):.0f} max={a.max():.0f}")
    print(f"\n{'trace':5s} {'model':12s} {'SLO':>4s} {'worst%':>7s} {'lostM':>7s} {'alloc':>6s} {'vsFloor%':>8s} {'acts':>4s} {'flaps':>5s}  coverage(out-horizons)")
    for name,f in TR.items():
        ue=json.load(open(f"{E}/{f}"))["ue"][:60]
        orc=oracle_alloc(ue,0); fl=oracle_alloc(ue,5)
        print(f"{name:5s} {'oracle/floor':12s} {'':4s} {'':7s} {'':7s} {orc:6.0f} / {fl:.0f}")
        rows=[("M0 batch",dict(model="M0"))]+[(f"MQ e={e}",dict(model="MQ",prior=prior,eps=e)) for e in (0.2,0.1,0.05,0.02,0.01)]
        for lab,kw in rows:
            r,_=simulate(ue,**kw)
            cov=" ".join(f"{h}:{r['cov'][h]:.2f}/m{r['margin'][h]:.0f}" for h in sorted(set(H_OUT.values()))) if "cov" in r else ""
            print(f"{name:5s} {lab:12s} {r['slo']:4d} {r['worst']:7.2f} {r['lost']:7.1f} {r['alloc']:6.0f} {100*(r['alloc']-fl)/fl:+8.1f} {r['acts']:4d} {r['flaps']:5d}  {cov}")
