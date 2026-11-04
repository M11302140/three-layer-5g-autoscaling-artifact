#!/usr/bin/env python3
"""(docstring removed)"""
import csv, json, os, statistics as S
HERE=os.path.dirname(os.path.abspath(__file__))
RQ='/home/user/experiment/paper_out_new/rq/rq_metrics.csv'
R=list(csv.DictReader(open(RQ)))
def grp(name):
    rows=[r for r in R if r['group']==name]; assert rows,name
    return [dict(run=r['run'],cost=float(r['alloc_vm']),viol=60-int(r['slo']),flaps=float(r['flaps'])) for r in rows]
def hard(runs): return [dict(run=a,cost=float(c),viol=int(v),flaps=f) for a,c,v,f in runs]
# cells not in rq_metrics.csv (sources in the docstring)
H={('CR05','t8'):hard([('r471',1091,1,None),('r478',1124,2,None)]),   # flaps cell mean 11.5 (numbers §6)
   ('CR2','t8'):hard([('r476',1058,2,None),('r500',1051,3,None)]),    # flaps 9.0
   ('B6d','t8'):hard([('r474',1068,0,None),('r504',1060,3,None)]),
   ('B6s','t3'):hard([('r493',1174,3,None),('r505',1184,4,None)]),   # viol 3.50 (3–4), cost 1179 (1174–1184)
   ('B6s','t6'):hard([('r498',1434,0,None),('r499',1453,0,None)])}
FLAPS_HARD={('CR05','t8'):11.5,('CR2','t8'):9.0}
def cellruns(arm,tn):
    if (arm,tn) in H: return H[(arm,tn)]
    g={'PL2':{'t3':'R73 t3 S4p2','t4':'R72 t4 S4p2','t5':'R73 t5 S4p2','t6':'R72 t6 S4p2','t7':'R73 t7 S4p2','t8':'R72 t8 S4p2','t11':'R72 t11 S4p2','t12':'R72 t12 S4p2'},
       'PL05':{'t3':'R73 t3 S4p05','t4':'R72 t4 S4p05','t5':'R73 t5 S4p05','t6':'R72 t6 S4p05','t7':'R73 t7 S4p05','t8':'R72 t8 S4p05'},
       'CR2':{**{t:f'MAIN {t} S4b' for t in 't3 t4 t5 t6 t7'.split()},'t11':'R72 t11 S4b','t12':'R72 t12 S4b'},
       'CR05':{t:f'MAIN {t} S4a' for t in 't3 t4 t5 t6 t7'.split()},
       'B4s':{'t4':'R73 t4 A:B4 3.75/300','t8':'R73 t8 A:B4 3.75/300','t11':'R72 t11 A:B4 3.75/300','t12':'R72 t12 A:B4 3.75/300'},
       'B4d':{t:f'MAIN {t} B4c2' for t in 't3 t4 t5 t6 t7'.split()},
       'B5':{**{t:f'MAIN {t} B5c1 (q11)' for t in 't3 t4 t5 t6 t7'.split()},'t11':'R72 t11 A:B5 4.0/L2','t12':'R72 t12 A:B5 4.0/L2'},
       'B6s':{'t4':'R73 t4 A:B6 0.775','t8':'R73 t8 A:B6 0.775','t11':'R72 t11 A:B6 0.775','t12':'R72 t12 A:B6 0.775'},
       'B6d':{t:f'MAIN {t} B6 u=0.70' for t in 't3 t4 t5 t6 t7'.split()}}
    return grp(g[arm][tn])
def stats(arm,tn):
    rs=cellruns(arm,tn); c=[r['cost'] for r in rs]; v=[r['viol'] for r in rs]; f=[r['flaps'] for r in rs if r['flaps'] is not None]
    return dict(arm=arm,trace=tn,n=len(rs),runs=[r['run'] for r in rs],cost=S.mean(c),lo=min(c),hi=max(c),costs=c,viol=S.mean(v),viols=v,
                flaps=(S.mean(f) if f else FLAPS_HARD.get((arm,tn))))
def verdict(a,b):
    cc=(a['hi']<b['lo']) or (b['hi']<a['lo']); cs=0 if not cc else (-1 if a['cost']<b['cost'] else 1)
    dv=a['viol']-b['viol']; vs=0 if abs(dv)<1-1e-9 else (-1 if dv<0 else 1)
    if cs==0 and vs==0: return 'equal'
    if cs<=0 and vs<=0: return 'dominates'
    if cs>=0 and vs>=0: return 'dominated'
    return 'trade-off'
NAME={'B4s':'B4* 3.75/300','B5':'B5 4.0/L2','B6s':'B6* 0.775','B6d':'B6 0.70','B4d':'B4c2 3.5/600','CR2':'CR 2 %','CR05':'CR 0.5 %'}
TR=['t3','t4','t5','t6','t7','t8','t11','t12']
# ---- main-text same-target matrix
main={'2 %':{}, '0.5 %':{}}
for tn in TR:
    pl=stats('PL2',tn)
    for arm in ('B4s','B5','B6s'):
        try: b=stats(arm,tn)
        except (KeyError,AssertionError): continue
        main['2 %'][f'{tn}|{arm}']=dict(planner=pl,base=b,verdict=verdict(pl,b),dcost_pct=100*(pl['cost']-b['cost'])/b['cost'],dviol=pl['viol']-b['viol'])
for tn in TR[:6]:
    pl=stats('PL05',tn); b=stats('B6d',tn)
    main['0.5 %'][f'{tn}|B6d']=dict(planner=pl,base=b,verdict=verdict(pl,b),dcost_pct=100*(pl['cost']-b['cost'])/b['cost'],dviol=pl['viol']-b['viol'])
