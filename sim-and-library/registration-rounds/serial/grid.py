#!/usr/bin/env python3
"""qsim/serial/grid.py (spec §4.134 items 2-3): P1 equivalence (fleet), the setting grid on t3/t4/t6/t7/t8 for all arms in both simulators,
the library-level S4b / B6 comparison (six splits, held-out, P1 vs P2 at lead 30 / 33 s), and the registered readings (a)(b)(c).
Output serial/out/grid.json, grid.txt"""
import sys, os, json, time, math, numpy as np
Q='/home/user/experiment/qsim'; sys.path.insert(0,Q); sys.path.insert(0,Q+'/serial'); os.chdir(Q)
_argv=sys.argv; sys.argv=[sys.argv[0]]
import v8sim10_ablation as AB
sys.argv=_argv
import v8sim2 as S, v8sim10 as Q2, v8sim_b6 as B, v8sim11 as V
import ps as PS, nest2c as N, fleetc as F
from v8sim3 import grouped_split
from concurrent.futures import ProcessPoolExecutor
E='/home/user/experiment'; lib=AB.lib; cfg=AB.cfg; V.cfg_prior(); _,GPR=V.cfg_prior(); MK=B.load_models()
TRS=('t3','t4','t8','t6','t7'); ARMS=('S4a','S4b','v6','B4c2','B5c1','B6','B1'); BASE=('B4c2','B5c1','B6')
LAM={"S4b":{"vy":1.83,"wk":1.83,"up":2.00},"S4a":{"vy":2.83,"wk":2.83,"up":3.08}}
SET={"P1":None,"P1u":(1,0)}
for C in (2,4,None):
    for dl in (0,3,15): SET[f"P{'inf' if C is None else C}/{30+dl}s"]=(C,dl)
UE={tn:json.load(open(f"{E}/trace_ue_60min_v3_{tn}.json"))["ue"][:60] for tn in TRS}
def fleet(arm,ue,st):
    q=[0]; C,dl=(st if st is not None else (0,0))
    if arm in LAM:
        r=N.sim_cap(ue,cfg,GPR,LAM[arm],acct='vmexist',capC=C,delta=dl,qbox=q); return dict(slo=r['slo'],cost=r['alloc'],flaps=AB.trace_metrics(r)['flaps'],queue=q[0])
    if arm=='v6': r=F.sim_v6c(ue,cfg,capC=C,delta=dl,qbox=q)
    elif arm=='B6': r=F.sim_b6c(ue,cfg,0.70,MK,capC=C,delta=dl,qbox=q)
    else: return None
    return dict(slo=r['slo'],cost=r['alloc'],flaps=r['flaps'],queue=q[0] if st is not None else None)
def cell(args):
    tn,arm,sn=args; st=SET[sn]; r=PS.run(UE[tn],arm,st); fl=fleet(arm,UE[tn],st)
    return (tn,arm,sn),dict(ps=dict(slo=r['slo'],viol=r['viol'],cost=r['alloc_vm'],flaps=r['flaps'],queue=r['queue']),fl=fl)
def libjob(seed):
    c,h=grouped_split(seed); pr=S.Prior([lib[i] for i in c],cfg); out={}
    for sn,st in (("P1",None),("P2/30s",(2,0)),("P2/33s",(2,3))):
        C,dl=(st if st is not None else (0,0))
        rs=[N.sim_cap(lib[i]["ue"][:60],cfg,pr,LAM["S4b"],acct='dispatch',capC=C,delta=dl) for i in h]
        bs=[F.sim_b6c(lib[i]["ue"][:60],cfg,0.70,MK,capC=C,delta=dl) for i in h]
        out[sn]=dict(S4b_risk=float(np.mean([(60-r['slo'])/60 for r in rs])),S4b_cost=float(np.mean([r['alloc'] for r in rs])),
                     B6_risk=float(np.mean([(60-r['slo'])/60 for r in bs])),B6_cost=float(np.mean([r['alloc'] for r in bs])))
    return seed,out
