#!/usr/bin/env python3
"""qsim/s6/s6core.py (10-26, spec §4.127): S6 = S4 + trend term.
sim_s6 = s5core.sim_s5 (itself a verbatim copy of v8sim10_abl.sim_nest2) with margin='trend':
  replenishment margin = s_hat*H_l + L[k]*sigma_res(W_s; k, D)  (s_hat = OLS slope of the last W_s tick observations, clipped at 0)
  release margin       = Lr[k]*sigma(run; k, D)                 (Lr = S4 multipliers at the same target -> release rule identical to S4)
margin='sigma' with Lr=None reproduces S4 (frozen v8sim10.sim_nest2) bit for bit (equivalence check in s6/equiv.py).
TPrior = v8sim2.Prior + residual tables: per win sample, residual = rise - max(0, s_hat_i)*H_l, std per 10-UE bucket (n>=30, else global),
interpolated with Prior.sigma (kind 'res3' / 'res5')."""
import sys, math, json, numpy as np
sys.path.insert(0,'/home/user/experiment/qsim')
import v8sim2 as S, v8sim7 as M
DT=S.DT; FMAX=S.FMAX; FMIN=S.FMIN; TICK=S.TICK
def slope(vals):
    """OLS slope per second of equally spaced tick observations (spacing TICK); fewer than 2 points -> 0"""
    m=len(vals)
    if m<2: return 0.0
    xb=(m-1)/2.0; yb=sum(vals)/m
    num=sum((j-xb)*(v-yb) for j,v in enumerate(vals)); den=sum((j-xb)**2 for j in range(m))
    return num/den/TICK
def horizon(cfg,k): return cfg.h[k] if k!="wk" else cfg.h["wk"]+cfg.h["up"]
class TPrior(S.Prior):
    def __init__(s, lib, cfg, ws=(3,5), **kw):
        super().__init__(lib, cfg, **kw)
        step=TICK//DT
        for W in ws:
            res={k:[] for k in cfg.h}
            for tr in lib:
                d=S.expand(tr["ue"])*cfg.scale
                for k in cfg.h:
                    h0=horizon(cfg,k); k0=h0//DT; k1=(h0+TICK)//DT; kw_=cfg.win[k]//DT
                    for i in range(0,len(d)-max(k1,kw_),step):
                        r=max(0.0,d[i+k0:i+k1+1].max()-d[i])
                        m=min(W,i//step+1); sh=max(0.0,slope([float(d[i-(m-1-j)*step]) for j in range(m)]))
                        res[k].append((d[i],r-sh*h0))
            for k in cfg.h:
                bb={}
                for D,x in res[k]: bb.setdefault(s.db(D),[]).append(x)
                s.sig[(f"res{W}",k)]={key:(float(np.std(v)) if len(v)>=30 else None) for key,v in bb.items()}
                s.sig[(f"res{W}",k,'all')]=float(np.std([x for _,x in res[k]]))
def sim_s6(ue, cfg, prior, L, release_serial=True, reversible_drain=True, worker_serial=True, slot_serial=True, idle_min=600, position_wait=True, episode_hold=True, start=None, drain_sec=None, lock_up=300, lock_vm=600, lead_scale=1.0, win_scale=1.0, d_scale=1.0, acct='dispatch', variant='full', margin='trend', Lr=None, ws=3):
    """(docstring removed)"""
    """(docstring removed)"""
    if variant in ('e','full','single_lambda'): indep=False; indep_rel=False; plain_release=False
    elif variant=='independent': indep=True; indep_rel=False; plain_release=False
    elif variant=='independent_full': indep=True; indep_rel=True; plain_release=False
    elif variant=='fixed_dwell': indep=False; indep_rel=False; plain_release=True
    elif variant=='lock_only': indep=False; indep_rel=False; plain_release=True; release_serial=False; reversible_drain=False; episode_hold=False; position_wait=False; win_scale=0.0
    else: raise ValueError('unknown variant %r'%(variant,))
    d=S.expand(ue)*cfg.scale; n=len(d); H={k:v*lead_scale for k,v in cfg.h.items()}; Dd={k:v*d_scale for k,v in cfg.d.items()}; LOCK={"up":lock_up,"vy":lock_vm,"wk":lock_vm}
    need=lambda k,x: float(cfg.need(k,x))
    tobs=[]   # tick observations of D (S6 slope); appended at every tick before the decisions
    if margin=='trend':      # S6: L = replenishment multipliers on sigma_res; Lr = release multipliers (S4, same target) on sigma(run)
        HZ={k:horizon(cfg,k) for k in cfg.h}; LR=Lr if Lr is not None else L; RK=f"res{ws}"
        def shat(): return max(0.0,slope(tobs[-ws:]))
        def mg(kind,k,D):
            if kind=="win": return shat()*HZ[k]+L[k]*prior.sigma(RK,k,D)
            return LR[k]*prior.sigma(kind,k,D)
        def ut(kind,D):
            if kind=="win": return shat()*HZ["wk"]+L["up"]*prior.sigma(RK,"wk",D)
            return LR["up"]*prior.sigma(kind,"wk",D)
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
        tobs.append(float(D))
        rep,ready,drn,booting=observe()

        eff={k:rep[k]-drn[k] for k in cfg.h}
        wants={"up":need("up",D+mg("win","up",D)),"vy":need("vy",D+mg("win","vy",D)),"wk":want_wk(D)}
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
            cands=[u for u in units if u["k"]==k and u["ready"]<=t and not u["draining"] and u["gone"]>t]
            if k=="wk" and idle_min: cands=[u for u in cands if u["ready"]<=t-idle_min]
            if k=="wk" and eff["up"]>(eff["wk"]-1)*cfg.spw: continue
            if not cands: ev.append((t,"blocked-idle",k)); continue
            u=cands[-1]; u["draining"]=True; u["gone"]=t+(drain_sec if (k=="up" and drain_sec) else Dd[k]); u["bend"]=t+5; last_in[k]=t; ev.append((t,"in",k))
    pct=100*lossmin/np.maximum(offmin,1e-9)
    return dict(slo=int((pct<=0.1).sum()), alloc=alloc, pct=pct, traj=traj, ev=ev, permin=permin, ticks=ticks, lostfrac=float(lossmin.sum()/max(offmin.sum(),1e-9)))
