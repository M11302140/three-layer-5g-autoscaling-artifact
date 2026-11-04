# Round-70 audit (spec §4.117): per run, formal-minute series of (daemon baseline "sessions" − harness active_ue).
# Session-input controllers: B4c2 (HPA/DASA), B5c1 (HPA/holt), B6. Daemon samples every 30 s; the sample nearest the minute end (±40 s) is used.
import json,csv,datetime,re,os,sys
P='/home/user/experiment/p2'
def formal_start(run):
    for l in open(f'{P}/trace_v7_{run}.log'):
        m=re.match(r'\[(\d\d):(\d\d):(\d\d)\] min0:',l)
        if m: return tuple(map(int,m.groups()))
def sess(run):
    out=[]
    for l in open(f'{P}/v7{run}_daemon.log'):
        if '"msg":"baseline ' not in l or '"sessions"' not in l: continue
        try: d=json.loads(l)
        except: continue
        t=datetime.datetime.fromisoformat(d['time'][:19])+datetime.timedelta(hours=8); out.append((t,int(d['sessions'])))
    return out
def audit(run):
    try:
        rows=list(csv.DictReader(open(f'{P}/trace_v7_{run}.csv'))); fs=formal_start(run); ss=sess(run)
    except FileNotFoundError as e: return None
    if not fs or not ss or not rows: return None
    t0=ss[0][0].replace(hour=fs[0],minute=fs[1],second=fs[2])
    if t0<ss[0][0]-datetime.timedelta(hours=12): t0+=datetime.timedelta(days=1)
    if t0>ss[-1][0]+datetime.timedelta(hours=12): t0-=datetime.timedelta(days=1)
    diffs=[]
    for r in rows:
        mi=int(r['min']); tm=t0+datetime.timedelta(minutes=mi+1)
        c=[(abs((t-tm).total_seconds()),v) for t,v in ss if abs((t-tm).total_seconds())<=40]
        if not c or not r['active_ue']: continue
        v=min(c)[1]; diffs.append((mi,v-int(float(r['active_ue']))))
    if not diffs: return None
    import statistics as st
    ds=[d for m,d in diffs]; med=st.median(ds); q=st.quantiles(ds,n=4) if len(ds)>=4 else [min(ds),med,max(ds)]
    pos=sum(1 for d in ds if d>0)/len(ds)
    return dict(n=len(diffs),med=med,p25=q[0],p75=q[2],mean=sum(ds)/len(ds),pos=pos,maxd=max(abs(d) for d in ds),flag=('POLLUTED' if abs(med)>=2 else ('offset+1' if med!=0 else 'clean')))
LED=[l.rstrip('\n').split('\t') for l in open(f'{P}/main_exp_ledger.tsv') if l.count('\t')>=3][1:]
MAIN=[(r,b,a) for r,b,a,*_ in LED if a in ('B4c2_slo','B5c1_slo','B6c4_slo')]
EXTRA=[('r450','t7','B6c4_slo r34-verify')]+[(f'r{i}','t6',a) for i,a in zip(range(460,467),['B4c2_em','B5c1_em','B6_em(void)','B5c1_em','B6_em','B4c2_em','B6_em'])]+[('r474','t8','B6'),('r477','t8','B6'),('r482','t3','B6c5_h(void)'),('r483','t3','B6c5_h'),('r484','t3','B6c5_h'),('r491','t6','B6c5_h'),('r492','t6','B6c5_h')]
print('| run | block | arm | harness | minutes | median diff | p25/p75 | mean | frac>0 | max|diff| | flag |\n|---|---|---|---|---|---|---|---|---|---|---|')
for grp,lst in (('r33b main',MAIN),('r34a post-campaign',EXTRA)):
    for r,b,a in lst:
        x=audit(r)
        if x is None: print(f'| {r} | {b} | {a} | {grp} | no data | | | | |'); continue
        print(f"| {r} | {b} | {a} | {grp} | {x['n']} | {x['med']:+.0f} | {x['p25']:+.0f}/{x['p75']:+.0f} | {x['mean']:+.2f} | {x['pos']:.2f} | {x['maxd']} | {x['flag']} |")
