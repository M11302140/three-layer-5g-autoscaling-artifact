#!/usr/bin/env python3
"""spec §4.141 r73fill: judgement over the 22 valid runs (phase F / F-retry, class ok, p2/s_ledger.tsv).
Hardware metrics = paper_out_new/rq_metrics (alloc_vm, flaps, acts; violation minutes = 0-based minutes failing loss<=0.1 % & p99<=1 ms).
Predictions (a)(b)(c)(d) = r73fill/out/predict.json (registered 10-31). CR references = rq groups MAIN t3/t5/t7 S4b (2 %) / S4a (0.5 %);
planner t4/t8 references = r72hw/out/e.json. Start audit I1 = r70eq/audit.hw_start. Output out/f.json. Importing rq_metrics regenerates rq/rq_metrics.csv."""
import sys, os, json, csv, io, contextlib, numpy as np
Q='/home/user/experiment/qsim'; R=f'{Q}/r73fill'; E='/home/user/experiment'; P2=f'{E}/p2'
for p in (Q,Q+'/r67band',Q+'/r68unif',Q+'/s7',Q+'/r70eq',Q+'/r71fin',Q+'/r72hw',f'{E}/paper_out_new'): sys.path.insert(0,p)
os.chdir(Q)
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    import rq_metrics as RQ
    import audit as AU
TRJ=lambda tn: f"trace_ue_60min_v3_{tn}.json"
led=[r for r in csv.DictReader(open(f"{P2}/s_ledger.tsv"),delimiter="\t") if r['phase'] in ('F','F-retry') and r['class']=='ok']
assert len(led)==22, len(led)
def viol(run):
    rows=list(csv.DictReader(open(f"{P2}/trace_v7_{run}.csv")))[:60]
    return [i for i,r in enumerate(rows) if not (RQ.f(r["e2e_pct"])<=0.1 and RQ.f(r["lat_p99_us"],1e9)<=1000)]
def hwrec(run,tn,arm,phase):
    with contextlib.redirect_stdout(io.StringIO()):
        m=RQ.metrics(run,TRJ(tn)); st=AU.hw_start(run)
    return dict(run=run,phase=phase,trace=tn,arm=arm,slo=m['slo'],viol=viol(run),alloc_vm=float(m['alloc_vm']),flaps=m['flaps'],
                acts=m['acts_vy']+m['acts_wk']+m['acts_up'],acts_vy=m['acts_vy'],acts_wk=m['acts_wk'],acts_up=m['acts_up'],
                wk_min=m['wk_min'],vy_min=m['vy_min'],slot_min=m['slot_min'],burned=m['burned'],p99max=m['p99max'],worst=m['worst'],start=list(st))
HW={r['run']:hwrec(r['run'],r['block'],r['arm'],r['phase']) for r in led}
CRR={('t3','S4b'):['r363','r369','r374'],('t3','S4a'):['r360','r372','r377'],('t5','S4b'):['r333'],('t5','S4a'):['r330'],('t7','S4b'):['r433','r439','r444'],('t7','S4a'):['r430','r442','r447']}
CR={f"{k[0]}|{k[1]}":[hwrec(run,k[0],k[1],'MAIN') for run in v] for k,v in CRR.items()}
E72=json.load(open(f'{Q}/r72hw/out/e.json'))['hw']
PL={f"{tn}|{arm}":[E72[k] for k in sorted(E72) if E72[k]['trace']==tn and E72[k]['arm']==arm] for tn in ('t4','t8') for arm in ('S4p2','S4p05')}
PRED=json.load(open(f'{R}/out/predict.json'))
def mean(xs): return float(np.mean(xs))
def stats(rs):
    c=[x['alloc_vm'] for x in rs]; v=[len(x['viol']) for x in rs]; fl=[x['flaps'] for x in rs]
    return dict(runs=[x['run'] for x in rs],n=len(rs),cost=mean(c),costs=c,lo=min(c),hi=max(c),viol=mean(v),viols=v,vlo=min(v),vhi=max(v),viol_lists=[x['viol'] for x in rs],
                flaps=mean(fl),flaps_each=fl,slo=[x['slo'] for x in rs],acts=mean([x['acts'] for x in rs]),start=[x.get('start') for x in rs])
