#!/usr/bin/env python3
"""qsim/r68unif/nest2gen.py (spec §4.136): copy of qsim/s7/s7core.py + variant 'apl' (independent targets, independent release, plain v6-type release). Original header: qsim/s7/s7core.py (10-27, spec §4.131): S7 = S4 + R1 ready headroom + R2 net-benefit slot scale-in (+ consistency guard).
sim_s7 = s5core.sim_s5 (a verbatim copy of v8sim10_abl.sim_nest2) run in its S4 path (margin='sigma', variant='full') with:
  R1 (B not None): each tick, ready_free = ready slots (ready, not draining) x 5 - D; if ready_free < B -> slot want >= current slots + 1
     (current = existing incl. booting, minus draining), worker want >= ceil(that / spw). Subject to the existing serialisation.
  guard (B not None): a slot scale-in is skipped when (ready slots - 1) x 5 - D < B (R1 would re-add it in the same tick).
  R2 (w not None): after every existing release check of the slot layer, net = s x E_T(b, h)/60 - w x EVM <= 0 -> skip,
     h = (slots - 1) x cap_up - D, s = 0.8 (a) or 3.8 (b: slots - 1 <= (workers - 1) x spw), EVM = P_b(R_L > h) x L/60 with
     L = h_UP (a) or h_WK + h_UP (b) and R_L the library win rises of that horizon (Prior.win up / wk), E_T = truncated mean first-passage time
     of the library rise above h (cap 1800 s). Buckets: 10 UE (n >= 30, else global).
B = None and w = None reproduce S4 (v8sim10.sim_nest2) bit for bit (s7/equiv.py)."""
import sys, math, json, numpy as np
sys.path.insert(0,'/home/user/experiment/qsim')
import v8sim2 as S, v8sim7 as M
DT=S.DT; FMAX=S.FMAX; FMIN=S.FMIN; TICK=S.TICK
TMAX=1800; XMAX=45
def horizon(cfg,k): return cfg.h[k] if k!="wk" else cfg.h["wk"]+cfg.h["up"]
class S7Prior(S.Prior):
    def __init__(s, lib, cfg, **kw):
        super().__init__(lib, cfg, **kw)
        s.exc={}
        for k in ("up","wk"):
            bb={}
            for D,a,r in s.win[k]: bb.setdefault(s.db(D),[]).append(r)
            allr=np.sort(np.array([r for _,_,r in s.win[k]],float))
            s.exc[k]=({b:np.sort(np.array(v,float)) for b,v in bb.items() if len(v)>=30}, allr)
        step=TICK//DT; nh=TMAX//DT; acc={}
        for tr in lib:
            d=S.expand(tr["ue"])*cfg.scale
            for i in range(0,len(d)-nh,step):
                rm=np.maximum.accumulate(d[i+1:i+nh+1]-d[i])
                tau=[]
                for x in range(-1,XMAX+1):
                    j=int(np.searchsorted(rm,x,side='right'))      # first index with rise > x
                    tau.append(min(TMAX,(j+1)*DT) if j<nh else TMAX)
                acc.setdefault(s.db(d[i]),[]).append(tau)
        allt=np.array([t for v in acc.values() for t in v],float).mean(axis=0)
        s.et=({b:np.array(v,float).mean(axis=0) for b,v in acc.items() if len(v)>=30}, allt)
    def p_exceed(s,k,D,h):
        tab,allr=s.exc[k]; arr=tab.get(s.db(D),allr)
        return float(len(arr)-np.searchsorted(arr,h,side='right'))/len(arr)
    def e_t(s,D,h):
        tab,allt=s.et; v=tab.get(s.db(D),allt); x=int(math.floor(h))
        return float(v[min(XMAX,max(-1,x))+1])
    def r2_ok(s,cfg,D,n_up,n_wk,w):
        h=(n_up-1)*cfg.cap_up-D
        b=(n_up-1)<=(n_wk-1)*cfg.spw
        rate=cfg.cores["up"]+(cfg.cores["wk"] if b else 0.0)
        L=horizon(cfg,"wk") if b else horizon(cfg,"up")
        evm=s.p_exceed("wk" if b else "up",D,h)*L/60.0
        return rate*s.e_t(D,h)/60.0-w*evm>0
