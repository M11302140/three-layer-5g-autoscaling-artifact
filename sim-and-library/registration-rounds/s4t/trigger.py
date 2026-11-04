#!/usr/bin/env python3
"""qsim/s4t/trigger.py (spec §4.133 item 1): share of library ticks with a(t) >= k (k = 4, 5, 6), a(t) = max(0, D(t) - D(t - 30 s)),
over every tick (t >= 30 s) of every library window; per scored hour (120 ticks) and the false-trigger cost bound (<= 4 core-min each). Written once."""
import sys, json, hashlib, numpy as np
Q='/home/user/experiment/qsim'; sys.path.insert(0,Q)
import v8sim2 as S, v8sim7 as M
P=f'{Q}/prior_traces.json'; lib=json.load(open(P)); cfg=M.cfg_measured(); st=S.TICK//S.DT
a=[]
for tr in lib:
    d=S.expand(tr["ue"])*cfg.scale; o=[float(d[i]) for i in range(0,len(d),st)]
    a.extend(max(0.0,o[j]-o[j-1]) for j in range(1,len(o)))
a=np.array(a); out=dict(n_ticks=len(a),prior_sha256=hashlib.sha256(open(P,'rb').read()).hexdigest(),rows={})
for k in (4,5,6):
    p=float((a>=k).mean()); out['rows'][k]=dict(share=p,per_hour=p*120,cost_bound_per_hour=p*120*4)
    print(f"k={k}: share {p:.4f} of ticks, {p*120:.2f} ticks/hour, false-trigger cost bound {p*120*4:.1f} core-min/hour (before the free<k and cooldown conditions)")
json.dump(out,open(f'{Q}/s4t/out/trigger_rate.json','w'),indent=1)