def verdict(a,b):
    """Table X rule, from a's side: cost counts only when the run ranges do not overlap; violation difference counts only when >= 1 min/run"""
    cc=(a['hi']<b['lo']) or (b['hi']<a['lo']); cs=0 if not cc else (-1 if a['cost']<b['cost'] else 1)
    dv=a['viol']-b['viol']; vs=0 if abs(dv)<1-1e-9 else (-1 if dv<0 else 1)
    if cs==0 and vs==0: return 'equal'
    if cs<=0 and vs<=0: return 'dominates'
    if cs>=0 and vs>=0: return 'dominated'
    return 'trade-off'
def weak(a,b):
    """Table 1 rule: cost not higher, violations not more, at least one strictly better (two-column: cost/viol; three-column: also flaps)"""
    le=a['cost']<=b['cost'] and a['viol']<=b['viol']
    return dict(two=le and (a['cost']<b['cost'] or a['viol']<b['viol']),three=le and (a['cost']<b['cost'] or a['viol']<b['viol'] or a['flaps']<b['flaps']),
                cost_lower=a['cost']<b['cost'],viol_lower=a['viol']<b['viol'],viol_equal=abs(a['viol']-b['viol'])<1e-9,flaps_lower=a['flaps']<b['flaps'],flaps_equal=a['flaps']==b['flaps'])
cell=lambda tn,arm: [HW[k] for k in sorted(HW) if HW[k]['trace']==tn and HW[k]['arm']==arm]
out=dict(hw=HW,cells={},cr={k:stats(v) for k,v in CR.items()},planner_ref={k:stats(v) for k,v in PL.items()},A={},B={},C={},I1=[],fidelity={})
# ---- 10 cells: stats + predictions
for key in PRED:
    tn,arm=key.split('|'); rs=cell(tn,arm); assert rs,(key)
    st=stats(rs); pv=PRED[key]
    st['pred']={}
    for v in 'abcd':
        p=pv[v]
        if p is None: st['pred'][v]=None; continue
        st['pred'][v]=dict(alloc_vm=p['alloc_vm'],viol=p['viol'],flaps=p['flaps'],err_pct=100*(p['alloc_vm']-st['cost'])/st['cost'],
                           err_each=[100*(p['alloc_vm']-c)/c for c in st['costs']])
    st['reg_start']=pv['start']; st['own_start']=pv.get('own_initial_fleet',pv['start']); st['L']=pv.get('L')
    out['cells'][key]=st
# ---- (A) t3/t5/t7 vs CR, Table X rule, against the registered expectation (§4.141 item 3)
EXP={('t3','S4p2'):'trade-off',('t3','S4p05'):'trade-off',('t5','S4p2'):'equal',('t5','S4p05'):'equal',('t7','S4p2'):'dominates',('t7','S4p05'):'dominates'}
for (tn,arm),exp in EXP.items():
    a=out['cells'][f"{tn}|{arm}"]; b=out['cr'][f"{tn}|{'S4b' if arm=='S4p2' else 'S4a'}"]
    vd=verdict(a,b); out['A'][f"{tn}|{arm}"]=dict(verdict=vd,expected=exp,consistent=(vd==exp),planner=dict(cost=a['cost'],range=[a['lo'],a['hi']],viol=a['viol'],flaps=a['flaps']),
                                               cr=dict(cost=b['cost'],range=[b['lo'],b['hi']],viol=b['viol'],flaps=b['flaps']),dcost_pct=100*(a['cost']-b['cost'])/b['cost'],dviol=a['viol']-b['viol'],weak=weak(a,b))
