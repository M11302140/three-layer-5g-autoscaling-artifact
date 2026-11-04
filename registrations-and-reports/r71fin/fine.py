#!/usr/bin/env python3
"""spec §4.139 item 1: fine scan c = lo + 0.0025k (k=1..7) inside the three E1 brackets whose points both missed target ± 0.05 pp
(2 % S8 [0.96,0.98], 2 % S4' [0.96,0.98], 0.5 % A-PL [0.92,0.94]); r70eq scan pipeline (per-slot v8sim11 R38 off, own initial_fleet) with acts recorded.
Then: chosen / bracket points of all eight E1 rows rerun with acts where the cached row has none (equivalence vs cache: slo, alloc_vm, flaps per trace),
and the six r67band baseline configs rerun with acts (equivalence vs r67band out/<cfg>.json). Rows -> out/fine/*.json. Prints DONE."""
import timeit  # noqa
import sys, os, json, glob, time, numpy as np
Q='/home/user/experiment/qsim'; R=f'{Q}/r71fin'
for p in (Q,Q+'/r67band',Q+'/r68unif',Q+'/s7',Q+'/r70eq'): sys.path.insert(0,p)
os.chdir(Q)
import v8sim11 as V, run as RB, scan as SC
from concurrent.futures import ProcessPoolExecutor
LIB=RB.LIB; N=len(LIB); TGT=SC.TGT; TOL=0.0005
FINE={("S8","2"):0.96,("S4p","2"):0.96,("APL","05"):0.92}
BASES={"2":["B4_3.75_300","B5_4.0_L2","B6_0.775"],"05":["B4_3.0_300","B5_3.5_L1","B6_0.7"]}
os.makedirs(f'{R}/out/fine',exist_ok=True)
def row(r):
    ab=r['alloc_by']
    return dict(slo=int(r['slo']),viol=[int(x) for x in r['viol']],alloc_vm=r['alloc_vm'],wk_min=ab['wk']/3,vy_min=ab['vy']/2,slot_min=ab['up']/0.8,
                flaps=int(RB.flaps(r['events'])),acts=sum(1 for e in r['events'] if e[1] in ('out','in')))
def job_s(args):
    arm,g,c,i=args; a,b=SC.BASE[g][arm]; L={"vy":round(c*a,4),"wk":round(c*a,4),"up":round(c*b,4)}; ue=LIB[i]["ue"][:60]
    return i,row(RB.run_ctl(ue,SC.ctl_of(arm,L),V.initial_fleet("S",ue[0],L=L)))
def job_b(args):
    name,i=args; fam,key=RB.CFG[name]; ue=LIB[i]["ue"][:60]; ctl,st=RB.make(fam,key,ue)
    return i,row(RB.run_ctl(ue,ctl,st))
def spt(pool,arm,g,c):
    fn=f'{R}/out/fine/{arm}_{g}_{c:.4f}.json'
    if os.path.exists(fn): return json.load(open(fn))
    res=dict(pool.map(job_s,[(arm,g,c,i) for i in range(N)],chunksize=8)); rows=[res[i] for i in range(N)]
    d=dict(arm=arm,g=g,c=c,risk=float(np.mean([(60-r['slo'])/60 for r in rows])),cost=float(np.mean([r['alloc_vm'] for r in rows])),rows=rows)
    old=f'{Q}/r70eq/out/scan/{arm}_{g}_{c:.2f}.json'
    if abs(round(c,2)-c)<1e-9 and os.path.exists(old):
        o=json.load(open(old))['rows']; d['equiv_r70eq']=all((x['slo'],x['alloc_vm'],x['flaps'])==(y['slo'],y['alloc_vm'],y['flaps']) for x,y in zip(o,rows))
        if not d['equiv_r70eq']: print(f"EQUIV FAIL {arm} {g} {c}",flush=True); sys.exit(3)
    json.dump(d,open(fn,'w')); print(f"[{time.strftime('%T')}] {arm} {g} c {c:.4f}: risk {100*d['risk']:.3f} % cost {d['cost']:.1f} flaps {np.mean([r['flaps'] for r in rows]):.2f}",flush=True); return d
def allpts(arm,g):
    ps={round(d['c'],4):d for d in (json.load(open(f)) for f in glob.glob(f'{Q}/r70eq/out/scan/{arm}_{g}_*.json'))}
    for f in glob.glob(f'{R}/out/fine/{arm}_{g}_*.json'): d=json.load(open(f)); ps[round(d['c'],4)]=d
    return [ps[c] for c in sorted(ps)]
def choose(arm,g):
    ps=allpts(arm,g); t=TGT[g]; w=[d for d in ps if abs(d['risk']-t)<=TOL]
    if w: return [min(w,key=lambda d:(abs(d['risk']-t),d['c']))['c']]
    br=[(x,y) for x,y in zip(ps,ps[1:]) if (x['risk']-t)*(y['risk']-t)<=0]
    return [br[0][0]['c'],br[0][1]['c']]
if __name__=="__main__":
    with ProcessPoolExecutor(2) as pool:
        for (arm,g),lo in FINE.items():
            for k in range(1,8): spt(pool,arm,g,round(lo+0.0025*k,4))
        for g in ("2","05"):
            for arm in ("S4","APL","S8","S4p"):
                cs=choose(arm,g); print(f"chosen {arm} {g}: {cs}",flush=True)
                for c in cs: spt(pool,arm,g,c)
        for g,names in BASES.items():
            for name in names:
                fn=f'{R}/out/fine/base_{name}.json'
                if os.path.exists(fn): continue
                res=dict(pool.map(job_b,[(name,i) for i in range(N)],chunksize=8)); rows=[res[i] for i in range(N)]
                o=json.load(open(f'{Q}/r67band/out/{name}.json'))['rows']; eq=all((x['slo'],x['alloc_vm'],x['flaps'])==(y['slo'],y['alloc_vm'],y['flaps']) for x,y in zip(o,rows))
                if not eq: print(f"EQUIV FAIL base {name}",flush=True); sys.exit(3)
                json.dump(dict(name=name,g=g,rows=rows,equiv_r67band=eq),open(fn,'w')); print(f"[{time.strftime('%T')}] base {name}: equiv {eq}",flush=True)
    print("DONE",flush=True)
