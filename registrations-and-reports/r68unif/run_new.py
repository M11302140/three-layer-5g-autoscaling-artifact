#!/usr/bin/env python3
"""spec §4.136 items 3-4: deployed lambda (six-split mean of out/cal.jsonl, rounded 0.01) for A-PL and S4' at 2 % and 0.5 %, whole-library per-slot
(v8sim11, R38 off, r67band runner) with CtlGen; rows in the r67band format -> out/<APL_2|APL_05|S4p_2|S4p_05>.json; also t4/t8/t6/t7 predictions
(per-slot and nest2) -> out/new_traces.json"""
import timeit  # noqa
import sys, os, json, numpy as np
Q='/home/user/experiment/qsim'; R=f'{Q}/r68unif'; sys.path.insert(0,Q); sys.path.insert(0,R); sys.path.insert(0,Q+'/s7'); sys.path.insert(0,Q+'/r67band'); os.chdir(Q)
import v8sim11 as V, v8sim7 as M, s7core as C7, nest2gen as G, ctlgen as CG, run as RB
from concurrent.futures import ProcessPoolExecutor
LIB=RB.LIB; E='/home/user/experiment'
cal=[json.loads(l) for l in open(f'{R}/out/cal.jsonl')]
DEP={}
for arm,flags,w in (("APL",dict(indep=True,indep_rel=True,plain=True),None),("S4p",dict(indep=True,indep_rel=True,plain=False),1600)):
    for tg,tn in ((0.02,"2"),(0.005,"05")):
        rs=[r for r in cal if r['arm']==arm and r['target']==tg]
        DEP[f"{arm}_{tn}"]=dict(a=round(float(np.mean([r['a'] for r in rs])),2),b=round(float(np.mean([r['b'] for r in rs])),2),flags=flags,w=w,n=len(rs),inf=sum(r['infeasible'] for r in rs))
_P={}
def prior(w):
    if w not in _P:
        cfg,pr=V.cfg_prior(); _P[w]=C7.S7Prior(LIB,cfg) if w is not None else pr
    return _P[w]
def one(args):
    name,i,ue=args; d=DEP[name]; cfg,_=V.cfg_prior(); L={"vy":d['a'],"wk":d['a'],"up":d['b']}
    if ue is None: ue=LIB[i]["ue"][:60]
    r=RB.run_ctl(ue,CG.CtlGen(cfg,prior(d['w']),L,w=d['w'],**d['flags']),V.initial_fleet("S",ue[0],L=L)); ab=r['alloc_by']
    return i,dict(slo=int(r['slo']),viol=[int(x) for x in r['viol']],alloc_vm=r['alloc_vm'],wk_core=ab['wk'],vy_core=ab['vy'],up_core=ab['up'],wk_min=ab['wk']/3.0,vy_min=ab['vy']/2.0,slot_min=ab['up']/0.8,flaps=int(RB.flaps(r['events'])))
if __name__=="__main__":
    json.dump(DEP,open(f'{R}/out/deployed.json','w'),indent=1); print(DEP,flush=True)
    with ProcessPoolExecutor(2) as pool:
        for name in DEP:
            res=dict(pool.map(one,[(name,i,None) for i in range(len(LIB))],chunksize=8))
            json.dump(dict(name=name,dep=DEP[name],phys=RB.PH,rows=[res[i] for i in range(len(LIB))]),open(f'{R}/out/{name}.json','w')); print("done",name,flush=True)
    TT={"t3":"t3","t4":"t4","t6":"t6","t7":"t7","t8":"t8"}; cfgM=M.cfg_measured(); out={}
    for tn,f in TT.items():
        ue=json.load(open(f"{E}/trace_ue_60min_v3_{f}.json"))["ue"][:60]
        for name,d in DEP.items():
            _,ps=one((name,-1,ue)); L={"vy":d['a'],"wk":d['a'],"up":d['b']}
            var="apl" if name.startswith("APL") else "independent_full"
            fl=G.sim_s7(ue,cfgM,prior(d['w']),L,variant=var,w=d['w'],acct='vmexist')
            out[f"{tn}|{name}"]=dict(ps=ps,fl=dict(slo=int(fl['slo']),alloc=fl['alloc']))
        for name,L in (("S4b",{"vy":1.83,"wk":1.83,"up":2.00}),("S4a",{"vy":2.83,"wk":2.83,"up":3.08})):
            fl=G.sim_s7(ue,cfgM,prior(None),L,acct='vmexist'); ctl,st=RB.make('S2',(L['vy'],L['up']),ue); r=RB.run_ctl(ue,ctl,st)
            out[f"{tn}|{name}"]=dict(fl=dict(slo=int(fl['slo']),alloc=fl['alloc']),ps=dict(slo=int(r['slo']),viol=[int(x) for x in r['viol']],alloc_vm=r['alloc_vm']))
    json.dump(out,open(f'{R}/out/new_traces.json','w'),indent=1); print("traces done")
