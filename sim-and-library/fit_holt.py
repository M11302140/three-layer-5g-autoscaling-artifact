#!/usr/bin/env python3
"""(docstring removed)"""
import json, itertools, random
import numpy as np
random.seed(3)
lib=random.sample(json.load(open("prior_traces.json")),400)
S=[np.repeat(np.array(t["ue"],float),2) for t in lib]   # 30 s tick
def mse(a,b,hs=(2,4,5)):
    e=0.0;n=0
    for s in S:
        L=s[0];T=0.0;f={}
        for i,x in enumerate(s):
            if i>0:
                Lp=L; L=a*x+(1-a)*(L+T); T=b*(L-Lp)+(1-b)*T
            for h in hs:
                if i+h<len(s): e+=(L+h*T-s[i+h])**2; n+=1
    return e/n
best=min(((mse(a,b),a,b) for a,b in itertools.product((0.2,0.3,0.5,0.7,0.9,1.0),(0.0,0.05,0.1,0.2,0.3,0.5))))
print("best mse %.3f alpha %.2f beta %.2f"%best)
print("persistence mse %.3f"%mse(1.0,0.0))
for a,b in ((0.5,0.1),(0.7,0.1),(0.9,0.05),(0.5,0.3)): print(a,b,"%.3f"%mse(a,b))
