#!/usr/bin/env python3
"""spec §4.139 item 2: registered predictions.
(1) S4' (2 % 1.5/1.92, 0.5 % 2.33/3.33) on t4/t6/t8, three versions: (a) per-slot v8sim11 R38 off, own initial_fleet; (b) fleet nest2gen.sim_s7
    variant independent_full w 1600, cfg_measured, vmexist (layer minutes = minute-sampled burn counts); (c) per-slot R38 on (frozen default physics).
    S4b / S4a (CtlSigma) with the same three versions as reference. Equivalence: (a) and (b) for S4' t4/t8 vs r68unif out/new_traces.json.
(2) t11/t12 per-slot R38 off, own initial_fleet: S4' 2 %, S4b, baselines set A (r67band library 2 % knobs) and set B (hardware-deployed knobs).
Output out/predict.json."""
import timeit  # noqa
import sys, os, json, numpy as np
Q='/home/user/experiment/qsim'; R=f'{Q}/r71fin'; E='/home/user/experiment'
for p in (Q,Q+'/r67band',Q+'/r68unif',Q+'/s7',Q+'/r70eq',R): sys.path.insert(0,p)
os.chdir(Q)
import v8sim11 as V, v8sim7 as M, s7core as C7, nest2gen as G, run as RB, scan as SC, fine as F
cfgV,prV=V.cfg_prior(); cfgM=M.cfg_measured(); S7P=C7.S7Prior(RB.LIB,cfgV)
PTS={"2":{"S4p":(1.5,1.92),"S4":(1.83,2.00)},"05":{"S4p":(2.33,3.33),"S4":(2.83,3.08)}}
def ue_of(tn): return json.load(open(f"{E}/trace_ue_60min_v3_{tn}.json"))["ue"][:60]
def ctl(arm,L): return CG_(arm,L)
def CG_(arm,L):
    import ctlgen as CG
    return CG.CtlGen(cfgV,S7P,L,indep=True,indep_rel=True,w=1600) if arm=="S4p" else V.CtlSigma(cfgV,prV,L)
def ps(ue,c,start,phys):
    ph=V.Phys(ue,start=start,p=phys)
    for _ in range(3600//V.DT):
        ph.advance_units()
        if ph.t%V.TICK==0:
            ob=ph.observe(); d=c.tick(ph,ob) if c is not None else False; ph.hot_relief(getattr(ph,"_over",{}))
            if not d and ph.t-ph.last_pool_relief>=ph.p["pool_relief_s"]: ph.enqueue_pool_relief(); ph.last_pool_relief=ph.t
        ph.step()
    return F.row(ph.result())
def fleet(ue,arm,L):
    r=G.sim_s7(ue,cfgM,S7P if arm=="S4p" else prV,L,variant="independent_full" if arm=="S4p" else "full",w=1600 if arm=="S4p" else None,acct="vmexist")
    ev=sorted((t/60.0,k,(+1 if a=='out' else -1)) for t,a,k in r['ev'] if a in ('out','in')); fl=0
    for i,(t,l,dr) in enumerate(ev):
        for t2,l2,d2 in ev[i+1:]:
            if l2==l and t2-t<=10 and d2==-dr: fl+=1; break
    tj=r['traj']
    return dict(slo=int(r['slo']),viol=[int(m) for m in np.where(r['pct']>0.1)[0]],alloc_vm=float(r['alloc']),flaps=fl,acts=len(ev),
                wk_min=float(sum(x[7] for x in tj)),vy_min=float(sum(x[6] for x in tj)),slot_min=float(sum(x[5] for x in tj)),layer_min_note="minute-sampled")
if __name__=="__main__":
    out=dict(s4p={},t1112={},equiv={})
    for g,arms in PTS.items():
        for arm,(a,b) in arms.items():
            L={"vy":a,"wk":a,"up":b}
            for tn in ("t4","t6","t8"):
                ue=ue_of(tn); st=V.initial_fleet("S",ue[0],L=L)
                out["s4p"][f"{tn}|{g}|{arm}"]=dict(L=L,start=[int(x) for x in st],a=ps(ue,ctl(arm,L),st,RB.PH),b=fleet(ue,arm,L),c=ps(ue,ctl(arm,L),st,None))
                print(tn,g,arm,{k:(v['alloc_vm'],v['viol'],v['flaps']) for k,v in out["s4p"][f"{tn}|{g}|{arm}"].items() if k in "abc"},flush=True)
    nt=json.load(open(f'{Q}/r68unif/out/new_traces.json'))
    for tn in ("t4","t8"):
        for g in ("2","05"):
            o=nt[f"{tn}|S4p_{g}"]; x=out["s4p"][f"{tn}|{g}|S4p"]
            out["equiv"][f"{tn}|{g}"]=dict(ps=(o['ps']['slo'],round(o['ps']['alloc_vm'],6))==(x['a']['slo'],round(x['a']['alloc_vm'],6)),fl=(o['fl']['slo'],round(o['fl']['alloc'],6))==(x['b']['slo'],round(x['b']['alloc_vm'],6)))
    print("equiv",out["equiv"],flush=True)
    B4c2=lambda ue:(V.CtlB4(predictive=False,mu=12.0,target=3.5),V.initial_fleet("B4c2",ue[0]))
    B5c1=lambda ue:(V.CtlB4(predictive=True,mu=14.0,target=4.0),V.initial_fleet("B5c1",ue[0]))
    for tn in ("t11","t12"):
        ue=ue_of(tn); arms={}
        for arm,(a,b) in (("S4p",(1.5,1.92)),("S4b",(1.83,2.00))):
            L={"vy":a,"wk":a,"up":b}; arms[arm]=ps(ue,CG_("S4p" if arm=="S4p" else "S4",L),V.initial_fleet("S",ue[0],L=L),RB.PH)
        for name in ("B4_3.75_300","B5_4.0_L2","B6_0.775"):
            fam,key=RB.CFG[name]; c,st=RB.make(fam,key,ue); arms["A:"+name]=ps(ue,c,st,RB.PH)
        for name,mk in (("B4c2 3.5/12",B4c2),("B5c1 4.0/14",B5c1),("B6 u0.70",lambda ue:RB.make("B6",(0.70,),ue))):
            c,st=mk(ue); arms["B:"+name]=ps(ue,c,st,RB.PH)
        out["t1112"][tn]=dict(ue0=ue[0],arms=arms)
        for k,v in arms.items(): print(tn,k,v['slo'],v['viol'],round(v['alloc_vm'],1),v['flaps'],flush=True)
    json.dump(out,open(f'{R}/out/predict.json','w'),indent=1); print("DONE",flush=True)
