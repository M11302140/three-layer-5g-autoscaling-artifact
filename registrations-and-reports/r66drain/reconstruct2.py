# reconstruct.py + arrival pruning: an arrival on DNN d at t while d is in the reconstructed (fresh) set proves d was
# not in the file -> remove d from the set from t until its next ON. Global chronological sweep over all runs.
import os,re,csv,pickle,datetime as dt,glob
hist=pickle.load(open('hist.pkl','rb'))   # (t, set, fts, on)
# rebuild raw events from hist diffs
ev=[]; prev=set(); pon={}
for t,s,fts,on in hist:
    for d in s-prev: ev.append((t,'ON',d))
    for d in prev-s: ev.append((t,'off',d))
    if not s and not prev and fts is None: ev.append((t,'reboot',''))
    for d in s&prev:
        if on.get(d)!=pon.get(d) and d in on: ev.append((t,'ON',d))
    for d in s&prev:
        if d in pon and d not in on: ev.append((t,'touch',d))
    if fts is not None and not (s^prev) and all(on.get(d)==pon.get(d) for d in s): ev.append((t,'tsonly',''))
    prev=set(s); pon=dict(on)
OCT={'internet':38,'internet2':31,'internet3':32,'internet4':33,'internet5':34,'internet6':35,'internet7':36,'internet8':37}
arr=[]
for cs in glob.glob('/home/user/experiment/p2/trace_v7_*.csv'):
    run=cs.split('trace_v7_')[1][:-4]
    if run.endswith('_1s'): continue
    lg=f'/home/user/experiment/p2/trace_v7_{run}.log'
    if not os.path.exists(lg): continue
    end=dt.datetime.fromtimestamp(os.path.getmtime(cs)); first=None
    for l in open(lg,errors='ignore'):
        m=re.match(r'\[(\d\d):(\d\d):(\d\d)\] min(\d+): UE-\d+ arrives on (\S+)',l) or re.match(r'\[(\d\d):(\d\d):(\d\d)\] (min)(\d*)',l) and None
        m0=re.match(r'\[(\d\d):(\d\d):(\d\d)\]',l)
        if not m0: continue
        t=dt.time(*map(int,m0.groups()))
        if first is None: first=t; base=end.date() if t<=end.time() else end.date()-dt.timedelta(days=1); lastt=t
        if t<lastt: base+=dt.timedelta(days=1)
        lastt=t
        a=re.search(r'UE-\d+ arrives on (\S+)',l)
        if a and a.group(1) in OCT: arr.append((dt.datetime.combine(base,t),'ARR',a.group(1)))
allv=sorted(ev+arr,key=lambda x:(x[0],0 if x[1]!='ARR' else 1))
st=set(); fts=None; on={}; out=[]; pruned=0
for t,op,d in allv:
    if op=='reboot': st=set(); fts=None; on={}
    elif op=='ON': st.add(d); fts=t; on[d]=t
    elif op=='off': st.discard(d); fts=t; on.pop(d,None)
    elif op=='touch': on.pop(d,None)
    elif op=='tsonly': fts=t
    elif op=='ARR':
        if d in st and fts and (t-fts).total_seconds()<600 and not (d in on and (t-on[d]).total_seconds()<360):
            st.discard(d); pruned+=1
        else: continue
    out.append((t,frozenset(st),fts,dict(on)))
pickle.dump(out,open('hist2.pkl','wb')); print('events',len(ev),'arrivals',len(arr),'pruned',pruned)