def sim_s7(ue, cfg, prior, L, release_serial=True, reversible_drain=True, worker_serial=True, slot_serial=True, idle_min=600, position_wait=True, episode_hold=True, start=None, drain_sec=None, lock_up=300, lock_vm=600, lead_scale=1.0, win_scale=1.0, d_scale=1.0, acct='dispatch', variant='full', margin='sigma', B=None, w=None):
    """(docstring removed)"""
    """(docstring removed)"""
    if variant in ('e','full','single_lambda'): indep=False; indep_rel=False; plain_release=False
    elif variant=='independent': indep=True; indep_rel=False; plain_release=False
    elif variant=='independent_full': indep=True; indep_rel=True; plain_release=False
    elif variant=='fixed_dwell': indep=False; indep_rel=False; plain_release=True
    elif variant=='apl': indep=True; indep_rel=True; plain_release=True   # r68unif A-PL = (b') + (c)
    elif variant=='lock_only': indep=False; indep_rel=False; plain_release=True; release_serial=False; reversible_drain=False; episode_hold=False; position_wait=False; win_scale=0.0
    else: raise ValueError('unknown variant %r'%(variant,))
    d=S.expand(ue)*cfg.scale; n=len(d); H={k:v*lead_scale for k,v in cfg.h.items()}; Dd={k:v*d_scale for k,v in cfg.d.items()}; LOCK={"up":lock_up,"vy":lock_vm,"wk":lock_vm}
    need=lambda k,x: float(cfg.need(k,x))
    if margin=='quantile':   # S5: L = {"vy":p_VM,"wk":p_VM,"up":p_UP} are quantile levels; margin = bucket quantile of the rise
        mg=lambda kind,k,D: prior.quant(kind,k,D,L[k]); ut=lambda kind,D: prior.quant(kind,"wk",D,L["up"])
    elif margin=='sigma':    # S4 (frozen semantics, for the equivalence check): L = multipliers
        mg=lambda kind,k,D: L[k]*prior.sigma(kind,k,D); ut=lambda kind,D: L["up"]*prior.sigma(kind,"wk",D)
    else: raise ValueError(margin)
    W={"up":0, "vy":0, "wk":0}
    W={k:int(round(cfg.win[k]*win_scale)) for k in cfg.h}
    def want_wk(D):
        if indep: return need("wk",D+mg("win","wk",D))
        return max(need("wk",D+mg("win","wk",D)), math.ceil(need("up",D+ut("win",D))/cfg.spw))
    cur={k:need(k,d[0]+mg("win",k,d[0])) for k in cfg.h}; cur["wk"]=max(want_wk(d[0]), math.ceil(cur["up"]/cfg.spw))
    if start: cur={"up":float(start[0]),"vy":float(start[1]),"wk":float(start[2])}
    units=[]
    for k in ("up","vy","wk"):
        for _ in range(int(cur[k])): units.append(dict(k=k,dispatch=-1e9,ready=-1e9,gone=1e18,draining=False))
    last_out={k:-1e9 for k in cur}; last_in={k:-1e9 for k in cur}; alloc=0.0; ev=[]; lossmin=np.zeros(60); offmin=np.zeros(60); permin=np.zeros(60); traj=[]; ticks=[]
    t=0.0
    def cnt(k,f): return sum(1 for u in units if u["k"]==k and u["gone"]>t and f(u))
    def observe():
        rep={k:cnt(k,lambda u:u["dispatch"]<=t) for k in cfg.h}
        ready={k:cnt(k,lambda u:u["ready"]<=t) for k in cfg.h}
        drn={k:cnt(k,lambda u:u["draining"]) for k in cfg.h}
        booting={k:rep[k]-ready[k] for k in cfg.h}
        return rep,ready,drn,booting
    for i in range(n):
        t=i*DT; D=d[i]
        nUP=cnt("up",lambda u:u["ready"]<=t and not u["draining"]); nVY=cnt("vy",lambda u:u["ready"]<=t and not u["draining"]); nWK=cnt("wk",lambda u:u["ready"]<=t and not u["draining"])
        cur={"up":nUP,"vy":nVY,"wk":nWK}
        l=S.loss_step(cfg,cur,D); lossmin[i*DT//60]+=l*D*DT; offmin[i*DT//60]+=D*DT
        if acct=='vmexist':
            burn={k:sum(1 for u in units if u["k"]==k and (u["dispatch"]+(30 if k!="up" else 0))<=t and (u["gone"] if k=="up" else u.get("bend",u["gone"]))>t) for k in cur}
        else:
            burn={k:cnt(k,lambda u:u["dispatch"]<=t) for k in cur}
        c=sum(cfg.cores[k]*burn[k] for k in burn)*DT/60; alloc+=c; permin[i*DT//60]+=c
        if t%60==0: traj.append((t//60,int(D),nUP,nVY,nWK,burn["up"],burn["vy"],burn["wk"]))
        if t%S.TICK!=0: continue
        rep,ready,drn,booting=observe()

        eff={k:rep[k]-drn[k] for k in cfg.h}
        wants={"up":need("up",D+mg("win","up",D)),"vy":need("vy",D+mg("win","vy",D)),"wk":want_wk(D)}
        if B is not None:   # R1 ready headroom (S7)
            nrdy=cnt("up",lambda u:u["ready"]<=t and not u["draining"])
            if nrdy*5-D<B:
                r1=float(min(FMAX["up"],eff["up"]+1))
                if r1>wants["up"]: wants["up"]=r1
                wk1=float(min(FMAX["wk"],math.ceil(wants["up"]/cfg.spw)))
                if wk1>wants["wk"]: wants["wk"]=wk1
        ticks.append((t,D,wants["up"],wants["vy"],wants["wk"],rep["up"],ready["up"],rep["vy"],ready["vy"],rep["wk"]))

        for k in ("vy","wk","up"):
            rep,ready,drn,booting=observe(); eff={kk:rep[kk]-drn[kk] for kk in cfg.h}
            if not (wants[k]>eff[k] and eff[k]<FMAX[k]): continue
            if k=="wk" and worker_serial and booting["wk"]>0: ev.append((t,"blocked-wkboot",k)); continue
            if k=="up":
                draining_up=[u for u in units if u["k"]=="up" and u["draining"] and u["gone"]>t]
                if reversible_drain and draining_up:
                    u=draining_up[-1]; u["draining"]=False; u["gone"]=1e18; ev.append((t,"cancel-drain","up")); continue
                if slot_serial and booting["up"]>0: ev.append((t,"blocked-slotboot",k)); continue
                if position_wait and rep["up"]>=ready["wk"]*cfg.spw:
                    ev.append((t,"wait-position","up")); continue
            units.append(dict(k=k,dispatch=t,ready=t+H[k],gone=1e18,draining=False)); last_out[k]=t; ev.append((t,"out",k))

        for k in ("up","vy","wk"):
            rep,ready,drn,booting=observe(); eff={kk:rep[kk]-drn[kk] for kk in cfg.h}
            if eff[k]<=FMIN[k]+1e-9 or booting[k]>0: continue

            if release_serial and (drn[k]>0 or t-last_in[k]<Dd[k]): continue
            if k=="wk" and release_serial and (drn["up"]>0 or t-last_in["up"]<Dd["up"]): continue
            if t-last_out[k]<LOCK[k]: continue
            if episode_hold and t<2*W[k]: continue
            j0=max(0,i-W[k]//DT); peak=d[j0:i+1].max()
            def rel_need(level):
                x=level+mg("run",k,level)
                if k=="wk":
                    nn=need("up",x) if indep_rel else max(need("up",x), math.ceil(need("up",level+ut("run",level))/cfg.spw)*cfg.spw)
                    return max(nn, eff["up"])
                return need(k,x)
            if plain_release:
                if not (wants[k]<=eff[k]-1): continue
            elif k=="wk":
                if not (rel_need(D)<=(eff["wk"]-1)*cfg.spw and rel_need(peak)<=(eff["wk"]-1)*cfg.spw): continue
            else:
                if not (rel_need(D)<=eff[k]-1 and rel_need(peak)<=eff[k]-1): continue
            if k=="up" and B is not None:   # guard: R1 would re-add the slot in the same tick
                nrdy=cnt("up",lambda u:u["ready"]<=t and not u["draining"])
                if (nrdy-1)*5-D<B: ev.append((t,"blocked-guard","up")); continue
            if k=="up" and w is not None and not prior.r2_ok(cfg,D,eff["up"],eff["wk"],w): ev.append((t,"blocked-r2","up")); continue
            cands=[u for u in units if u["k"]==k and u["ready"]<=t and not u["draining"] and u["gone"]>t]
            if k=="wk" and idle_min: cands=[u for u in cands if u["ready"]<=t-idle_min]
            if k=="wk" and eff["up"]>(eff["wk"]-1)*cfg.spw: continue
            if not cands: ev.append((t,"blocked-idle",k)); continue
            u=cands[-1]; u["draining"]=True; u["gone"]=t+(drain_sec if (k=="up" and drain_sec) else Dd[k]); u["bend"]=t+5; last_in[k]=t; ev.append((t,"in",k))
    pct=100*lossmin/np.maximum(offmin,1e-9)
    return dict(slo=int((pct<=0.1).sum()), alloc=alloc, pct=pct, traj=traj, ev=ev, permin=permin, ticks=ticks, lostfrac=float(lossmin.sum()/max(offmin.sum(),1e-9)))
