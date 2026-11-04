
import csv,sys,statistics as st,importlib.util
src=open('/home/user/experiment/paper_out_new/rq_metrics.py').read(); g={}; exec(src[:src.index('GROUPS=[')],g)
M=lambda r,t: g['metrics'](r,TR[t])
TR={t:f'trace_ue_60min_v3_{t}.json' for t in ('t3','t4','t6','t7','t8')}
au={}; exec(open('/home/user/experiment/qsim/r66audit/audit.py').read().split('LED=[')[0],au)
print('## session 稽核(中位數判準)')
for r in ('r503','r504','r505'): print(r, au['audit'](r))
def stat(runs,t):
    ms=[M(r,t) for r in runs]; return ms,sum(60-m['slo'] for m in ms)/len(ms),sum(m['alloc_vm'] for m in ms)/len(ms)
RQ=list(csv.DictReader(open('/home/user/experiment/paper_out_new/rq/rq_metrics.csv')))
def grp(name): rs=[r for r in RQ if r['group']==name]; return sum(60-int(r['slo']) for r in rs)/len(rs), sum(float(r['alloc_vm']) for r in rs)/len(rs), [r['run'] for r in rs]
print('\n## H(B6c5_h u=0.775)vs S4b')
for t,runs,s4b in (('t3',['r493','r505'],'MAIN t3 S4b'),('t6',['r498','r499'],'MAIN t6 S4b')):
    ms,v,a=stat(runs,t); sv,sa,sr=grp(s4b); dc=100*(a/sa-1); dv=v-sv
    vd='(a) same cost level' if abs(dc)<=2 and abs(dv)<=2 else ('(b) S4b cheaper' if dc>2 else ('(c) baseline cheaper' if dc<-2 else '(a/边界) cost within 2% but Δviol>2'))
    print(t,[(r,m['slo'],m['alloc_vm'],m['burned']) for r,m in zip(runs,ms)],f'H viol/run {v:.2f} alloc {a:.1f} | S4b {sr} viol {sv:.2f} alloc {sa:.1f} | Δcost {dc:+.2f}% Δviol {dv:+.2f} → {vd}')
print('\n## t8 G')
T8={'S4a':['r471','r478'],'S4b':['r476','r500'],'v6':['r475','r479'],'B6':['r474','r504']}
res={}
for arm,runs in T8.items():
    ms,v,a=stat(runs,'t8'); res[arm]=(v,a,ms)
    print(arm,[(r,m['slo'],m['alloc_vm'],m['burned']) for r,m in zip(runs,ms)],f'viol/run {v:.2f} alloc {a:.1f}', '(a) in [1,2]:', 1<=v<=2)
print('(b) S4a<S4b<v6 (viol/run):',res['S4a'][0],res['S4b'][0],res['v6'][0], res['S4a'][0]<res['S4b'][0]<res['v6'][0])
b6v,b6a=res['B6'][0],res['B6'][1]
h1=[(m['alloc_vm']<=1.02*b6a, (60-m['slo'])<=b6v) for m in res['S4b'][2]]
print(f'(c) H1 S4b each run alloc ≤ 1.02×B6 mean ({1.02*b6a:.1f}) and viol ≤ B6 mean ({b6v:.2f}):',h1)
print('\n## t4 S4a(r300 → r502)與 B4c2 支配、H2 格')
ms,v,a=stat(['r502','r312','r317'],'t4'); bv,ba,br=grp('MAIN t4 B4c2'); ov,oa,_=grp('MAIN t4 S4a')
print('S4a new',[(r,m['slo'],m['alloc_vm']) for r,m in zip(['r502','r312','r317'],ms)],f'viol {v:.2f} alloc {a:.1f} (old {ov:.2f} @ {oa:.1f}) | B4c2 {bv:.2f} @ {ba:.1f}')
sys.path.insert(0,'/home/user/docs/paper/figs/scripts'); import common as C; pred=C.load_predictions()
p=pred[('S4a','t4')]; print(f'H2 t4 S4a: pred {p:.0f} meas mean {a:.1f} err {100*(a/p-1):+.2f}% (old {100*(oa/p-1):+.2f}%)')
for arm in ('B5c1 (q11)','B6 u=0.70','v6','S4b','B1'):
    try: x=grp(f'MAIN t4 {arm}'); print(' t4',arm,f'{x[0]:.2f} @ {x[1]:.1f}')
    except ZeroDivisionError: pass
print('\n## t3 B6(r383 → r503)')
ms,v,a=stat(['r365','r371','r503'],'t3'); ov,oa,_=grp('MAIN t3 B6 u=0.70')
print([(r,m['slo'],m['alloc_vm']) for r,m in zip(['r365','r371','r503'],ms)],f'new {v:.2f} @ {a:.1f} (old {ov:.2f} @ {oa:.1f})')
for arm in ('S4a','S4b','v6','B4c2','B5c1 (q11)','B1'):
    x=grp(f'MAIN t3 {arm}'); print(' t3',arm,f'{x[0]:.2f} @ {x[1]:.1f}')
