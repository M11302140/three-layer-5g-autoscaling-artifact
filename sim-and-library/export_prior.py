#!/usr/bin/env python3
"""(docstring removed)"""
import json, numpy as np
from qsim import expand, DT
LMIN=8.0; GRID=15; HMAX=420; Q=0.005
lib=json.load(open("prior_traces.json"))
out={"lmin_ue":LMIN,"grid_sec":GRID,"quant":Q,"n_traces":len(lib),
     "source":"Melbourne Pedestrian Counting System per-minute, same pipeline as evaluation traces; loc-days of traces 1-5 excluded (experiment/qsim/make_prior.py)",
     "horizons":{}}
D=[expand(t["ue"]) for t in lib]
for h in range(GRID,HMAX+1,GRID):
    k=h//DT; vals=[]
    for d in D:
        for i in range(0,len(d)-k,30//DT):
            vals.append((d[i+1:i+k+1].max()-d[i])/max(d[i],LMIN))
    v=np.round(np.array(vals)/Q)*Q
    u,c=np.unique(np.round(v,4),return_counts=True)
    out["horizons"][str(h)]={"v":[float(x) for x in u],"c":[int(x) for x in np.cumsum(c)]}
json.dump(out,open("/home/user/hhro-daemon/internal/hbo/prior_rise.json","w"))

exp=[]
for h in (45,115,145,165,205):
    hh=out["horizons"][str(((h+GRID-1)//GRID)*GRID)]; u=np.array(hh["v"]); c=np.array(hh["c"])
    for eps in (0.2,0.1,0.05,0.02,0.01):
        k=int(np.ceil((1-eps)*c[-1])); i=int(np.searchsorted(c,k,side="left"))
        for lvl in (5.0,20.0,32.0):
            exp.append(dict(h=h,eps=eps,level_ue=lvl,margin_ue=float(u[i]*max(lvl,LMIN))))
json.dump(exp,open("/home/user/hhro-daemon/internal/hbo/testdata_rise_expect.json","w"))
import os; print("prior bytes",os.path.getsize("/home/user/hhro-daemon/internal/hbo/prior_rise.json"),"uniq@45",len(out["horizons"]["45"]["v"]))
print([ (e["h"],e["eps"],round(e["margin_ue"],2)) for e in exp if e["level_ue"]==20.0 and e["eps"] in (0.05,0.02)])
