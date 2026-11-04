#!/usr/bin/env python3
"""r62de six-split recalibration driver (one process, no pool).
  --lib PATH        trace library (default: frozen prior_traces.json); Prior σ̂ is re-estimated on THIS library with THIS cfg
  --h up,vy,wk      lead dict for cfg_with_h (default = cfg_measured HM 30,150,120); win = h+g (wk: h_wk+h_up+g), g = TICK = 30 s
  --rates           per-UE rate model: each trace draws a rate per UE index from {150,250,350} kpps (np.random.default_rng(20261021),
                    library order, 40 draws per trace); loss sees Σ_{i<n(t)} r_i/250 UE-equivalents, the controller sees n(t)
  --no-refine       coarse grid only
  --name NAME       output tag → r62de/out/NAME.json (+ matrix cache NAME.pkl)
Usage: cd /home/user/experiment/qsim/r62de && nice -n 19 taskset -c 13,14 python3 run_cal.py --name base"""
import sys, os, json, time, argparse, itertools, datetime as dt, numpy as np
R='/home/user/experiment/qsim/r62de'; sys.path.insert(0,R)
import eng
S=eng.S
ap=argparse.ArgumentParser(); ap.add_argument('--lib',default='/home/user/experiment/qsim/prior_traces.json'); ap.add_argument('--h',default='30,150,120')
ap.add_argument('--rates',action='store_true'); ap.add_argument('--no-refine',action='store_true'); ap.add_argument('--name',required=True); ap.add_argument('--equiv',type=int,default=0)
a=ap.parse_args()
os.makedirs(f'{R}/out',exist_ok=True)
def log(m):
    line=f"[{dt.datetime.now():%F %T}] [{a.name}] {m}"; print(line,flush=True)
    open(f'{R}/progress.log','a').write(line+'\n')
T0=time.time()
lib=json.load(open(a.lib)); hu,hv,hw=[int(x) for x in a.h.split(',')]; cfg=eng.cfg_with_h(dict(up=hu,vy=hv,wk=hw))
pr=S.Prior(lib,cfg)
loads=None
if a.rates:
    rng=np.random.default_rng(20261021); loads=[]
    for tr in lib:
        r=rng.choice([150,250,350],size=40); cs=np.concatenate([[0],np.cumsum(r)])/250.0
        loads.append([float(cs[n]) for n in tr["ue"]])
log(f"start: lib {a.lib} n {len(lib)} groups {len(set((t['loc'],t['date']) for t in lib))} h {cfg.h} win {cfg.win} d {cfg.d} rates {a.rates} refine {not a.no_refine}; pid {os.getpid()} affinity {sorted(os.sched_getaffinity(0))}")
if a.equiv:
    bad,n=eng.check_equiv(lib,cfg,pr,n=a.equiv); log(f"equivalence vs frozen v8sim10.sim_nest2 (dispatch+vmexist, 3 λ sets × {a.equiv} traces): {n-bad}/{n} identical")
mx=eng.Matrix(f'{R}/out/{a.name}.pkl',lib,cfg,pr,loads=loads,log=log)
mx.prefill(list(itertools.product(eng.GRID_VM,eng.GRID_UP)))
log(f"coarse grid done: {time.time()-T0:.0f}s")
rows=eng.six_split(mx,lib,refine=not a.no_refine,log=log)
summ={str(t):eng.summarize(rows,t) for t in (0.02,0.005)}
for t,sm in summ.items():
    if sm['n']: log(f"SUMMARY target {t}: λ {sm['lam_vm'][0]:.2f}±{sm['lam_vm'][1]:.2f}/{sm['lam_up'][0]:.2f}±{sm['lam_up'][1]:.2f} cal {sm['cal_risk'][0]:.4f} ho risk {sm['risk'][0]:.4f}±{sm['risk'][1]:.4f} alloc_vm {sm['alloc_vm'][0]:.1f}±{sm['alloc_vm'][1]:.1f} (disp {sm['alloc_d'][0]:.1f}) n {sm['n']} infeasible {sm['ninf']}")
    else: log(f"SUMMARY target {t}: all splits infeasible")
# library statistics: rise1 / rise10 (max 1-min / 10-min rise of the UE trace)
def rise(ue,w):   # = lib_percentiles.py: max{u[j]-u[i]: 0<j-i<=w} over the 60 experiment minutes
    u=list(ue[:60]); n=len(u); return float(max(u[j]-u[i] for i in range(n) for j in range(i+1,min(n-1,i+w)+1)))
r1=[rise(t['ue'],1) for t in lib]; r10=[rise(t['ue'],10) for t in lib]
libstats=dict(n=len(lib),groups=len(set((t['loc'],t['date']) for t in lib)),rise1=[float(np.percentile(r1,p)) for p in (10,50,90)],rise10=[float(np.percentile(r10,p)) for p in (10,50,90)])
sig={f"{kind}_{k}@20":float(pr.sigma(kind,k,20)) for kind in ('win','run') for k in ('vy','up','wk')}
json.dump(dict(name=a.name,args=vars(a),cfg=dict(h=cfg.h,win=cfg.win,d=cfg.d),libstats=libstats,sigma20=sig,rows=rows,summary=summ,sim_s=mx.sim_s,nsim=mx.nsim,total_s=time.time()-T0),open(f'{R}/out/{a.name}.json','w'),indent=1)
log(f"DONE {time.time()-T0:.0f}s (sim {mx.sim_s:.0f}s, {mx.nsim} trace-sims) libstats {libstats}")
