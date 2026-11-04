#!/usr/bin/env python3
"""spec §4.138 item 2: start-fleet audit.
I1: hardware minute-0 fleet (slots: rq_metrics.daemon kube_pod_info; VyOS / workers: trace CSV row 0) for every listed hardware run vs the simulator
initial_fleet of the arm / knob. I2: registered-version predictions (per-slot v8sim11 default PHYS = R38 on; fleet nest2 / sim_v6 / sim_b6) with the own
start (original) and with the hardware start (new; mean over the cell's runs), against hardware alloc_vm (rq_metrics.metrics mean).
HPA prefill: CtlB4P (v8sim11.CtlB4 + prefill of the stabilization window with 20 samples at -600..-30 s equal to the start slot count).
Equivalence: prefill off == v8sim11.CtlB4 (20 library traces x B4c2, B5c1, R38 off); fleet start patches with start=None == frozen sim_v6 / sim_b6 on t3..t8.
Output out/audit.json"""
import timeit  # noqa
import sys, os, json, csv, io, contextlib, random, math, inspect, textwrap, numpy as np
Q='/home/user/experiment/qsim'; R=f'{Q}/r70eq'; E='/home/user/experiment'; P2=f'{E}/p2'
for p in (Q,Q+'/r67band','/home/user/experiment/paper_out_new'): sys.path.insert(0,p)
os.chdir(Q)
import v8sim11 as V, v8sim2 as S, v8sim7 as M, v8sim_b6 as B, v8sim10_abl as A, run as RB
with contextlib.redirect_stdout(io.StringIO()):
    import rq_metrics as RQ
LIB=RB.LIB; cfgM=M.cfg_measured(); MK=B.load_models(); cfgV,prV=V.cfg_prior()
# ---- fleet start patches (checked text patch; start=None -> frozen code)
def patch(fn,name,anchor,ins):
    src=textwrap.dedent(inspect.getsource(fn)); assert src.count(anchor)==1, name
    head=src.split("\n",1)[0]; args=head[head.index("(")+1:head.rindex(")")]
    src=src.replace(head,f"def {name}({args}, start=None):",1).replace(anchor,anchor+ins,1); g=dict(vars(sys.modules[fn.__module__])); exec(src,g); return g[name]
sim_v6s=patch(S.sim_v6,"sim_v6s",'cur={k:cfg.need(k,d[0]+b) for k in cfg.h}; cur["wk"]=max(cur["wk"],math.ceil(cur["up"]/cfg.spw))',
              '\n    if start: cur={"up":int(start[0]),"vy":int(start[1]),"wk":int(start[2])}')
sim_b6s=patch(B.sim_b6,"sim_b6s",'cur = {k: cfg.need(k, d[0]) for k in cfg.h}; cur["wk"] = max(cur["wk"], math.ceil(cur["up"] / cfg.spw))',
              '\n    if start: cur = {"up": int(start[0]), "vy": int(start[1]), "wk": int(start[2])}')
# ---- HPA prefill controller
class CtlB4P(V.CtlB4):
    def __init__(s,*a,prefill=False,**k): super().__init__(*a,**k); s.prefill=prefill; s._pf=False
    def tick(s,ph,ob):
        if s.prefill and not s._pf:
            s._pf=True; n=ob["ready_up"]; s.hpa.hist=[(ph.t-600+30*j,n) for j in range(20)]
        return super().tick(ph,ob)
def b4ctl(arm,prefill):
    return CtlB4P(predictive=False,mu=12.0,target=3.5,prefill=prefill) if arm=="B4c2" else CtlB4P(predictive=True,mu=14.0,target=4.0,prefill=prefill)
# ---- cells
TRF={"t1":"40","t2":"pm","t3":"t3","t4":"t4","t5":"t5","t6":"t6","t7":"t7","t8":"t8"}
CELLS=[("t1","S4a",["r249","r253","r259","r263"]),("t1","S4b",["r251","r255","r261"]),("t1","B4c2",["r272"]),("t1","B5c1",["r274"]),("t1","B6",["r285"]),
       ("t2","S4a",["r250","r254","r260"]),("t2","S4b",["r252","r256","r262"]),("t2","B4c2",["r276"]),("t2","B5c1",["r278","r287"]),("t2","B6",["r286"]),
       ("t8","S4a",["r471","r478"]),("t8","S4b",["r476","r500"]),("t8","v6",["r475","r479"]),("t8","B6",["r474","r504"]),
       ("t3","B6_0.775",["r493","r505"]),("t6","B6_0.775",["r498","r499"])]
GMAP={"S4a":"S4a","S4b":"S4b","v6":"v6","B4c2":"B4c2","B5c1":"B5c1","B6":"B6 u=0.70","B1":"B1"}
for g,t,rs in RQ.GROUPS:
    if g.startswith("MAIN t") and 'VOID' not in g and 'r302' not in g and 'confirm' not in g:
        tn=g.split()[1]; arm=g.split()[2]
        if arm in GMAP: CELLS.append((tn,arm,rs))
def hw_start(run):
    rows=list(csv.DictReader(open(f'{P2}/trace_v7_{run}.csv')))
    with contextlib.redirect_stdout(io.StringIO()):
        eupf,_=RQ.daemon(run)
    return (int(round(eupf[0])),int(rows[0]['vyos_n']),int(rows[0]['worker_n']))
def hw_cost(run,tn):
    with contextlib.redirect_stdout(io.StringIO()):
        m=RQ.metrics(run,f"trace_ue_60min_v3_{TRF[tn]}.json")
    return float(m['alloc_vm'])
