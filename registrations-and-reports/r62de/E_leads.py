#!/usr/bin/env python3
"""Task E (spec §4.104 E): ready lead per layer from the 84 valid main-experiment runs (t3–t7 + r381).
Scored window = last 'autoscale toggled' enabled=true → next enabled=false (daemon log, UTC).
Definitions (dispatch → ready):
  VY  dispatch = daemon 'hbo deploy_vyos' (name vyos-i);  ready = first harness line after dispatch that admits the
      VyOS data IP 10.0.1.(4+i) into the traffic pool: 'vyos-pool grow [ip]' (event-driven, 5-s check) or
      'SEG SA rebind (new vyos: [..ip..])' (minute-boundary admission). Harness clock = local (UTC+8); clock check below.
  UP  dispatch = daemon 'hbo scale_out_up (eupf)' with slot=eupf-j (new slot; 'cancelled in-flight drain' lines excluded);
      ready = daemon 'eupf rehome (scale-out) done' slot=eupf-j (tick-gated, 30 s resolution).
  WK  dispatch = daemon 'hbo create_worker' name=worker-k, or 'hbo scale_out_up (eupf): creating slot worker first' worker=worker-k;
      ready = daemon 'eupf worker provisioned' node=worker-k.
  Secondary (all layers): daemon 'v6 inflight done' elapsed_s for DEPLOY_VYOS / SCALE_OUT_UP / CREATE_WORKER, matched to the
      dispatch by T_done − elapsed ≈ T_dispatch (±6 s).  NOTE: in-flight done requires elapsed ≥ the arm's T_ready constant
      (daemon v6shadow.go reconcileInflight: done && el >= tr), so it is censored from below and tick-quantised.
Usage: python3 E_leads.py → E_leads.json + printed table"""
import json, re, datetime as dt, numpy as np, collections, sys
P2='/home/user/experiment/p2'; OUT='/home/user/experiment/qsim/r62de'
runs=[l.split('\t') for l in open(f'{OUT}/runs84.txt').read().split('\n') if l]
def ts(s):
    s=s.replace('Z',''); a,_,f=s.partition('.')
    return dt.datetime.fromisoformat(a).replace(tzinfo=dt.timezone.utc).timestamp()+(float('0.'+f) if f else 0.0)
