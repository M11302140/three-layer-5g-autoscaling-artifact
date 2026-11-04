#!/usr/bin/env python3
"""qsim/s5/gates.py (spec §4.124): G1, G3 and the decoupling choice from out/cal.jsonl; deployed p (six-split mean, rounded to 0.005).
Registered rules: b' first; if S5(b') held-out flaps > S4 flaps + 2 at either target -> use b.
G1 (i) mean over splits of S5 held-out dispatch cost at eps_v6 <= 1.01 x mean v6 held-out dispatch cost;
   (ii) at 2 % and 0.5 %, S5 held-out vmexist cost <= 0.98 x S4 held-out vmexist cost.  G3: S5 held-out flaps <= S4 (both targets)."""
import json, numpy as np, sys
R='/home/user/experiment/qsim/s5/out'
rows=[json.loads(l) for l in open(f'{R}/cal.jsonl')]
def agg(arm,variant,t,key):
    xs=[r['rows'][t]['ho'][key] for r in rows if r['arm']==arm and r['variant']==variant and not r['rows'][t]['infeasible']]
    return float(np.mean(xs)) if xs else None, len(xs)
def pmean(arm,variant,t):
    xs=[(r['rows'][t]['a'],r['rows'][t]['b']) for r in rows if r['arm']==arm and r['variant']==variant and not r['rows'][t]['infeasible']]
    if not xs: return None
    a=np.mean([x[0] for x in xs]); b=np.mean([x[1] for x in xs]); return round(round(a/0.005)*0.005,3), round(round(b/0.005)*0.005,3), [tuple(x) for x in xs]
v6d=float(np.mean([r['v6']['alloc_dispatch'] for r in rows if r['arm']=='S4'])); v6r=float(np.mean([r['v6']['risk'] for r in rows if r['arm']=='S4']))
print(f"splits: S4 {sum(1 for r in rows if r['arm']=='S4')}, S5 b' {sum(1 for r in rows if r['variant']=='independent_full')}, S5 b {sum(1 for r in rows if r['variant']=='independent')}")
print(f"v6 (held-out, six-split mean): risk {v6r:.4f}  dispatch {v6d:.1f}\n")
print("| arm | target | n | ho risk | ho vmexist | ho dispatch | ho flaps | per-split picks |\n|---|---|---|---|---|---|---|---|")
for arm,v in (('S4','full'),('S5','independent_full'),('S5','independent')):
    for t in ('0.02','0.005','eps_v6'):
        rk,n=agg(arm,v,t,'risk'); vm,_=agg(arm,v,t,'alloc'); dp,_=agg(arm,v,t,'alloc_dispatch'); fl,_=agg(arm,v,t,'flaps'); pm=pmean(arm,v,t)
        if rk is None: print(f"| {arm} {v} | {t} | 0 | infeasible |"); continue
        print(f"| {arm} {v} | {t} | {n} | {rk:.4f} | {vm:.1f} | {dp:.1f} | {fl:.2f} | {pm[2]} |")
s4f={t:agg('S4','full',t,'flaps')[0] for t in ('0.02','0.005')}
bpf={t:agg('S5','independent_full',t,'flaps')[0] for t in ('0.02','0.005')}
use='independent_full' if all(bpf[t] is not None and bpf[t]<=s4f[t]+2 for t in s4f) else 'independent'
print(f"\ndecoupling rule: S5 b' flaps {bpf} vs S4 {s4f} (+2 allowed) -> S5 = {use}")
g1i_val=agg('S5',use,'eps_v6','alloc_dispatch')[0]; g1i=(g1i_val is not None and g1i_val<=1.01*v6d)
g1ii={t:(agg('S5',use,t,'alloc')[0] is not None and agg('S5',use,t,'alloc')[0]<=0.98*agg('S4','full',t,'alloc')[0]) for t in ('0.02','0.005')}
rat={t:(agg('S5',use,t,'alloc')[0]/agg('S4','full',t,'alloc')[0]-1 if agg('S5',use,t,'alloc')[0] else None) for t in ('0.02','0.005')}
g3={t:(agg('S5',use,t,'flaps')[0] is not None and agg('S5',use,t,'flaps')[0]<=agg('S4','full',t,'flaps')[0]) for t in ('0.02','0.005')}
print(f"G1 (i) S5@eps_v6 dispatch {g1i_val} vs 1.01 x v6 {1.01*v6d:.1f} ({(g1i_val/v6d-1)*100 if g1i_val else float('nan'):+.2f} %) -> {'PASS' if g1i else 'FAIL'}")
print(f"G1 (ii) S5 vs S4 vmexist: {{{', '.join(f'{t}: {rat[t]*100:+.2f} %' if rat[t] is not None else f'{t}: n/a' for t in rat)}}} (need <= -2 %) -> {g1ii}")
print(f"G1 overall: {'PASS' if g1i and all(g1ii.values()) else 'FAIL'}")
print(f"G3 S5 flaps <= S4: {g3} -> {'PASS' if all(g3.values()) else 'FAIL (reported, not in decision rule)'}")
for t,arm in (('0.005','S5a'),('0.02','S5b')):
    pm=pmean('S5',use,t); print(f"deployed {arm} ({use}): p_VM/p_UP = {pm[0]}/{pm[1]} (six-split mean, rounded to 0.005)")
