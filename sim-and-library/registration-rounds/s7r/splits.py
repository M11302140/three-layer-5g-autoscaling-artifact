#!/usr/bin/env python3
"""qsim/s7r/splits.py (S7R protocol P0 §3, P3 §6.1): group lists and disjointness checks.
Outer: v8sim3.grouped_split(seed) for seeds 0-5 (60/40 by (loc,date)) = 'development-period grouped cross-validation' (studied before; not a final test).
Inner: outer-train groups shuffled with random.Random(20261026+s); first 70 % = fit, rest = cal.
Cal traces (<=300): cal groups ordered by sha256(canonical JSON [loc,date]); traces within a group by sha256([loc,date,start]); round-robin one per group.
Dev-final split (P3 §6.5, deployed parameters): same rule over the whole library with seed 20261026 (fit/cal 70/30, no outer validation).
Development material (never sealed test): t1-t10 loc-days.  Sealed-test pool: Melbourne local dates 2026-10-26..2026-10-27 (live collection), see protocol.json.
Output: s7r/out/P0/splits.json (+ printed checks)."""
import json, hashlib, random, sys, os
Q='/home/user/experiment/qsim'; sys.path.insert(0,Q)
lib=json.load(open(f'{Q}/prior_traces.json'))
def h(x): return hashlib.sha256(json.dumps(x,ensure_ascii=False,separators=(',',':'),sort_keys=True).encode('utf-8')).hexdigest()
groups={}
for i,tr in enumerate(lib): groups.setdefault((tr['loc'],tr['date']),[]).append(i)
def outer(seed,frac=0.6):
    keys=sorted(groups); rnd=random.Random(seed); rnd.shuffle(keys); n=int(frac*len(keys)); return keys[:n], keys[n:]
def inner(train_keys,seed,frac=0.7):
    keys=sorted(train_keys); rnd=random.Random(seed); rnd.shuffle(keys); n=int(round(frac*len(keys))); return keys[:n], keys[n:]
def cal_traces(cal_keys,nmax=300):
    ks=sorted(cal_keys,key=lambda k:h([k[0],k[1]]))
    per={k:sorted(groups[k],key=lambda i:h([lib[i]['loc'],lib[i]['date'],lib[i]['start']])) for k in ks}
    out=[]; r=0
    while len(out)<nmax and any(len(v)>r for v in per.values()):
        for k in ks:
            if r<len(per[k]) and len(out)<nmax: out.append(per[k][r])
        r+=1
    return out
DEV=[('t1',35,'2024-06-12'),('t2',84,'2024-06-18'),('t3',5,'2024-06-15'),('t4',41,'2024-06-13'),('t5',4,'2024-06-14'),
     ('t6',3,'2026-10-14'),('t7',4,'2026-10-13'),('t8',35,'2026-10-17'),('t9',35,'2026-10-24'),('t10',66,'2026-10-24')]
res={'library_sha256':hashlib.sha256(open(f'{Q}/prior_traces.json','rb').read()).hexdigest(),'n_groups':len(groups),'n_traces':len(lib),'folds':{},'dev_traces':DEV}
ok=True
import v8sim3
for s in range(6):
    tr,va=outer(s); fi,ca=inner(tr,20261026+s); ct=cal_traces(ca)
    # same as the frozen grouped_split?
    c_old,h_old=v8sim3.grouped_split(s); same=(sorted(c_old)==sorted(i for k in tr for i in groups[k]) and sorted(h_old)==sorted(i for k in va for i in groups[k]))
    sets={'fit':set(fi),'cal':set(ca),'val':set(va)}
    disj=all(not(sets[a]&sets[b]) for a,b in (('fit','cal'),('fit','val'),('cal','val')))
    cover=(sets['fit']|sets['cal']|sets['val'])==set(groups)
    devhit=[d for d in DEV if (d[1],d[2]) in groups]
    ok&=same and disj and cover and not devhit
    res['folds'][s]=dict(fit=[list(k) for k in fi],cal=[list(k) for k in ca],val=[list(k) for k in va],cal_traces=ct,
        n=dict(fit_groups=len(fi),cal_groups=len(ca),val_groups=len(va),fit_traces=sum(len(groups[k]) for k in fi),cal_traces_all=sum(len(groups[k]) for k in ca),cal_traces_used=len(ct),val_traces=sum(len(groups[k]) for k in va)),
        checks=dict(outer_equals_frozen_grouped_split=same,pairwise_disjoint=disj,covers_library=cover,dev_locdays_in_library=devhit))
    print(f"fold {s}: groups fit/cal/val {len(fi)}/{len(ca)}/{len(va)}; traces fit {res['folds'][s]['n']['fit_traces']} cal {len(ct)}/{res['folds'][s]['n']['cal_traces_all']} val {res['folds'][s]['n']['val_traces']}; outer==frozen {same}; disjoint {disj}; covers {cover}; dev loc-days in library {devhit}")
fi,ca=inner(sorted(groups),20261026); res['final']=dict(fit=[list(k) for k in fi],cal=[list(k) for k in ca],cal_traces=cal_traces(ca))
print(f"final dev split: fit groups {len(fi)}, cal groups {len(ca)}, cal traces {len(res['final']['cal_traces'])}")
dates={d for _,d in groups}; print(f"library dates {min(dates)}..{max(dates)}; sealed pool dates 2026-10-26..2026-10-27 -> date overlap with library: {bool({'2026-10-26','2026-10-27'}&dates)}; with dev traces: {[d for d in DEV if d[2] in ('2026-10-26','2026-10-27')]}")
res['all_checks_pass']=bool(ok)
json.dump(res,open(f'{Q}/s7r/out/P0/splits.json','w'))
print('all checks pass:',ok,' sha256',hashlib.sha256(open(f'{Q}/s7r/out/P0/splits.json','rb').read()).hexdigest())
