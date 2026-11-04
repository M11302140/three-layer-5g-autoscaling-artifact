#!/usr/bin/env python3
"""r63a driver (spec §4.107 A). Each job = one Prior context (core.run_context); at most 2 worker processes; results appended to
out/<mode>.jsonl (resumable: tags already present are skipped).
  verify          control context (split 0, Prior = FULL library) must reproduce r62ab split 0; + eng vs frozen sim_nest2 with a split Prior
  split           task 1: grouped_split seeds 0-5, Prior from the calibration groups (all their traces), cal = first 300, ho = held-out groups
  boot [N]        task 2: cluster bootstrap, resamples 0..N-1 (draws from numpy default_rng(20261021), generated for all 200 in order)
  bucket          task 3: rise1 buckets (r62ab definition) x six grouped splits over the bucket's groups, bucket-internal Prior
usage: cd /home/user/experiment/qsim/r63a && nice -n 19 taskset -c 13,14 python3 run.py <mode> [args]"""
import sys, os, json, time, random, datetime as dt, numpy as np
R='/home/user/experiment/qsim/r63a'; sys.path.insert(0,R)
import core as C
from concurrent.futures import ProcessPoolExecutor
os.makedirs(f'{R}/out',exist_ok=True)
mode=sys.argv[1]
def log(m):
    line=f"[{dt.datetime.now():%F %T}] [{mode}] {m}"; print(line,flush=True)
    open(f'{R}/progress.log','a').write(line+'\n')
LIB=C.LIB

def boot_jobs(N):
    G=C.groups_of(); KEYS=sorted(G); NG=len(KEYS); rng=np.random.default_rng(20261021); jobs=[]
    for b in range(200):
        draw=rng.integers(0,NG,size=NG); drawn=set(int(x) for x in draw)
        tr=[i for q in draw for i in G[KEYS[int(q)]]]; h=[i for q in range(NG) if q not in drawn for i in G[KEYS[q]]]
        if b<N: jobs.append(dict(tag=f"b{b}",prior_idx=tr,cal_idx=tr[:300],ho_idx=h,n_groups_drawn=len(drawn)))
    return jobs

def rise1_buckets():
    rise1=np.array([float(np.max(np.diff(np.asarray(tr["ue"][:60],float)))) for tr in LIB])
    thr=np.percentile(rise1,np.arange(10,100,10))
    dec=np.array([next((j for j in range(9) if x<=thr[j]),9) for x in rise1])
    buckets=[]; pend=[]
    for j in range(10):
        pend.append(j)
        if (dec==j).any(): buckets.append(list(pend)); pend=[]
    if pend: buckets[-1]+=pend
    return thr, dec, buckets

def bucket_jobs():
    thr,dec,buckets=rise1_buckets(); jobs=[]
    for k,b in enumerate(buckets):
        idx=[i for i in range(len(LIB)) if dec[i] in b]; g=C.groups_of(idx); keys=sorted(g)
        bn="D"+"+".join(str(j+1) for j in b)
        for s in range(6):
            kk=list(keys); random.Random(s).shuffle(kk); nc=int(0.6*len(kk))
            pidx=[i for q in kk[:nc] for i in g[q]]; c=pidx[:300]; h=[i for q in kk[nc:] for i in g[q]]
            jobs.append(dict(tag=f"{bn}|s{s}",bucket=bn,bk=k,seed=s,n_bucket=len(idx),n_groups=len(keys),n_cal_groups=nc,prior_idx=pidx,cal_idx=c,ho_idx=h))
    return thr,buckets,jobs

def run_jobs(jobs, fn, nproc=2, est_after=None, budget_s=None):
    done=set()
    if os.path.exists(fn):
        for ln in open(fn): done.add(json.loads(ln)["tag"])
    todo=[j for j in jobs if j["tag"] not in done]
    log(f"{len(jobs)} jobs, {len(done)} already done, {len(todo)} to run, nproc {nproc}")
    t0=time.time(); k=0
    with ProcessPoolExecutor(nproc) as pool:
        for r,j in zip(pool.map(C.run_context,todo),todo):
            k+=1; r.update({kk:v for kk,v in j.items() if kk not in ("prior_idx","cal_idx","ho_idx","tag")})
            open(fn,'a').write(json.dumps(r)+'\n')
            el=time.time()-t0
            rs="; ".join(f"{tg}: λ {x['lam_vm']}/{x['lam_up']} cal {x['cal_risk']:.4f}{' INF' if x['infeasible'] else ''} ho {x['ho']['risk']:.4f} vm {x['ho']['alloc_vm']:.1f}" for tg,x in r["rows"].items() if x['ho'])
            log(f"{r['tag']} ({k}/{len(todo)}) nprior {r['n_prior']} ncal {r['n_cal']} (uniq {r['n_cal_unique']}) nho {r['n_ho']} sims {r['nsim']} {r['t_total']:.0f}s | {rs} | elapsed {el:.0f}s eta {el/k*(len(todo)-k):.0f}s")
    return time.time()-t0

if mode=="verify":
    c,h=C.grouped_split(0)
    r=C.run_context(dict(tag="control_full_prior_split0",prior_idx=list(range(len(LIB))),cal_idx=c[:300],ho_idx=h))
    exp={"0.02":(1.75,2.0,0.0190,1288.5),"0.005":(3.0,3.0,0.0050,1346.9)}
    ok=all((r["rows"][t]["lam_vm"],r["rows"][t]["lam_up"],round(r["rows"][t]["ho"]["risk"],4),round(r["rows"][t]["ho"]["alloc_vm"],1))==e for t,e in exp.items())
    log(f"control (full-library Prior, split 0): {json.dumps(r['rows'])} | expected r62ab {exp} -> {'MATCH' if ok else 'MISMATCH'} ({r['t_total']:.0f}s, {r['nsim']} sims)")
    pr=C.S.Prior([LIB[i] for i in c],C.CFG); bad,n=C.eng.check_equiv(LIB,C.CFG,pr,n=4)
    log(f"eng.sim2 vs frozen v8sim10.sim_nest2 (dispatch+vmexist) with the split-0 calibration-group Prior: {n-bad}/{n} identical")
    json.dump(dict(control=r,equiv=[n-bad,n],match=ok),open(f'{R}/out/verify.json','w'),indent=1)
elif mode=="split":
    jobs=[]
    for s in range(6):
        c,h=C.grouped_split(s); jobs.append(dict(tag=f"split{s}",seed=s,prior_idx=c,cal_idx=c[:300],ho_idx=h))
    el=run_jobs(jobs,f'{R}/out/split.jsonl'); log(f"DONE split {el:.0f}s")
elif mode=="boot":
    N=int(sys.argv[2]); el=run_jobs(boot_jobs(N),f'{R}/out/boot.jsonl'); log(f"DONE boot N={N} {el:.0f}s")
elif mode=="bucket":
    thr,buckets,jobs=bucket_jobs(); log(f"thresholds {thr.tolist()} buckets {buckets}")
    el=run_jobs(jobs,f'{R}/out/bucket.jsonl'); log(f"DONE bucket {el:.0f}s")
