"""look.py (r62ab): lookup-based calibration on the step-0 matrix, same procedure as frozen v8sim10_cal.py / v8sim10_full.py
(coarse GRID_VM x GRID_UP in itertools.product order; feasible = mean cal risk <= target; cheapest mean dispatch alloc, first in
table order on ties (python min); +-0.25 refinement appended in product((-.25,0,.25),(-.25,0,.25)) order; re-select).
Points outside the matrix (lv 3.75 / lu 4.75 from refining an edge optimum) are simulated fresh (frozen-equivalent dual sim) and cached."""
import sys, os, json, itertools, numpy as np
sys.path.insert(0,'/home/user/experiment/qsim/r62ab')
import dual as D
from dual import S, M, Q2
R='/home/user/experiment/qsim/r62ab'
lib=json.load(open('/home/user/experiment/qsim/prior_traces.json')); cfg=M.cfg_measured(); pr=S.Prior(lib,cfg)
X=np.load(f'{R}/matrix.npz')
PIDX={(round(float(a),2),round(float(b),2)):j for j,(a,b) in enumerate(zip(X['lv'],X['lu']))}
SLO=X['slo'].astype(np.int64); AD=X['alloc_d']; AV=X['alloc_v']; VB=X['vbits']; FL=X['flaps']; NA=X['nact']
RISK=(60-SLO)/60.0
GRID_VM=[1.0,1.5,2.0,2.5,3.0,3.5]; GRID_UP=[1.5,2.0,2.5,3.0,3.5,4.0,4.5]
CACHE_F=f'{R}/offgrid_cache.json'
CACHE=json.load(open(CACHE_F)) if os.path.exists(CACHE_F) else {}
NFRESH=[0]
def _fresh(i,lv,lu):
    k=f"{i}|{lv}|{lu}"
    if k not in CACHE:
        r=D.sim_nest2_dual(lib[i]["ue"][:60],cfg,pr,{"vy":lv,"wk":lv,"up":lu}); CACHE[k]=[int(r["slo"]),float(r["alloc"]),float(r["alloc_vm"])]; NFRESH[0]+=1
    return CACHE[k]
def save_cache(): json.dump(CACHE,open(CACHE_F,'w'))
def cols(idx,lv,lu):
    """per-trace (risk, alloc_dispatch, alloc_vmexist) arrays for traces idx at point (lv,lu)"""
    idx=np.asarray(idx); p=PIDX.get((round(lv,2),round(lu,2)))
    if p is not None: return RISK[idx,p], AD[idx,p], AV[idx,p]
    v=[_fresh(int(i),round(lv,2),round(lu,2)) for i in idx]
    return np.array([(60-a[0])/60.0 for a in v]), np.array([a[1] for a in v]), np.array([a[2] for a in v])
def ev(idx,lv,lu):
    r,a,_=cols(idx,lv,lu); return (float(np.mean(r)),float(np.mean(a)))
def calibrate(idx,target):
    """returns (res dict | None, table). res=None: infeasible on coarse grid -> res_min (min-risk coarse point, cheapest on ties) in table['_min']"""
    table={}
    for lv,lu in itertools.product(GRID_VM,GRID_UP): table[(lv,lu)]=ev(idx,lv,lu)
    feas=[(k,v) for k,v in table.items() if v[0]<=target]
    if not feas:
        (lv,lu),(risk,al)=min(table.items(),key=lambda kv:(kv[1][0],kv[1][1]))
        return None, dict(lam_vm=lv,lam_up=lu,cal_risk=risk,cal_alloc=al,offgrid=False)
    (lv,lu),_=min(feas,key=lambda kv:kv[1][1])
    refine=[(round(lv+dv,2),round(lu+du,2)) for dv,du in itertools.product((-0.25,0,0.25),(-0.25,0,0.25)) if (round(lv+dv,2),round(lu+du,2)) not in table and lv+dv>0 and lu+du>0]
    off=any((round(a,2),round(b,2)) not in PIDX for a,b in refine)
    for k in refine: table[k]=ev(idx,*k)
    feas=[(k,v) for k,v in table.items() if v[0]<=target]
    (lv,lu),(risk,al)=min(feas,key=lambda kv:kv[1][1])
    return dict(lam_vm=lv,lam_up=lu,cal_risk=risk,cal_alloc=al,offgrid=off), table
def heldout(idx,lv,lu):
    """held-out risk and allocs: mean over traces (v8sim10_full mean_over uses chunk-of-200 weighted means = same value up to fp)"""
    r,a,v=cols(idx,lv,lu); return float(np.mean(r)), float(np.mean(a)), float(np.mean(v))
def groups_of(idx=None):
    g={}
    for i in (range(len(lib)) if idx is None else idx): g.setdefault((lib[i]["loc"],lib[i]["date"]),[]).append(i)
    return g
def vbits_to_mat(vb):
    vb=np.asarray(vb,dtype=np.uint64); return ((vb[...,None]>>np.arange(60,dtype=np.uint64))&np.uint64(1)).astype(bool)
