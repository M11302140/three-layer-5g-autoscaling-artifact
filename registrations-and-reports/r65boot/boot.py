# spec §4.112 D: run-level bootstrap of mean alloc_vm differences on t6/t7 (fixed trace, run-to-run uncertainty only)
import csv, numpy as np
rows=list(csv.DictReader(open('/home/user/experiment/paper_out_new/rq/rq_metrics.csv')))
G={'S4b':'S4b','v6':'v6','B4c2':'B4c2','B5c1':'B5c1 (q11)','B6':'B6 u=0.70'}
out=[]
for tr in ('t6','t7'):
    v={a:np.array([float(r['alloc_vm']) for r in rows if r['group']==f'MAIN {tr} {g}']) for a,g in G.items()}
    for a in ('B4c2','B5c1','B6','v6'):
        x,y=v['S4b'],v[a]; assert len(x)==3 and len(y)==3,(tr,a,len(x),len(y))
        rng=np.random.default_rng(20261021); B=10000
        d=np.array([rng.choice(x,3).mean()-rng.choice(y,3).mean() for _ in range(B)])
        obs=x.mean()-y.mean(); lo,hi=np.percentile(d,[2.5,97.5])
        out.append((tr,a,obs,obs/y.mean()*100,lo,hi,lo/y.mean()*100,hi/y.mean()*100))
print('| trace | S4b − arm | mean diff core-min (%) | 95 % run-bootstrap interval core-min (%) |\n|---|---|---|---|')
for tr,a,o,op,lo,hi,lp,hp in out: print(f'| {tr} | {a} | {o:+.1f} ({op:+.1f} %) | [{lo:+.1f}, {hi:+.1f}] ([{lp:+.1f}, {hp:+.1f}] %) |')