if __name__=="__main__":
    t0=time.time(); L=[]
    def P(s): print(s,flush=True); L.append(s)
    # fleet P1 equivalence
    ok=True
    for tn in TRS:
        ue=UE[tn]; ok&=(N.sim_cap(ue,cfg,GPR,LAM['S4b'])['ev']==Q2.sim_nest2(ue,cfg,GPR,LAM['S4b'])['ev'])
        a=S.sim_v6(ue,cfg); b=F.sim_v6c(ue,cfg); ok&=(a['slo'],a['alloc'],a['flaps'])==(b['slo'],b['alloc'],b['flaps'])
        a=B.sim_b6(ue,cfg,0.70,MK); b=F.sim_b6c(ue,cfg,0.70,MK); ok&=(a['slo'],a['alloc'],a['flaps'])==(b['slo'],b['alloc'],b['flaps'])
    P(f"fleet P1 (capC=0) vs frozen nest2 / sim_v6 / sim_b6 on 5 traces: {'IDENTICAL' if ok else 'MISMATCH'}")
    jobs=[(tn,arm,sn) for tn in TRS for arm in ARMS for sn in SET]
    with ProcessPoolExecutor(4) as pool: res=dict(pool.map(cell,jobs,chunksize=4))
    P(f"grid {len(res)} cells, {time.time()-t0:.0f}s")
    for tn in TRS:
        P(f"\n### {tn}\n| arm | "+" | ".join(SET)+" |\n|---|"+"---|"*len(SET))
        for arm in ARMS:
            P(f"| {arm} per-slot viol / cost / queue | "+" | ".join(f"{60-res[(tn,arm,sn)]['ps']['slo']} / {res[(tn,arm,sn)]['ps']['cost']:.0f} / {res[(tn,arm,sn)]['ps']['queue']}" for sn in SET)+" |")
        for arm in ARMS:
            if res[(tn,arm,'P1')]['fl'] is None: continue
            P(f"| {arm} fleet viol / cost | "+" | ".join(f"{60-res[(tn,arm,sn)]['fl']['slo']} / {res[(tn,arm,sn)]['fl']['cost']:.0f}" for sn in SET)+" |")
    # (a) relative benefit, per-slot, vs P1 and vs P1u
    P("\n### (a) relative benefit (per-slot): violation reduction of S4b minus each baseline's, vs base setting")
    A={}
    for basen in ("P1","P1u"):
        for sn in [x for x in SET if x.startswith("P2") or x.startswith("P4")]:
            for tn in ('t3','t4','t8'):
                v=lambda arm,s: 60-res[(tn,arm,s)]['ps']['slo']
                dS=v('S4b',basen)-v('S4b',sn); diffs={b:dS-(v(b,basen)-v(b,sn)) for b in BASE}
                A[(basen,sn,tn)]=dict(dS=dS,diffs=diffs,disprop=all(x>=1 for x in diffs.values()))
                P(f"base {basen} -> {sn} {tn}: S4b reduction {dS:+d}; minus B4c2/B5c1/B6 = {diffs['B4c2']:+d}/{diffs['B5c1']:+d}/{diffs['B6']:+d} -> {'DISPROPORTIONATE' if A[(basen,sn,tn)]['disprop'] else 'not'}")
    # (b) dominance per trace and setting (per-slot)
    P("\n### (b) dominance (per-slot): who dominates S4b / S4a")
    def dom(a,b,tn,sn):   # a dominates b
        va,vb=60-res[(tn,a,sn)]['ps']['slo'],60-res[(tn,b,sn)]['ps']['slo']; ca,cb=res[(tn,a,sn)]['ps']['cost'],res[(tn,b,sn)]['ps']['cost']
        return va<=vb and ca<=cb and (va<vb or ca<cb)
    D={}
    for sn in SET:
        for tn in TRS:
            for s in ('S4b','S4a'):
                by=[b for b in BASE+('B1',) if dom(b,s,tn,sn)]; D[(sn,tn,s)]=by
        P(f"{sn}: "+"; ".join(f"{tn} S4b<-{','.join(D[(sn,tn,'S4b')]) or '-'} S4a<-{','.join(D[(sn,tn,'S4a')]) or '-'}" for tn in TRS))
    # (c) cost on t6/t7
    P("\n### (c) t6/t7 per-slot cost and violations vs P1")
    for tn in ('t6','t7'):
        for arm in ARMS:
            b=res[(tn,arm,'P1')]['ps']
            P(f"{tn} {arm}: P1 {60-b['slo']} / {b['cost']:.0f}; "+"; ".join(f"{sn} {60-res[(tn,arm,sn)]['ps']['slo']} / {res[(tn,arm,sn)]['ps']['cost']-b['cost']:+.0f}" for sn in SET if sn not in ('P1',)))
    # library
    with ProcessPoolExecutor(4) as pool: lr=dict(pool.map(libjob,range(6)))
    P("\n### library (six splits, held-out, fleet: S4b nest2 dispatch, B6 sim_b6)")
    for sn in ("P1","P2/30s","P2/33s"):
        m=lambda k: float(np.mean([lr[s][sn][k] for s in range(6)]))
        P(f"{sn}: S4b risk {m('S4b_risk'):.4f} cost {m('S4b_cost'):.1f} | B6 risk {m('B6_risk'):.4f} cost {m('B6_cost'):.1f}")
    P(f"\ntotal {time.time()-t0:.0f}s")
    json.dump(dict(res={'|'.join(map(str,k)):v for k,v in res.items()},A={'|'.join(k):v for k,v in A.items()},D={'|'.join(k):v for k,v in D.items()},lib=lr),open(f'{Q}/serial/out/grid.json','w'),indent=1,default=lambda o: o.item() if hasattr(o,'item') else str(o))
    open(f'{Q}/serial/out/grid.txt','w').write("\n".join(L)+"\n")
