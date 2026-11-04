#!/usr/bin/env python3
"""spec §4.140 A (supplement): the pre-hardware equivalence standard used for S4 / S6 / S7R (equiv_compare.py logic, gate of equiv_gate.sh):
daemon closed-loop timeline (hhro-daemon-s4p testdata/equiv_s4p, TestDecisionEquivalenceDumpS4p) vs qsim nest2 on the same scenario,
(minute, action) multiset of the six core actions. S4a/S4b -> v8sim10.sim_nest2 (frozen, as equiv_compare.py); S4' -> r68unif nest2gen.sim_s7
variant independent_full, w 1600, S7Prior (= the r68unif calibration simulator). Gate: exact / fail scenarios 0 differing cells, pps <= 2."""
import timeit  # noqa
import sys, os, json, glob, collections
Q='/home/user/experiment/qsim'; sys.path[:0]=[Q,Q+'/s7',Q+'/r68unif']; os.chdir(Q)
import v8sim2 as S, v8sim7 as M, v8sim10 as Q2, s7core as C7, nest2gen as G
lib=json.load(open(f'{Q}/prior_traces.json')); cfg=M.cfg_measured(); pr=S.Prior(lib,cfg); p7=C7.S7Prior(lib,cfg)
ACT={('out','up'):'SCALE_OUT_UP',('in','up'):'SCALE_IN_UP',('out','vy'):'DEPLOY_VYOS',('in','vy'):'DELETE_VYOS',('out','wk'):'CREATE_WORKER',('in','wk'):'DELETE_WORKER'}
CORE=set(ACT.values())
LAM={'S4b':{'vy':1.83,'wk':1.83,'up':2.00},'S4a':{'vy':2.83,'wk':2.83,'up':3.08},'S4p2':{'vy':1.5,'wk':1.5,'up':1.92},'S4p05':{'vy':2.33,'wk':2.33,'up':3.33}}
D='/home/user/hhro-daemon-s4p/internal/hbo/testdata/equiv_s4p'
out=[]; summ=collections.defaultdict(lambda:[0,0]); bad=[]
for fn in sorted(glob.glob(f'{D}/*.json')):
    name=os.path.basename(fn)[:-5]; grp,tn,tag=name.split('_',2); r=json.load(open(fn))
    ue=json.load(open(f'/home/user/hhro-daemon-s4p/internal/hbo/testdata/s4ptraces/{tn}.json'))['ue']
    ds=30 if '_d30' in tag else None
    if grp.startswith('S4p'): q=G.sim_s7(ue,cfg,p7,LAM[grp],drain_sec=ds,variant='independent_full',w=1600)
    else: q=Q2.sim_nest2(ue,cfg,pr,LAM[grp],drain_sec=ds)
    cq=collections.Counter((int(t)//60,ACT[(a,k)]) for t,a,k in q['ev'] if (a,k) in ACT)
    cd=collections.Counter((int(e['t'])//60,e['act']) for e in r['events'] if e['act'] in CORE)
    keys=sorted(set(cq)|set(cd)); nd=sum(1 for k in keys if cq.get(k,0)!=cd.get(k,0))
    lim=2 if tag.startswith('pps') else 0; ok=nd<=lim
    summ[(grp,tag)][0]+=1; summ[(grp,tag)][1]+=nd
    if not ok: bad.append(name)
    line=f"=== {name}: qsim alloc {q['alloc']:.0f} SLO {q['slo']} | daemon alloc {r['alloc']:.0f} SLO {r['slo']} | differing (min,act) cells {nd} {'ok' if ok else 'FAIL'}"
    print(line); out.append(line)
    shown=0
    for k in keys:
        if cq.get(k,0)!=cd.get(k,0) and shown<6: out.append(f"   min{k[0]:2d} {k[1]:14s} qsim {cq.get(k,0)} daemon {cd.get(k,0)}"); shown+=1
out.append("summary (group, scenario): traces, differing cells total"); [out.append(f"  {k}: {v[0]}, {v[1]}") for k,v in sorted(summ.items())]
out.append(f"GATE: {'PASS' if not bad else 'FAIL'} ({len(bad)} failing: {bad})")
open(f'{Q}/r72hw/out/equiv_nest2.txt','w').write("\n".join(out)+"\n"); print("\n".join(out[-(len(summ)+2):]))