def kw(arm): return dict(u=0.775) if arm=="B6_0.775" else (dict(u=0.70) if arm=="B6" else {})
def vname(arm): return "B6" if arm.startswith("B6") else arm
def ps_pred(arm,ue,start,phys=None,prefill=False):
    if arm in ("B4c2","B5c1"):
        st=start or V.initial_fleet(arm,ue[0]); ph=V.Phys(ue,start=st,p=phys); ctl=b4ctl(arm,prefill)
        for _ in range(3600//V.DT):
            ph.advance_units()
            if ph.t%V.TICK==0:
                ob=ph.observe(); d=ctl.tick(ph,ob); ph.hot_relief(getattr(ph,"_over",{}))
                if not d and ph.t-ph.last_pool_relief>=ph.p["pool_relief_s"]: ph.enqueue_pool_relief(); ph.last_pool_relief=ph.t
            ph.step()
        return ph.result()['alloc_vm']
    if arm=="B1": return 1464.0
    return V.run(ue,vname(arm),start=start,phys=phys,**kw(arm))['alloc_vm']
LAM={"S4a":{"vy":2.83,"wk":2.83,"up":3.08},"S4b":{"vy":1.83,"wk":1.83,"up":2.00}}
def fl_pred(arm,ue,start):
    if arm in LAM: return A.sim_nest2(ue,cfgM,prV,LAM[arm],acct='vmexist',start=start)['alloc']
    if arm=="v6": return sim_v6s(ue,cfgM,start=start)['alloc']
    if arm.startswith("B6"): return sim_b6s(ue,cfgM,kw(arm)['u'],MK,start=start)['alloc']
    return None
def sim_start(arm,ue):
    if arm=="B1": return (8,3,4)
    return tuple(int(x) for x in V.initial_fleet(vname(arm),ue[0],**kw(arm)))
if __name__=="__main__":
    out=dict(equiv={},I1=[],I2=[],prefill=[])
    idx=random.Random(20261027).sample(range(len(LIB)),20); ok=True
    for arm in ("B4c2","B5c1"):
        for i in idx:
            ue=LIB[i]["ue"][:60]; a=RB.run_ctl(ue,V.CtlB4(predictive=(arm=="B5c1"),mu=14.0 if arm=="B5c1" else 12.0,target=4.0 if arm=="B5c1" else 3.5),V.initial_fleet(arm,ue[0]))
            b=RB.run_ctl(ue,b4ctl(arm,False),V.initial_fleet(arm,ue[0])); ok&=(a['slo'],a['alloc_vm'],a['events'])==(b['slo'],b['alloc_vm'],b['events'])
    ok2=True
    for tn in ("t3","t4","t6","t7","t8"):
        ue=json.load(open(f"{E}/trace_ue_60min_v3_{tn}.json"))["ue"][:60]
        x,y=S.sim_v6(ue,cfgM),sim_v6s(ue,cfgM); ok2&=(x['slo'],x['alloc'],x['flaps'])==(y['slo'],y['alloc'],y['flaps'])
        x,y=B.sim_b6(ue,cfgM,0.70,MK),sim_b6s(ue,cfgM,0.70,MK); ok2&=(x['slo'],x['alloc'],x['flaps'])==(y['slo'],y['alloc'],y['flaps'])
    out['equiv']=dict(prefill_off_vs_CtlB4=ok,fleet_patches_vs_frozen=ok2); print(out['equiv'],flush=True)
    for tn,arm,runs in CELLS:
        ue=json.load(open(f"{E}/trace_ue_60min_v3_{TRF[tn]}.json"))["ue"][:60]; ss=sim_start(arm,ue); hs={}; hc={}
        for r in runs:
            try: hs[r]=hw_start(r); hc[r]=hw_cost(r,tn)
            except Exception as e: print("skip",r,e,flush=True)
        for r in hs: out['I1'].append(dict(trace=tn,arm=arm,run=r,hw=hs[r],sim=ss,same=tuple(hs[r])==ss))
        if not hs or arm=="B1": continue
        o_ps=ps_pred(arm,ue,None); n_ps=float(np.mean([ps_pred(arm,ue,hs[r]) for r in hs]))
        o_fl=fl_pred(arm,ue,None); n_fl=(float(np.mean([fl_pred(arm,ue,hs[r]) for r in hs])) if o_fl is not None else None)
        hw=float(np.mean(list(hc.values())))
        out['I2'].append(dict(trace=tn,arm=arm,runs=list(hs),hw=hw,ps_orig=o_ps,ps_new=n_ps,fl_orig=o_fl,fl_new=n_fl))
        if arm in ("B4c2","B5c1"):
            pf=float(np.mean([ps_pred(arm,ue,hs[r],prefill=True) for r in hs])); pf_off=float(np.mean([ps_pred(arm,ue,hs[r],phys=RB.PH,prefill=True) for r in hs]))
            out['prefill'].append(dict(trace=tn,arm=arm,hw=hw,ps_orig=o_ps,ps_hwstart=n_ps,ps_hwstart_prefill=pf,ps_hwstart_prefill_r38off=pf_off))
        print(tn,arm,list(hs.values())[:1],ss,f"hw {hw:.1f} ps {o_ps:.1f}->{n_ps:.1f} fl {o_fl}->{n_fl}",flush=True)
    json.dump(out,open(f'{R}/out/audit.json','w'),indent=1,default=str)