counts={pt:{k:sum(1 for c in cells.values() if c['verdict']==k) for k in ('dominates','trade-off','equal','dominated')} for pt,cells in main.items()}
# ---- TR: cross-target / deployed-knob pairings (not same-target)
tr={}
for tn in TR[:6]:
    pl=stats('PL05',tn)
    for arm in ('B4s','B5','B6s','B4d'):
        try: b=stats(arm,tn)
        except (KeyError,AssertionError): continue
        tr[f'0.5 %|{tn}|{arm}']=dict(planner=pl,base=b,verdict=verdict(pl,b),dcost_pct=100*(pl['cost']-b['cost'])/b['cost'],dviol=pl['viol']-b['viol'])
for tn in TR[:6]:
    pl=stats('PL2',tn)
    for arm in ('B6d','B4d'):
        try: b=stats(arm,tn)
        except (KeyError,AssertionError): continue
        tr[f'2 %|{tn}|{arm}']=dict(planner=pl,base=b,verdict=verdict(pl,b),dcost_pct=100*(pl['cost']-b['cost'])/b['cost'],dviol=pl['viol']-b['viol'])
# ---- planner vs CR: 14 cells, flaps, J = cost + 3*flaps
ALPHA=3.0
pairs={}
for tn in TR:
    for pt,pa,ca in (('2 %','PL2','CR2'),('0.5 %','PL05','CR05')):
        try: pl=stats(pa,tn); cr=stats(ca,tn)
        except (KeyError,AssertionError): continue
        Jp=pl['cost']+ALPHA*pl['flaps']; Jc=cr['cost']+ALPHA*cr['flaps']
        pairs[f'{tn}|{pt}']=dict(planner=pl,cr=cr,verdict=verdict(pl,cr),dcost_pct=100*(pl['cost']-cr['cost'])/cr['cost'],
            flap_change_pct=(100*(pl['flaps']-cr['flaps'])/cr['flaps'] if cr['flaps'] else None),Jp=Jp,Jc=Jc,dJ_pct=100*(Jp-Jc)/Jc,
            J_cheaper=Jp<Jc,viol_not_more=pl['viol']<=cr['viol']+1e-9,flaps_lower=pl['flaps']<cr['flaps'])
sec=dict(alpha=ALPHA,n=len(pairs),J_cheaper=sum(p['J_cheaper'] for p in pairs.values()),viol_not_more=sum(p['viol_not_more'] for p in pairs.values()),
         flaps_lower=sum(p['flaps_lower'] for p in pairs.values()),
         J_dearer_cells={k:round(p['dJ_pct'],2) for k,p in pairs.items() if not p['J_cheaper']},
         viol_more_cells={k:round(p['planner']['viol']-p['cr']['viol'],2) for k,p in pairs.items() if not p['viol_not_more']},
         flap_change_range=[min(p['flap_change_pct'] for p in pairs.values()),max(p['flap_change_pct'] for p in pairs.values())],
         flaps_equal_cells=[k for k,p in pairs.items() if p['planner']['flaps']==p['cr']['flaps']])
out=dict(main=main,counts=counts,tr=tr,pairs=pairs,secondary=sec)
os.makedirs(f'{HERE}/out',exist_ok=True)
json.dump(out,open(f'{HERE}/out/same_target.json','w'),indent=1,default=str)
# ---- markdown
def fr(s): return f"{s['cost']:.1f} ({s['lo']:.0f}–{s['hi']:.0f})" if s['n']>1 else f"{s['cost']:.0f}"
L=['# same-target recount (rev. 4.3)\n']
for pt in ('2 %','0.5 %'):
    L.append(f'## planner {pt} vs same-target knobs\n\n| trace | baseline | planner cost / viol | baseline cost / viol | Δcost % | Δviol | verdict |\n|---|---|---|---|---|---|---|')
    for k,c in main[pt].items():
        tn,arm=k.split('|'); L.append(f"| {tn} | {NAME[arm]} (n={c['base']['n']}) | {fr(c['planner'])} / {c['planner']['viol']:.2f} | {fr(c['base'])} / {c['base']['viol']:.2f} | {c['dcost_pct']:+.2f} | {c['dviol']:+.2f} | {c['verdict']} |")
    L.append(f"\ncounts: {counts[pt]}\n")
L.append('## TR: cross-target / deployed-knob pairings\n\n| point | trace | baseline | planner | baseline | Δcost % | Δviol | verdict |\n|---|---|---|---|---|---|---|---|')
for k,c in tr.items():
    pt,tn,arm=k.split('|'); L.append(f"| {pt} | {tn} | {NAME[arm]} (n={c['base']['n']}) | {fr(c['planner'])} / {c['planner']['viol']:.2f} | {fr(c['base'])} / {c['base']['viol']:.2f} | {c['dcost_pct']:+.2f} | {c['dviol']:+.2f} | {c['verdict']} |")
L.append('\n## planner vs CR, 14 cells, J = cost + 3·flaps\n\n| cell | planner cost / viol / flaps | CR cost / viol / flaps | Δcost % | flap change % | J planner | J CR | ΔJ % | verdict |\n|---|---|---|---|---|---|---|---|---|')
for k,p in pairs.items():
    a,b=p['planner'],p['cr']; L.append(f"| {k} | {fr(a)} / {a['viol']:.2f} / {a['flaps']:.2f} | {fr(b)} / {b['viol']:.2f} / {b['flaps']:.2f} | {p['dcost_pct']:+.2f} | {p['flap_change_pct']:+.0f} | {p['Jp']:.1f} | {p['Jc']:.1f} | {p['dJ_pct']:+.2f} | {p['verdict']} |")
L.append(f"\nsecondary: {json.dumps(sec)}\n")
open(f'{HERE}/out/same_target.md','w').write('\n'.join(L)); print('\n'.join(L))
