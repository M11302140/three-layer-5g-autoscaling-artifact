#!/usr/bin/env python3
"""r62de engine (§4.104 D/E). Frozen modules are imported, never modified.
sim2() = copy of v8sim10.sim_nest2 with default flags, computing BOTH accounting modes in one pass
(alloc_d = acct 'dispatch', alloc_vm = acct 'vmexist'), plus optional `load` (UE-equivalent demand series for the loss
model; the controller still sees the integer UE count `ue`) for the per-UE-rate experiment.  Equivalence to the frozen
sim_nest2 is checked by check_equiv().
Calibration = lookup on a per-trace result matrix (slo, alloc_d, alloc_vm per trace per λ point); identical arithmetic to
v8sim10_cal.py / v8sim10_ablation.py: grouped_split(seed) on the variant's own library, cal = first 300 cal traces,
coarse grid GRID_VM×GRID_UP → feasible (cal risk ≤ target) min cal alloc (dispatch) → ±0.25 refine (8 neighbours, only that
split's own refine points join its table) → held-out risk and alloc (vmexist; dispatch in brackets) over all held-out traces."""
import sys, os, json, math, time, random, itertools, pickle, numpy as np
Q='/home/user/experiment/qsim'; sys.path.insert(0,Q)
_cwd=os.getcwd(); os.chdir(Q)   # v8sim3 (imported by v8sim7) opens prior_traces.json relative to cwd
import v8sim2 as S, v8sim7 as M
os.chdir(_cwd)
DT=S.DT; FMAX=S.FMAX; FMIN=S.FMIN
GRID_VM=[1.0,1.5,2.0,2.5,3.0,3.5]; GRID_UP=[1.5,2.0,2.5,3.0,3.5,4.0,4.5]
def cfg_with_h(h):
    """cfg_measured() with the lead dict HM replaced by h (all derived fields follow cfg_measured's formulas:
       w = d + h, hout = win = {up: h_up+g, vy: h_vy+g, wk: h_wk+h_up+g}, delta, drain unchanged)."""
    cfg=M.cfg_measured(); cfg.h=dict(h); cfg.w={k:cfg.d[k]+cfg.h[k] for k in cfg.h}
    cfg.hout=dict(up=cfg.h["up"]+S.TICK, vy=cfg.h["vy"]+S.TICK, wk=cfg.h["wk"]+cfg.h["up"]+S.TICK); cfg.win=dict(cfg.hout)
    cfg.delta=dict(up=cfg.w["up"], vy=cfg.h["vy"]+cfg.d["vy"], wk=cfg.w["wk"])
    return cfg