# (iii) same-target baselines on t4/t8 vs the planner (verdict from the planner's side)
EXP3={('t4','B4A_375_300','S4p2'):'trade-off',('t4','B6c5_h','S4p2'):'trade-off',('t4','B4A_375_300','S4p05'):'equal|dominates',('t4','B6c5_h','S4p05'):'equal|dominates',
      ('t8','B6c5_h','S4p2'):'trade-off',('t8','B6c5_h','S4p05'):'trade-off',('t8','B4A_375_300','S4p2'):None,('t8','B4A_375_300','S4p05'):None}
out['A3']={}
for (tn,b_arm,p_arm),exp in EXP3.items():
    a=out['planner_ref'][f"{tn}|{p_arm}"]; b=out['cells'][f"{tn}|{b_arm}"]; vd=verdict(a,b)
    out['A3'][f"{tn}|{b_arm}|vs {p_arm}"]=dict(verdict=vd,expected=exp,consistent=(None if exp is None else vd in exp.split('|')),planner=dict(cost=a['cost'],range=[a['lo'],a['hi']],viol=a['viol'],flaps=a['flaps']),
                                               baseline=dict(cost=b['cost'],range=[b['lo'],b['hi']],viol=b['viol'],flaps=b['flaps']),planner_minus_pct=100*(a['cost']-b['cost'])/b['cost'],dviol=a['viol']-b['viol'])
# ---- (B) ±2 % hits per version: per cell (10; (b) 8) and per run (22; (b) 18)
for v in 'abcd':
    cells=[(k,c['pred'][v]) for k,c in out['cells'].items() if c['pred'][v] is not None]
    out['B'][v]=dict(cell_within2=sum(1 for k,p in cells if abs(p['err_pct'])<=2),cell_n=len(cells),
                     run_within2=sum(1 for k,p in cells for e in p['err_each'] if abs(e)<=2),run_n=sum(len(p['err_each']) for k,p in cells),
                     cell_err={k:p['err_pct'] for k,p in cells},max_abs_cell_err=max(abs(p['err_pct']) for k,p in cells))
# ---- (C) weak dominance over the paired cells (Table 1 rule): six known (r72) + t3/t5/t7
S4REF={('t4','S4p2'):dict(cost=1420.0,viol=3.33,flaps=1.0),('t4','S4p05'):dict(cost=1449.3,viol=1.0,flaps=2.0),('t6','S4p2'):dict(cost=1390.3,viol=0,flaps=6.0),('t6','S4p05'):dict(cost=1435.0,viol=0,flaps=9.33),
       ('t8','S4p2'):dict(cost=1054.5,viol=2.5,flaps=9.0),('t8','S4p05'):dict(cost=1107.5,viol=1.5,flaps=11.5)}
PREF={('t4','S4p2'):dict(cost=1394.0,viol=2.0,flaps=0),('t4','S4p05'):dict(cost=1447.7,viol=0,flaps=2.0),('t6','S4p2'):dict(cost=1362.0,viol=0,flaps=2.0),('t6','S4p05'):dict(cost=1424.0,viol=0,flaps=2.0),
      ('t8','S4p2'):dict(cost=1045.7,viol=2.33,flaps=2.33),('t8','S4p05'):dict(cost=1100.0,viol=0,flaps=5.0)}
for k in S4REF: out['C'][f"{k[0]}|{k[1]}"]=dict(known=True,**weak(PREF[k],S4REF[k]))
for (tn,arm) in EXP: out['C'][f"{tn}|{arm}"]=dict(known=False,**out['A'][f"{tn}|{arm}"]['weak'])
out['C_summary']=dict(n_two=sum(1 for c in out['C'].values() if c['two']),n_three=sum(1 for c in out['C'].values() if c['three']),cells=len(out['C']),
                      n_two_no_t5=sum(1 for k,c in out['C'].items() if c['two'] and not k.startswith('t5')),n_three_no_t5=sum(1 for k,c in out['C'].items() if c['three'] and not k.startswith('t5')))
