# spec §4.114 item 3: A/B judgement. Uses rq_metrics.py's per-run functions (lines before GROUPS) unchanged; does not rewrite rq_metrics.csv.
import csv
src=open('/home/user/experiment/paper_out_new/rq_metrics.py').read(); src=src[:src.index('GROUPS=[')]
g={}; exec(src,g)
T='trace_ue_60min_v3_t6.json'
chk=g['metrics']('r404',T); ref=[r for r in csv.DictReader(open('/home/user/experiment/paper_out_new/rq/rq_metrics.csv')) if r['run']=='r404'][0]
print('check r404 alloc_vm', chk['alloc_vm'], 'csv', ref['alloc_vm'], 'slo', chk['slo'], ref['slo'])
AB={'B4c2':['r460','r465'],'B5c1':['r461','r463'],'B6':['r464','r466']}
ORIG={'B4c2':(58.33,1.67,1455.7),'B5c1':(59.33,0.67,1433.0),'B6':(60.00,0.0,1447.3)}   # §4.114 / rq_metrics.csv run means
rows=[]; allok=True
for a,rs in AB.items():
    ms=[g['metrics'](r,T) for r in rs]
    slo=sum(m['slo'] for m in ms)/len(ms); viol=60-slo; av=sum(m['alloc_vm'] for m in ms)/len(ms); bu=sum(m['burned'] for m in ms)/len(ms)
    os_,ov,oa=ORIG[a]
    i=abs(av-oa)/oa<=0.02; ii=abs(slo-os_)/60<=0.02; iii=viol>=ov-1e-9
    allok&=i and ii and iii
    rows.append((a,rs,[(m['slo'],m['alloc_vm'],m['burned']) for m in ms],slo,viol,av,bu,oa,100*(av/oa-1),os_,i,ii,iii))
print('| arm | runs (SLO/alloc_vm/burned) | A/B SLO | viol/run | alloc_vm | orig alloc_vm | Δ | orig SLO | (i) | (ii) | (iii) |')
for a,rs,per,slo,viol,av,bu,oa,d,os_,i,ii,iii in rows:
    print(f'| {a} | {per} | {slo:.2f} | {viol:.2f} | {av:.1f} | {oa:.1f} | {d:+.2f}% | {os_:.2f} | {i} | {ii} | {iii} |')
print('ALL (i)-(iii):', allok)
