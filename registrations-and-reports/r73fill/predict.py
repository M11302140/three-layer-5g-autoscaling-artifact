#!/usr/bin/env python3
"""spec §4.141 r73fill: registered predictions for the 22 fill-in runs, four versions per cell:
(a) per-slot R38 off (r67band PH), (b) fleet nest2 (nest2gen.sim_s7 / sim_b6 patch; B4 has no fleet model), (c) per-slot R38 on (frozen default
physics), (d) daemon-faithful CtlGen (r72hw ctlgen_d, excl_left + quant_d + no_serial; baselines (d) = (a)).
Planner cells: deployed λ (2 % 1.5/1.92, 0.5 % 2.33/3.33), start = the harness alignment rule of §4.140 / main_exp10 (slots/VyOS/workers):
t3 6/2/3, t5 8/3/4, t7 7/3/4 (t6t7_start.json). Same-target baseline cells (B4 3.75/300, B6 0.775) on t4 / t8: own initial_fleet (warm-in convergence start).
Output out/predict.json; frozen files untouched."""
import timeit  # noqa
import sys, os, json, numpy as np
Q='/home/user/experiment/qsim'; R=f'{Q}/r73fill'; E='/home/user/experiment'
for p in (Q,Q+'/r67band',Q+'/r68unif',Q+'/s7',Q+'/r70eq',Q+'/r71fin',Q+'/r72hw'): sys.path.insert(0,p)
os.chdir(Q)
import v8sim11 as V, v8sim7 as M, s7core as C7, nest2gen as G, run as RB, fine as F, ctlgen as CG, ctlgen_d as CD
import audit as AU   # r70eq: sim_b6s (fleet B6 with start), ps_pred helpers
cfgV,prV=V.cfg_prior(); cfgM=M.cfg_measured(); S7P=C7.S7Prior(RB.LIB,cfgV)
LAM={"S4p2":(1.5,1.92),"S4p05":(2.33,3.33)}
START={"t3":(6,2,3),"t5":(8,3,4),"t7":(7,3,4)}   # slots / VyOS / workers = harness START_REP / START_VY / START_WK
def ue_of(tn): return json.load(open(f"{E}/trace_ue_60min_v3_{tn}.json"))["ue"][:60]
def ps(ue,c,start,phys):
    ph=V.Phys(ue,start=start,p=phys)
    for _ in range(3600//V.DT):
        ph.advance_units()
        if ph.t%V.TICK==0:
            ob=ph.observe(); d=c.tick(ph,ob) if c is not None else False; ph.hot_relief(getattr(ph,"_over",{}))
            if not d and ph.t-ph.last_pool_relief>=ph.p["pool_relief_s"]: ph.enqueue_pool_relief(); ph.last_pool_relief=ph.t
        ph.step()
    r=ph.result(); x=F.row(r); x["layer_min"]=[x["wk_min"],x["vy_min"],x["slot_min"]]; return x
def fleet_s4p(ue,L,start):
    r=G.sim_s7(ue,cfgM,S7P,L,variant="independent_full",w=1600,acct="vmexist",start=start)
    ev=sorted((t/60.0,k,(+1 if a=='out' else -1)) for t,a,k in r['ev'] if a in ('out','in')); fl=0
    for i,(t,l,dr) in enumerate(ev):
        for t2,l2,d2 in ev[i+1:]:
            if l2==l and t2-t<=10 and d2==-dr: fl+=1; break
    tj=r['traj']
    return dict(slo=int(r['slo']),viol=[int(m) for m in np.where(r['pct']>0.1)[0]],alloc_vm=float(r['alloc']),flaps=fl,acts=len(ev),
                wk_min=float(sum(x[7] for x in tj)),vy_min=float(sum(x[6] for x in tj)),slot_min=float(sum(x[5] for x in tj)),layer_min="minute-sampled")
out={}
for tn in ("t3","t5","t7"):
    ue=ue_of(tn)
    for arm,(a,b) in LAM.items():
        L={"vy":a,"wk":a,"up":b}; st=START[tn]
        own=tuple(int(x) for x in V.initial_fleet("S",ue[0],L=L))
        cell=dict(L=L,start=list(st),own_initial_fleet=list(own),
                  a=ps(ue,CG.CtlGen(cfgV,S7P,L,indep=True,indep_rel=True,w=1600),st,RB.PH),
                  b=fleet_s4p(ue,L,st),
                  c=ps(ue,CG.CtlGen(cfgV,S7P,L,indep=True,indep_rel=True,w=1600),st,None),
                  d=ps(ue,CD.CtlGen(cfgV,S7P,L,indep=True,indep_rel=True,w=1600,excl_left=True,quant_d=True,no_serial=True),st,RB.PH))
        out[f"{tn}|{arm}"]=cell
        print(tn,arm,"start",st,"own",own,{k:(round(v['alloc_vm'],1),v['viol'],v['flaps'],v['acts']) for k,v in cell.items() if k in "abcd"},flush=True)
for tn in ("t4","t8"):
    ue=ue_of(tn)
    for arm,name in (("B4A_375_300","B4_3.75_300"),("B6c5_h","B6_0.775")):
        fam,key=RB.CFG[name]; c,st=RB.make(fam,key,ue); st=tuple(int(x) for x in st)
        cell=dict(knob=name,start=list(st),a=ps(ue,RB.make(fam,key,ue)[0],st,RB.PH),c=ps(ue,RB.make(fam,key,ue)[0],st,None))
        cell["d"]=cell["a"]
        if fam=="B6":
            r=AU.sim_b6s(ue,cfgM,0.775,AU.MK,start=st)
            cell["b"]=dict(slo=int(r['slo']),viol=[int(m) for m in np.where(np.array(r['pct'])>0.1)[0]] if 'pct' in r else None,alloc_vm=float(r['alloc']),flaps=int(r['flaps']),acts=None,note="fleet sim_b6 (dispatch accounting)")
        else: cell["b"]=None
        out[f"{tn}|{arm}"]=cell
        print(tn,arm,"start",st,{k:(round(v['alloc_vm'],1),v['viol'],v['flaps'],v.get('acts')) for k,v in cell.items() if k in "abcd" and v},flush=True)
json.dump(out,open(f"{R}/out/predict.json","w"),indent=1,default=str); print("DONE")
