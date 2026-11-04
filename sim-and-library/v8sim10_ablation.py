#!/usr/bin/env python3
"""(docstring removed)"""
import sys, os, json, math, time, random, itertools, datetime as dt, numpy as np
from concurrent.futures import ProcessPoolExecutor
Q='/home/user/experiment/qsim'; os.chdir(Q); sys.path.insert(0,Q)
import v8sim2 as S, v8sim7 as M, v8sim10 as Q2, v8sim10_abl as A
from v8sim3 import grouped_split, risk_vec
OUT=f'{Q}/abl'; os.makedirs(OUT,exist_ok=True)
lib=json.load(open(f'{Q}/prior_traces.json')); cfg=M.cfg_measured(); pr=S.Prior(lib,cfg)
GRID_VM=[1.0,1.5,2.0,2.5,3.0,3.5]; GRID_UP=[1.5,2.0,2.5,3.0,3.5,4.0,4.5]          # = v8sim10_cal.py
GRID_1D=sorted(set(GRID_VM)|set(GRID_UP))
VARIANTS=[('e','full'),('a','single_lambda'),('b','independent'),("b'",'independent_full'),('c','fixed_dwell'),('d','lock_only')]
TARGETS=(0.02,0.005); SEEDS=range(6); NCAL=300; STEP=5
REFINE={'mode':'full'}
def log(msg):
    line=f"[{dt.datetime.now():%F %T}] {msg}"; print(line, flush=True)
    with open(f'{OUT}/progress.log','a') as f: f.write(line+'\n')

def trace_metrics(r):
    ev=sorted((t/60.0,k,(+1 if a=='out' else -1)) for t,a,k in r['ev'] if a in ('out','in'))
    flaps=0
    for i,(t,l,dr) in enumerate(ev):
        for t2,l2,d2 in ev[i+1:]:
            if l2==l and t2-t<=10 and d2==-dr: flaps+=1; break

    ev2=sorted((t/60.0,k,(+1 if a in ('out','cancel-drain') else -1)) for t,a,k in r['ev'] if a in ('out','in','cancel-drain'))
    flaps2=0
    for i,(t,l,dr) in enumerate(ev2):
        for t2,l2,d2 in ev2[i+1:]:
            if l2==l and t2-t<=10 and d2==-dr: flaps2+=1; break
    under={'vy':0,'up':0}; over={'vy':0,'up':0}
    for (m,D,nUP,nVY,nWK,bUP,bVY,bWK) in r['traj']:
        for k,n in (('vy',nVY),('up',nUP)):
            if n<cfg.need(k,D): under[k]+=1
            if n>cfg.need(k,D+STEP): over[k]+=1
    return dict(risk=(60-r['slo'])/60.0, alloc=r['alloc'], flaps=flaps, flaps_cd=flaps2, acts=len(ev),
                acts_vy=sum(1 for e in ev if e[1]=='vy'), acts_wk=sum(1 for e in ev if e[1]=='wk'), acts_up=sum(1 for e in ev if e[1]=='up'),
                under_vy=under['vy'], under_up=under['up'], over_vy=over['vy'], over_up=over['up'])
# ---------- workers
def run_cal(args):
    idx,lv,lu,variant=args; L={"vy":lv,"wk":lv,"up":lu}
    rs=[A.sim_nest2(lib[i]["ue"][:60],cfg,pr,L,variant=variant) for i in idx]
    return (lv,lu,float(np.mean(risk_vec(rs))),float(np.mean([r["alloc"] for r in rs])))
def run_ho(args):
    idx,lv,lu,variant=args; L={"vy":lv,"wk":lv,"up":lu}; out=[]
    for i in idx:
        r=A.sim_nest2(lib[i]["ue"][:60],cfg,pr,L,variant=variant,acct='vmexist'); m=trace_metrics(r)
        r2=A.sim_nest2(lib[i]["ue"][:60],cfg,pr,L,variant=variant,acct='dispatch'); m['alloc_dispatch']=r2['alloc']
        assert r2['slo']==r['slo'] and r2['ev']==r['ev']
        out.append(m)
    return out
def evaluate(pool,idx,grid,variant):
    return {(lv,lu):(risk,al) for lv,lu,risk,al in pool.map(run_cal,[(idx,lv,lu,variant) for lv,lu in grid])}
