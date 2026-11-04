#!/usr/bin/env python3
"""qsim/s9/gates.py (spec §4.132 item 3): G1, G3, library risk check and deployed S9a/S9b parameters from s9/out/cal.jsonl (S4/v6: s5/out/cal.jsonl).
G1 (i) six-split mean S9 held-out dispatch at eps_v6 <= 1.01 x v6; (ii) 2 %: S9b held-out vmexist <= 0.99 x S4b.  G3 flaps <= S7 (3.64 / 3.67).
Library risk check (not a gate): six-split mean held-out risk within target +- 1 SE (SE = mean of the per-split standard errors over held-out traces).
Deployed: per-bucket lambda = mean over the six splits rounded 0.01; w = six-split mode (tie -> smaller). Output s9/out/gates.json, gates.txt"""
import json, numpy as np, collections
Q='/home/user/experiment/qsim'; BK=("calm","normal","burst")
R=[json.loads(l) for l in open(f'{Q}/s9/out/cal.jsonl')]
S4={}
for l in open(f'{Q}/s5/out/cal.jsonl'):
    r=json.loads(l)
    if r['arm']=='S4': S4[r['seed']]=r
m=lambda xs: float(np.mean(xs)); out=[]
def P(s): print(s); out.append(s)
rows=lambda t: sorted([r for r in R if r['target_name']==t],key=lambda r:r['seed'])
P(f"jobs {len(R)} (expect 18)")
P("| target | split | calm VM/UP | normal VM/UP | burst VM/UP | w | flags | redoA | cal cond calm/normal/burst (nest2) | cal per-slot burst | ho risk ± SE | ho cond calm/normal/burst | ho ps burst | ho vmexist | ho disp | ho flaps | S4 ho vmexist | S4 flaps |")
P("|"+"---|"*18)
for t in ('0.02','0.005','eps_v6'):
    for r in rows(t):
        s4=S4[r['seed']]['rows'][t]['ho']; c=r['cal_cond']; h=r['ho_cond']
        P(f"| {t} | {r['seed']} | {r['Lb']['calm'][0]}/{r['Lb']['calm'][1]} | {r['Lb']['normal'][0]}/{r['Lb']['normal'][1]} | {r['Lb']['burst'][0]}/{r['Lb']['burst'][1]} | {r['w']} | {','.join(r['flags']) or '-'} | {r['redoA']} | {c['calm']:.4f}/{c['normal']:.4f}/{c['burst']:.4f} | {r['cal_ps_burst']:.4f} | {r['ho']['risk']:.4f} ± {r['ho_se']:.4f} | {h['calm']:.4f}/{h['normal']:.4f}/{h['burst']:.4f} | {r.get('ho_ps_burst',float('nan')):.4f} | {r['ho']['alloc']:.1f} | {r['ho']['alloc_dispatch']:.1f} | {r['ho']['flaps']:.2f} | {s4['alloc']:.1f} | {s4['flaps']:.2f} |")
agg=lambda t,k: m([r['ho'][k] for r in rows(t)])
s4a=lambda t,k: m([S4[s]['rows'][t]['ho'][k] for s in range(6)])
v6d=m([S4[s]['v6']['alloc_dispatch'] for s in range(6)])
P("")
for t in ('0.02','0.005','eps_v6'):
    P(f"target {t}: S9 risk {agg(t,'risk'):.4f} vmexist {agg(t,'alloc'):.1f} disp {agg(t,'alloc_dispatch'):.1f} flaps {agg(t,'flaps'):.2f} | S4 risk {s4a(t,'risk'):.4f} vmexist {s4a(t,'alloc'):.1f} flaps {s4a(t,'flaps'):.2f} | S9 vs S4 vmexist {100*(agg(t,'alloc')/s4a(t,'alloc')-1):+.2f} %")
ok=len(R)==18
g1i=agg('eps_v6','alloc_dispatch')<=1.01*v6d; g1ii=agg('0.02','alloc')<=0.99*s4a('0.02','alloc')
P(f"\nG1 (i) S9@eps_v6 dispatch {agg('eps_v6','alloc_dispatch'):.1f} vs v6 {v6d:.1f}: {100*(agg('eps_v6','alloc_dispatch')/v6d-1):+.2f} % (<= +1 %) -> {'PASS' if g1i else 'FAIL'}")
P(f"G1 (ii) S9b vs S4b vmexist at 2 %: {100*(agg('0.02','alloc')/s4a('0.02','alloc')-1):+.2f} % (<= -1 %) -> {'PASS' if g1ii else 'FAIL'}")
g1=ok and g1i and g1ii; P(f"G1: {'PASS' if g1 else 'FAIL'}")
S7F={'0.02':3.64,'0.005':3.67}; g3={t:agg(t,'flaps')<=S7F[t] for t in S7F}
P(f"G3 flaps S9 <= S7: 2 % {agg('0.02','flaps'):.2f} vs 3.64, 0.5 % {agg('0.005','flaps'):.2f} vs 3.67 -> {'PASS' if all(g3.values()) else 'FAIL'}")
chk={}
for t,eps in (('0.02',0.02),('0.005',0.005)):
    se=m([r['ho_se'] for r in rows(t)]); rk=agg(t,'risk'); chk[t]=dict(risk=rk,se=se,inside=abs(rk-eps)<=se)
    P(f"library risk check {t}: held-out risk {rk:.4f} vs {eps} ± {se:.4f} -> {'inside' if chk[t]['inside'] else 'OUTSIDE (report)'}")
nflag=collections.Counter(f for r in R for f in r['flags']); P(f"infeasibility flags over 18 jobs: {dict(nflag)}")
dep={}
for t,arm in (('0.005','S9a'),('0.02','S9b')):
    rs=rows(t); cw=collections.Counter(r['w'] for r in rs); w=sorted(cw,key=lambda k:(-cw[k],k))[0]
    Lb={b:[round(m([r['Lb'][b][0] for r in rs]),2),round(m([r['Lb'][b][1] for r in rs]),2)] for b in BK}
    dep[arm]=dict(Lb=Lb,w=w,w_counts=dict(cw)); P(f"deployed {arm}: {Lb}, w {w} (counts {dict(cw)})")
json.dump(dict(g1=dict(i=g1i,ii=g1ii,passed=g1),g3=g3,risk_check=chk,flags=dict(nflag),deployed=dep),open(f'{Q}/s9/out/gates.json','w'),indent=1)
open(f'{Q}/s9/out/gates.txt','w').write("\n".join(out)+"\n")
