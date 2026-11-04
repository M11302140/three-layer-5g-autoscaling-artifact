#!/usr/bin/env python3
"""spec §4.140 E: judgement over the 38 hardware runs (C r530-r547, D r560-r581 valid rows of p2/s_ledger.tsv).
Hardware metrics = paper_out_new/rq_metrics (alloc_vm, flaps, acts, violation minutes = rows failing loss<=0.1 & p99<=1000, 0-based minute).
Predictions: (a)(b)(c) r71fin/out/predict.json, (d) r72hw/out/dver.json; baselines (d)=(a). Start audit I1 = r70eq/audit.hw_start.
HPA prefill = r70eq/audit.CtlB4P semantics applied to the A-group B5 controller (RB.make). Output out/e.json"""
import sys, os, json, csv, io, contextlib, numpy as np
Q='/home/user/experiment/qsim'; R=f'{Q}/r72hw'; E='/home/user/experiment'; P2=f'{E}/p2'
for p in (Q,Q+'/r67band',Q+'/r68unif',Q+'/s7',Q+'/r70eq',Q+'/r71fin',R,f'{E}/paper_out_new'): sys.path.insert(0,p)
os.chdir(Q)
import v8sim11 as V, run as RB, fine as F
with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
    import rq_metrics as RQ
    import audit as AU
TRJ=lambda tn: f"trace_ue_60min_v3_{tn}.json"
def ue_of(tn): return json.load(open(f"{E}/{TRJ(tn)}"))["ue"][:60]
# ---- ledger
led=[r for r in csv.DictReader(open(f"{P2}/s_ledger.tsv"),delimiter="\t") if r['run']>='r530' and r['class']=='ok']
assert len(led)==38, len(led)
def viol(run):
    rows=list(csv.DictReader(open(f"{P2}/trace_v7_{run}.csv")))[:60]
    return [i for i,r in enumerate(rows) if not (RQ.f(r["e2e_pct"])<=0.1 and RQ.f(r["lat_p99_us"],1e9)<=1000)]
HW={}
for r in led:
    with contextlib.redirect_stdout(io.StringIO()):
        m=RQ.metrics(r['run'],TRJ(r['block']))
    HW[r['run']]=dict(run=r['run'],phase=r['phase'],trace=r['block'],arm=r['arm'],slo=m['slo'],viol=viol(r['run']),alloc_vm=float(m['alloc_vm']),flaps=m['flaps'],
                      acts=m['acts_vy']+m['acts_wk']+m['acts_up'],acts_vy=m['acts_vy'],acts_wk=m['acts_wk'],acts_up=m['acts_up'],
                      wk_min=m['wk_min'],vy_min=m['vy_min'],slot_min=m['slot_min'],burned=m['burned'],p99max=m['p99max'],worst=m['worst'],start=AU.hw_start(r['run']))
def cell(tn,arm): return [HW[k] for k in sorted(HW) if HW[k]['trace']==tn and HW[k]['arm']==arm]
def mean(xs): return float(np.mean(xs))
PRED=json.load(open(f"{Q}/r71fin/out/predict.json")); DV=json.load(open(f"{R}/out/dver.json"))['pred']
S4REF={("t4","2"):dict(cost=1420.0,fl=1.0,viol=[[20,21,49,50],[20,21],[20,21,49,50]]),("t4","05"):dict(cost=1449.3,fl=2.0,viol=[[],[20],[20,21]]),
       ("t6","2"):dict(cost=1390.3,fl=6.0,viol=[[],[],[]]),("t6","05"):dict(cost=1435.0,fl=9.33,viol=[[],[],[]]),
       ("t8","2"):dict(cost=1054.5,fl=9.0,viol=[[20,21],[20,21,22]]),("t8","05"):dict(cost=1107.5,fl=11.5,viol=[[20],[20,21]])}
def majority(vs):
    n=len(vs); from collections import Counter
    c=Counter(m for v in vs for m in set(v)); return sorted(m for m,k in c.items() if k>=2) if n>=2 else sorted(vs[0])