def calibrate(pool,cal_idx,target,variant,one_d):
    grid=[(l,l) for l in GRID_1D] if one_d else list(itertools.product(GRID_VM,GRID_UP))
    table=evaluate(pool,cal_idx,grid,variant)
    feas=[(k,v) for k,v in table.items() if v[0]<=target]
    if not feas: return None,table
    (lv,lu),_=min(feas,key=lambda kv:kv[1][1])
    if REFINE['mode']=='full':
        if one_d: refine=[(round(lv+dv,2),round(lv+dv,2)) for dv in (-0.25,0.25) if (round(lv+dv,2),round(lv+dv,2)) not in table and lv+dv>0]
        else: refine=[(round(lv+dv,2),round(lu+du,2)) for dv,du in itertools.product((-0.25,0,0.25),(-0.25,0,0.25)) if (round(lv+dv,2),round(lu+du,2)) not in table and lv+dv>0 and lu+du>0]
        table.update(evaluate(pool,cal_idx,refine,variant))
    feas=[(k,v) for k,v in table.items() if v[0]<=target]
    (lv,lu),(risk,al)=min(feas,key=lambda kv:kv[1][1])
    return dict(lam_vm=lv,lam_up=lu,cal_risk=risk,cal_alloc=al,n_eval=len(table)),table
def heldout(pool,ho_idx,lv,lu,variant):
    chunks=[ho_idx[j:j+80] for j in range(0,len(ho_idx),80)]
    ms=[m for part in pool.map(run_ho,[(c,lv,lu,variant) for c in chunks]) for m in part]
    keys=['risk','alloc','alloc_dispatch','flaps','flaps_cd','acts','acts_vy','acts_wk','acts_up','under_vy','under_up','over_vy','over_up']
    return {k:float(np.mean([m[k] for m in ms])) for k in keys}|{'n':len(ms)}

def equiv_check(n=20, seed=20261020):
    rnd=random.Random(seed); idx=rnd.sample(range(len(lib)),n); lines=[]; ok=True
    for L in ({"vy":1.83,"wk":1.83,"up":2.00},{"vy":2.83,"wk":2.83,"up":3.08},{"vy":1.0,"wk":1.0,"up":1.5}):
        for acct in ('dispatch','vmexist'):
            for i in idx:
                ue=lib[i]["ue"][:60]; r0=Q2.sim_nest2(ue,cfg,pr,L,acct=acct)
                for v in ('e','full','single_lambda'):
                    r1=A.sim_nest2(ue,cfg,pr,L,acct=acct,variant=v)
                    same=(r0['slo']==r1['slo'] and r0['alloc']==r1['alloc'] and r0['ev']==r1['ev'] and r0['traj']==r1['traj'] and np.array_equal(r0['pct'],r1['pct']) and np.array_equal(r0['permin'],r1['permin']))
                    ok&=same
                    if not same: lines.append(f"MISMATCH trace {i} L {L} acct {acct} variant {v}: slo {r0['slo']}/{r1['slo']} alloc {r0['alloc']}/{r1['alloc']}")

    diff={}
    for v in ('independent','independent_full','fixed_dwell','lock_only'):
        L={"vy":1.83,"wk":1.83,"up":2.00}
        diff[v]=sum(1 for i in idx if A.sim_nest2(lib[i]["ue"][:60],cfg,pr,L,variant=v)['ev']!=Q2.sim_nest2(lib[i]["ue"][:60],cfg,pr,L)['ev'])
    hdr=f"equivalence check: {n} random traces (seed {seed}) × 3 λ sets × 2 acct × variants e/full/single_lambda vs v8sim10.sim_nest2 → {'IDENTICAL' if ok else 'MISMATCH'} (slo/alloc/ev/traj/pct/permin); traces where variant differs from full (λ 1.83/2.00): {diff}"
    open(f'{OUT}/equiv_check.txt','w').write(hdr+'\n'+'\n'.join(lines)+'\n'); log(hdr)
    for l in lines[:10]: log('  '+l)
    return ok
