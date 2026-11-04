#!/usr/bin/env python3
"""spec §4.139: REPORT.md = refined E1 (point / interpolation rule, U = max(bootstrap CI upper - point, interpolation error)), churn-adjusted cost table,
S4' registration prediction tables (t4/t6/t8 three versions, endpoints' reference), t11/t12 predictions."""
import timeit  # noqa
import sys, os, json, glob, hashlib, numpy as np
Q='/home/user/experiment/qsim'; R=f'{Q}/r71fin'
for p in (Q,Q+'/r67band',Q+'/r68unif',Q+'/s7',Q+'/r70eq',R): sys.path.insert(0,p)
os.chdir(Q)
import fine as F
TGT=F.TGT; TOL=F.TOL; N=F.N; ALPHA=3.0
BOOT=np.random.default_rng(20261027).integers(0,N,size=(1000,N))
out=[]; P=lambda s="": (print(s),out.append(s))
md5=lambda f: hashlib.md5(open(f'{Q}/{f}','rb').read()).hexdigest()[:8]
FZ=("v8sim10.py","v8sim10_abl.py","v8sim11.py","v8sim2.py","v8sim_b6.py","prior_traces.json")
P("# r71fin (spec §4.139)\n"); P("Frozen-file md5 after: "+" ".join(md5(f) for f in FZ)+" (before 3daf1387 7a2b02ec ecdfff61 4697713c b24eae16 edb8e00c).\n")
def withacts(arm,g,c):
    fn=f'{R}/out/fine/{arm}_{g}_{c:.4f}.json'; return json.load(open(fn))
NAME={"S4":"S4","APL":"A-PL","S8":"S8","S4p":"S4′"}
P("## 1. Refined E1 (per-slot v8sim11 R38 off, own initial_fleet)\n")
P(f"Targets: 2 % group {100*TGT['2']:.3f} %, 0.5 % group {100*TGT['05']:.3f} %; window ± 0.05 pp.\n")
P("Fine-scan points (c step 0.0025):\n")
for (arm,g),lo in F.FINE.items():
    ps=[d for d in F.allpts(arm,g) if lo-1e-9<=d['c']<=lo+0.02+1e-9]
    P(f"- {g} {NAME[arm]}: "+"; ".join(f"c {d['c']:.4f} → {100*d['risk']:.3f} % / {d['cost']:.1f}" for d in ps))
P("")
E={}
for g in ("2","05"):
    for arm in ("S4","APL","S8","S4p"):
        ps=F.allpts(arm,g); t=TGT[g]; cs=F.choose(arm,g); br=[(x,y) for x,y in zip(ps,ps[1:]) if (x['risk']-t)*(y['risk']-t)<=0]
        x,y=br[0]; s=(y['cost']-x['cost'])/(100*(y['risk']-x['risk'])) if y['risk']!=x['risk'] else 0.0   # core-min per pp
        if len(cs)==1:
            d=withacts(arm,g,cs[0]); w=0.0; rows=[d['rows']]; risk=d['risk']; e=0.0 if arm=="S4" else abs(s)*100*abs(risk-t); how=f"point c {cs[0]:.4f}"
        else:
            lo_,hi_=withacts(arm,g,cs[0]),withacts(arm,g,cs[1]); w=(t-lo_['risk'])/(hi_['risk']-lo_['risk']); rows=[lo_['rows'],hi_['rows']]; risk=t
            e=abs(s)*100*min(abs(lo_['risk']-t),abs(hi_['risk']-t)); how=f"interp c {cs[0]:.4f} ({100*lo_['risk']:.3f} %) – {cs[1]:.4f} ({100*hi_['risk']:.3f} %), w {w:.3f}"
        def mix(key):
            a=np.array([r[key] for r in rows[0]],float)
            return a if len(rows)==1 else (1-w)*a+w*np.array([r[key] for r in rows[1]],float)
        E[(arm,g)]=dict(how=how,risk=risk,cost=mix('alloc_vm'),flaps=mix('flaps'),acts=mix('acts'),e=e,s=s,cs=cs,within=len(cs)==1,rv=None)
    S4=E[("S4",g)]['cost']; C4=S4.mean()
    P(f"### {g if g=='2' else '0.5'} % group\n\n| arm | selection | risk % | alloc_vm | Δcost % [95 % CI] | interp. error (core-min / %) | U % | point + U | verdict | flaps | equal-risk c vs 1.00 |\n|---|---|---|---|---|---|---|---|---|---|---|")
    for arm in ("S4","APL","S8","S4p"):
        d=E[(arm,g)]; c=d['cost']; pt=100*(c.mean()/C4-1); bs=np.array([100*(c[ix].mean()/S4[ix].mean()-1) for ix in BOOT]); lo,hi=np.percentile(bs,[2.5,97.5])
        ep=100*d['e']/C4; U=max(hi-pt,ep); v="—" if arm=="S4" else ("cheaper" if pt+U<0 else "indistinguishable")
        cc=np.mean(d['cs']) if len(d['cs'])==1 else d['cs'][0]+(d['cs'][1]-d['cs'][0])*((TGT[g]-withacts(arm,g,d['cs'][0])['risk'])/(withacts(arm,g,d['cs'][1])['risk']-withacts(arm,g,d['cs'][0])['risk']))
        d.update(pt=pt,ci=(lo,hi),U=U,verdict=v,ceq=cc)
        P(f"| {NAME[arm]} | {d['how']} | {100*d['risk']:.3f} | {c.mean():.1f} | {pt:+.2f} [{lo:+.2f}, {hi:+.2f}] | {d['e']:.2f} / {ep:.2f} | {U:.2f} | {pt+U:+.2f} | {v} | {d['flaps'].mean():.2f} | {cc:.4f} ({'differs > 0.02' if abs(cc-1)>0.02 else 'within 0.02'}) |")
    P("")
