#!/usr/bin/env python3
"""qsim/serial/lead_from_logs.py (spec §4.134 item 1): measured slot boot lead by concurrency, from every p2/v7r*_daemon.log.
A dispatch = 'hbo scale_out_up (eupf)' line (slot, time). Concurrency of a dispatch = number of dispatches within the same 2 s (one tick's
decision batch). Lead = time from dispatch to the first later 'eupf rehome (scale-out) done' line of the same slot (the daemon's
slot-ready-and-relieved event), only if < 300 s and no second dispatch of that slot in between. Output serial/out/lead_from_logs.txt / .json"""
import glob, json, re, datetime as dt, statistics as st, collections, os
P='/home/user/experiment/p2'; rows=[]
def ts(s): return dt.datetime.fromisoformat(s.replace('Z','')[:26]).timestamp()
for f in sorted(glob.glob(f'{P}/v7r*_daemon.log')):
    run=os.path.basename(f).split('_')[0][2:]
    disp=[]; done=collections.defaultdict(list)
    for line in open(f,errors='replace'):
        if '"hbo scale_out_up (eupf)"' in line or '"eupf rehome (scale-out) done"' in line:
            try: j=json.loads(line)
            except Exception: continue
            t=ts(j['time'])
            if j['msg']=='hbo scale_out_up (eupf)' and 'slot' in j: disp.append((t,j['slot']))
            elif 'slot' in j: done[j['slot']].append(t)
    for i,(t,s) in enumerate(disp):
        conc=sum(1 for (u,_) in disp if abs(u-t)<=2.0)
        nxt=min([u for (u,x) in disp if x==s and u>t] or [1e18])
        d=[u for u in done[s] if t<u<nxt and u-t<300]
        if d: rows.append(dict(run=run,t=t,slot=s,conc=conc,lead=d[0]-t))
by=collections.defaultdict(list)
for r in rows: by[min(r['conc'],3)].append(r['lead'])
out=[f"dispatches with a matched rehome-done: {len(rows)} from {len(set(r['run'] for r in rows))} runs"]
for c in sorted(by):
    v=sorted(by[c]); q=lambda p: v[min(len(v)-1,int(p*len(v)))]
    out.append(f"concurrency {c}{'+' if c==3 else ''}: n {len(v)}, median {st.median(v):.1f} s, p10 {q(0.1):.1f}, p90 {q(0.9):.1f}, mean {st.mean(v):.1f}")
print("\n".join(out)); open('/home/user/experiment/qsim/serial/out/lead_from_logs.txt','w').write("\n".join(out)+"\n")
json.dump(rows,open('/home/user/experiment/qsim/serial/out/lead_from_logs.json','w'))
