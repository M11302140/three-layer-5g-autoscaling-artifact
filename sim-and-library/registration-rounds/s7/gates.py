#!/usr/bin/env python3
"""qsim/s7/gates.py (spec §4.131 item 7): G1, G3(i) and deployed S7a/S7b parameters from s7/out/cal.jsonl (S4/v6 from s5/out/cal.jsonl).
G1 (i) six-split mean S7 held-out dispatch at eps_v6 <= 1.01 x v6; (ii) 2 %: S7b held-out vmexist <= 1.01 x S4b.  G3 (i) flaps <= S4 (2 %, 0.5 %).
Deployed: w and P = six-split modes (tie -> smaller); lambda = mean over splits with that (w, P) (fallback: same P, then all), rounded 0.01."""
import json, numpy as np, collections
Q='/home/user/experiment/qsim'
S7=[json.loads(l) for l in open(f'{Q}/s7/out/cal.jsonl')]
S4={}
for l in open(f'{Q}/s5/out/cal.jsonl'):
    r=json.loads(l)
    if r['arm']=='S4': S4[r['seed']]=r
m=lambda xs: float(np.mean(xs))
rows=lambda t: sorted([r for r in S7 if r['target_name']==t],key=lambda r:r['seed'])
print(f"jobs {len(S7)} (expect 18); infeasible {[ (r['seed'],r['target_name']) for r in S7 if r['infeasible']]}")
print("| target | split | lambda VM/UP | w | P | cal risk | cal disp | ho risk | ho vmexist | ho disp | ho flaps | S4 ho vmexist | S4 flaps |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|")
for t in ('0.02','0.005','eps_v6'):
    for r in rows(t):
        if r['infeasible']: print(f"| {t} | {r['seed']} | INFEASIBLE {r['min_cal_risk']:.4f} |"); continue
        s4=S4[r['seed']]['rows'][t]['ho']
        print(f"| {t} | {r['seed']} | {r['a']}/{r['b']} | {r['w']} | {r['P']} | {r['cal_risk']:.4f} | {r['cal_alloc']:.1f} | {r['ho']['risk']:.4f} | {r['ho']['alloc']:.1f} | {r['ho']['alloc_dispatch']:.1f} | {r['ho']['flaps']:.2f} | {s4['alloc']:.1f} | {s4['flaps']:.2f} |")
agg=lambda t,k: m([r['ho'][k] for r in rows(t) if not r['infeasible']])
s4a=lambda t,k: m([S4[s]['rows'][t]['ho'][k] for s in range(6)])
v6d=m([S4[s]['v6']['alloc_dispatch'] for s in range(6)])
for t in ('0.02','0.005','eps_v6'):
    print(f"target {t}: S7 risk {agg(t,'risk'):.4f} vmexist {agg(t,'alloc'):.1f} disp {agg(t,'alloc_dispatch'):.1f} flaps {agg(t,'flaps'):.2f} | S4 risk {s4a(t,'risk'):.4f} vmexist {s4a(t,'alloc'):.1f} flaps {s4a(t,'flaps'):.2f} | S7 vs S4 vmexist {100*(agg(t,'alloc')/s4a(t,'alloc')-1):+.2f} %")
ok=len(S7)==18 and not any(r['infeasible'] for r in S7)
g1i=agg('eps_v6','alloc_dispatch')<=1.01*v6d; g1ii=agg('0.02','alloc')<=1.01*s4a('0.02','alloc')
print(f"\nG1 (i) S7@eps_v6 dispatch {agg('eps_v6','alloc_dispatch'):.1f} vs v6 {v6d:.1f}: {100*(agg('eps_v6','alloc_dispatch')/v6d-1):+.2f} % (<= +1 %) -> {'PASS' if g1i else 'FAIL'}")
print(f"G1 (ii) S7b vs S4b vmexist at 2 %: {100*(agg('0.02','alloc')/s4a('0.02','alloc')-1):+.2f} % (<= +1 %) -> {'PASS' if g1ii else 'FAIL'}")
print(f"G1: {'PASS' if (ok and g1i and g1ii) else 'FAIL'}")
g3={t:agg(t,'flaps')<=s4a(t,'flaps') for t in ('0.02','0.005')}
print(f"G3 (i) flaps S7 <= S4: {g3} -> {'PASS' if all(g3.values()) else 'FAIL'}")
dep={}
for t,arm in (('0.005','S7a'),('0.02','S7b')):
    rs=[r for r in rows(t) if not r['infeasible']]
    cw=collections.Counter(r['w'] for r in rs); cp=collections.Counter(r['P'] for r in rs)
    w=sorted(cw,key=lambda k:(-cw[k],k))[0]; P=sorted(cp,key=lambda k:(-cp[k],{'P85':0,'P90':1,'P95':2}[k]))[0]
    sel=[r for r in rs if r['w']==w and r['P']==P] or [r for r in rs if r['P']==P] or rs
    a=round(m([r['a'] for r in sel]),2); b=round(m([r['b'] for r in sel]),2); B={'P85':4,'P90':5,'P95':7}[P]
    dep[arm]=dict(a=a,b=b,w=w,P=P,B=B,splits=[r['seed'] for r in sel],w_counts=dict(cw),P_counts=dict(cp))
    print(f"deployed {arm}: lambda {a}/{b}, w {w}, {P} (B={B}); from splits {dep[arm]['splits']}; w counts {dict(cw)}; P counts {dict(cp)}")
json.dump(dict(g1=dict(i=g1i,ii=g1ii),g3_i=g3,deployed=dep),open(f'{Q}/s7/out/gates.json','w'),indent=1)
print(f"\npredict: python3 s7/predict.py")
