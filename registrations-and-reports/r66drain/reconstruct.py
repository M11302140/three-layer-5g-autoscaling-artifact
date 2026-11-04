# Rebuild /tmp/slot_drain.json history from daemon logs (UTC→CST +8). Episode per slot:
# ON at first "drain: plan" (or end-2s if none); end at "hbo scale_in_up (eupf)[ failed]";
# retract fails if "slot-drain retract failed" for that slot logged in the episode; a plan with
# no end in the same log (daemon killed) = stale. Sender reboots clear the file.
import json, glob, re, datetime as dt, pickle
P2='/home/user/experiment/p2'
def dnn(slot):
    n=int(slot.split('-')[1]); return 'internet' if n==0 else f'internet{n+1}'
REBOOTS=[dt.datetime(2026,9,19,23,43),dt.datetime(2026,10,23,1,34)]
logs=[]
for f in glob.glob(f'{P2}/v7*_daemon.log'):
    try:
        first=json.loads(open(f).readline())['time']
    except Exception: continue
    logs.append((first,f))
logs.sort()
ev=[]   # (time, op, dnn, src)
for first,f in logs:
    open_ep={}   # slot -> {'on':t,'rfail':bool}
    for l in open(f):
        if '"drain' not in l and 'scale_in_up (eupf)' not in l: continue
        try: j=json.loads(l)
        except Exception: continue
        t=dt.datetime.fromisoformat(j['time'][:26].rstrip('Z'))+dt.timedelta(hours=8)
        msg=j.get('msg',''); s=j.get('slot','')
        if not s.startswith('eupf-'): continue
        if msg=='drain: plan' and s not in open_ep:
            open_ep[s]={'on':t,'rfail':False}; ev.append((t,'ON',dnn(s),f))
        elif msg=='drain: slot-drain retract failed':
            open_ep.setdefault(s,{'on':t,'rfail':False})['rfail']=True
        elif msg=='drain: slot-drain publish failed':
            pass
        elif msg.startswith('hbo scale_in_up (eupf)'):
            ep=open_ep.pop(s,None)
            if ep is None: ev.append((t-dt.timedelta(seconds=2),'ON',dnn(s),f)); ep={'rfail':False}
            if not ep['rfail']: ev.append((t,'off',dnn(s),f))
            else: ev.append((t,'touch',dnn(s),f))   # retract failed: entry stays, file ts not updated (no write)
    # plans with no end in this log: daemon gone mid-drain -> stale (no write)
for r in REBOOTS: ev.append((r,'reboot','',''))
ev.sort(key=lambda x:x[0])
st=set(); fts=None; on={}; hist=[]
for t,op,d,f in ev:
    if op=='reboot': st=set(); fts=None; on={}
    elif op=='ON': st.add(d); fts=t; on[d]=t
    elif op=='off': st.discard(d); fts=t; on.pop(d,None)
    elif op=='touch': on.pop(d,None)   # drain over, entry stale
    hist.append((t,frozenset(st),fts,dict(on)))
pickle.dump(hist,open('/home/user/experiment/qsim/r66drain/hist.pkl','wb'))
print('events',len(ev),'hist',len(hist))
# validate vs agent log ground truth (10-23 02:09 onward)
import bisect
times=[h[0] for h in hist]
day=dt.date(2026,10,23); prev=None; agree=dis=0; ex=[]
for l in open('/tmp/rehome_agent.log'):
    m=re.match(r'(\d\d):(\d\d):(\d\d) ',l)
    if not m: continue
    t=dt.time(*map(int,m.groups()))
    if prev and t<prev and prev.hour==23 and t.hour==0: day+=dt.timedelta(days=1)
    prev=t
    m2=re.match(r'\S+ slot drain (ON |off) (\S+) → (.*)',l)
    if not m2: continue
    ts=dt.datetime.combine(day,t)+dt.timedelta(seconds=30)
    i=bisect.bisect_right(times,ts)-1
    rec=set(hist[i][1]) if i>=0 else set(); tru=set(eval(m2.group(3)))
    if rec==tru: agree+=1
    else: dis+=1; ex.append((ts,sorted(tru),sorted(rec)))
print('agent-vs-reconstruct agree',agree,'disagree',dis)
for x in ex[:12]: print(' ',x[0],'agent',x[1],'recon',x[2])
