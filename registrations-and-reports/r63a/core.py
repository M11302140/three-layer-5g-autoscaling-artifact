#!/usr/bin/env python3
"""r63a core (spec §4.107 A): leakage-free σ̂ calibration.
One "context" = one Prior (σ̂) fitted on a given list of library traces (calibration groups only; duplicates allowed for the
bootstrap) + calibration on a given cal list (both targets) + held-out evaluation on a given ho list, all with THAT Prior.
Simulator: r62de/eng.sim2 (bit-identical to frozen v8sim10.sim_nest2, acct dispatch and vmexist in one pass).
Calibration arithmetic = frozen v8sim10_cal.py / r62ab look.py:
  coarse GRID_VM x GRID_UP (itertools.product order) -> feasible = mean cal risk <= target -> cheapest mean cal dispatch alloc
  (python min, first in insertion order on ties) -> +-0.25 refinement (product((-.25,0,.25),(-.25,0,.25)) order, new points only,
  lv+dv>0 and lu+du>0) -> re-select over the whole table.  Infeasible coarse grid -> min-risk coarse point (ties: cheaper), as look.py.
Means are over the list entries (a duplicated trace counts twice, as in r62ab's bootstrap)."""
import sys, os, json, math, time, random, itertools, numpy as np
sys.path.insert(0,'/home/user/experiment/qsim/r62de')
import eng
S=eng.S; M=eng.M
GRID_VM=eng.GRID_VM; GRID_UP=eng.GRID_UP
LIB=json.load(open('/home/user/experiment/qsim/prior_traces.json'))
CFG=M.cfg_measured()
TGT=(0.02,0.005)

def prior_diag(pr):
    """D-buckets (10-UE) of each (kind, layer) that have < 30 samples (sigma() falls back to the global σ̂ of this Prior)"""
    out={}
    for kind in ("win","run"):
        for k in CFG.h:
            tab=pr.sig[(kind,k)]; n=(max(tab)+1) if tab else 0
            fb=[b for b in range(n) if tab.get(b) is None]
            if fb: out[f"{kind}_{k}"]=fb
    return out

def run_context(job):
    """job: dict(tag, prior_idx, cal_idx, ho_idx, targets) -> result dict"""
    t0=time.time()
    pr=S.Prior([LIB[i] for i in job["prior_idx"]],CFG)
    tp=time.time()-t0
    cache={}; nsim=[0]
    def res(i,lv,lu):
        key=(i,lv,lu); r=cache.get(key)
        if r is None:
            s,ad,av,_=eng.sim2(LIB[i]["ue"][:60],CFG,pr,{"vy":lv,"wk":lv,"up":lu}); r=cache[key]=(int(s),float(ad),float(av)); nsim[0]+=1
        return r
    def ev(idx,lv,lu):
        rr=[res(i,lv,lu) for i in idx]
        return float(np.mean([(60-r[0])/60.0 for r in rr])), float(np.mean([r[1] for r in rr]))
    def ho(idx,lv,lu):
        rr=[res(i,lv,lu) for i in idx]
        return dict(risk=float(np.mean([(60-r[0])/60.0 for r in rr])),alloc_d=float(np.mean([r[1] for r in rr])),alloc_vm=float(np.mean([r[2] for r in rr])),n=len(idx))
    cal=job["cal_idx"]; out=dict(tag=job["tag"],n_prior=len(job["prior_idx"]),n_cal=len(cal),n_ho=len(job["ho_idx"]),
                                  n_cal_unique=len(set(cal)),prior_fallback=prior_diag(pr),
                                  sigma20={f"{kind}_{k}":float(pr.sigma(kind,k,20)) for kind in ("win","run") for k in ("vy","up","wk")},rows={})
    coarse={}
    for lv,lu in itertools.product(GRID_VM,GRID_UP): coarse[(lv,lu)]=ev(cal,lv,lu)
    for tg in job.get("targets",TGT):
        table=dict(coarse)
        feas=[(k,v) for k,v in table.items() if v[0]<=tg]
        if not feas:
            (lv,lu),(risk,al)=min(table.items(),key=lambda kv:(kv[1][0],kv[1][1])); inf=True
        else:
            inf=False
            (lv,lu),_=min(feas,key=lambda kv:kv[1][1])
            ref=[(round(lv+dv,2),round(lu+du,2)) for dv,du in itertools.product((-0.25,0,0.25),(-0.25,0,0.25)) if (round(lv+dv,2),round(lu+du,2)) not in table and lv+dv>0 and lu+du>0]
            for k in ref: table[k]=ev(cal,*k)
            feas=[(k,v) for k,v in table.items() if v[0]<=tg]
            (lv,lu),(risk,al)=min(feas,key=lambda kv:kv[1][1])
        h=ho(job["ho_idx"],lv,lu) if job["ho_idx"] else None
        out["rows"][str(tg)]=dict(lam_vm=lv,lam_up=lu,cal_risk=risk,cal_alloc=al,infeasible=inf,offgrid=(lv>max(GRID_VM) or lu>max(GRID_UP) or lv<0.5 or lu<0.5),ho=h)
    out.update(t_prior=tp,t_total=time.time()-t0,nsim=nsim[0])
    return out

def groups_of(idx=None):
    g={}
    for i in (range(len(LIB)) if idx is None else idx): g.setdefault((LIB[i]["loc"],LIB[i]["date"]),[]).append(i)
    return g

def grouped_split(seed, frac_cal=0.6):
    """= v8sim3.grouped_split on the frozen library; returns (cal groups' traces, ho traces)"""
    return eng.grouped_split(LIB,seed,frac_cal)
