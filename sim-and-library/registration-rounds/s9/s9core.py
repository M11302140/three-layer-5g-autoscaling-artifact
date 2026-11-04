#!/usr/bin/env python3
"""qsim/s9/s9core.py (10-27, spec §4.132): S9 = S4 + regime-conditional (lambda_VM, lambda_UP) and sigma + burst-bucket trend term + R2.
sim_s9 = s7core.sim_s7 (S4 path of a verbatim copy of v8sim10.sim_nest2) with R1/guard removed and:
  regime (thr = (T50, T85)): rise1_10 = max one-minute rise of the tick observations in the last 600 s (floor 0); candidate calm (<= T50) /
     normal (<= T85) / burst; switch after 2 consecutive identical candidates, leave burst after 4 consecutive non-burst candidates;
     start = calm. Decisions use Lb[regime] and S9Prior.sigma_c(regime, ...) (cond=False -> global sigma).
  trend (burst only, replenishment side): + s_hat * H_l, s_hat = OLS slope of the last 3 tick observations (s6core.slope), clipped at 0.
  R2 (w not None): S7Prior.r2_ok after every existing release check of the slot layer (spec §4.131 item 2).
thr = None, w = None reproduce S4 (v8sim10.sim_nest2) bit for bit (s9/equiv.py). force_reg pins the regime (G4b ablation)."""
import sys, math, json, numpy as np
sys.path.insert(0,'/home/user/experiment/qsim'); sys.path.insert(0,'/home/user/experiment/qsim/s7'); sys.path.insert(0,'/home/user/experiment/qsim/s6')
import v8sim2 as S, v8sim7 as M
from s7core import S7Prior, horizon, FMAX, FMIN, TICK, DT
from s6core import slope
BUCKETS=("calm","normal","burst")
STEP=TICK//DT
def rise_series(dt_obs):
    """rise1_10 at each tick from the list of tick observations (tick spacing TICK = 30 s): max(0, max_{m in (j-20, j], m >= 2} D_m - D_{m-2})"""
    out=[]; r1=[]
    for j,v in enumerate(dt_obs):
        r1.append(v-dt_obs[j-2] if j>=2 else None)
        w=[x for x in r1[max(0,j-19):j+1] if x is not None]
        out.append(max(0.0,max(w)) if w else 0.0)
    return out
def cand(thr,r): return "calm" if r<=thr[0] else ("normal" if r<=thr[1] else "burst")
class Regime:
    def __init__(s,thr): s.thr=thr; s.obs=[]; s.r1=[]; s.cur=None; s.pend=None; s.npend=0; s.nout=0
    def step(s,D):
        j=len(s.obs); s.obs.append(float(D)); s.r1.append(s.obs[j]-s.obs[j-2] if j>=2 else None)
        w=[x for x in s.r1[max(0,j-19):j+1] if x is not None]; r=max(0.0,max(w)) if w else 0.0
        c=cand(s.thr,r)
        if s.cur is None: s.cur=c; return s.cur
        if s.cur=="burst":
            if c!="burst":
                s.nout+=1
                if s.nout>=4: s.cur=c; s.nout=0; s.pend=None; s.npend=0
            else: s.nout=0
            return s.cur
        if c==s.cur: s.pend=None; s.npend=0; return s.cur
        if c==s.pend: s.npend+=1
        else: s.pend=c; s.npend=1
        if s.npend>=2: s.cur=c; s.pend=None; s.npend=0; s.nout=0
        return s.cur
def lib_thresholds(lib,cfg):
    """T50, T85 = numpy linear percentiles of rise1_10 over every tick with t >= 660 s of every library window"""
    allr=[]
    for tr in lib:
        d=S.expand(tr["ue"])*cfg.scale; obs=[float(d[i]) for i in range(0,len(d),STEP)]
        rs=rise_series(obs); allr.extend(rs[22:])
    a=np.array(allr,float); return float(np.percentile(a,50)), float(np.percentile(a,85)), a
