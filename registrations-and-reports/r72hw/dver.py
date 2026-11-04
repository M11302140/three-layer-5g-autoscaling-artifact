#!/usr/bin/env python3
"""spec §4.140 A″: version (d) = daemon-faithful CtlGen (r72hw/ctlgen_d.py, three flags on), per-slot v8sim11 R38 off, own initial_fleet.
1) equivalence: flags off == r68unif CtlGen (events, slo, alloc_vm, per tick) on t1..t12 x {S4b, S4a, S4'2, S4'05} and 20 seeded library traces;
2) per-tick dumps of the (d) runs (same format as eqdump.py) -> out/replay_d (for the Go replay: how close (d) is to the daemon);
3) (d) predictions of every §4.139 registered cell: S4' and S4 at both points on t4/t6/t8, S4' 2 % and S4b on t11/t12 (baselines have no (d)
   flags -> (d) = (a)). Output out/dver.json."""
import timeit  # noqa
import sys, os, json, random
Q='/home/user/experiment/qsim'; R=f'{Q}/r72hw'; E='/home/user/experiment'
for p in (Q,Q+'/r67band',Q+'/r68unif',Q+'/s7',R,Q+'/r71fin'): sys.path.insert(0,p)
os.chdir(Q)
import v8sim11 as V, s7core as C7, ctlgen as CG, ctlgen_d as CD, run as RB, eqdump as EQ, fine as F
cfg,pr=V.cfg_prior(); S7P=C7.S7Prior(RB.LIB,cfg)
CF={"S4b":((1.83,2.00),{}),"S4a":((2.83,3.08),{}),"S4p2":((1.5,1.92),dict(indep=True,indep_rel=True,w=1600)),"S4p05":((2.33,3.33),dict(indep=True,indep_rel=True,w=1600))}
DFL=dict(excl_left=True,quant_d=True,no_serial=True)
def ctl(name,mod,extra):
    (a,b),fl=CF[name]; L={"vy":a,"wk":a,"up":b}; pri=S7P if fl else pr
    return (CG.CtlGen(cfg,pri,L,**fl) if mod=="g" else CD.CtlGen(cfg,pri,L,**fl,**extra)),L
def run(ue,name,mod,extra,record=False):
    c,L=ctl(name,mod,extra); st=V.initial_fleet("S",ue[0],L=L); ph=V.Phys(ue,start=st,p=RB.PH); intents=[]; ticks=[]; d5=[]
    if record:
        for m,lab in EQ.NAMES.items():
            f=getattr(ph,m)
            def w(*a,_f=f,_lab=lab,**k):
                r=_f(*a,**k); intents.append([_lab, r if isinstance(r,bool) else r[0]]); return r
            setattr(ph,m,w)
    for _ in range(3600//V.DT):
        ph.advance_units()
        if ph.t%V.TICK==0:
            ob=ph.observe(); i=ob["idle_wk"]
            rec=dict(t=ph.t,D=ob["D"],rep_up=ob["rep_up"],ready_up=ob["ready_up"],drain_up=ob["drain_up"],vy_vm=ob["vy_vm"],vy_adm=ob["vy_adm"],wk_vm=ob["wk_vm"],wk_ready=ob["wk_ready"],
                     idle=bool(i is not None and ph.t-ph.workers[i]["ready"]>=600),idle_any=i is not None)
            intents.clear(); n0=len(ph.events)
            d=c.tick(ph,ob); ph.hot_relief(getattr(ph,"_over",{}))
            if not d and ph.t-ph.last_pool_relief>=ph.p["pool_relief_s"]: ph.enqueue_pool_relief(); ph.last_pool_relief=ph.t
            rec["intents"]=[list(x) for x in intents]; rec["executed"]=[[e[1],e[2]] for e in ph.events[n0:] if e[1] in ("out","in","cancel-drain")]; ticks.append(rec)
        d5.append(ph.D()); ph.step()
    r=ph.result()
    return dict(name=name,L=L,start=list(st),ticks=ticks,d5=d5,res=F.row(r),events=[[e[0],e[1],e[2]] for e in r['events']])
if __name__=="__main__":
    out=dict(equiv={},pred={})
    ok=True
    cases=[(tn,json.load(open(f"{E}/trace_ue_60min_v3_{f}.json"))["ue"][:60]) for tn,f in EQ.TR.items()]
    cases+= [(f"lib{i}",RB.LIB[i]["ue"][:60]) for i in random.Random(20261028).sample(range(len(RB.LIB)),20)]
    for name in CF:
        for tn,ue in cases:
            a=run(ue,name,"g",{}); b=run(ue,name,"d",{})
            same=(a['events'],a['res'])==(b['events'],b['res']); ok&=same
            if not same: print("EQUIV FAIL",name,tn,flush=True)
    out["equiv"]["flags_off_vs_CtlGen"]=dict(cases=len(CF)*len(cases),all_same=ok); print("equiv flags off == CtlGen:",ok,flush=True)
    for name in CF:
        for tn,ue in cases[:12]:
            d=run(ue,name,"d",DFL,record=True); d['trace']=tn; d['name']=name
            json.dump(d,open(f"{R}/out/replay_d/{name}_{tn}.json","w"))
            if tn in ("t4","t6","t8","t11","t12"):
                out["pred"][f"{tn}|{name}"]=d['res']; print(tn,name,d['res']['alloc_vm'],d['res']['viol'],d['res']['flaps'],d['res']['acts'],flush=True)
    json.dump(out,open(f"{R}/out/dver.json","w"),indent=1); print("DONE")