# ---- I1: hardware minute-0 fleet (slots/VyOS/workers) vs registered start and own initial_fleet
for k in sorted(HW):
    h=HW[k]; c=out['cells'][f"{h['trace']}|{h['arm']}"]
    out['I1'].append(dict(run=k,trace=h['trace'],arm=h['arm'],hw=h['start'],reg=c['reg_start'],own=c['own_start'],same_reg=h['start']==list(c['reg_start']),same_own=h['start']==list(c['own_start'])))
out['I1_summary']=dict(same_reg=sum(1 for x in out['I1'] if x['same_reg']),same_own=sum(1 for x in out['I1'] if x['same_own']),n=len(out['I1']))
# ---- fidelity, version (a), 10 new cells
fa={k:c['pred']['a']['err_pct'] for k,c in out['cells'].items()}
out['fidelity']=dict(new_cells=len(fa),new_within2=sum(1 for e in fa.values() if abs(e)<=2),errs=fa,outside=[k for k,e in fa.items() if abs(e)>2],
                     planner_cells=6,planner_max_abs=max(abs(e) for k,e in fa.items() if 'S4p' in k),total_cells=35+len(fa),total_within2=33+sum(1 for e in fa.values() if abs(e)<=2))
json.dump(out,open(f"{R}/out/f.json","w"),indent=1,default=str)
# ---- print
def fmt(st):
    v=f"{st['viol']:.2f}" if st['viol']%1 else f"{int(st['viol'])}"
    if st['n']>1 and st['vhi']>st['vlo']: v+=f" ({st['vlo']}–{st['vhi']})"
    c=f"{st['cost']:.0f}"
    if st['n']>1: c+=f" ({st['lo']:.0f}–{st['hi']:.0f})"
    return f"{v} / {c}"
print("== cells (viol/run (range) / alloc_vm (range)); flaps each; viol lists; starts hw vs reg/own; pred errs a/b/c/d")
for k,c in out['cells'].items():
    print(k,c['runs'],fmt(c),'flaps',c['flaps_each'],'viol',c['viol_lists'],'start',c['start'],'reg',c['reg_start'],'own',c['own_start'],{v:(round(c['pred'][v]['err_pct'],2) if c['pred'][v] else None) for v in 'abcd'})
print("== CR refs"); [print(k,fmt(v),'flaps',v['flaps_each'],'viol',v['viol_lists']) for k,v in out['cr'].items()]
print("== (A)"); [print(k,'verdict',a['verdict'],'expected',a['expected'],'consistent',a['consistent'],f"dcost {a['dcost_pct']:+.2f}% dviol {a['dviol']:+.2f} flaps {a['planner']['flaps']:.2f} vs {a['cr']['flaps']:.2f}",'ranges',a['planner']['range'],a['cr']['range']) for k,a in out['A'].items()]
print("== (iii)"); [print(k,'verdict(planner side)',a['verdict'],'expected',a['expected'],'consistent',a['consistent'],f"planner-baseline {a['planner_minus_pct']:+.2f}% dviol {a['dviol']:+.2f}",'ranges',a['planner']['range'],a['baseline']['range'],'flaps',a['planner']['flaps'],a['baseline']['flaps']) for k,a in out['A3'].items()]
print("== (B)"); [print(v,b['cell_within2'],'/',b['cell_n'],'cells;',b['run_within2'],'/',b['run_n'],'runs; max|cell err|',round(b['max_abs_cell_err'],2)) for v,b in out['B'].items()]
print("== (C)",out['C_summary']); [print(k,c) for k,c in out['C'].items()]
print("== I1",out['I1_summary']); [print(x) for x in out['I1'] if not x['same_own'] or not x['same_reg']]
print("== fidelity",{k:v for k,v in out['fidelity'].items() if k!='errs'})
