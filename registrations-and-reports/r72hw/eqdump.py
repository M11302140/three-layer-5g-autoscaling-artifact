#!/usr/bin/env python3
"""spec §4.140 A: per-tick input dump for the Go decision-equivalence replay (S4' daemon vs v8sim11 R38-off CtlGen).
For t1..t12 x configs, runs the r67band runner (v8sim11 Phys, PH = knee38 5, own initial_fleet) with the arm's controller, the Phys instance's
actuators wrapped to record intents (call + result); per tick: pre-decision observation, idle-worker eligibility, intents, executed events.
The wrapped run must reproduce the unwrapped run exactly (slo, alloc_vm, events) -> checked per case. Output out/replay/<cfg>_<tn>.json."""
import timeit  # noqa
import sys, os, json
Q='/home/user/experiment/qsim'; R=f'{Q}/r72hw'; E='/home/user/experiment'
for p in (Q,Q+'/r67band',Q+'/r68unif',Q+'/s7'): sys.path.insert(0,p)
os.chdir(Q)
import v8sim11 as V, s7core as C7, ctlgen as CG, run as RB
TR={"t1":"40","t2":"pm",**{f"t{i}":f"t{i}" for i in range(3,13)}}
CFGS={"S4b":((1.83,2.00),None),"S4a":((2.83,3.08),None),"S4p2":((1.5,1.92),dict(indep=True,indep_rel=True,w=1600)),"S4p05":((2.33,3.33),dict(indep=True,indep_rel=True,w=1600))}
cfg,pr=V.cfg_prior(); S7P=None
def ctl_of(name):
    global S7P
    (a,b),fl=CFGS[name]; L={"vy":a,"wk":a,"up":b}
    if fl is None: return V.CtlSigma(cfg,pr,L),L
    if S7P is None: S7P=C7.S7Prior(RB.LIB,cfg)
    return CG.CtlGen(cfg,S7P,L,**fl),L
NAMES={"scale_out_up":"SCALE_OUT_UP","cancel_drain":"CANCEL_DRAIN","deploy_vy":"DEPLOY_VYOS","create_wk":"CREATE_WORKER","scale_in_up":"SCALE_IN_UP","delete_vy":"DELETE_VYOS","delete_wk":"DELETE_WORKER"}
def run(ue,name,record):
    ctl,L=ctl_of(name); st=V.initial_fleet("S",ue[0],L=L); ph=V.Phys(ue,start=st,p=RB.PH); intents=[]
    if record:
        for m,lab in NAMES.items():
            f=getattr(ph,m)
            def w(*a,_f=f,_lab=lab,**k):
                r=_f(*a,**k); intents.append([_lab, r if isinstance(r,bool) else r[0]]); return r
            setattr(ph,m,w)
    ticks=[]; d5=[]
    for _ in range(3600//V.DT):
        ph.advance_units()
        if ph.t%V.TICK==0:
            ob=ph.observe(); i=ob["idle_wk"]
            idle_ok=(i is not None and ph.t-ph.workers[i]["ready"]>=600)
            rec=dict(t=ph.t,D=ob["D"],rep_up=ob["rep_up"],ready_up=ob["ready_up"],drain_up=ob["drain_up"],vy_vm=ob["vy_vm"],vy_adm=ob["vy_adm"],
                     wk_vm=ob["wk_vm"],wk_ready=ob["wk_ready"],idle=bool(idle_ok),idle_any=i is not None)
            intents.clear(); n0=len(ph.events)
            d=ctl.tick(ph,ob); ph.hot_relief(getattr(ph,"_over",{}))
            if not d and ph.t-ph.last_pool_relief>=ph.p["pool_relief_s"]: ph.enqueue_pool_relief(); ph.last_pool_relief=ph.t
            rec["intents"]=[list(x) for x in intents]; rec["executed"]=[[e[1],e[2]] for e in ph.events[n0:] if e[1] in ("out","in","cancel-drain")]
            ticks.append(rec)
        d5.append(ph.D())
        ph.step()
    r=ph.result()
    return dict(name=name,L=L,start=list(st),ticks=ticks,d5=d5,slo=int(r['slo']),alloc_vm=r['alloc_vm'],events=[[e[0],e[1],e[2]] for e in r['events']])
if __name__=="__main__":
    ok=True
    for name in CFGS:
        for tn,f in TR.items():
            ue=json.load(open(f"{E}/trace_ue_60min_v3_{f}.json"))["ue"][:60]
            a=run(ue,name,True); b=run(ue,name,False)
            same=(a['slo'],a['alloc_vm'],a['events'])==(b['slo'],b['alloc_vm'],b['events']); ok&=same
            a['wrap_equiv']=same; a['trace']=tn; json.dump(a,open(f"{R}/out/replay/{name}_{tn}.json","w"))
            print(name,tn,"slo",a['slo'],"alloc",round(a['alloc_vm'],1),"ticks",len(a['ticks']),"intents",sum(len(x['intents']) for x in a['ticks']),"wrap_equiv",same,flush=True)
    print("ALL WRAP EQUIV",ok)