# ---------- main
if __name__=="__main__":
    nproc=int(sys.argv[1]) if len(sys.argv)>1 and sys.argv[1].isdigit() else 2
    T0=time.time(); log(f"=== ablation start: nproc {nproc}, pid {os.getpid()}, affinity {sorted(os.sched_getaffinity(0))}, lib {len(lib)}, targets {TARGETS}, seeds {list(SEEDS)}, cal {NCAL}, grid {len(GRID_VM)}×{len(GRID_UP)} (1-D {GRID_1D}), refine ±0.25")
    ok=equiv_check()
    if not ok: log("ABORT: variant 'e' not equivalent to v8sim10"); sys.exit(2)
    if '--check-only' in sys.argv: sys.exit(0)
    rawp=f'{OUT}/ablation_raw.json'
    raw=json.load(open(rawp)) if os.path.exists(rawp) and '--resume' in sys.argv else {'meta':{'start':f'{dt.datetime.now():%F %T}','nproc':nproc,'grid_vm':GRID_VM,'grid_up':GRID_UP,'grid_1d':GRID_1D,'ncal':NCAL,'targets':list(TARGETS),'seeds':list(SEEDS),'refine':REFINE['mode'],'step_floor':STEP,'equiv_ok':ok},'rows':[]}
    done={(r['variant'],r['target'],r['seed']) for r in raw['rows']}
    n2d=sum(1 for tag,v in VARIANTS if v!='single_lambda')*len(TARGETS)*len(SEEDS); n1d=len(TARGETS)*len(SEEDS); first=None
    with ProcessPoolExecutor(nproc) as pool:
        for tag,variant in VARIANTS:
            one_d=(variant=='single_lambda')
            for target in TARGETS:
                for seed in SEEDS:
                    if (variant,target,seed) in done: continue
                    ts=time.time(); cal_idx,ho_idx=grouped_split(seed); cal_idx=cal_idx[:NCAL]
                    res,table=calibrate(pool,cal_idx,target,variant,one_d)
                    if res is None:
                        log(f"({tag}) {variant} target {target} split{seed}: INFEASIBLE on grid (min cal risk {min(v[0] for v in table.values()):.4f})")
                        raw['rows'].append(dict(variant=variant,tag=tag,target=target,seed=seed,infeasible=True,table={f"{k[0]}/{k[1]}":v for k,v in table.items()})); json.dump(raw,open(rawp,'w'),indent=1); continue
                    ho=heldout(pool,ho_idx,res['lam_vm'],res['lam_up'],variant); el=time.time()-ts
                    row=dict(variant=variant,tag=tag,target=target,seed=seed,n_cal=len(cal_idx),n_ho=len(ho_idx),**res,ho=ho,elapsed_s=round(el,1),table={f"{k[0]}/{k[1]}":v for k,v in table.items()})
                    raw['rows'].append(row); json.dump(raw,open(rawp,'w'),indent=1)
                    log(f"({tag}) {variant:16s} target {target} split{seed}: λ {res['lam_vm']}/{res['lam_up']} cal {res['cal_risk']:.4f} alloc {res['cal_alloc']:.1f} ({res['n_eval']} pts) | ho n {ho['n']} risk {ho['risk']:.4f} alloc_vmexist {ho['alloc']:.1f} alloc_disp {ho['alloc_dispatch']:.1f} flaps {ho['flaps']:.2f} (cd {ho['flaps_cd']:.2f}) acts {ho['acts']:.1f} under vy/up {ho['under_vy']:.2f}/{ho['under_up']:.2f} over vy/up {ho['over_vy']:.2f}/{ho['over_up']:.2f}  [{el:.0f}s, total {time.time()-T0:.0f}s]")
                    if first is None and not one_d:
                        first=el; proj=first*(n2d+0.25*n1d)
                        log(f"RUNTIME PROJECTION from first 2-D split: {first:.0f}s/split × ({n2d} 2-D + {n1d}×0.25 1-D) ≈ {proj/3600:.2f} h")
                        if proj>6*3600:
                            REFINE['mode']='none'; raw['meta']['refine']='none (reduced after projection %.2f h > 6 h; first split used full refine)'%(proj/3600)
                            log("PROJECTION > 6 h → refinement reduced to 'none' (coarse grid only) for remaining splits; number of splits unchanged")
    # ---------- table
    rows=[r for r in raw['rows'] if not r.get('infeasible')]
    def agg(variant,target):
        rs=[r for r in rows if r['variant']==variant and r['target']==target]
        if not rs: return None
        g=lambda f: (float(np.mean([f(r) for r in rs])), float(np.std([f(r) for r in rs])))
        return dict(n=len(rs), lam_vm=g(lambda r:r['lam_vm']), lam_up=g(lambda r:r['lam_up']), cal_risk=g(lambda r:r['cal_risk']),
                    risk=g(lambda r:r['ho']['risk']), alloc=g(lambda r:r['ho']['alloc']), alloc_d=g(lambda r:r['ho']['alloc_dispatch']), flaps=g(lambda r:r['ho']['flaps']), flaps_cd=g(lambda r:r['ho']['flaps_cd']),
                    acts=g(lambda r:r['ho']['acts']), under_vy=g(lambda r:r['ho']['under_vy']), under_up=g(lambda r:r['ho']['under_up']), over_vy=g(lambda r:r['ho']['over_vy']), over_up=g(lambda r:r['ho']['over_up']))
    pm=lambda x,p=2: f"{x[0]:.{p}f} ± {x[1]:.{p}f}"
    L=[f"# §4.99 C 部件 ablation(等風險重校準)— {dt.datetime.now():%F %T}", "",
       f"nest2 副本 `v8sim10_abl.py`(凍結版不動;variant 'e' 與 v8sim10.sim_nest2 逐位元等價:{'PASS' if ok else 'FAIL'},見 abl/equiv_check.txt)。每格 = 六切分(grouped_split seed 0–5)、校準集 300 條、粗網格 {GRID_VM} × {GRID_UP}(單 λ:{GRID_1D})→ 可行(cal risk ≤ 目標)取最便宜 → ±0.25 細化({raw['meta']['refine']});留出 = 該切分的全部留出 trace(~{rows[0]['n_ho'] if rows else '?'} 條)。",
       "欄位:風險 = 留出違規分鐘比例;成本 = 留出 alloc core-min/場(acct=vmexist;括號 dispatch);flaps = 同層 10 分鐘內反向(只算 out/in;括號 = 另把 cancel-drain 當 out);under/over = ready 數 < need(D) / > need(D+5) 的分鐘數(VY/UP);mean ± std(母體,n=6 切分)。",
       "判讀規則(寫死):相對 (e) 成本差 >1% 或 flap 差 >2 次/場 → 該部件「有貢獻」。", "",
       "| variant | target | λ_vm | λ_up | cal risk | held-out risk | alloc vmexist (dispatch) | Δcost vs e | flaps/run (cd) | Δflaps | acts/run | under VY/UP | over VY/UP | verdict |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    verdicts={}
    for target in TARGETS:
        base=agg('full',target)
        for tag,variant in VARIANTS:
            a=agg(variant,target)
            if a is None: L.append(f"| ({tag}) {variant} | {target} | infeasible/none | | | | | | | | | | | |"); continue
            dc=100*(a['alloc'][0]-base['alloc'][0])/base['alloc'][0]; df=a['flaps'][0]-base['flaps'][0]
            if variant=='full': vd='baseline'
            else:
                contrib=abs(dc)>1.0 or abs(df)>2.0
                vd=('CONTRIBUTES' if contrib else 'no contribution')+f" (|Δcost| {abs(dc):.2f}% {'>' if abs(dc)>1 else '≤'} 1%, |Δflaps| {abs(df):.2f} {'>' if abs(df)>2 else '≤'} 2)"
                if a['risk'][0]>base['risk'][0]+0.25*target: vd+=f"; NOTE held-out risk {a['risk'][0]:.4f} vs e {base['risk'][0]:.4f} (not equal-risk)"
            verdicts[(variant,target)]=dict(dcost_pct=dc,dflaps=df,verdict=vd)
            lam=(f"{pm(a['lam_vm'])}" if variant!='single_lambda' else f"{pm(a['lam_vm'])} (shared)")
            L.append(f"| ({tag}) {variant} | {target} | {lam} | {pm(a['lam_up'])} | {pm(a['cal_risk'],4)} | {pm(a['risk'],4)} | {pm(a['alloc'],1)} ({a['alloc_d'][0]:.1f}) | {dc:+.2f}% | {pm(a['flaps'])} ({a['flaps_cd'][0]:.2f}) | {df:+.2f} | {pm(a['acts'],1)} | {pm(a['under_vy'])} / {pm(a['under_up'])} | {pm(a['over_vy'])} / {pm(a['over_up'])} | {vd} |")
    L+=["", "## 逐切分", "", "| variant | target | seed | λ_vm/λ_up | cal risk | cal alloc | ho n | ho risk | ho alloc vmexist | ho alloc dispatch | flaps | flaps(cd) | acts | under VY/UP | over VY/UP | s |", "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in raw['rows']:
        if r.get('infeasible'): L.append(f"| {r['variant']} | {r['target']} | {r['seed']} | infeasible | | | | | | | | | | | | |"); continue
        h=r['ho']; L.append(f"| {r['variant']} | {r['target']} | {r['seed']} | {r['lam_vm']}/{r['lam_up']} | {r['cal_risk']:.4f} | {r['cal_alloc']:.1f} | {h['n']} | {h['risk']:.4f} | {h['alloc']:.1f} | {h['alloc_dispatch']:.1f} | {h['flaps']:.2f} | {h['flaps_cd']:.2f} | {h['acts']:.1f} | {h['under_vy']:.2f}/{h['under_up']:.2f} | {h['over_vy']:.2f}/{h['over_up']:.2f} | {r['elapsed_s']:.0f} |")
    L+=["", f"總耗時 {(time.time()-T0)/3600:.2f} h(nproc {nproc});原始數 abl/ablation_raw.json;進度 abl/progress.log。"]
    open(f'{OUT}/ablation_table.md','w').write('\n'.join(L)+'\n')
    raw['meta']['end']=f'{dt.datetime.now():%F %T}'; raw['meta']['total_s']=round(time.time()-T0); raw['verdicts']={f"{k[0]}@{k[1]}":v for k,v in verdicts.items()}
    json.dump(raw,open(rawp,'w'),indent=1)
    log(f"=== DONE total {(time.time()-T0)/3600:.2f} h → {OUT}/ablation_table.md")
