# Supplementary (not the registered rule): for each in-window hit, which slots received the affected arrivals
# in the window, which live slots were excluded, and per-slot oob in the hit minute.
import os,sys,json,re,csv,datetime as dt
RUNS=sys.argv[1:]
src=open('decision_audit.py').read().replace("runs=RUNS","runs=[]")
g={'__name__':'x'}; sys.argv=['x']; exec(src,g)
OCT=g['GA']['OCT']
for run in RUNS:
    G=g['GA'] if int(run[1:])>=471 else g['GD']
    cs=f'/home/user/experiment/p2/trace_v7_{run}.csv'; end=dt.datetime.fromtimestamp(os.path.getmtime(cs))
    rows={int(r['min']):r for r in csv.DictReader(open(cs))}
    live={m:{o for o in OCT.values() if r.get(f'slot_oob_{o}','')!=''} for m,r in rows.items()}
    arr=[]; mt={}; first=None
    for l in open(f'/home/user/experiment/p2/trace_v7_{run}.log'):
        m=re.match(r'\[(\d\d):(\d\d):(\d\d)\] min(\d+): (.*)',l)
        if not m: continue
        t=dt.time(*map(int,m.groups()[:3]))
        if first is None: first=t; base=end.date() if t<=end.time() else end.date()-dt.timedelta(days=1); lastt=t
        if t<lastt: base+=dt.timedelta(days=1)
        lastt=t; ts=dt.datetime.combine(base,t); mn=int(m.group(4)); mt.setdefault(mn,ts)
        a=re.match(r'UE-(\d+) arrives on (\S+)',m.group(5))
        if a:
            ex=G['stale_excl'](ts,live.get(mn,set()))
            if ex: arr.append((ts,mn,OCT[a.group(2)],sorted(OCT[d] for d in ex)))
    a=g['audit'](run)
    for k,hh,slot,act,mv in a[1]:
        # locate hit time
        cands=[x for x in arr]
        ht=None
        for x in arr:
            d=x[0].date(); t=dt.datetime.combine(d,dt.time.fromisoformat(hh))
            if x[0]<=t<=x[0]+dt.timedelta(minutes=3): ht=t; break
        if ht is None:
            for x in arr:
                t=dt.datetime.combine(x[0].date()+dt.timedelta(days=1),dt.time.fromisoformat(hh))
                if x[0]<=t<=x[0]+dt.timedelta(minutes=3): ht=t; break
        win=[x for x in arr if x[0]<=ht<=x[0]+dt.timedelta(minutes=3)]
        hm=max(m for m,t in mt.items() if t<=ht)
        r=rows.get(hm,{})
        oob={o:r.get(f'slot_oob_{o}','') for o in (38,31,32,33,34,35,36,37)}
        dest=sorted({x[2] for x in win}); exc=sorted({o for x in win for o in x[3]})
        print(f"{run} {k} {hh} slot={slot} {act} moves={mv} | min{hm} dest={dest} excluded={exc} oob={ {o:v for o,v in oob.items() if v!=''} }")
