#!/usr/bin/env python3
"""spec §4.136 item 2: t6/t7 per-trace per-slot (v8sim11 R38 off, r67band runner, own initial_fleet) for the listed knobs, against hardware (rq_metrics.csv;
B6 u=0.775 r498/r499 recomputed with rq_metrics.metrics). Output out/t6t7.json"""
import timeit  # noqa
import sys, os, json, csv, io, contextlib
Q='/home/user/experiment/qsim'; R=f'{Q}/r68unif'; E='/home/user/experiment'; sys.path.insert(0,Q); sys.path.insert(0,Q+'/r67band'); os.chdir(Q)
import run as RB
KN=["S4b","S4a","B4_3.75_300","B4_3.0_300","B5_4.0_L2","B5_3.5_L1","B6_0.775","B6_0.7"]
RB.CFG["B4_3.5_600"]=("B4",(3.5,600)); KN.append("B4_3.5_600")
sim={}
for tn in ("t6","t7"):
    ue=json.load(open(f"{E}/trace_ue_60min_v3_{tn}.json"))["ue"][:60]
    for k in KN:
        fam,key=RB.CFG[k]; ctl,st=RB.make(fam,key,ue); r=RB.run_ctl(ue,ctl,st); ab=r['alloc_by']
        sim[f"{tn}|{k}"]=dict(viol=60-int(r['slo']),alloc_vm=r['alloc_vm'],wk=ab['wk']/3,vy=ab['vy']/2,slot=ab['up']/0.8)
sys.path.insert(0,'/home/user/experiment/paper_out_new')
with contextlib.redirect_stdout(io.StringIO()):
    import rq_metrics as RQ
hw={}
GR={"S4b":"S4b","S4a":"S4a","B4c2 3.5/600 (deployed)":"B4c2","B5c1 4.0/L2 (deployed)":"B5c1","B6 0.70 (deployed)":"B6 u=0.70"}
rows=list(csv.DictReader(open('/home/user/experiment/paper_out_new/rq/rq_metrics.csv')))
for tn in ("t6","t7"):
    for lab,g in GR.items():
        rs=[r for r in rows if r['group'].startswith(f"MAIN {tn} {g}") and 'VOID' not in r['group']]
        if rs: hw[f"{tn}|{lab}"]=dict(runs=[r['run'] for r in rs],alloc_vm=[float(r['alloc_vm']) for r in rs],viol=[60-int(r['slo']) for r in rs],wk=[float(r['wk_min']) for r in rs],vy=[float(r['vy_min']) for r in rs],slot=[float(r['slot_min']) for r in rs])
for run in ("r498","r499"):
    with contextlib.redirect_stdout(io.StringIO()):
        m=RQ.metrics(run,"trace_ue_60min_v3_t6.json")
    hw.setdefault("t6|B6 0.775 (offline knob)",dict(runs=[],alloc_vm=[],viol=[],wk=[],vy=[],slot=[]))
    h=hw["t6|B6 0.775 (offline knob)"]; h['runs'].append(run); h['alloc_vm'].append(float(m['alloc_vm'])); h['viol'].append(60-int(m['slo'])); h['wk'].append(float(m.get('wk_min',0))); h['vy'].append(float(m.get('vy_min',0))); h['slot'].append(float(m.get('slot_min',0)))
json.dump(dict(sim=sim,hw=hw),open(f'{R}/out/t6t7.json','w'),indent=1)
for k,v in sim.items(): print("sim",k,{a:round(b,1) for a,b in v.items()})
for k,v in hw.items(): print("hw ",k,v)