out=dict(hw=HW,C={},endpoints={},D={},I1=[],prefill=[])
# ---- C cells
pooled=0.0; percell={}
for tn in ("t4","t6","t8"):
    for g,arm in (("2","S4p2"),("05","S4p05")):
        rs=cell(tn,arm); assert len(rs)==3,(tn,arm,len(rs))
        pv=PRED['s4p'][f"{tn}|{g}|S4p"]; d=DV[f"{tn}|{arm}"]
        preds={'a':pv['a'],'b':pv['b'],'c':pv['c'],'d':d}
        hwc=mean([x['alloc_vm'] for x in rs]); hwf=mean([x['flaps'] for x in rs]); pooled+=hwf
        thr=0.5*S4REF[(tn,g)]['fl']
        c=dict(runs=[x['run'] for x in rs],hw_cost=hwc,hw_costs=[x['alloc_vm'] for x in rs],hw_flaps=hwf,hw_flaps_each=[x['flaps'] for x in rs],hw_acts=mean([x['acts'] for x in rs]),
               hw_viol=[x['viol'] for x in rs],hw_major=majority([x['viol'] for x in rs]),hw_slo=[x['slo'] for x in rs],thr=thr,percell_pass=hwf<=thr+1e-9,
               s4_hw_cost=S4REF[(tn,g)]['cost'],s4_hw_flaps=S4REF[(tn,g)]['fl'],
               pred={k:dict(alloc_vm=v['alloc_vm'],viol=v['viol'],flaps=v['flaps'],err_pct=100*(v['alloc_vm']-hwc)/hwc,viol_match=sorted(v['viol'])==majority([x['viol'] for x in rs]),
                            symdiff=len(set(v['viol'])^set(majority([x['viol'] for x in rs])))) for k,v in preds.items()},
               hw_start=[x['start'] for x in rs],sim_start=pv['start'],
               hw_layer_min=[mean([x[k] for x in rs]) for k in ('wk_min','vy_min','slot_min')])
        out['C'][f"{tn}|{g}"]=c
out['endpoints']['i']=dict(pooled=pooled,threshold=19.4,pooled_pass=pooled<=19.4,percell_pass_k=sum(1 for c in out['C'].values() if c['percell_pass']),
                           pred_pooled={k:sum(c['pred'][k]['flaps'] for c in out['C'].values()) for k in 'abcd'})
t42=out['C']['t4|2']
out['endpoints']['ii']=dict(viol=t42['hw_viol'],has_49_50=[bool({49,50}&set(v)) for v in t42['hw_viol']],major=t42['hw_major'],
                            match={k:t42['pred'][k]['viol_match'] for k in 'abcd'},symdiff={k:t42['pred'][k]['symdiff'] for k in 'abcd'},
                            s4b_hw_major=majority(S4REF[("t4","2")]['viol']))
out['endpoints']['iii']=dict(within2={k:sum(1 for c in out['C'].values() if abs(c['pred'][k]['err_pct'])<=2) for k in 'abcd'},
                             errs={k:{cn:c['pred'][k]['err_pct'] for cn,c in out['C'].items()} for k in 'abcd'})
out['endpoints']['t8_ratio']=dict(hw={g:out['C'][f"t8|{g}"]['hw_cost']/S4REF[("t8",g)]['cost'] for g in ("2","05")},
                                  pred_a={"2":1050/1041,"05":1096/1085},pred_b={"2":1.0221,"05":1.0168})
# ---- D generalisation
ARMS=["S4p2","S4b","B4A_375_300","B5c1_slo","B6c5_h"]; PK={"S4p2":"S4p","S4b":"S4b","B4A_375_300":"A:B4_3.75_300","B5c1_slo":"A:B5_4.0_L2","B6c5_h":"A:B6_0.775"}
for tn in ("t11","t12"):
    ue=ue_of(tn); dd={}
    for arm in ARMS:
        rs=cell(tn,arm); assert len(rs)==2,(tn,arm,len(rs))
        pa=PRED['t1112'][tn]['arms'][PK[arm]]; pdd=DV.get(f"{tn}|{arm}",pa)
        hwc=mean([x['alloc_vm'] for x in rs])
        dd[arm]=dict(runs=[x['run'] for x in rs],hw_cost=hwc,hw_costs=[x['alloc_vm'] for x in rs],hw_flaps=mean([x['flaps'] for x in rs]),hw_flaps_each=[x['flaps'] for x in rs],
                     hw_viol=[x['viol'] for x in rs],hw_slo=[x['slo'] for x in rs],hw_acts=mean([x['acts'] for x in rs]),hw_start=[x['start'] for x in rs],
                     pred_a=dict(alloc_vm=pa['alloc_vm'],viol=pa['viol'],flaps=pa['flaps'],err_pct=100*(pa['alloc_vm']-hwc)/hwc),
                     pred_d=dict(alloc_vm=pdd['alloc_vm'],viol=pdd['viol'],flaps=pdd['flaps'],err_pct=100*(pdd['alloc_vm']-hwc)/hwc))
    s=dd['S4p2']
    for arm in ARMS[1:]:
        dd[arm]['s4p_minus_pct']=100*(s['hw_cost']-dd[arm]['hw_cost'])/dd[arm]['hw_cost']; dd[arm]['s4p_flap_diff']=s['hw_flaps']-dd[arm]['hw_flaps']
        dd[arm]['pred_s4p_minus_pct']=100*(s['pred_a']['alloc_vm']-dd[arm]['pred_a']['alloc_vm'])/dd[arm]['pred_a']['alloc_vm']
    out['D'][tn]=dd
