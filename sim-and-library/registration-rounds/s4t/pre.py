#!/usr/bin/env python3
"""qsim/s4t/pre.py (spec §4.133 item 2, record only; used by G-sim): deployed lambda (S4b 1.83/2.00, S4a 2.83/3.08), k3 in {None, 4, 5, 6}.
(1) six splits (grouped_split 0-5), split prior (v8sim2.Prior of the calibration groups), all held-out traces, nest2 sim_s4t: risk, vmexist,
    dispatch, flaps (AB.trace_metrics), R3 triggers per trace; paired against k3 = None.
(2) t3-t8 (and t1/t2) predictions, fleet (vmexist) and per-slot (run_s4t, whole-library prior). Output s4t/out/pre.txt / pre.json"""
import os, sys, json, time, numpy as np
Q="/home/user/experiment/qsim"; sys.path.insert(0,Q); sys.path.insert(0,Q+"/s4t"); os.chdir(Q)
_argv=sys.argv; sys.argv=[sys.argv[0]]
import v8sim10_ablation as AB
sys.argv=_argv
import v8sim2 as S, v8sim11 as V, s4tcore as C, v8sim11_s4t as W
from v8sim3 import grouped_split
from concurrent.futures import ProcessPoolExecutor
lib=AB.lib; cfg=AB.cfg; E='/home/user/experiment'
LAM={"S4b":{"vy":1.83,"wk":1.83,"up":2.00},"S4a":{"vy":2.83,"wk":2.83,"up":3.08}}; KS=(None,4,5,6)
TR={'t1':'40','t2':'pm','t3':'t3','t4':'t4','t5':'t5','t6':'t6','t7':'t7','t8':'t8'}
def job(seed):
    c,h=grouped_split(seed); pr=S.Prior([lib[i] for i in c],cfg); out={}
    for arm,L in LAM.items():
        for k in KS:
            ms=[]; trig=[]
            for i in h:
                r=C.sim_s4t(lib[i]["ue"][:60],cfg,pr,L,k3=k,acct="vmexist"); m=AB.trace_metrics(r); trig.append(sum(1 for e in r['ev'] if e[1]=="r3"))
                m["alloc_dispatch"]=C.sim_s4t(lib[i]["ue"][:60],cfg,pr,L,k3=k,acct="dispatch")["alloc"]; ms.append(m)
            out[f"{arm}|{k}"]={**{x:float(np.mean([m[x] for m in ms])) for x in ('risk','alloc','alloc_dispatch','flaps')},'trig_per_trace':float(np.mean(trig)),'traces_with_trig':int(sum(1 for t in trig if t>0)),'n':len(h)}
    return seed,out
if __name__=="__main__":
    t0=time.time(); lines=[]
    def P(s): print(s,flush=True); lines.append(s)
    with ProcessPoolExecutor(int(sys.argv[1]) if len(sys.argv)>1 else 4) as pool: res=dict(pool.map(job,range(6)))
    P("| arm | k | risk | Δ risk (pp) | vmexist | Δ vmexist | dispatch | flaps | R3 triggers / trace | traces with a trigger (of 638 per split, mean) |\n|---|---|---|---|---|---|---|---|---|---|")
    agg={}
    for arm in LAM:
        for k in KS:
            m=lambda x: float(np.mean([res[s][f"{arm}|{k}"][x] for s in range(6)])); agg[f"{arm}|{k}"]={x:m(x) for x in ('risk','alloc','alloc_dispatch','flaps','trig_per_trace','traces_with_trig')}
        b=agg[f"{arm}|None"]
        for k in KS:
            a=agg[f"{arm}|{k}"]; P(f"| {arm} | {k} | {a['risk']:.4f} | {100*(a['risk']-b['risk']):+.3f} | {a['alloc']:.1f} | {100*(a['alloc']/b['alloc']-1):+.2f} % | {a['alloc_dispatch']:.1f} | {a['flaps']:.2f} | {a['trig_per_trace']:.3f} | {a['traces_with_trig']:.1f} |")
    V.cfg_prior(); _,gpr=V.cfg_prior(); pred={}
    P("\n| trace | arm | k | fleet SLO | fleet vmexist | per-slot SLO | per-slot viol | per-slot cost | per-slot R3 triggers (s) |\n|---|---|---|---|---|---|---|---|---|")
    for tn,fn in TR.items():
        ue=json.load(open(f"{E}/trace_ue_60min_v3_{fn}.json"))["ue"][:60]
        for arm,L in LAM.items():
            for k in KS:
                rv=C.sim_s4t(ue,cfg,gpr,L,k3=k,acct="vmexist"); rs=W.run_s4t(ue,L,k3=k,prior=gpr)
                pred[f"{tn}|{arm}|{k}"]=dict(fl_slo=rv['slo'],fl_cost=rv['alloc'],ps_slo=rs['slo'],ps_viol=rs['viol'],ps_cost=rs['alloc_vm'],ps_r3=rs['r3'])
                P(f"| {tn} | {arm} | {k} | {rv['slo']}/60 | {rv['alloc']:.0f} | {rs['slo']}/60 | {rs['viol']} | {rs['alloc_vm']:.0f} | {rs['r3']} |")
    P(f"\ntime {time.time()-t0:.0f}s")
    json.dump(dict(splits=res,agg=agg,pred=pred),open(f"{Q}/s4t/out/pre.json","w"),indent=1,default=lambda o: o.item() if hasattr(o,"item") else str(o)); open(f"{Q}/s4t/out/pre.txt","w").write("\n".join(lines)+"\n")
