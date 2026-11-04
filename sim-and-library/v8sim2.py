#!/usr/bin/env python3
"""v8sim2.py(10-03):審查要求的三個決定性 qsim 實驗。
  Exp1 槓桿格子:v6-sim(不重調 / 重調)vs v8-sim 跑過 {base, lead 縮短, 4 槽 worker, 160 制, 全部}。
  Exp2 v8 + 波動度條件(分位數再按「過去 w_A 內實現振幅」分桶)。
  Exp3 v8 + ACI,miss 定義 (a) 上升量 > 餘裕(決策相關) vs (b) 該層實際短缺;先在 1000 條上連續訓練 α 再凍結評估 300 條。
單位:UE(40 制 1 UE = 250 kpps 雙向;160 制把 UE 數 ×4、每 UE 62.5 k)。DT 5 s、tick 30 s、60 分鐘。
"""
import json, math, sys, bisect, numpy as np
SIGMA_INTERP=True   # v7.1.3 桶間插值(設 False 重現舊結果)
DT=5; TICK=30; FMAX=dict(vy=3,wk=4,up=8); FMIN=dict(vy=1,wk=1,up=2)
CORES_BASE=dict(vy=2.0, up=0.8)
class Cfg:
    def __init__(s, scale=1, lead="base", spw=2, name="base"):
        s.name=name; s.scale=scale; s.spw=spw
        s.cap_up=5*scale; s.cap_vy=4.45e6*0.93/250e3*scale
        s.h=dict(up=15, vy=85, wk=100) if lead=="base" else dict(up=15, vy=40, wk=40)
        s.d=dict(up=30, vy=30, wk=60); s.w={k:s.d[k]+s.h[k] for k in s.h}
        s.cores=dict(vy=2.0, up=0.8, wk=1.0+1.0*spw)          # HK core + 1 per slot
        s.batch_v6=5                                           # v6 StepFloor (UE) — untuned
        s.hout=dict(up=s.h["up"]+TICK, vy=s.h["vy"]+TICK, wk=s.h["wk"]+s.h["up"]+TICK)
        s.win =dict(up=s.h["up"]+TICK, vy=s.h["vy"]+TICK, wk=s.h["wk"]+s.h["up"]+TICK)
        s.delta=dict(up=s.w["up"], vy=s.h["vy"]+s.d["vy"], wk=s.w["wk"])
        s.drain=dict(up=120, vy=60, wk=0)
    def need(s,k,x):
        if k=="vy": n=math.ceil(x/s.cap_vy-1e-9)
        elif k=="up": n=math.ceil(math.ceil(x-0.25)/s.cap_up)
        else: n=math.ceil(s.need("up",x)/s.spw)
        return min(FMAX[k], max(FMIN[k], n))
