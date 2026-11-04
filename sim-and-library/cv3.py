#!/usr/bin/env python3
"""(docstring removed)"""
import json, math, sys, random
import numpy as np
import qsim, cv, cv2
from qsim import DT, TICK, HS, NEED, H_OUT, W_IN, DWELL, T, CORES, SPW, FMAX, FMIN, CAP_VY, CAP_UP, expand, oracle_alloc
def simulate(ue, qm_out, qm_in, inmode="w", start_full=False, batch=None, m0_hold=True):
    d=expand(ue); n=len(d)
    if batch is not None: cur={k:NEED[k](d[0]+batch) for k in ("vy","up","wk")}
    else: cur={k:NEED[k](d[0]+qm_out.margin(H_OUT[k],d[0])) for k in ("vy","up","wk")}
    if start_full: cur=dict(FMAX)
    if cur["wk"]*SPW<cur["up"]: cur["wk"]=math.ceil(cur["up"]/SPW)
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
        if qm_out: qm_out.tick(t,d,i)
        if qm_in is not None and qm_in is not qm_out: qm_in.tick(t,d,i)
        pend={k:sum(1 for x in infl if x[1]==k) for k in cur}
        for k in ("vy","wk","up"):
            want=NEED[k](d[i]+(qm_out.margin(H_OUT[k],d[i]) if qm_out else batch))
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
            if qm_in is not None:
                if inmode=="h": w=H_OUT[k]
                elif inmode=="wfree": w=(45 if cur["up"]<cur["wk"]*SPW else 165) if k=="up" else W_IN[k]
                else: w=W_IN[k]
                hh=min(HS,key=lambda x:abs(x-w)) if w not in HS else w
                j0=max(0,i-int(DWELL[k])//DT); base=d[j0:i+1].max()
                ok=NEED[k](base+qm_in.margin(hh,base))<=cur[k]-1; dwell=0; vmdw=DWELL[k]
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
    return dict(slo=int((pct<=0.1).sum()), lost=float(lossmin.sum()*250e3/1e6), alloc=alloc, acts=acts, flaps=flaps)
if __name__=="__main__":
    random.seed(7)

    lib=json.load(open("prior_traces.json"))
    locs=sorted({t["loc"] for t in lib}); random.shuffle(locs)
    K=6; folds=[locs[i::K] for i in range(K)]
    NTEST=int(sys.argv[1]) if len(sys.argv)>1 else 25
    CFG=[]
    for eo in (0.1,0.05,0.02):
        for mode in ("w","wfree","h"):
            CFG.append((f"out{eo} in={mode} e_in={eo}",eo,eo,mode))
        for ei in (0.2,0.1):
            if ei>eo: CFG.append((f"out{eo} in=wfree e_in={ei}",eo,ei,"wfree"))
    agg={}
    def add(key,r,fl):
        a=agg.setdefault(key,dict(slo=[],full=[],over=[],flaps=[],lost=[]))
        a["slo"].append(r["slo"]); a["full"].append(r["slo"]==60); a["over"].append(100*(r["alloc"]-fl)/fl); a["flaps"].append(r["flaps"]); a["lost"].append(r["lost"])
    for fi,fold in enumerate(folds):
        train=[t for t in lib if t["loc"] not in fold]; test=[t for t in lib if t["loc"] in fold]
        test=random.sample(test,min(NTEST,len(test)))
        prior={h:[] for h in HS}
        for tr in train:
            d=expand(tr["ue"])
            for h in HS: prior[h]+=cv.samples(d,h)
        P=cv2.Prior2(prior,8.0)
        for tr in test:
            ue=tr["ue"]; fl=oracle_alloc(ue,5)
            for sf in (False,True):
                for b in (5.0,8.0): add((f"M0 batch{b:.0f}",sf),simulate(ue,None,None,batch=b,start_full=sf),fl)
                for name,eo,ei,mode in CFG:
                    qo=cv2.QM(P,eo,scale="rel",adapt="aci"); qi=qo if ei==eo else cv2.QM(P,ei,scale="rel",adapt="aci")
                    add((name,sf),simulate(ue,qo,qi,inmode=mode,start_full=sf),fl)
        print("fold",fi,file=sys.stderr)
    print(f"{'config':30s} | {'SLO':>6s} {'P60':>5s} {'over%':>6s} {'flaps':>5s} | start-full: {'SLO':>6s} {'over%':>6s} {'flaps':>5s}")
    names=[]
    for (n_,sf) in agg:
        if n_ not in names: names.append(n_)
    for n_ in names:
        a=agg[(n_,False)]; b=agg[(n_,True)]
        print(f"{n_:30s} | {np.mean(a['slo']):6.2f} {np.mean(a['full']):5.2f} {np.mean(a['over']):+6.1f} {np.mean(a['flaps']):5.2f} |             {np.mean(b['slo']):6.2f} {np.mean(b['over']):+6.1f} {np.mean(b['flaps']):5.2f}")