# churn
P("## 2. Churn-adjusted cost (α = 3 core-min per event; library means)\n")
P("Primary churn = flaps (same layer reversed within 10 min, sim = rq_metrics definition); secondary churn = all actions (out + in, three layers).\n")
for g in ("2","05"):
    rowsT=[]
    for arm in ("S4","APL","S8","S4p"):
        d=E[(arm,g)]; rowsT.append((NAME[arm]+" (equal-risk)",100*d['risk'],d['cost'].mean(),d['flaps'].mean(),d['acts'].mean()))
    for name in F.BASES[g]:
        b=json.load(open(f'{R}/out/fine/base_{name}.json')); rs=b['rows']
        rowsT.append((name,100*np.mean([(60-r['slo'])/60 for r in rs]),np.mean([r['alloc_vm'] for r in rs]),np.mean([r['flaps'] for r in rs]),np.mean([r['acts'] for r in rs])))
    s4=rowsT[0]; a4=s4[2]+ALPHA*s4[3]; b4=s4[2]+ALPHA*s4[4]
    P(f"### {g if g=='2' else '0.5'} % group\n\n| arm | risk % | alloc_vm | flaps | acts | alloc_vm + 3·flaps | Δ vs S4 % | alloc_vm + 3·acts | Δ vs S4 % |\n|---|---|---|---|---|---|---|---|---|")
    for n,rk,c,fl,ac in rowsT:
        P(f"| {n} | {rk:.3f} | {c:.1f} | {fl:.2f} | {ac:.2f} | {c+ALPHA*fl:.1f} | {100*((c+ALPHA*fl)/a4-1):+.2f} | {c+ALPHA*ac:.1f} | {100*((c+ALPHA*ac)/b4-1):+.2f} |")
    P("")
# predictions
PR=json.load(open(f'{R}/out/predict.json'))
HW={("t4","2"):dict(runs="r303/r314/r322",cost=1420.0,fl=1.0,viol=[[20,21,49,50],[20,21],[20,21,49,50]]),("t4","05"):dict(runs="r502/r312/r317",cost=1449.3,fl=2.0,viol=[[],[20],[20,21]]),
    ("t6","2"):dict(runs="r405/r411/r416",cost=1390.3,fl=6.0,viol=[[],[],[]]),("t6","05"):dict(runs="r402/r414/r419",cost=1435.0,fl=9.333,viol=[[],[],[]]),
    ("t8","2"):dict(runs="r476/r500",cost=1054.5,fl=9.0,viol=[[20,21],[20,21,22]]),("t8","05"):dict(runs="r471/r478",cost=1107.5,fl=11.5,viol=[[20],[20,21]])}
P("## 3. S4′ hardware registration: predictions (§4.139 item 2)\n")
P(f"Equivalence of (a) and (b) with r68unif out/new_traces.json (t4/t8): {PR['equiv']}.\n")
P("| trace | point | arm | λ | start | version | alloc_vm | violation minutes | flaps | acts | worker / VyOS / slot-min |\n|---|---|---|---|---|---|---|---|---|---|---|")
for tn in ("t4","t6","t8"):
    for g in ("2","05"):
        for arm in ("S4p","S4"):
            c=PR['s4p'][f"{tn}|{g}|{arm}"]
            for v,lab in (("a","(a) per-slot R38 off"),("b","(b) fleet"),("c","(c) per-slot R38 on")):
                x=c[v]; P(f"| {tn} | {'2' if g=='2' else '0.5'} % | {NAME[arm]} | {c['L']['vy']}/{c['L']['up']} | {'/'.join(map(str,c['start']))} | {lab} | {x['alloc_vm']:.1f} | {x['viol']} | {x['flaps']} | {x['acts']} | {x['wk_min']:.1f} / {x['vy_min']:.1f} / {x['slot_min']:.1f} |")
