# arrivals that landed ON a DNN the reconstruction says was stale-excluded at that moment = reconstruction false positive
import os,sys,re,csv,datetime as dt
RUNS=sys.argv[2:]; SRCN=sys.argv[1]
src=open('audit_drain.py').read(); src=src[:src.index('runs=sys.argv')]
os.environ['SRC']=SRCN; g={'__name__':'x'}; sys.argv=['x','360']; exec(src,g)
OCT=g['OCT']; tot=[0,0,0]
for run in RUNS:
    cs=f'/home/user/experiment/p2/trace_v7_{run}.csv'
    if not os.path.exists(cs): continue
    end=dt.datetime.fromtimestamp(os.path.getmtime(cs))
    rows={int(r['min']):r for r in csv.DictReader(open(cs))}
    live={m:{o for o in OCT.values() if r.get(f'slot_oob_{o}','')!=''} for m,r in rows.items()}
    first=None; aff=con=0
    for l in open(f'/home/user/experiment/p2/trace_v7_{run}.log'):
        m=re.match(r'\[(\d\d):(\d\d):(\d\d)\] min(\d+): (.*)',l)
        if not m: continue
        t=dt.time(*map(int,m.groups()[:3]))
        if first is None: first=t; base=end.date() if t<=end.time() else end.date()-dt.timedelta(days=1); lastt=t
        if t<lastt: base+=dt.timedelta(days=1)
        lastt=t; ts=dt.datetime.combine(base,t)
        a=re.match(r'UE-(\d+) arrives on (\S+)',m.group(5))
        if a:
            live2=live.get(int(m.group(4)),set())|{OCT[a.group(2)]}
            ex=g['stale_excl'](ts,live2)
            if ex: aff+=1
            if a.group(2) in ex: con+=1
    tot[0]+=1; tot[1]+=aff; tot[2]+=con
    if aff: print(run,'affected',aff,'contradictions',con)
print('TOTAL runs',tot[0],'affected',tot[1],'contradictions',tot[2])
