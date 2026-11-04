# 10-25: stale slot-drain audit. Agent /tmp/slot_drain.json kept DNNs whose drain
# retract never arrived; harness excludes listed DNNs from arrivals while file ts<600s.
# Reconstruct the file over time from /tmp/rehome_agent.log (10-23 02:09 onward) and
# score each run: arrivals made while a LIVE slot was excluded by a STALE entry.
import re, csv, os, sys, datetime as dt
P2='/home/user/experiment/p2'
GEN=int(sys.argv[1]) if len(sys.argv)>1 else 360   # entry ON'd within GEN s = genuinely draining
OCT={'internet':38,'internet2':31,'internet3':32,'internet4':33,'internet5':34,'internet6':35,'internet7':36,'internet8':37}
# --- agent timeline
ev=[]; day=dt.date(2026,10,23); prev=None
for l in open('/tmp/rehome_agent.log'):
    m=re.match(r'(\d\d):(\d\d):(\d\d) ',l)
    if not m: continue
    t=dt.time(*map(int,m.groups()))
    if prev and t<prev and (prev.hour==23 and t.hour==0): day+=dt.timedelta(days=1)
    prev=t
    m2=re.match(r'\S+ slot drain (ON |off) (\S+) → (.*)',l)
    if m2:
        ev.append((dt.datetime.combine(day,t), m2.group(1).strip(), m2.group(2), set(eval(m2.group(3)))))
SRC=os.environ.get('SRC','agent')
import pickle, bisect
HIST=pickle.load(open('/home/user/experiment/qsim/r66drain/'+('hist2.pkl' if SRC=='daemon2' else 'hist.pkl'),'rb')); HT=[h[0] for h in HIST]
def state(ts):
    """(file set, file ts, last-ON time per dnn) as of ts."""
    if SRC in ('daemon','daemon2'):
        i=bisect.bisect_right(HT,ts)-1
        if i<0: return set(),None,{}
        return set(HIST[i][1]),HIST[i][2],HIST[i][3]
    s=set(); fts=None; on={}
    for t,op,d,after in ev:
        if t>ts: break
        s=after; fts=t
        if op=='ON': on[d]=t
        else: on.pop(d,None)
    return s,fts,on
def stale_excl(ts, live):
    s,fts,on=state(ts)
    if fts is None or (ts-fts).total_seconds()>=600: return set()
    gen={d for d in s if d in on and (ts-on[d]).total_seconds()<GEN}
    return {d for d in s-gen if OCT[d] in live}
def run_audit(run):
    log=f'{P2}/trace_v7_{run}.log'; cs=f'{P2}/trace_v7_{run}.csv'
    end=dt.datetime.fromtimestamp(os.path.getmtime(cs))
    rows=list(csv.DictReader(open(cs)))
    live={int(r['min']):{o for o in OCT.values() if r.get(f'slot_oob_{o}','')!=''} for r in rows}
    ok={int(r['min']):(float(r['e2e_pct'] or 1e9)<=0.1 and float(r['lat_p99_us'] or 1e9)<=1000) for r in rows}
    times=[]; arr=[]
    lines=open(log).read().splitlines()
    first=None
    for l in lines:
        m=re.match(r'\[(\d\d):(\d\d):(\d\d)\] min(\d+): (.*)',l)
        if not m: continue
        t=dt.time(*map(int,m.groups()[:3]))
        if first is None:
            first=t; d0=end.date() if t<=end.time() else end.date()-dt.timedelta(days=1)
            base=d0; lastt=t
        if t<lastt: base=base+dt.timedelta(days=1)
        lastt=t
        ts=dt.datetime.combine(base,t); mn=int(m.group(4))
        a=re.match(r'UE-(\d+) arrives on (\S+)',m.group(5))
        if a: arr.append((ts,mn,a.group(2)))
    if first is None or (SRC=='agent' and ts< ev[0][0]): return None
    aff=[(ts,mn,d,stale_excl(ts,live.get(mn,set()))) for ts,mn,d in arr]
    affn=[x for x in aff if x[3]]
    affmin=sorted({x[1] for x in affn})
    bad=sorted(m for m,g in ok.items() if not g)
    near=[m for m in bad if any(0<=m-a<=3 for a in affmin)]
    exset=sorted({OCT[d] for x in affn for d in x[3]})
    return dict(run=run,arr=len(arr),aff=len(affn),affmin=affmin,excl=exset,slo=sum(ok.values()),bad=bad,near=near)
runs=sys.argv[2:] if len(sys.argv)>2 else None
if not runs:
    runs=sorted({f[9:-4] for f in os.listdir(P2) if f.startswith('trace_v7_') and f.endswith('.csv') and not f.endswith('_1s.csv')
                 and dt.datetime.fromtimestamp(os.path.getmtime(f'{P2}/{f}'))>=dt.datetime(2026,10,23,3,0)})
print(f'GEN={GEN}s  | run | arrivals | affected arrivals | affected minutes | stale-excluded live slots | SLO/60 | violation minutes | viol ≤3 min after affected arrival |')
for r in runs:
    try: a=run_audit(r)
    except Exception as e: print(r,'ERR',e); continue
    if a: print(f"| {a['run']} | {a['arr']} | {a['aff']} | {a['affmin']} | {a['excl']} | {a['slo']} | {a['bad']} | {a['near']} |")