def expand(ue): return np.repeat(np.array(ue,float), 60//DT)
def amp(d,i,wa):   # realized amplitude over the past wa seconds
    j=max(0,i-wa//DT); seg=d[j:i+1]; return float(seg.max()-seg.min())
# ---------- prior with optional (D bucket, A bucket)
class Prior:
    def __init__(s, lib, cfg, vol=False, wa=150):
        s.cfg=cfg; s.vol=vol; s.wa=wa; s.win={k:[] for k in cfg.h}; s.run={k:[] for k in cfg.h}
        for tr in lib:
            d=expand(tr["ue"])*cfg.scale
            for k in cfg.h:
                h0=(cfg.h[k] if k!="wk" else cfg.h["wk"]+cfg.h["up"]); k0=h0//DT; k1=(h0+TICK)//DT; kw=cfg.win[k]//DT
                for i in range(0,len(d)-max(k1,kw),TICK//DT):
                    a=amp(d,i,wa) if vol else 0.0
                    s.win[k].append((d[i],a,max(0.0,d[i+k0:i+k1+1].max()-d[i])))
                    s.run[k].append((d[i],a,max(0.0,d[i+1:i+kw+1].max()-d[i])))
        s.abk={}
        if vol:
            allA=np.array([a for k in cfg.h for _,a,_ in s.win[k]]); s.aq=np.quantile(allA[allA>0],[1/3,2/3]) if (allA>0).any() else [0,0]
        s.idx={}; s.sig={}
        for kind,tab in (("win",s.win),("run",s.run)):
            for k in cfg.h:
                bb={}
                for D,a,r in tab[k]: bb.setdefault(s.db(D),[]).append(r)
                s.sig[(kind,k)]={key:(float(np.std(v)) if len(v)>=30 else None) for key,v in bb.items()}
                allv=[r for _,_,r in tab[k]]; s.sig[(kind,k,'all')]=float(np.std(allv))
        for kind,tab in (("win",s.win),("run",s.run)):
            for k in cfg.h:
                b={}
                for D,a,r in tab[k]: b.setdefault((s.db(D),s.ab(a)),[]).append(r)
                for key in b: b[key].sort()
                s.idx[(kind,k)]=b
    def db(s,D): return int(D//(10*s.cfg.scale))
    def ab(s,a):
        if not s.vol: return 0
        return 0 if a<=0 else (1 if a<=s.aq[0] else (2 if a<=s.aq[1] else 3))
    def sigma(s,kind,k,D):
        """v7.1.3(10-05):桶間線性插值(SIGMA_INTERP=True,與 daemon sigma.go 同定義;False = 舊 floor 桶,重現 10-03/04 的數)"""
        tab=s.sig[(kind,k)]; allv=s.sig[(kind,k,'all')]
        if not SIGMA_INTERP:
            v=tab.get(s.db(D)); return v if v is not None else allv
        B=10*s.cfg.scale; n=(max(tab)+1) if tab else 0
        val=lambda b: (tab.get(b) if tab.get(b) is not None else allv)
        if n==0: return allv
        x=D/B-0.5
        if x<=0: return val(0)
        if x>=n-1: return val(n-1)
        b0=int(math.floor(x)); fr=x-b0
        return (1-fr)*val(b0)+fr*val(b0+1)
    def q(s,kind,k,D,a,level,nmin=30):
        b=s.idx[(kind,k)]; key=(s.db(D),s.ab(a))
        arr=b.get(key,[])
        if len(arr)<nmin:   # fall back: D bucket any A, then any D
            arr=sorted(x for (dbk,abk),v in b.items() if dbk==key[0] for x in v)
            if len(arr)<nmin: arr=sorted(x for v in b.values() for x in v)
        if level<=0: return arr[-1]
        if level>=1: return 0.0
        return arr[min(len(arr)-1, max(0, math.ceil((1-level)*len(arr))-1))]
# ---------- simulators
def loss_step(cfg,cur,D):
    capv=cur["vy"]*cfg.cap_vy; capu=cur["up"]*cfg.cap_up; l=0.0
    if D>capv: l=1-capv/D
    x=D*(1-l)
    if x>capu: l=1-(1-l)*capu/x
    return l
def sim_v6(ue, cfg, retune=False):
    """v6-sim(qsim.py M0 的移植):out = NEED(D+batch) at each layer's lead;in = NEED(past-window max + batch) ≤ cur−1,VM dwell 600 / UP 300(不重調)"""
    d=expand(ue)*cfg.scale; n=len(d); b=cfg.batch_v6*(cfg.scale if retune else 1)
    cur={k:cfg.need(k,d[0]+b) for k in cfg.h}; cur["wk"]=max(cur["wk"],math.ceil(cur["up"]/cfg.spw))
    infl=[]; dying=[]; burn=dict(cur); last_out={k:-1e9 for k in cur}; red={k:None for k in cur}
    alloc=0; acts=0; flaps=0; last_dir={k:(None,-1e9) for k in cur}; lossmin=np.zeros(60); offmin=np.zeros(60)
    W6={"up":300,"vy":115,"wk":145}; VMDW={"up":300,"vy":600,"wk":600}
    for i in range(n):
        t=i*DT
        for x in [x for x in infl if x[0]<=t]: cur[x[1]]+=1; infl.remove(x)
        for x in [x for x in dying if x[0]<=t]: burn[x[1]]-=1; dying.remove(x)
        l=loss_step(cfg,cur,d[i]); lossmin[i*DT//60]+=l*d[i]*DT; offmin[i*DT//60]+=d[i]*DT
        alloc+=sum(cfg.cores[k]*burn[k] for k in burn)*DT/60
        if t%TICK==0:
            pend={k:sum(1 for x in infl if x[1]==k) for k in cur}
            for k in ("vy","wk","up"):
                want=cfg.need(k,d[i]+b)
                if want>cur[k]+pend[k] and cur[k]+pend[k]<FMAX[k]:
                    if k=="up" and cur["up"]+pend["up"]+1>(cur["wk"]+pend["wk"])*cfg.spw: continue
                    teff=t+cfg.h[k]
                    if k=="up" and cur["up"]+pend["up"]+1>cur["wk"]*cfg.spw and any(x[1]=="wk" for x in infl): teff=max(teff,max(x[0] for x in infl if x[1]=="wk")+cfg.h["up"])
                    infl.append((teff,k)); burn[k]+=1; acts+=1; last_out[k]=t
                    if last_dir[k][0]==-1 and t-last_dir[k][1]<=600: flaps+=1
                    last_dir[k]=(+1,t)
            for k in ("up","vy","wk"):
                if cur[k]<=FMIN[k] or pend[k]>0: red[k]=None; continue
                if k=="wk" and (cur["wk"]-1)*cfg.spw<cur["up"]+pend["up"]: red[k]=None; continue
                j0=max(0,i-W6[k]//DT); ok=cfg.need(k,d[j0:i+1].max()+b)<=cur[k]-1
                if not ok: red[k]=None; continue
                if red[k] is None: red[k]=t
                if t-last_out[k]>=VMDW[k]:
                    cur[k]-=1; dying.append((t+cfg.d[k],k)); acts+=1; red[k]=None
                    if last_dir[k][0]==+1 and t-last_dir[k][1]<=600: flaps+=1
                    last_dir[k]=(-1,t)
    pct=100*lossmin/np.maximum(offmin,1e-9)
    return dict(slo=int((pct<=0.1).sum()), alloc=alloc, acts=acts, flaps=flaps)
def sim_v6c(ue, cfg, prior, lam, lock_v6=True, window="lead", lock="v6"):
    L=(lam if isinstance(lam,dict) else {k:lam for k in cfg.h})
    """v6 的結構 + 固定程序給的餘裕:補貨 need(D + lam*sigma_win);退貨 need(past-window max + lam*sigma_run) ≤ cur−1,
       past window = 由 lead 推出的 W_l(window="lead")或 v6 的 300/115/145(window="v6");lock = v6 的 300/600 s(自上次擴容)或 0。"""
    d=expand(ue)*cfg.scale; n=len(d)
    cur={k:cfg.need(k,d[0]+L[k]*prior.sigma("win",k,d[0])) for k in cfg.h}; cur["wk"]=max(cur["wk"],math.ceil(cur["up"]/cfg.spw))
    infl=[]; dying=[]; burn=dict(cur); last_out={k:-1e9 for k in cur}
    alloc=0; acts=0; flaps=0; last_dir={k:(None,-1e9) for k in cur}; lossmin=np.zeros(60); offmin=np.zeros(60)
    W6={"up":300,"vy":115,"wk":145}
    if lock=="w": LOCK={k:cfg.w[k] for k in cfg.h}
    elif lock=="none" or not lock_v6: LOCK={"up":0,"vy":0,"wk":0}
    else: LOCK={"up":300,"vy":600,"wk":600}
    for i in range(n):
        t=i*DT
        for x in [x for x in infl if x[0]<=t]: cur[x[1]]+=1; infl.remove(x)
        for x in [x for x in dying if x[0]<=t]: burn[x[1]]-=1; dying.remove(x)
        l=loss_step(cfg,cur,d[i]); lossmin[i*DT//60]+=l*d[i]*DT; offmin[i*DT//60]+=d[i]*DT
        alloc+=sum(cfg.cores[k]*burn[k] for k in burn)*DT/60
        if t%TICK==0:
            D=d[i]; pend={k:sum(1 for x in infl if x[1]==k) for k in cur}
            for k in ("vy","wk","up"):
                want=cfg.need(k,D+L[k]*prior.sigma("win",k,D))
                if want>cur[k]+pend[k] and cur[k]+pend[k]<FMAX[k]:
                    if k=="up" and cur["up"]+pend["up"]+1>(cur["wk"]+pend["wk"])*cfg.spw: continue
                    teff=t+cfg.h[k]
                    if k=="up" and cur["up"]+pend["up"]+1>cur["wk"]*cfg.spw and any(x[1]=="wk" for x in infl): teff=max(teff,max(x[0] for x in infl if x[1]=="wk")+cfg.h["up"])
                    infl.append((teff,k)); burn[k]+=1; acts+=1; last_out[k]=t
                    if last_dir[k][0]==-1 and t-last_dir[k][1]<=600: flaps+=1
                    last_dir[k]=(+1,t)
            for k in ("up","vy","wk"):
                if cur[k]<=FMIN[k] or pend[k]>0: continue
                if k=="wk" and (cur["wk"]-1)*cfg.spw<cur["up"]+pend["up"]: continue
                Wb=(cfg.win[k] if window=="lead" else W6[k]); j0=max(0,i-Wb//DT)
                ok=cfg.need(k,d[j0:i+1].max()+L[k]*prior.sigma("run",k,D))<=cur[k]-1
                if ok and t-last_out[k]>=LOCK[k]:
                    cur[k]-=1; dying.append((t+cfg.d[k],k)); acts+=1
                    if last_dir[k][0]==+1 and t-last_dir[k][1]<=600: flaps+=1
                    last_dir[k]=(-1,t)
    pct=100*lossmin/np.maximum(offmin,1e-9)
    return dict(slo=int((pct<=0.1).sum()), alloc=alloc, acts=acts, flaps=flaps)
def calibrate_fn(cal, fn, target, grid=None):
    grid=grid or [round(0.2+0.1*i,2) for i in range(40)]
    last=None
    for lam in grid:
        v=0; n=0
        for tr in cal: r=fn(tr["ue"][:60],lam); v+=60-r["slo"]; n+=60
        last=v/n
        if last<=target: return lam,last
    return None,last
class ACI:
    def __init__(s, eps, gamma, miss="rise"): s.eps=eps; s.g=gamma; s.miss=miss; s.alpha={k:eps for k in ("up","vy","wk")}
def sim_v8(ue, cfg, prior, eps=0.05, aci=None, wa=150, lam=None, rep="quantile", rel="R", batch=None):
    """lam: if set, margin = lam*sigma (SLO-calibrated multiplier) instead of quantile; rep: "quantile"|"batch"(v6-style D+batch); rel: "R"|"v6past"(past-window max + batch, holds 300/600)"""
    """v8 R 規則;部位 = cur + |O| − |R|;窗上升補貨、running-max 退貨、N_in = max(N_in,N_out);每單位計時 LIFO;Δ 依層;UP/VY 可取消。
       aci: ACI 物件(跨場保留 α);miss='rise'(決策相關:上升量>餘裕且需要多一單位)或 'short'(該層實際短缺:窗內 D > 在手有效容量)。"""
    d=expand(ue)*cfg.scale; n=len(d)
    cur={k:cfg.need(k,d[0]) for k in cfg.h}; cur["wk"]=max(cur["wk"],math.ceil(cur["up"]/cfg.spw))
    O={k:[] for k in cfg.h}; R={k:[] for k in cfg.h}; timers={k:[] for k in cfg.h}
    alloc=0; acts=0; flaps=0; last_dir={k:(None,-1e9) for k in cfg.h}; lossmin=np.zeros(60); offmin=np.zeros(60)
    pending={k:[] for k in cfg.h}   # (t_issue, D, margin, onhand_cap) for ACI
    for i in range(n):
        t=i*DT
        for k in cfg.h:
            for te in [x for x in O[k] if x<=t]: cur[k]+=1; O[k].remove(te)
            for r in [x for x in R[k] if x["t_done"]<=t]: cur[k]-=1; R[k].remove(r)
        l=loss_step(cfg,cur,d[i]); lossmin[i*DT//60]+=l*d[i]*DT; offmin[i*DT//60]+=d[i]*DT
        alloc+=sum(cfg.cores[k]*(cur[k]+len(O[k])) for k in cfg.h)*DT/60
        if t%TICK==0:
            D=d[i]; a=amp(d,i,wa) if prior.vol else 0.0
            # ACI observe (non-overlapping windows of length hout[k])
            if aci:
                for k in cfg.h:
                    H=cfg.hout[k]
                    while pending[k] and pending[k][0][0]+H<=t:
                        t0,D0,M,capon=pending[k].pop(0); i0=t0//DT
                        if aci.miss=="rise":
                            real=max(0.0,d[i0+1:i0+H//DT+1].max()-D0); m=1.0 if cfg.need(k,D0+real)>cfg.need(k,D0+M) else 0.0
                        else:
                            seg=d[i0+1:i0+H//DT+1]; m=1.0 if (seg>capon).any() else 0.0
                        aci.alpha[k]+=aci.g*(aci.eps-m)
                    if not pending[k] or pending[k][-1][0]+H<=t:
                        capon=(cur[k]*(cfg.cap_vy if k=="vy" else cfg.cap_up) if k!="wk" else cur["wk"]*cfg.spw*cfg.cap_up)
                        lvl=aci.alpha[k]; pending[k].append((t,D,prior.q("win",k,D,a,lvl),capon))
            for k in ("wk","vy","up"):
                lvl=aci.alpha[k] if aci else eps
                if rep=="batch": qo=(batch if batch is not None else cfg.batch_v6*cfg.scale)
                elif lam is not None: qo=lam*prior.sigma("win",k,D)
                else: qo=prior.q("win",k,D,a,lvl)
                if rel=="v6past":
                    W6={"up":300,"vy":115,"wk":145}[k]; j0=max(0,i-W6//DT); bq=(batch if batch is not None else cfg.batch_v6*cfg.scale)
                    qr_abs=d[j0:i+1].max()+bq-D
                elif lam is not None: qr_abs=lam*prior.sigma("run",k,D)
                else: qr_abs=prior.q("run",k,D,a,lvl)
                Nout=cfg.need(k,D+qo); Nin=max(Nout,cfg.need(k,D+qr_abs))
                P=cur[k]+len(O[k])-len(R[k])
                if P<Nout:
                    deficit=Nout-P
                    for r in sorted(R[k],key=lambda r:-r["t0"]):
                        if deficit<=0: break
                        if t<r["t_commit"]: R[k].remove(r); deficit-=1
                    while deficit>0 and cur[k]+len(O[k])<FMAX[k]:
                        if k=="up":
                            pos=(cur["wk"]+len(O["wk"])-len(R["wk"]))*cfg.spw-cur["up"]-len(O["up"])
                            if pos<=0: break
                            teff=t+cfg.h["up"]
                            if cur["up"]+len(O["up"])+1>cur["wk"]*cfg.spw and O["wk"]: teff=max(teff,max(O["wk"])+cfg.h["up"])
                        else: teff=t+cfg.h[k]
                        O[k].append(teff); deficit-=1; acts+=1
                        if last_dir[k][0]==-1 and t-last_dir[k][1]<=600: flaps+=1
                        last_dir[k]=(+1,t)
                    timers[k]=[]; continue
                kmax=max(0,min(P-Nin, cur[k]-FMIN[k]))
                if k=="wk": kmax=min(kmax, max(0,cur["wk"]-math.ceil((cur["up"]+len(O["up"]))/cfg.spw)))
                if k=="up" and R["up"]: kmax=min(kmax,1)
                while len(timers[k])<kmax: timers[k].append(t)
                while len(timers[k])>kmax: timers[k].pop()
                if rel=='v6past':
                    lock={'up':300,'vy':600,'wk':600}[k]; due_ok = (t-last_dir[k][1]>=lock) if last_dir[k][0]==+1 else True
                    cand=[e for e in timers[k]] if due_ok else []
                else: cand=[e for e in timers[k] if t-e>=cfg.delta[k]]
                for e in cand[:2]:
                    timers[k].remove(e)
                    R[k].append(dict(t0=t,t_commit=t+cfg.drain[k],t_done=t+cfg.drain[k]+cfg.d[k])); acts+=1
                    if last_dir[k][0]==+1 and t-last_dir[k][1]<=600: flaps+=1
                    last_dir[k]=(-1,t)
    pct=100*lossmin/np.maximum(offmin,1e-9)
    return dict(slo=int((pct<=0.1).sum()), alloc=alloc, acts=acts, flaps=flaps)
def calibrate(cal, cfg, prior, target, grid=None, **kw):
    """Learn-then-Test (fixed sequence, monotone): smallest lam on grid with pooled violation-minute fraction <= target on calibration traces."""
    grid=grid or [round(0.2+0.1*i,2) for i in range(40)]
    out=[]
    for lam in grid:
        v=0; n=0
        for tr in cal:
            r=sim_v8(tr["ue"][:60],cfg,prior,lam=lam,**kw); v+=60-r["slo"]; n+=60
        risk=v/n; out.append((lam,risk))
        if risk<=target: return lam,risk,out
    return None,out[-1][1],out
def floor_alloc(ue,cfg,lead_batch=None):
    d=expand(ue)*cfg.scale; lb=cfg.batch_v6*cfg.scale if lead_batch is None else lead_batch; a=0.0
    for i in range(len(d)):
        x=d[i]+lb; a+=(cfg.cores["vy"]*cfg.need("vy",x)+cfg.cores["up"]*cfg.need("up",x)+cfg.cores["wk"]*cfg.need("wk",x))*DT/60
    return a
def summarize(rs,fls):
    import statistics as st
    return f"SLO={st.mean(r['slo'] for r in rs):5.2f} P60={st.mean(r['slo']==60 for r in rs):4.2f} over_floor={100*st.mean((r['alloc']-f)/f for r,f in zip(rs,fls)):+6.1f}% acts={st.mean(r['acts'] for r in rs):4.1f} flaps={st.mean(r['flaps'] for r in rs):4.2f}"
if __name__=="__main__":
    lib=json.load(open("prior_traces.json")); EVAL=lib[:300]; TRAIN=lib[300:1300]
    which=sys.argv[1] if len(sys.argv)>1 else "all"
    if which in ("1","all"):
        print("=== Exp1 lever grid: v6-sim untuned / v6-sim retuned(batch×scale) / v8 (eps 0.05)")
        grid=[Cfg(1,"base",2,"base(40,lead base,2-slot)"), Cfg(1,"short",2,"lead short (VY/WK 40 s)"), Cfg(1,"base",4,"4-slot worker"), Cfg(4,"base",2,"160-scale"), Cfg(4,"short",4,"160+short+4-slot")]
        for cfg in grid:
            pr=Prior(lib,cfg); fls=[floor_alloc(tr["ue"][:60],cfg) for tr in EVAL]
            r6=[sim_v6(tr["ue"][:60],cfg) for tr in EVAL]; r6r=[sim_v6(tr["ue"][:60],cfg,retune=True) for tr in EVAL]; r8=[sim_v8(tr["ue"][:60],cfg,pr) for tr in EVAL]
            print(f"[{cfg.name}]\n   v6 untuned : {summarize(r6,fls)}\n   v6 retuned : {summarize(r6r,fls)}\n   v8 eps.05  : {summarize(r8,fls)}", flush=True)
    if which in ("2","all"):
        print("=== Exp2 volatility conditioning (base cfg)")
        cfg=Cfg(); fls=[floor_alloc(tr["ue"][:60],cfg) for tr in EVAL]
        for vol in (False,True):
            pr=Prior(lib,cfg,vol=vol)
            for eps in (0.05,0.10):
                r8=[sim_v8(tr["ue"][:60],cfg,pr,eps=eps) for tr in EVAL]; print(f"   vol={vol} eps={eps}: {summarize(r8,fls)}", flush=True)
        r6=[sim_v6(tr["ue"][:60],cfg) for tr in EVAL]; print(f"   v6-sim      : {summarize(r6,fls)}")
    if which in ("4",):
        import statistics as st
        print("=== Exp4 SLO-calibrated margins (lam*sigma), Learn-then-Test on 1000 calibration traces, validated on 300 held-out; Delta = w; v6 = reference line only")
        CAL=lib[300:1300]
        for cfgname,cfg in (("base",Cfg(1,"base",2,"base")),("lead-short",Cfg(1,"short",2,"short"))):
            pr=Prior(lib,cfg); fls=[floor_alloc(tr["ue"][:60],cfg) for tr in EVAL]
            print(f"[{cfgname}] sigma_win (UE) by layer, all-D: " + ", ".join(f"{k}={pr.sig[('win',k,'all')]:.2f}" for k in cfg.h) + " | sigma_run: " + ", ".join(f"{k}={pr.sig[('run',k,'all')]:.2f}" for k in cfg.h))
            for target in (0.005,0.01,0.02):
                lam,risk,curve=calibrate(CAL[:400],cfg,pr,target)      # 400 calibration traces for speed
                if lam is None: print(f"   target {target:.3f}: no lam on grid reaches target (min risk {risk:.4f})"); continue
                rs=[sim_v8(tr["ue"][:60],cfg,pr,lam=lam) for tr in EVAL]
                # implied margins in UE at the median demand bucket (D=20 UE for 40-scale)
                Dref=20*cfg.scale; mw={k:lam*pr.sigma("win",k,Dref) for k in cfg.h}; mr={k:lam*pr.sigma("run",k,Dref) for k in cfg.h}
                print(f"   target {target:.3f}: lam={lam} cal_risk={risk:.4f} | held-out {summarize(rs,fls)} | margins@D={Dref}: win " + ", ".join(f"{k}={v:.1f}" for k,v in mw.items()) + "; run " + ", ".join(f"{k}={v:.1f}" for k,v in mr.items()) + "  (v6 hand value: 5 UE all layers)", flush=True)
            r6=[sim_v6(tr["ue"][:60],cfg) for tr in EVAL]; r8=[sim_v8(tr["ue"][:60],cfg,pr) for tr in EVAL]
            print(f"   reference: v6-sim untuned {summarize(r6,fls)}\n   reference: v8 eps=0.05  {summarize(r8,fls)}", flush=True)
        print("=== Exp5 flaps source (base cfg, eps=0.05 quantile margins): replenish x release cross")
        cfg=Cfg(); pr=Prior(lib,cfg); fls=[floor_alloc(tr["ue"][:60],cfg) for tr in EVAL]
        for rep in ("quantile","batch"):
            for rel in ("R","v6past"):
                rs=[sim_v8(tr["ue"][:60],cfg,pr,rep=rep,rel=rel) for tr in EVAL]; print(f"   rep={rep:8s} rel={rel:6s}: {summarize(rs,fls)}", flush=True)
    if which in ("6",):
        import statistics as st
        CAL=lib[300:700]
        print("=== Exp5b flaps source (fixed v6past semantics: lock since last scale-out)")
        cfg=Cfg(); pr=Prior(lib,cfg); fls=[floor_alloc(tr["ue"][:60],cfg) for tr in EVAL]
        for rep in ("quantile","batch"):
            for rel in ("R","v6past"):
                rs=[sim_v8(tr["ue"][:60],cfg,pr,rep=rep,rel=rel) for tr in EVAL]; print(f"   rep={rep:8s} rel={rel:6s}: {summarize(rs,fls)}", flush=True)
        print("=== Exp6 v6 STRUCTURE + calibrated lam*sigma margins (LtT on 400 cal traces, held-out 300); windows derived from lead; lock 300/600 kept")
        for cfgname,cfg in (("base",Cfg(1,"base",2,"base")),("lead-short",Cfg(1,"short",2,"short")),("160-scale",Cfg(4,"base",2,"160"))):
            pr=Prior(lib,cfg); fls=[floor_alloc(tr["ue"][:60],cfg) for tr in EVAL]; Dref=20*cfg.scale
            for lock in (True,False):
                for target in (0.01,0.02):
                    lam,risk=calibrate_fn(CAL, lambda u,l: sim_v6c(u,cfg,pr,l,lock_v6=lock), target)
                    if lam is None: print(f"  [{cfgname}] lock={lock} target {target}: not reachable (min risk {risk:.4f})"); continue
                    rs=[sim_v6c(tr["ue"][:60],cfg,pr,lam,lock_v6=lock) for tr in EVAL]
                    mw=", ".join(f"{k}={lam*pr.sigma('win',k,Dref)/cfg.scale:.1f}" for k in cfg.h)
                    print(f"  [{cfgname}] lock={lock} target {target}: lam={lam} cal_risk={risk:.4f} | held-out {summarize(rs,fls)} | margins (UE, 40-scale units) {mw}  (v6 hand: 5)", flush=True)
            r6=[sim_v6(tr["ue"][:60],cfg) for tr in EVAL]; r6r=[sim_v6(tr["ue"][:60],cfg,retune=True) for tr in EVAL]
            print(f"  [{cfgname}] reference v6 untuned: {summarize(r6,fls)} | v6 retuned(batch x scale): {summarize(r6r,fls)}", flush=True)
    if which in ("7",):
        import statistics as st, itertools
        CAL=lib[300:600]
        print("=== Exp7 per-layer lambda (lam_vm for VY&WK, lam_up) by fixed procedure: min mean alloc s.t. pooled violation-minute fraction <= target on 300 cal traces; held-out 300")
        for cfgname,cfg in (("base",Cfg(1,"base",2,"base")),("lead-short",Cfg(1,"short",2,"short"))):
            pr=Prior(lib,cfg); fls=[floor_alloc(tr["ue"][:60],cfg) for tr in EVAL]; Dref=20*cfg.scale
            # v6 reference risk on CAL and held-out
            v6c=[sim_v6(tr["ue"][:60],cfg) for tr in CAL]; v6risk=sum(60-r["slo"] for r in v6c)/(60*len(CAL))
            r6=[sim_v6(tr["ue"][:60],cfg) for tr in EVAL]
            print(f"  [{cfgname}] v6 untuned: cal risk={v6risk:.4f} | held-out {summarize(r6,fls)}", flush=True)
            table={}
            for lv,lu in itertools.product([0.5,1.0,1.5,2.0,2.5,3.0,3.5],[1.0,1.5,2.0,2.5,3.0,3.5,4.0]):
                L={"vy":lv,"wk":lv,"up":lu}; v=0; a=0
                for tr in CAL: r=sim_v6c(tr["ue"][:60],cfg,pr,L); v+=60-r["slo"]; a+=r["alloc"]
                table[(lv,lu)]=(v/(60*len(CAL)), a/len(CAL))
            for target in (0.01, 0.02, round(v6risk,4)):
                feas=[(k,v) for k,v in table.items() if v[0]<=target]
                if not feas: print(f"   target {target}: infeasible (min risk {min(v[0] for v in table.values()):.4f})"); continue
                (lv,lu),(risk,_)=min(feas,key=lambda kv: kv[1][1])
                L={"vy":lv,"wk":lv,"up":lu}; rs=[sim_v6c(tr["ue"][:60],cfg,pr,L) for tr in EVAL]
                mw=", ".join(f"{k}={L[k]*pr.sigma('win',k,Dref)/cfg.scale:.1f}" for k in cfg.h)
                print(f"   target {target}: lam_vm={lv} lam_up={lu} cal_risk={risk:.4f} | held-out {summarize(rs,fls)} | margins (UE) {mw}  (v6 hand: 5 all)", flush=True)
    if which in ("3","all"):
        print("=== Exp3 ACI miss definition (base cfg): train alpha on 1000 traces (continuous), freeze, eval 300")
        cfg=Cfg(); pr=Prior(lib,cfg); fls=[floor_alloc(tr["ue"][:60],cfg) for tr in EVAL]
        for miss in ("rise","short"):
            for eps in (0.05,0.02):
                a=ACI(eps,gamma=max(0.005,eps/5),miss=miss)
                for tr in TRAIN: sim_v8(tr["ue"][:60],cfg,pr,eps=eps,aci=a)
                alpha=dict(a.alpha); frozen=ACI(eps,0.0,miss); frozen.alpha=alpha
                r8=[sim_v8(tr["ue"][:60],cfg,pr,eps=eps,aci=frozen) for tr in EVAL]
                print(f"   miss={miss:5s} eps={eps}: alpha={ {k:round(v,3) for k,v in alpha.items()} } {summarize(r8,fls)}", flush=True)
