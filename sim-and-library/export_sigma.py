#!/usr/bin/env python3
"""(docstring removed)"""
import json, numpy as np, os
from v8sim2 import expand, DT
G=30; GRID=5; HMAX=420; BUCKET=10; NMIN=30
lib=json.load(open("prior_traces.json"))
D=[expand(t["ue"]) for t in lib]
def table(kind,H):
    byb={}; allv=[]
    kH=H//DT; k0=max(0,(H-G)//DT)
    for d in D:
        for i in range(0,len(d)-kH,G//DT):
            r=max(0.0,(d[i+k0:i+kH+1].max() if kind=="win" else d[i+1:i+kH+1].max())-d[i])
            byb.setdefault(int(d[i]//BUCKET),[]).append(r); allv.append(r)
    nb=max(byb)+1
    return {"all":float(np.std(allv)),"n":len(allv),"b":[(float(np.std(byb[b])) if b in byb and len(byb[b])>=NMIN else None) for b in range(nb)]}
out={"ue_pps":250000.0,"bucket_ue":BUCKET,"grid_sec":GRID,"g_sec":G,"n_traces":len(lib),
     "source":"same library as prior_rise.json (experiment/qsim/make_prior.py; evaluation loc-days excluded); definition = experiment/qsim/v8sim2.Prior",
     "win":{str(H):table("win",H) for H in range(GRID,HMAX+1,GRID)},
     "run":{str(W):table("run",W) for W in range(GRID,HMAX+1,GRID)}}
json.dump(out,open("/home/user/hhro-daemon/internal/hbo/prior_sigma.json","w"))

exp=[]
for kind,H in (("win",45),("win",115),("win",145),("run",45),("run",115),("run",145),("run",205)):
    t=out[kind][str(H)]
    for lvl in (5.0,12.0,20.0,32.0):

        val=lambda b: (t["b"][b] if 0<=b<len(t["b"]) and t["b"][b] is not None else t["all"])
        n=len(t["b"]); x=lvl/BUCKET-0.5
        if n==0: s=t["all"]
        elif x<=0: s=val(0)
        elif x>=n-1: s=val(n-1)
        else:
            b0=int(np.floor(x)); fr=x-b0; s=(1-fr)*val(b0)+fr*val(b0+1)
        exp.append(dict(kind=kind,h=H,level_ue=lvl,sigma_ue=s))
json.dump(exp,open("/home/user/hhro-daemon/internal/hbo/testdata/sigma_expect.json","w"),indent=0)
print("bytes",os.path.getsize("/home/user/hhro-daemon/internal/hbo/prior_sigma.json"))
for kind,H in (("win",45),("win",115),("win",145),("run",45),("run",115),("run",145)):
    t=out[kind][str(H)]; print(kind,H,"all %.2f"%t["all"],"buckets",[None if x is None else round(x,2) for x in t["b"]])

import v8sim2 as S
cfg=S.Cfg(); pr=S.Prior(lib,cfg)
for k,H,W in (("up",45,45),("vy",115,115),("wk",145,145)):
    for Dv in (5,12,20,32): print(f"  check {k} D={Dv}: Prior win {pr.sigma('win',k,Dv):.3f} vs export {out['win'][str(H)]['b'][Dv//10] or out['win'][str(H)]['all']:.3f} | run {pr.sigma('run',k,Dv):.3f} vs {out['run'][str(W)]['b'][Dv//10] or out['run'][str(W)]['all']:.3f}")