P("\nLayer minutes of (b) are minute-sampled counts; slot / VyOS / worker order in 'start' = slots / VyOS / workers.\n")
P("### Endpoint references (S4 same-point hardware) and S4′ predicted values\n\n| trace | point | S4 hw runs | S4 hw alloc_vm | S4 hw flaps | (i) threshold 0.5× | S4′ pred flaps a / b / c | S4′ pred alloc_vm a / b / c | hw majority violation set (S4) |\n|---|---|---|---|---|---|---|---|---|")
for tn in ("t4","t6","t8"):
    for g in ("2","05"):
        h=HW[(tn,g)]; c=PR['s4p'][f"{tn}|{g}|S4p"]; n=len(h['viol']); maj=sorted({m for vv in h['viol'] for m in vv if sum(m in u for u in h['viol'])*2>n})
        P(f"| {tn} | {'2' if g=='2' else '0.5'} % | {h['runs']} | {h['cost']:.1f} | {h['fl']:.2f} | {0.5*h['fl']:.2f} | {c['a']['flaps']} / {c['b']['flaps']} / {c['c']['flaps']} | {c['a']['alloc_vm']:.1f} / {c['b']['alloc_vm']:.1f} / {c['c']['alloc_vm']:.1f} | {maj} |")
P("")
t4=PR['s4p']["t4|2|S4p"]; s4=PR['s4p']["t4|2|S4"]
P("### t4 2 % point, three versions (S4′ registered; S4b for reference against its hardware)\n\n| version | S4′ violation minutes | contains 49 or 50 | S4′ alloc_vm | S4b violation minutes | S4b = hw majority [20, 21, 49, 50]? |\n|---|---|---|---|---|---|")
for v,lab in (("a","(a) per-slot R38 off"),("b","(b) fleet"),("c","(c) per-slot R38 on")):
    P(f"| {lab} | {t4[v]['viol']} | {'yes' if (49 in t4[v]['viol'] or 50 in t4[v]['viol']) else 'no'} | {t4[v]['alloc_vm']:.1f} | {s4[v]['viol']} | {'yes' if s4[v]['viol']==[20,21,49,50] else 'no'} |")
P("")
P("Secondary (t8): predicted S4′ / S4 ratios — " + "; ".join(f"{'2' if g=='2' else '0.5'} %: (a) {100*(PR['s4p'][f't8|{g}|S4p']['a']['alloc_vm']/PR['s4p'][f't8|{g}|S4']['a']['alloc_vm']-1):+.2f} %, (b) {100*(PR['s4p'][f't8|{g}|S4p']['b']['alloc_vm']/PR['s4p'][f't8|{g}|S4']['b']['alloc_vm']-1):+.2f} %, (c) {100*(PR['s4p'][f't8|{g}|S4p']['c']['alloc_vm']/PR['s4p'][f't8|{g}|S4']['c']['alloc_vm']-1):+.2f} %" for g in ("2","05"))+".\n")
P("## 4. Generalisation set t11 / t12 (per-slot R38 off, own initial_fleet)\n")
RS=json.load(open(f'{R}/t1112/result.json'))
for tn in ("t11","t12"):
    x=RS[tn]; P(f"- {tn}: sensor {x['loc']}, {x['date']} {x['start']//60:02d}:00–{x['start']//60+4:02d}:00 (Melbourne), {x['band']}, pool rank {x['rank']} (rejected before it: {x['rank']-1}), UE0 {x['ue0']}, stats {', '.join(f'{k} {v:.3g}' for k,v in x['stats'].items())}")
P("\n| trace | arm | SLO / 60 | violation minutes | alloc_vm | flaps | acts | worker / VyOS / slot-min |\n|---|---|---|---|---|---|---|---|")
for tn in ("t11","t12"):
    for k,v in PR['t1112'][tn]['arms'].items():
        P(f"| {tn} | {k.replace('S4p','S4′ 1.5/1.92').replace('S4b','S4b 1.83/2.00')} | {v['slo']} | {v['viol']} | {v['alloc_vm']:.1f} | {v['flaps']} | {v['acts']} | {v['wk_min']:.1f} / {v['vy_min']:.1f} / {v['slot_min']:.1f} |")
open(f'{R}/REPORT.md','w').write("\n".join(out)+"\n"); json.dump({f"{a}|{g}":dict(pt=d['pt'],ci=d['ci'],U=d['U'],verdict=d['verdict'],flaps=float(d['flaps'].mean()),ceq=d['ceq'],e=d['e'],how=d['how']) for (a,g),d in E.items()},open(f'{R}/out/e1.json','w'),indent=1)
