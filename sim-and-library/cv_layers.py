#!/usr/bin/env python3
"""(docstring removed)"""
import json, sys, random, itertools
import numpy as np
import cv, qsim
from qsim import HS, expand, oracle_alloc
LAYER_OF={45:"up",165:"up",115:"vy",145:"wk",205:"wk"}
class QL(cv.QModel):
    def __init__(s,P,epsl,**kw):
        super().__init__(P,0.05,**kw); s.epsl=epsl
        s.alpha={h:epsl[LAYER_OF[h]] for h in HS}
    def margin(s,h,level,c):
        e=s.epsl[LAYER_OF[h]]; s.amin=e/4; return super().margin(h,level,c)
    def tick(s,t,d,i):

        c=cv.ctx_of(d,i)
        for h in HS:
            e_t=s.epsl[LAYER_OF[h]]; g=max(0.005,e_t/5); k=h//qsim.DT
            while s.pending[h] and s.pending[h][0][0]+h<=t:
                t0,base,m,c0=s.pending[h].pop(0); i0=t0//qsim.DT
                real=d[i0+1:i0+k+1].max()-base
                e=1.0 if real>m+1e-9 else 0.0; s.err[h].append(e)
                if s.aci: s.alpha[h]=min(1.0,max(-0.5,s.alpha[h]+g*(e_t-e)))
                v=round(real/max(base,cv.LMIN),3) if s.rel else real
                s.on.setdefault((h,c0 if s.ctx else None),[]).append(v)
            s.pending[h].append((t,d[i],s.margin(h,d[i],c),c))
        return c
if __name__=="__main__":
    random.seed(7)
    lib=json.load(open("prior_traces.json"))
    locs=sorted({t["loc"] for t in lib}); random.shuffle(locs)
    K=6; folds=[locs[i::K] for i in range(K)]
    NTEST=int(sys.argv[1]) if len(sys.argv)>1 else 30
    G=(0.2,0.1,0.05,0.02,0.01)
    agg={}
    for fi,fold in enumerate(folds):
        train=[t for t in lib if t["loc"] not in fold]; test=[t for t in lib if t["loc"] in fold]
        test=random.sample(test,min(NTEST,len(test)))
        prior={h:[] for h in HS}
        for tr in train:
            d=expand(tr["ue"])
            for h in HS: prior[h]+=cv.samples(d,h)
        PR=cv.Prior(prior)
        for tr in test:
            ue=tr["ue"]; fl=oracle_alloc(ue,5)
            for ev,eu,ew in itertools.product(G,G,G):
                r=cv.simulate(ue,QL(PR,dict(vy=ev,up=eu,wk=ew),rel=True,ctx=False,aci=True))
                a=agg.setdefault((ev,eu,ew),dict(slo=[],over=[],lost=[],flaps=[]))
                a["slo"].append(r["slo"]); a["over"].append(100*(r["alloc"]-fl)/fl); a["lost"].append(r["lost"]); a["flaps"].append(r["flaps"])
        print("fold",fi,file=sys.stderr)
    rows=[(k,np.mean(a["slo"]),np.mean(a["over"]),np.mean(a["lost"]),np.mean(a["flaps"])) for k,a in agg.items()]

    front=[r for r in rows if not any((o[1]>=r[1] and o[2]<=r[2]) and (o[1]>r[1] or o[2]<r[2]) for o in rows)]
    front.sort(key=lambda r:r[2])
    print("uniform ε:")
    for e in G:
        r=[x for x in rows if x[0]==(e,e,e)][0]; print(f"  eps={e:<5} SLO {r[1]:.2f}  over_floor {r[2]:+.1f}%  lost {r[3]:.1f}  flaps {r[4]:.2f}")
    print("Pareto frontier over (ε_vy, ε_up, ε_wk):")
    for r in front: print(f"  {r[0]}  SLO {r[1]:.2f}  over_floor {r[2]:+.1f}%  lost {r[3]:.1f}  flaps {r[4]:.2f}")
    json.dump([dict(eps=list(r[0]),slo=r[1],over=r[2],lost=r[3],flaps=r[4]) for r in rows],open("cv_layers_result.json","w"),indent=1)
