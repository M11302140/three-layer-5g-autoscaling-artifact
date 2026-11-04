#!/usr/bin/env python3
"""qsim/s5/predict.py (spec §4.124 G2 + registration): deployed S5 (mean p over six splits, rounded to 0.005; quantiles from the
whole library) on t1..t8 with nest2 (s5core.sim_s5, vmexist = alloc_vm and dispatch) and v8sim11 (v8sim11_s5.run_s5), start = own
convergence (start=None, the S-arm convention of all earlier registrations).
Usage: python3 s5/predict.py <variant> <pVM_a> <pUP_a> <pVM_b> <pUP_b>   -> prints table, writes out/predict_<variant>.json"""
import sys, os, json, time
Q='/home/user/experiment/qsim'; sys.path.insert(0,Q); sys.path.insert(0,Q+'/s5'); os.chdir(Q)
import s5core as C, v8sim11_s5 as W, v8sim7 as M
E='/home/user/experiment'
TR={'t1':'40','t2':'pm','t3':'t3','t4':'t4','t5':'t5','t6':'t6','t7':'t7','t8':'t8'}
variant=sys.argv[1]; Pa={'vy':float(sys.argv[2]),'wk':float(sys.argv[2]),'up':float(sys.argv[3])}; Pb={'vy':float(sys.argv[4]),'wk':float(sys.argv[4]),'up':float(sys.argv[5])}
lib=json.load(open(f'{Q}/prior_traces.json')); cfg=M.cfg_measured(); qp=C.QPrior(lib,cfg)
out={'time':time.strftime('%F %T'),'variant':variant,'S5a':Pa,'S5b':Pb,'rows':{}}
print(f"=== S5 predictions {out['time']} variant {variant}  S5a p {Pa['vy']}/{Pa['up']}  S5b p {Pb['vy']}/{Pb['up']}")
print("| arm | trace | nest2 SLO | nest2 viol | nest2 alloc_vm (vmexist) | nest2 dispatch | v8sim11 SLO | v8sim11 viol min | v8sim11 alloc_vm |\n|---|---|---|---|---|---|---|---|---|")
for arm,P in (('S5a',Pa),('S5b',Pb)):
    for tn,f in TR.items():
        ue=json.load(open(f"{E}/trace_ue_60min_v3_{f}.json"))["ue"][:60]
        rv=C.sim_s5(ue,cfg,qp,P,variant=variant,acct='vmexist'); rd=C.sim_s5(ue,cfg,qp,P,variant=variant,acct='dispatch')
        rs=W.run_s5(ue,P,variant=variant,prior=qp)
        out['rows'][f'{arm}|{tn}']=dict(nest2_slo=rv['slo'],nest2_alloc_vm=rv['alloc'],nest2_dispatch=rd['alloc'],v11_slo=rs['slo'],v11_viol=rs['viol'],v11_alloc_vm=rs['alloc_vm'])
        print(f"| {arm} | {tn} | {rv['slo']}/60 | {60-rv['slo']} | {rv['alloc']:.0f} | {rd['alloc']:.0f} | {rs['slo']}/60 | {rs['viol']} | {rs['alloc_vm']:.0f} |",flush=True)
json.dump(out,open(f'{Q}/s5/out/predict_{variant}.json','w'),indent=1,default=str)
r=out['rows']; g2=dict(t3=(60-r['S5b|t3']['nest2_slo']<=3 and 60-r['S5b|t3']['v11_slo']<=3),
    t8=(60-r['S5b|t8']['nest2_slo']<=1 and 60-r['S5b|t8']['v11_slo']<=2),
    t6t7=all(r[f'S5b|{t}'][k]==60 for t in ('t6','t7') for k in ('nest2_slo','v11_slo')))
print('G2 (registered thresholds: t3 <= 3 both sims; t8 <= 1 nest2 and <= 2 v8sim11; t6/t7 60/60 both):',g2,'->','PASS' if all(g2.values()) else 'FAIL')
