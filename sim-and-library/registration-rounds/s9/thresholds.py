#!/usr/bin/env python3
"""qsim/s9/thresholds.py (spec §4.132 item 1.1): T50, T85 of rise1_10 over every tick (t >= 660 s) of every library window; written once.
Also reports bucket shares (raw candidate and with hysteresis) and the conditional-sigma cell counts. Output s9/out/thresholds.json"""
import sys, json, hashlib, numpy as np, collections
Q='/home/user/experiment/qsim'; sys.path.insert(0,Q); sys.path.insert(0,Q+'/s9')
import v8sim2 as S, v8sim7 as M, s9core as C
P=f'{Q}/prior_traces.json'; lib=json.load(open(P)); cfg=M.cfg_measured()
T50,T85,a=C.lib_thresholds(lib,cfg)
raw=collections.Counter(C.cand((T50,T85),r) for r in a)
hy=collections.Counter()
for tr in lib:
    d=S.expand(tr["ue"])*cfg.scale; rg=C.Regime((T50,T85)); regs=[rg.step(float(d[i])) for i in range(0,len(d),C.STEP)]
    hy.update(regs[22:])
n=len(a); out=dict(T50=T50,T85=T85,n_ticks=n,n_windows=len(lib),prior_sha256=hashlib.sha256(open(P,'rb').read()).hexdigest(),
  pct={str(q):float(np.percentile(a,q)) for q in (10,25,50,75,85,90,95,99)},share_raw={k:raw[k]/n for k in C.BUCKETS},share_hyst={k:hy[k]/sum(hy.values()) for k in C.BUCKETS})
json.dump(out,open(f'{Q}/s9/out/thresholds.json','w'),indent=1); print(json.dumps(out,indent=1))
low=[k for k in C.BUCKETS if out['share_hyst'][k]<0.05 or out['share_raw'][k]<0.05]
print("BUCKET < 5 % -> report before calibration:",low if low else "none")