HR=re.compile(r'^\[(\d\d):(\d\d):(\d\d)\]\s+(.*)$')
res=collections.defaultdict(list); sec=collections.defaultdict(list); unmatched=[]; clock=[]; per_run={}
for rid,blk,arm in runs:
    ev=[]
    for l in open(f'{P2}/v7{rid}_daemon.log'):
        try: j=json.loads(l)
        except Exception: continue
        ev.append((ts(j['time']),j))
    tog=[(t,j['enabled']) for t,j in ev if j['msg']=='autoscale toggled']
    on=[i for i,(t,e) in enumerate(tog) if e]; t_on=tog[on[-1]][0]
    offs=[t for t,e in tog[on[-1]+1:] if not e]; t_off=offs[0] if offs else ev[-1][0]
    # harness lines → (sod_local, text)
    H=[]
    for l in open(f'{P2}/trace_v7_{rid}.log'):
        m=HR.match(l.rstrip('\n'))
        if m: H.append((int(m[1])*3600+int(m[2])*60+int(m[3]), m[4]))
    def h_after(t_utc, pred, lim=1800):
        sod=(int(t_utc)+8*3600)%86400; best=None
        for s,txt in H:
            d=(s-sod)%86400
            if d<=lim and pred(txt) and (best is None or d<best[0]): best=(d,txt)
        return best
    # clock check: daemon delete_vyos repath (drain file written) → harness 'vyos drain announced ip'
    for t,j in ev:
        if j['msg']=='hbo delete_vyos: repathed UEs off victim' and t_on<=t<=t_off:
            ip=f"10.0.1.{4+int(j['name'].split('-')[1])}"
            b=h_after(t-30, lambda x,ip=ip: 'vyos drain announced '+ip in x, lim=120)
            if b: clock.append((rid,b[0]-30))   # seconds (harness − daemon), integer resolution
    inf=[(t,j) for t,j in ev if j['msg']=='v6 inflight done']
    used_inf=set(); rr=collections.defaultdict(list)
    def inflight(act,t0):
        for k,(t,j) in enumerate(inf):
            if k in used_inf or j['action']!=act: continue
            if abs((t-j['elapsed_s'])-t0)<=6: used_inf.add(k); return j['elapsed_s']
        return None
    for t,j in ev:
        if not (t_on<=t<=t_off): continue
        m=j['msg']
        if m=='hbo deploy_vyos':
            i=int(j['name'].split('-')[1]); ip=f"10.0.1.{4+i}"
            b=h_after(t, lambda x,ip=ip: (x.startswith('min') and 'vyos-pool grow' in x and "'"+ip+"'" in x) or ('SEG SA rebind' in x and "'"+ip+"'" in x))
            frac=t-int(t)
            if b: lead=b[0]-frac; res['vy'].append(lead); rr['vy'].append(lead)
            else: unmatched.append((rid,'vy',j['name']))
            e=inflight('DEPLOY_VYOS',t)
            if e is not None: sec['vy'].append(e)
        elif m=='hbo scale_out_up (eupf)':
            slot=j['slot']; done=[t2 for t2,j2 in ev if t2>t and j2['msg']=='eupf rehome (scale-out) done' and j2.get('slot')==slot]
            if done: res['up'].append(done[0]-t); rr['up'].append(done[0]-t)
            else: unmatched.append((rid,'up',slot))
            e=inflight('SCALE_OUT_UP',t)
            if e is not None: sec['up'].append(e)
        elif m=='hbo create_worker' or m=='hbo scale_out_up (eupf): creating slot worker first':
            w=j.get('name') or j.get('worker')
            done=[t2 for t2,j2 in ev if t2>t and j2['msg']=='eupf worker provisioned' and j2.get('node')==w]
            if done: res['wk'].append(done[0]-t); rr['wk'].append(done[0]-t)
            else: unmatched.append((rid,'wk',w))
            e=inflight('CREATE_WORKER',t)
            if e is not None: sec['wk'].append(e)
    per_run[rid]=dict(block=blk,arm=arm,window_s=round(t_off-t_on),**{k:[round(x,1) for x in v] for k,v in rr.items()})
def stats(v):
    v=np.array(v,float)
    return dict(n=int(len(v)), p50=float(np.percentile(v,50)), p90=float(np.percentile(v,90)), p95=float(np.percentile(v,95)), p99=float(np.percentile(v,99)), max=float(v.max()), min=float(v.min()), mean=float(v.mean()))
out=dict(primary={k:stats(v) for k,v in res.items()}, inflight={k:stats(v) for k,v in sec.items()}, unmatched=unmatched,
         clock_check=dict(n=len(clock), values=sorted(c for _,c in clock), neg=[x for x in clock if x[1]<0]),
         per_run=per_run, raw={k:[round(x,2) for x in v] for k,v in res.items()}, raw_inflight=sec)
json.dump(out,open(f'{OUT}/E_leads.json','w'),indent=1)
for name,d in (('primary (readiness signal)',out['primary']),('daemon in-flight done (censored ≥ T_ready)',out['inflight'])):
    print(f'== {name}')
    for k in ('vy','up','wk'):
        s=d.get(k)
        if s: print(f"  {k}: n {s['n']:3d}  min {s['min']:6.1f}  p50 {s['p50']:6.1f}  p90 {s['p90']:6.1f}  p95 {s['p95']:6.1f}  p99 {s['p99']:6.1f}  max {s['max']:6.1f}")
print('unmatched',unmatched); print('clock check (harness drain-announce − daemon repath, s):',out['clock_check'])