class S9Prior(S7Prior):
    """S7Prior (S4 sigma tables + R2 tables) + regime-conditional sigma: samples split by the regime of their origin tick
    (Regime run over the training trace); cell (regime, kind, layer, 10-UE bucket) with n >= 30 -> its std, else the global S4 cell."""
    def __init__(s, lib, cfg, thr=None, **kw):
        super().__init__(lib, cfg, **kw); s.thr=thr; s.sigc={}; s.ncell={}
        if thr is None: return
        win={b:{k:[] for k in cfg.h} for b in BUCKETS}; run={b:{k:[] for k in cfg.h} for b in BUCKETS}
        for tr in lib:
            d=S.expand(tr["ue"])*cfg.scale; rg=Regime(thr); regs=[rg.step(float(d[i])) for i in range(0,len(d),STEP)]
            for k in cfg.h:
                h0=horizon(cfg,k); k0=h0//DT; k1=(h0+TICK)//DT; kw_=cfg.win[k]//DT
                for i in range(0,len(d)-max(k1,kw_),STEP):
                    b=regs[i//STEP]
                    win[b][k].append((d[i],max(0.0,d[i+k0:i+k1+1].max()-d[i]))); run[b][k].append((d[i],max(0.0,d[i+1:i+kw_+1].max()-d[i])))
        for b in BUCKETS:
            for kind,tab in (("win",win[b]),("run",run[b])):
                for k in cfg.h:
                    bb={}
                    for D,r in tab[k]: bb.setdefault(s.db(D),[]).append(r)
                    s.sigc[(b,kind,k)]={key:(float(np.std(v)) if len(v)>=30 else None) for key,v in bb.items()}
                    s.ncell[(b,kind,k)]={key:len(v) for key,v in bb.items()}
    def sigma_c(s,reg,kind,k,D):
        """S.Prior.sigma with the per-bucket value replaced by the regime cell when it has n >= 30"""
        tab=s.sig[(kind,k)]; allv=s.sig[(kind,k,'all')]; ct=s.sigc.get((reg,kind,k),{})
        def val(b):
            c=ct.get(b)
            if c is not None: return c
            return tab.get(b) if tab.get(b) is not None else allv
        if not S.SIGMA_INTERP:
            return val(s.db(D))
        B=10*s.cfg.scale; n=(max(tab)+1) if tab else 0
        if n==0: return allv
        x=D/B-0.5
        if x<=0: return val(0)
        if x>=n-1: return val(n-1)
        b0=int(math.floor(x)); fr=x-b0
        return (1-fr)*val(b0)+fr*val(b0+1)
def sim_s9(ue, cfg, prior, L, release_serial=True, reversible_drain=True, worker_serial=True, slot_serial=True, idle_min=600, position_wait=True, episode_hold=True, start=None, drain_sec=None, lock_up=300, lock_vm=600, lead_scale=1.0, win_scale=1.0, d_scale=1.0, acct='dispatch', variant='full', margin='sigma', w=None, Lb=None, thr=None, trend=False, cond=True, force_reg=None):
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
    if margin=='quantile':   # S5: L = {"vy":p_VM,"wk":p_VM,"up":p_UP} are quantile levels; margin = bucket quantile of the rise
        mg=lambda kind,k,D: prior.quant(kind,k,D,L[k]); ut=lambda kind,D: prior.quant(kind,"wk",D,L["up"])
    elif margin=='sigma' and thr is None:    # S4 (frozen semantics, for the equivalence check): L = multipliers
        mg=lambda kind,k,D: L[k]*prior.sigma(kind,k,D); ut=lambda kind,D: L["up"]*prior.sigma(kind,"wk",D)
    elif margin=='sigma':    # S9: regime-conditional lambda and sigma (+ burst trend on the replenishment side)
        st=dict(reg=force_reg or "calm",sh=0.0); HZ={k:horizon(cfg,k) for k in cfg.h}
        sg=(lambda kind,k,D: prior.sigma_c(st["reg"],kind,k,D)) if cond else (lambda kind,k,D: prior.sigma(kind,k,D))
        def tr_(kind,k): return st["sh"]*HZ[k] if (kind=="win" and trend and st["reg"]=="burst") else 0.0
        mg=lambda kind,k,D: tr_(kind,k)+Lb[st["reg"]][k]*sg(kind,k,D); ut=lambda kind,D: tr_(kind,"wk")+Lb[st["reg"]]["up"]*sg(kind,"wk",D)
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
    rg=Regime(thr) if thr is not None else None; tobs=[]; regmin=[]
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
        if thr is not None:
            rg.step(D); st["reg"]=force_reg or rg.cur; tobs.append(float(D)); st["sh"]=max(0.0,slope(tobs[-3:]))
            if t%60==0: regmin.append(st["reg"])
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
            if k=="up" and w is not None and not prior.r2_ok(cfg,D,eff["up"],eff["wk"],w): ev.append((t,"blocked-r2","up")); continue
            cands=[u for u in units if u["k"]==k and u["ready"]<=t and not u["draining"] and u["gone"]>t]
            if k=="wk" and idle_min: cands=[u for u in cands if u["ready"]<=t-idle_min]
            if k=="wk" and eff["up"]>(eff["wk"]-1)*cfg.spw: continue
            if not cands: ev.append((t,"blocked-idle",k)); continue
            u=cands[-1]; u["draining"]=True; u["gone"]=t+(drain_sec if (k=="up" and drain_sec) else Dd[k]); u["bend"]=t+5; last_in[k]=t; ev.append((t,"in",k))
    pct=100*lossmin/np.maximum(offmin,1e-9)
    return dict(slo=int((pct<=0.1).sum()), alloc=alloc, pct=pct, traj=traj, ev=ev, permin=permin, ticks=ticks, reg=regmin, lostfrac=float(lossmin.sum()/max(offmin.sum(),1e-9)))
