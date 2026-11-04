#!/usr/bin/env python3
"""(docstring removed)"""
import json, math, sys, random
import numpy as np
import qsim, cv, cv2, cv3
from qsim import HS, expand, oracle_alloc
random.seed(11)
lib=json.load(open("prior_traces.json"))
NT=int(sys.argv[1]) if len(sys.argv)>1 else 150
WIN=int(sys.argv[2]) if len(sys.argv)>2 else 60
test=random.sample(lib,NT)
def prior_of(trs):
    p={h:[] for h in HS}
    for tr in trs:
        d=expand(tr["ue"])
        for h in HS: p[h]+=cv.samples(d,h)
    return p
by_loc={}
for t in lib: by_loc.setdefault(t["loc"],[]).append(t)
agg={}
def add(key,r,fl,n=None):
    a=agg.setdefault(key,dict(slo=[],full=[],over=[],flaps=[],lost=[],n=[]))
    a["slo"].append(r["slo"]); a["full"].append(r["slo"]==60); a["over"].append(100*(r["alloc"]-fl)/fl); a["flaps"].append(r["flaps"]); a["lost"].append(r["lost"]); a["n"].append(n or 0)
pooled_cache={}
for k,tr in enumerate(test):
    ue=tr["ue"]; fl=oracle_alloc(ue,5)
    site=[t for t in by_loc[tr["loc"]] if t["date"]!=tr["date"] and abs(t["start"]-tr["start"])<=WIN]
    if tr["loc"] not in pooled_cache:
        pooled_cache[tr["loc"]]=cv2.Prior2(prior_of([t for t in lib if t["loc"]!=tr["loc"]]),8.0)
    Pp=pooled_cache[tr["loc"]]
    if len(site)<6: continue
    Ps=cv2.Prior2(prior_of(site),8.0)
    for b in (5.0,8.0): add((f"M0 batch{b:.0f}",None),cv3.simulate(ue,None,None,batch=b),fl)
    for e in (0.1,0.05,0.02):
        for name,P in (("pooled",Pp),("site+tod",Ps)):
            for adapt in ("aci","none"):
                q=cv2.QM(P,e,scale="rel",adapt=adapt); add((f"{name} {adapt}",e),cv3.simulate(ue,q,q,inmode="w"),fl,len(site))
    if k%25==0: print("done",k,file=sys.stderr)
print(f"site window ±{WIN} min; test traces used: {len(agg[('M0 batch5',None)]['slo'])}; site prior traces median {np.median(agg[('site+tod aci',0.05)]['n']):.0f}")
print(f"{'prior':18s} {'eps':>5s} | {'SLO':>6s} {'P60':>5s} {'over%':>6s} {'flaps':>5s} {'lostM':>6s}")
for (n_,e),a in agg.items():
    print(f"{n_:18s} {str(e) if e else '':>5s} | {np.mean(a['slo']):6.2f} {np.mean(a['full']):5.2f} {np.mean(a['over']):+6.1f} {np.mean(a['flaps']):5.2f} {np.mean(a['lost']):6.1f}")
