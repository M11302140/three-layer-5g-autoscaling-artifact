#!/usr/bin/env python3
"""qsim/s6/gates.py (spec §4.127 §2): G1, G3 and the deployed S6a/S6b parameters from s6/out/cal.jsonl (S4 and v6 from s5/out/cal.jsonl).
G1 (i)  six-split mean of S6 held-out dispatch cost at eps_v6 <= 1.01 x six-split mean of v6 held-out dispatch cost;
   (ii) eps = 2 %: six-split mean S6b held-out vmexist cost <= 0.99 x S4 (same splits, same target).
G3: S6 held-out flaps <= S4 at 2 % and 0.5 %.
Deployed: ws = mode over six splits (3:3 tie -> the ws with the lower six-split mean best cal cost at that ws); lambda = mean over the splits
that picked that ws, rounded to 0.01."""
import json, numpy as np, collections
Q='/home/user/experiment/qsim'
S6=[json.loads(l) for l in open(f'{Q}/s6/out/cal.jsonl')]
S4={}
for l in open(f'{Q}/s5/out/cal.jsonl'):
    r=json.loads(l)
    if r['arm']=='S4': S4[r['seed']]=r
def rows(t): return sorted([r for r in S6 if r['target_name']==t],key=lambda r:r['seed'])
def m(xs): return float(np.mean(xs))
print(f"jobs: {len(S6)} (expect 18)")
print("| target | split | Lr (S4) | S6 lambda VM/UP | ws | cal risk | cal disp | ho risk | ho vmexist | ho disp | ho flaps | S4 ho risk | S4 ho vmexist | S4 ho disp | S4 flaps |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
for t in ('0.02','0.005','eps_v6'):
    for r in rows(t):
        s4=S4[r['seed']]['rows'][t]['ho']
        if r['infeasible']: print(f"| {t} | {r['seed']} | | INFEASIBLE (min cal risk {r['min_cal_risk']:.4f}) |"); continue
        print(f"| {t} | {r['seed']} | {r['Lr']['vy']}/{r['Lr']['up']} | {r['a']}/{r['b']} | {r['ws']} | {r['cal_risk']:.4f} | {r['cal_alloc']:.1f} | {r['ho']['risk']:.4f} | {r['ho']['alloc']:.1f} | {r['ho']['alloc_dispatch']:.1f} | {r['ho']['flaps']:.2f} | {s4['risk']:.4f} | {s4['alloc']:.1f} | {s4['alloc_dispatch']:.1f} | {s4['flaps']:.2f} |")
def agg(t,key,src='S6'):
    if src=='S6': return m([r['ho'][key] for r in rows(t) if not r['infeasible']])
    return m([S4[s]['rows'][t]['ho'][key] for s in range(6)])
v6d=m([S4[s]['v6']['alloc_dispatch'] for s in range(6)]); v6r=m([S4[s]['v6']['risk'] for s in range(6)])
ok=all(not r['infeasible'] for r in S6) and len(S6)==18
print(f"\nall 18 jobs feasible: {ok}")
print(f"v6 held-out (six-split mean): risk {v6r:.4f} dispatch {v6d:.1f}")
for t in ('0.02','0.005','eps_v6'):
    print(f"target {t}: S6 ho risk {agg(t,'risk'):.4f} vmexist {agg(t,'alloc'):.1f} disp {agg(t,'alloc_dispatch'):.1f} flaps {agg(t,'flaps'):.2f} | S4 ho risk {agg(t,'risk','S4'):.4f} vmexist {agg(t,'alloc','S4'):.1f} disp {agg(t,'alloc_dispatch','S4'):.1f} flaps {agg(t,'flaps','S4'):.2f} | S6 vs S4 vmexist {100*(agg(t,'alloc')/agg(t,'alloc','S4')-1):+.2f} %")
g1i_v=agg('eps_v6','alloc_dispatch'); g1i=g1i_v<=1.01*v6d
g1ii_r=agg('0.02','alloc')/agg('0.02','alloc','S4'); g1ii=g1ii_r<=0.99
print(f"\nG1 (i) S6@eps_v6 dispatch {g1i_v:.1f} vs v6 {v6d:.1f}: {100*(g1i_v/v6d-1):+.2f} % (need <= +1 %) -> {'PASS' if g1i else 'FAIL'}")
print(f"G1 (ii) S6b vs S4b held-out vmexist at 2 %: {100*(g1ii_r-1):+.2f} % (need <= -1 %) -> {'PASS' if g1ii else 'FAIL'}")
print(f"G1: {'PASS' if (g1i and g1ii and ok) else 'FAIL'}")
g3={t:agg(t,'flaps')<=agg(t,'flaps','S4') for t in ('0.02','0.005')}
print(f"G3 S6 flaps <= S4: {g3} -> {'PASS' if all(g3.values()) else 'FAIL (reported; not in the decision rule)'}")
dep={}
for t,arm in (('0.005','S6a'),('0.02','S6b')):
    rs=[r for r in rows(t) if not r['infeasible']]; cnt=collections.Counter(r['ws'] for r in rs)
    best={}
    for w in (3,5):
        xs=[(r['cal_alloc'] if r['ws']==w else (r['other_ws']['cal_alloc'] if r['other_ws'] else None)) for r in rs]
        best[w]=m([x for x in xs if x is not None]) if all(x is not None for x in xs) else float('inf')
    if cnt[3]!=cnt[5]: w=max(cnt,key=lambda k:cnt[k]); rule='mode'
    else: w=min(best,key=lambda k:best[k]); rule=f'tie -> lower mean best cal cost {best}'
    sel=[r for r in rs if r['ws']==w]
    a=round(m([r['a'] for r in sel]),2); b=round(m([r['b'] for r in sel]),2); dep[arm]=(a,b,w)
    print(f"deployed {arm}: lambda VM/UP {a}/{b}, ws {w} ({rule}; ws counts {dict(cnt)}; from splits {[r['seed'] for r in sel]})")
json.dump(dict(g1=dict(i=g1i,i_val=g1i_v,v6=v6d,ii=g1ii,ii_ratio=g1ii_r),g3=g3,deployed=dep),open(f'{Q}/s6/out/gates.json','w'),indent=1)
print(f"\npredict command: python3 s6/predict.py {dep['S6a'][0]} {dep['S6a'][1]} {dep['S6a'][2]} {dep['S6b'][0]} {dep['S6b'][1]} {dep['S6b'][2]}")
