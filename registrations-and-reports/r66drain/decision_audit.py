# spec §4.119: decisions triggered inside exclusion windows ([affected arrival, +3 min]).
# K1 hot slot relief moves>0, K2 pool relief moves>0, K3 emergency force (not suppressed), K4 reason emerg=true.
import os, sys, json, datetime as dt, re
RUNS=sys.argv[1:]
src=open('/home/user/experiment/qsim/r66drain/audit_drain.py').read()
src=src[:src.index('runs=sys.argv')]
def load(srcname):
    os.environ['SRC']=srcname; g={'__name__':'x'}; sys.argv=['x','360']; exec(src,g); return g
GA=load('agent'); GD=load(os.environ.get('DSRC','daemon2'))
def windows(g,run):
    log=f'/home/user/experiment/p2/trace_v7_{run}.log'; cs=f'/home/user/experiment/p2/trace_v7_{run}.csv'
    import csv
    end=dt.datetime.fromtimestamp(os.path.getmtime(cs))
    rows=list(csv.DictReader(open(cs)))
    live={int(r['min']):{o for o in g['OCT'].values() if r.get(f'slot_oob_{o}','')!=''} for r in rows}
    first=None; out=[]
    for l in open(log):
        m=re.match(r'\[(\d\d):(\d\d):(\d\d)\] min(\d+): (.*)',l)
        if not m: continue
        t=dt.time(*map(int,m.groups()[:3]))
        if first is None:
            first=t; base=end.date() if t<=end.time() else end.date()-dt.timedelta(days=1); lastt=t
        if t<lastt: base+=dt.timedelta(days=1)
        lastt=t; ts=dt.datetime.combine(base,t)
        a=re.match(r'UE-(\d+) arrives on (\S+)',m.group(5))
        if a and g['stale_excl'](ts,live.get(int(m.group(4)),set())): out.append((ts,ts+dt.timedelta(minutes=3)))
    return out
def kind(j):
    msg=j.get('msg','')
    if msg.endswith('hot slot relief') and int(j.get('moves',0))>0: return 'K1'
    if msg.endswith('pool relief') and int(j.get('moves',0))>0: return 'K2'
    if re.match(r'v\d+ emergency force$',msg): return 'K3'
    if msg.endswith(' decision') and 'emerg=true' in j.get('reason',''): return 'K4'
def audit(run):
    g=GA if int(run[1:])>=471 else GD
    W=windows(g,run)
    if not W: return None
    hits=[]
    f=f'/home/user/experiment/p2/v7{run}_daemon.log'
    for l in open(f):
        if not any(k in l for k in ('relief','emergency','emerg=true')): continue
        try: j=json.loads(l)
        except Exception: continue
        k=kind(j)
        if not k: continue
        t=dt.datetime.fromisoformat(j['time'][:26].rstrip('Z'))+dt.timedelta(hours=8)
        if any(a<=t<=b for a,b in W): hits.append((k,t.strftime('%H:%M:%S'),str(j.get('slot','')),str(j.get('action','')),str(j.get('moves',''))))
    return len(W),hits
runs=RUNS
print('| run | affected arrivals | K1 | K2 | K3 | K4 | hits |\n|---|---|---|---|---|---|---|')
for r in runs:
    a=audit(r)
    if a is None: print(f'| {r} | 0 | - | - | - | - | |'); continue
    n,h=a; c={k:sum(1 for x in h if x[0]==k) for k in ('K1','K2','K3','K4')}
    print(f"| {r} | {n} | {c['K1']} | {c['K2']} | {c['K3']} | {c['K4']} | {'; '.join(' '.join(x) for x in h[:6])} |")