# ---- I1 (38 starts) + hw-start / prefill recomputation for A-group baselines on t11/t12
def sim_start(tn,arm,ue):
    if arm=="S4p2": return tuple(int(x) for x in V.initial_fleet("S",ue[0],L={"vy":1.5,"wk":1.5,"up":1.92}))
    if arm=="S4p05": return tuple(int(x) for x in V.initial_fleet("S",ue[0],L={"vy":2.33,"wk":2.33,"up":3.33}))
    if arm=="S4b": return tuple(int(x) for x in V.initial_fleet("S4b",ue[0]))
    fam,key=RB.CFG[{"B4A_375_300":"B4_3.75_300","B5c1_slo":"B5_4.0_L2","B6c5_h":"B6_0.775"}[arm]]; return tuple(int(x) for x in RB.make(fam,key,ue)[1])
for k in sorted(HW):
    h=HW[k]; ss=sim_start(h['trace'],h['arm'],ue_of(h['trace']))
    out['I1'].append(dict(run=k,trace=h['trace'],arm=h['arm'],hw=list(h['start']),sim=list(ss),same=tuple(h['start'])==ss))
class Pre:
    """HPA prefill wrapper (audit.CtlB4P semantics) around any CtlB4 instance"""
    def __init__(s,c): s.c=c; s._pf=False
    def tick(s,ph,ob):
        if not s._pf: s._pf=True; n=ob["ready_up"]; s.c.hpa.hist=[(ph.t-600+30*j,n) for j in range(20)]
        return s.c.tick(ph,ob)
for tn in ("t11","t12"):
    ue=ue_of(tn)
    for arm,name in (("B5c1_slo","B5_4.0_L2"),("B4A_375_300","B4_3.75_300"),("B6c5_h","B6_0.775")):
        fam,key=RB.CFG[name]; rs=cell(tn,arm); hwc=mean([x['alloc_vm'] for x in rs])
        orig=F.row(RB.run_ctl(ue,RB.make(fam,key,ue)[0],RB.make(fam,key,ue)[1]))
        hs=[F.row(RB.run_ctl(ue,RB.make(fam,key,ue)[0],tuple(x['start']))) for x in rs]
        rec=dict(trace=tn,arm=arm,hw=hwc,ps_orig=orig['alloc_vm'],ps_hwstart=mean([x['alloc_vm'] for x in hs]),ps_hwstart_viol=[x['viol'] for x in hs],ps_hwstart_flaps=[x['flaps'] for x in hs])
        if fam in ("B4","B5"):
            pf=[F.row(RB.run_ctl(ue,Pre(RB.make(fam,key,ue)[0]),tuple(x['start']))) for x in rs]
            rec.update(ps_hwstart_prefill=mean([x['alloc_vm'] for x in pf]),ps_hwstart_prefill_viol=[x['viol'] for x in pf],ps_hwstart_prefill_flaps=[x['flaps'] for x in pf])
        out['prefill'].append(rec); print(tn,arm,rec,flush=True)
json.dump(out,open(f"{R}/out/e.json","w"),indent=1,default=str)
print(json.dumps(out['endpoints'],indent=1))
for k,c in out['C'].items(): print(k,c['runs'],'cost',round(c['hw_cost'],1),c['hw_costs'],'flaps',c['hw_flaps_each'],'viol',c['hw_viol'],'start',c['hw_start'],c['sim_start'],{v:round(c['pred'][v]['err_pct'],2) for v in 'abcd'})
for tn,dd in out['D'].items():
    for arm,d in dd.items(): print(tn,arm,d['runs'],round(d['hw_cost'],1),d['hw_costs'],'fl',d['hw_flaps_each'],'viol',d['hw_viol'],'start',d['hw_start'],'pred_a',round(d['pred_a']['alloc_vm'],1),round(d['pred_a']['err_pct'],2),'pred_d',round(d['pred_d']['alloc_vm'],1))
print("I1 same:",sum(1 for x in out['I1'] if x['same']),"/",len(out['I1']))
