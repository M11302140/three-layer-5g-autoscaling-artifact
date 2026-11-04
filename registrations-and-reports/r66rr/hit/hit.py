#!/usr/bin/env python3
"""R75 D2 fleet-shortage hit table (spec §4.125).
Prediction = the registered fleet-level prediction, i.e. the frozen v8sim10.sim_nest2 with the frozen λ (S4a 2.83/3.08, S4b 1.83/2.00),
whole-library Prior, start = own convergence, acct dispatch; deterministic, so re-running it reproduces the registered numbers
(checked against the registered violation counts below). A predicted violating minute = minute with simulated loss > 0.1 %.
Hardware = minutes of every valid S4a/S4b run classified 'fleet' (fleet shortage) by the B2 rule (classify_b2 = verbatim r63bf_rr code).
Alignment: scored minute index m of the run = trace minute m (both start at trace minute 0). exact: same minute; ±1: a predicted minute
within one minute. Per run: hit = hardware fleet minutes matched, miss = hardware fleet minutes not matched, false alarm = predicted
minutes with no matching hardware fleet minute; summed over the runs of the cell."""
import sys, json, csv, collections
Q='/home/user/experiment/qsim'; sys.path.insert(0,Q); sys.path.insert(0,Q+'/r66rr/hit')
import os; os.chdir(Q)
import v8sim10 as N, v8sim2 as S, v8sim7 as M, classify_b2 as C
E='/home/user/experiment'
lib=json.load(open(f'{Q}/prior_traces.json')); cfg=M.cfg_measured(); pr=S.Prior(lib,cfg)
LAM={"S4a":{"vy":2.83,"wk":2.83,"up":3.08},"S4b":{"vy":1.83,"wk":1.83,"up":2.00}}
REG={('S4a','t3'):3,('S4a','t4'):0,('S4a','t6'):0,('S4a','t7'):0,('S4a','t8'):1,('S4b','t3'):None,('S4b','t4'):None,('S4b','t6'):0,('S4b','t7'):0,('S4b','t8'):1}
for l in open(f'{Q}/v8_predict_t345_2026-10-07.txt'):
    f=l.split()
    if len(f)>3 and f[0] in ('S4a','S4b') and f[1] in ('t3','t4') and '/60' in f[3]: REG[(f[0],f[1])]=60-int(f[3].split('/')[0])
TRF={'t3':'t3','t4':'t4','t6':'t6','t7':'t7','t8':'t8'}
runs=collections.defaultdict(list)
for l in list(open(f'{E}/paper_out_new/valid_runs.tsv'))[1:]:
    r,t,a,_=l.rstrip('\n').split('\t')
    if a in ('S4a','S4b') and t in TRF: runs[(a,t)].append(r)
runs[('S4a','t8')]=['r471','r478']; runs[('S4b','t8')]=['r476','r500']
# consistency of the classifier with the stored B2 minutes (t3-t7)
b2=json.load(open(f'{Q}/r66rr/b2/results.json'))['B2_minutes']
stored=collections.defaultdict(dict)
for m in b2: stored[m['run']][m['min']]=m['new']
bad=[r for (a,t),rs in runs.items() if t!='t8' for r in rs if C.classify(r)!=stored.get(r,{})]
print('classifier vs stored B2 minutes (S-arm runs t3-t7):','identical' if not bad else f'DIFFERENT {bad}')
print('| arm | trace | runs | registered viol/run | re-run viol/run (check) | predicted minutes | hardware fleet-shortage minutes (all runs) | hit exact | miss exact | false alarm exact | hit ±1 | miss ±1 | false alarm ±1 | hardware violating minutes of other classes |')
print('|---|---|---|---|---|---|---|---|---|---|---|---|---|---|')
tot=collections.Counter()
for a in ('S4a','S4b'):
    for t in ('t3','t4','t6','t7','t8'):
        ue=json.load(open(f'{E}/trace_ue_60min_v3_{TRF[t]}.json'))['ue'][:60]
        r=N.sim_nest2(ue,cfg,pr,LAM[a]); P=[m for m in range(60) if r['pct'][m]>0.1]
        chk=(REG[(a,t)] is None) or (REG[(a,t)]==len(P))
        rs=runs[(a,t)]; c=collections.Counter(); hwF=[]; other=0
        for run in rs:
            cl=C.classify(run); F=sorted(m for m,k in cl.items() if k=='fleet'); other+=sum(1 for k in cl.values() if k!='fleet'); hwF.append((run,F))
            c['hit']+=sum(1 for m in F if m in P); c['miss']+=sum(1 for m in F if m not in P); c['fa']+=sum(1 for m in P if m not in F)
            c['hit1']+=sum(1 for m in F if any(abs(m-p)<=1 for p in P)); c['miss1']+=sum(1 for m in F if not any(abs(m-p)<=1 for p in P)); c['fa1']+=sum(1 for p in P if not any(abs(m-p)<=1 for m in F))
        tot.update(c)
        print(f"| {a} | {t} | {len(rs)} | {REG[(a,t)] if REG[(a,t)] is not None else 'n/a'} | {len(P)}{'' if chk else ' MISMATCH'} | {P} | {'; '.join(f'{x}: {F}' for x,F in hwF)} | {c['hit']} | {c['miss']} | {c['fa']} | {c['hit1']} | {c['miss1']} | {c['fa1']} | {other} |")
print(f"\ntotal: hit {tot['hit']} miss {tot['miss']} false alarm {tot['fa']} (exact); hit {tot['hit1']} miss {tot['miss1']} false alarm {tot['fa1']} (±1)")