def sim2(ue, cfg, prior, L, load=None, idle_min=600, lock_up=300, lock_vm=600):
    """same semantics as v8sim10.sim_nest2 (default flags), single-pass counting; returns (slo, alloc_dispatch, alloc_vmexist, n_actions)"""
    d=S.expand(ue)*cfg.scale; dl=d if load is None else S.expand(load)*cfg.scale
    n=len(d); H=dict(cfg.h); Dd=dict(cfg.d); LOCK={"up":lock_up,"vy":lock_vm,"wk":lock_vm}
    need=lambda k,x: float(cfg.need(k,x)); _sc={}
    def sig(kind,k,D):
        key=(kind,k,D); v=_sc.get(key)
        if v is None: v=_sc[key]=prior.sigma(kind,k,D)
        return v
    W={k:int(round(cfg.win[k]*1.0)) for k in cfg.h}
    def want_wk(D): return max(need("wk",D+L["wk"]*sig("win","wk",D)), math.ceil(need("up",D+L["up"]*sig("win","wk",D))/cfg.spw))
    cur={k:need(k,d[0]+L[k]*sig("win",k,d[0])) for k in cfg.h}; cur["wk"]=max(want_wk(d[0]), math.ceil(cur["up"]/cfg.spw))
    units=[]   # [k, dispatch, ready, gone, draining, bend]
    for k in ("up","vy","wk"):
        for _ in range(int(cur[k])): units.append([k,-1e9,-1e9,1e18,False,None])
    last_out={k:-1e9 for k in cur}; last_in={k:-1e9 for k in cur}; alloc=0.0; alloc_vm=0.0; nact=0
    lossmin=np.zeros(60); offmin=np.zeros(60); cores=cfg.cores; KS=("up","vy","wk")
    ob=[None,None]   # cache: (version, result); units only change via append/cancel/drain, which bump ver[0]
    ver=[0]
    def observe(t):
        if ob[0]==(ver[0],t): return ob[1]
        rep={"up":0,"vy":0,"wk":0}; ready={"up":0,"vy":0,"wk":0}; drn={"up":0,"vy":0,"wk":0}
        for u in units:
            if u[3]>t:
                k=u[0]
                if u[1]<=t: rep[k]+=1
                if u[2]<=t: ready[k]+=1
                if u[4]: drn[k]+=1
        r=(rep,ready,drn,{k:rep[k]-ready[k] for k in KS}); ob[0]=(ver[0],t); ob[1]=r
        return r
    dirty=True; nxt=-1e18
    for i in range(n):
        t=i*DT; D=d[i]
        if dirty or t>=nxt:   # unit-state counts only change at unit event times (dispatch, ready, gone, dispatch+30, bend) or after a tick edit
            cur={"up":0,"vy":0,"wk":0}; burn={"up":0,"vy":0,"wk":0}; burn_vm={"up":0,"vy":0,"wk":0}; nxt=1e18
            for u in units:
                k=u[0]; g=u[3]
                if g>t:
                    if u[2]<=t and not u[4]: cur[k]+=1
                    if u[1]<=t: burn[k]+=1
                if k=="up":
                    if u[1]<=t and g>t: burn_vm[k]+=1
                else:
                    if (u[1]+30)<=t and (u[5] if u[5] is not None else g)>t: burn_vm[k]+=1
                for x in (u[1],u[2],g,u[1]+30,u[5]):
                    if x is not None and t<x<nxt: nxt=x
            a_inc=sum(cores[k]*burn[k] for k in burn)*DT/60; v_inc=sum(cores[k]*burn_vm[k] for k in burn_vm)*DT/60; dirty=False
        l=S.loss_step(cfg,cur,dl[i]); lossmin[i*DT//60]+=l*dl[i]*DT; offmin[i*DT//60]+=dl[i]*DT
        alloc+=a_inc; alloc_vm+=v_inc
        if t%S.TICK!=0: continue
        dirty=True
        wants={"up":need("up",D+L["up"]*sig("win","up",D)),"vy":need("vy",D+L["vy"]*sig("win","vy",D)),"wk":want_wk(D)}
        for k in ("vy","wk","up"):
            rep,ready,drn,booting=observe(t); eff={kk:rep[kk]-drn[kk] for kk in KS}
            if not (wants[k]>eff[k] and eff[k]<FMAX[k]): continue
            if k=="wk" and booting["wk"]>0: continue
            if k=="up":
                draining_up=[u for u in units if u[0]=="up" and u[4] and u[3]>t]
                if draining_up:
                    u=draining_up[-1]; u[4]=False; u[3]=1e18; ver[0]+=1; continue
                if booting["up"]>0: continue
                if rep["up"]>=ready["wk"]*cfg.spw: continue
            units.append([k,t,t+H[k],1e18,False,None]); last_out[k]=t; nact+=1; ver[0]+=1
        for k in ("up","vy","wk"):
            rep,ready,drn,booting=observe(t); eff={kk:rep[kk]-drn[kk] for kk in KS}
            if eff[k]<=FMIN[k]+1e-9 or booting[k]>0: continue
            if (drn[k]>0 or t-last_in[k]<Dd[k]): continue
            if k=="wk" and (drn["up"]>0 or t-last_in["up"]<Dd["up"]): continue
            if t-last_out[k]<LOCK[k]: continue
            if t<2*W[k]: continue
            j0=max(0,i-W[k]//DT); peak=d[j0:i+1].max()
            def rel_need(level):
                x=level+L[k]*sig("run",k,level)
                if k=="wk":
                    nn=max(need("up",x), math.ceil(need("up",level+L["up"]*sig("run","wk",level))/cfg.spw)*cfg.spw)
                    return max(nn, eff["up"])
                return need(k,x)
            if k=="wk":
                if not (rel_need(D)<=(eff["wk"]-1)*cfg.spw and rel_need(peak)<=(eff["wk"]-1)*cfg.spw): continue
            else:
                if not (rel_need(D)<=eff[k]-1 and rel_need(peak)<=eff[k]-1): continue
            cands=[u for u in units if u[0]==k and u[2]<=t and not u[4] and u[3]>t]
            if k=="wk" and idle_min: cands=[u for u in cands if u[2]<=t-idle_min]
            if k=="wk" and eff["up"]>(eff["wk"]-1)*cfg.spw: continue
            if not cands: continue
            u=cands[-1]; u[4]=True; u[3]=t+Dd[k]; u[5]=t+5; last_in[k]=t; nact+=1; ver[0]+=1
    pct=100*lossmin/np.maximum(offmin,1e-9)
    return int((pct<=0.1).sum()), alloc, alloc_vm, nact
def check_equiv(lib, cfg, pr, n=12, seed=20261021, load_fn=None):
    import v8sim10 as Q2
    rnd=random.Random(seed); idx=rnd.sample(range(len(lib)),n); bad=0
    for L in ({"vy":1.83,"wk":1.83,"up":2.00},{"vy":2.67,"wk":2.67,"up":3.12},{"vy":1.0,"wk":1.0,"up":1.5}):
        for i in idx:
            ue=lib[i]["ue"][:60]; a=Q2.sim_nest2(ue,cfg,pr,L,acct='dispatch'); b=Q2.sim_nest2(ue,cfg,pr,L,acct='vmexist'); s,ad,av,_=sim2(ue,cfg,pr,L)
            if not (a['slo']==s and b['slo']==s and a['alloc']==ad and b['alloc']==av): bad+=1
    return bad, 3*n
# ---------------- splits / matrix / calibration
def grouped_split(lib, seed, frac_cal=0.6):   # = v8sim3.grouped_split, on the given library
    groups={}
    for i,tr in enumerate(lib): groups.setdefault((tr["loc"],tr["date"]),[]).append(i)
    keys=sorted(groups); rnd=random.Random(seed); rnd.shuffle(keys)
    ncal=int(frac_cal*len(keys)); cal=[i for k in keys[:ncal] for i in groups[k]]; ho=[i for k in keys[ncal:] for i in groups[k]]
    return cal, ho
class Matrix:
    """per-trace results (slo, alloc_dispatch, alloc_vmexist) for each λ point, computed lazily for the traces a query needs;
    cached to disk (pickle) after every new evaluation batch."""
    def __init__(s, path, lib, cfg, pr, loads=None, log=print):
        s.path=path; s.lib=lib; s.cfg=cfg; s.pr=pr; s.loads=loads; s.log=log; s.pts={}; s.sim_s=0.0; s.nsim=0
        if path and os.path.exists(path): s.pts=pickle.load(open(path,'rb'))
    def _ensure(s, key, idx):
        N=len(s.lib)
        if key not in s.pts: s.pts[key]=(np.full(N,-1,np.int16),np.zeros(N),np.zeros(N))
        slo,ad,av=s.pts[key]; miss=[i for i in idx if slo[i]<0]
        if miss:
            t0=time.time(); L={"vy":key[0],"wk":key[0],"up":key[1]}
            for i in miss:
                r=sim2(s.lib[i]["ue"][:60],s.cfg,s.pr,L,load=(s.loads[i][:60] if s.loads is not None else None)); slo[i]=r[0]; ad[i]=r[1]; av[i]=r[2]
            el=time.time()-t0; s.sim_s+=el; s.nsim+=len(miss)
            if s.path: pickle.dump(s.pts,open(s.path+'.tmp','wb')); os.replace(s.path+'.tmp',s.path)
        return slo,ad,av
    def cal_eval(s, idx, lv, lu):
        slo,ad,av=s._ensure((round(lv,2),round(lu,2)),idx)
        return float(np.mean([(60-int(slo[i]))/60.0 for i in idx])), float(np.mean([ad[i] for i in idx]))
    def ho_eval(s, idx, lv, lu):
        slo,ad,av=s._ensure((round(lv,2),round(lu,2)),idx)
        return dict(risk=float(np.mean([(60-int(slo[i]))/60.0 for i in idx])), alloc_vm=float(np.mean([av[i] for i in idx])), alloc_d=float(np.mean([ad[i] for i in idx])), n=len(idx))
    def prefill(s, points):
        """evaluate the whole library at the given points (the coarse grid is needed for every trace across the 6 splits)"""
        allidx=list(range(len(s.lib)))
        for lv,lu in points:
            t0=time.time(); s._ensure((round(lv,2),round(lu,2)),allidx); s.log(f"    point {lv}/{lu}: {time.time()-t0:.0f}s")
def calibrate(mx, cal_idx, target, refine=True):
    table={}
    for lv,lu in itertools.product(GRID_VM,GRID_UP): table[(lv,lu)]=mx.cal_eval(cal_idx,lv,lu)
    feas=[(k,v) for k,v in table.items() if v[0]<=target]
    if not feas: return None, table
    (lv,lu),_=min(feas,key=lambda kv:kv[1][1])
    if refine:
        ref=[(round(lv+dv,2),round(lu+du,2)) for dv,du in itertools.product((-0.25,0,0.25),(-0.25,0,0.25)) if (round(lv+dv,2),round(lu+du,2)) not in table and lv+dv>0 and lu+du>0]
        for k in ref: table[k]=mx.cal_eval(cal_idx,*k)
    feas=[(k,v) for k,v in table.items() if v[0]<=target]
    (lv,lu),(risk,al)=min(feas,key=lambda kv:kv[1][1])
    return dict(lam_vm=lv,lam_up=lu,cal_risk=risk,cal_alloc=al,n_eval=len(table)), table
def six_split(mx, lib, targets=(0.02,0.005), seeds=range(6), ncal=300, refine=True, log=print):
    rows=[]
    for target in targets:
        for seed in seeds:
            cal_idx,ho_idx=grouped_split(lib,seed); cal_idx=cal_idx[:ncal]
            res,table=calibrate(mx,cal_idx,target,refine)
            if res is None:
                mn=min(table.items(),key=lambda kv:kv[1][0])
                rows.append(dict(target=target,seed=seed,infeasible=True,min_cal_risk=mn[1][0],min_at=mn[0])); log(f"  target {target} split{seed}: INFEASIBLE (min cal risk {mn[1][0]:.4f} at {mn[0]})"); continue
            ho=mx.ho_eval(ho_idx,res['lam_vm'],res['lam_up'])
            rows.append(dict(target=target,seed=seed,n_cal=len(cal_idx),**res,ho=ho))
            log(f"  target {target} split{seed}: λ {res['lam_vm']}/{res['lam_up']} cal {res['cal_risk']:.4f} alloc {res['cal_alloc']:.1f} | ho n {ho['n']} risk {ho['risk']:.4f} alloc_vm {ho['alloc_vm']:.1f} (disp {ho['alloc_d']:.1f})")
    return rows
def summarize(rows, target):
    rs=[r for r in rows if r['target']==target and not r.get('infeasible')]
    ninf=sum(1 for r in rows if r['target']==target and r.get('infeasible'))
    if not rs: return dict(n=0,ninf=ninf)
    g=lambda f:(float(np.mean([f(r) for r in rs])),float(np.std([f(r) for r in rs])))
    return dict(n=len(rs),ninf=ninf,lam_vm=g(lambda r:r['lam_vm']),lam_up=g(lambda r:r['lam_up']),cal_risk=g(lambda r:r['cal_risk']),
                risk=g(lambda r:r['ho']['risk']),alloc_vm=g(lambda r:r['ho']['alloc_vm']),alloc_d=g(lambda r:r['ho']['alloc_d']))
