
import csv
R={(r['group'],r['run']):r for r in csv.DictReader(open('/home/user/experiment/paper_out_new/rq/rq_metrics.csv'))}
src=open('/home/user/experiment/paper_out_new/rq_metrics.py').read(); g={}; exec(src[:src.index('GROUPS=[')],g)
TR={t:f'trace_ue_60min_v3_{t}.json' for t in ('t3','t4','t6','t7')}
ARMS=['S4a','S4b','v6','B4c2','B5c1 (q11)','B6 u=0.70','B1']
REPL={('t4','S4a'):{'r300':'r502'},('t3','B6 u=0.70'):{'r383':'r503'}}
DROP={('t4','B6 u=0.70'):{'r316'},('t6','B6 u=0.70'):{'r407'}}
for t in TR:
    pts={}
    for a in ARMS:
        rs=[(gr,run) for (gr,run) in R if gr==f'MAIN {t} {a}']
        runs=[REPL.get((t,a),{}).get(run,run) for _,run in rs if run not in DROP.get((t,a),set())]
        ms=[g['metrics'](r,TR[t]) for r in runs]
        if not ms: continue
        pts[a]=(sum(60-m['slo'] for m in ms)/len(ms), sum(m['alloc_vm'] for m in ms)/len(ms), runs)
    print(f'== {t}');
    for a,(v,c,runs) in pts.items():
        dom=[b for b,(v2,c2,_) in pts.items() if b!=a and v2<=v and c2<=c and (v2<v or c2<c)]
        print(f'  {a:12s} {v:.2f} @ {c:7.1f} n={len(runs)} {runs} dominated_by={dom}')
