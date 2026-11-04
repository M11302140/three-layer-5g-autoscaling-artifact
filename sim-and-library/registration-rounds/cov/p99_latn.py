#!/usr/bin/env python3
"""cov/p99_latn.py (10-20, spec §4.102 item 5): lat_n / p99 facts over the main-experiment formal runs (t3-t7).
Formal set = the MAIN groups of paper_out_new/rq_metrics.py (VOID / replaced / confirm runs excluded);
sensitivity = every t3-t7 row of p2/main_exp_ledger.tsv whose CSV exists."""
import csv, json, re, statistics as st, sys, os
import numpy as np
P="/home/user/experiment/p2"
FORMAL={"t4":"r300 r312 r317 r301 r318 r321 r308 r313 r320 r303 r314 r322 r310 r315 r319 r305 r311 r316 r306",
        "t5":"r330 r331 r332 r333 r334 r335 r336",
        "t3":"r360 r372 r377 r361 r367 r378 r362 r373 r382 r363 r369 r374 r364 r375 r380 r365 r371 r383 r366",
        "t6":"r402 r414 r419 r403 r409 r420 r404 r410 r415 r405 r411 r416 r406 r412 r417 r407 r413 r418 r408",
        "t7":"r430 r442 r447 r431 r437 r448 r432 r438 r443 r433 r439 r444 r434 r440 r445 r435 r441 r446 r436"}
FORMAL={k:v.split() for k,v in FORMAL.items()}
def f(s,d=None):
    try: return float(s)
    except: return d
def rows(run): return list(csv.DictReader(open(f"{P}/trace_v7_{run}.csv")))[:60]
def up_rep(run):
    """per-minute mean daemon up_rep (same parse as rq_metrics.daemon) -> slot count proxy"""
    try:
        t0=None
        for line in open(f"{P}/trace_v7_{run}.log"):
            m=re.match(r"\[(\d\d):(\d\d):(\d\d)\] start:", line)
            if m: t0=((int(m[1])-8)%24)*3600+int(m[2])*60+int(m[3]); break
        rep={}
        for line in open(f"{P}/v7{run}_daemon.log"):
            if '"time"' not in line: continue
            try: d=json.loads(line)
            except: continue
            hh,mm,ss=d["time"][11:19].split(":"); t=int(hh)*3600+int(mm)*60+int(ss)-t0; t=((t+43200)%86400)-43200
            if 0<=t<3600 and d.get("msg")=="mid": rep.setdefault(int(t//60),[]).append(d["up_rep"])
        return {m:sum(v)/len(v) for m,v in rep.items()}
    except Exception: return {}
def summ(runs, label):
    n=[];p99e=0;mins=0;low=[];cov=[];X=[];Y=[];per_run=[]
    for r in runs:
        R=rows(r); ur=up_rep(r); rn=[]
        for x in R:
            mins+=1; ln=f(x["lat_n"],0.0); n.append(ln); rn.append(ln)
            if f(x["lat_p99_us"]) is None: p99e+=1
            c=f(x["covered_s"],0.0); cov.append(c)
            m=int(x["min"]); off=f(x["offered_pps"],0.0); tx=f(x["txreal"],0.0); ue=f(x["active_ue"],0.0)
            if m in ur and off>0 and tx>0 and c>0:
                mult=tx/off; X.append((ur[m],ue)); Y.append(ln/c/mult)
        per_run.append((r,len(R),min(rn),st.median(rn),max(rn)))
    a=np.array(n)
    out=dict(label=label,runs=len(runs),minutes=mins,lat_n_min=float(a.min()),lat_n_median=float(np.median(a)),lat_n_max=float(a.max()),
             lat_n_p1=float(np.percentile(a,1)),lat_n_p5=float(np.percentile(a,5)),lat_n_mean=float(a.mean()),
             p99_empty=p99e,lat_n_zero=int((a==0).sum()),
             below={str(t):int((a<t).sum()) for t in (1,100,1000,10000,50000,100000)},
             covered_s_min=float(min(cov)),covered_s_median=float(st.median(cov)))
    if X:
        A=np.array(X); y=np.array(Y); M=np.c_[A[:,0],A[:,1]]
        coef,res,_,_=np.linalg.lstsq(M,y,rcond=None); pred=M@coef
        out["fit_pps_per_slot"]=float(coef[0]); out["fit_pps_per_ue"]=float(coef[1])
        out["fit_r2"]=float(1-((y-pred)**2).sum()/((y-y.mean())**2).sum()); out["fit_n"]=len(y)
    out["per_run"]=per_run
    return out
if __name__=="__main__":
    allf=[r for b in ("t3","t4","t5","t6","t7") for r in FORMAL[b]]
    led=[l.split("\t") for l in open(f"{P}/main_exp_ledger.tsv") if l.startswith("r")]
    ledr=sorted({l[0] for l in led if l[1] in ("t3","t4","t5","t6","t7") and os.path.exists(f"{P}/trace_v7_{l[0]}.csv")})
    res=dict(formal=summ(allf,"formal t3-t7 (rq_metrics MAIN groups, 83 runs)"),
             ledger_all=summ(ledr,"all ledger t3-t7 rows with CSV (incl. void/replaced/confirm)"),
             r452=summ(["r452"],"r452"))
    for b in ("t3","t4","t5","t6","t7"): res["formal_"+b]=summ(FORMAL[b],b)
    json.dump(res,open(os.path.join(os.path.dirname(os.path.abspath(__file__)),"p99_latn.json"),"w"),indent=1)
    for k,v in res.items():
        print(k, {kk:vv for kk,vv in v.items() if kk!="per_run"})
    # lowest minutes in formal set
    lo=[]
    for r in allf:
        for x in rows(r): lo.append((f(x["lat_n"],0.0),r,x["min"],x["active_ue"],x["lat_p99_us"],x["e2e_pct"],x["covered_s"]))
    lo.sort(); print("lowest 12 formal minutes (lat_n, run, min, active_ue, p99, e2e, covered_s):"); [print(" ",z) for z in lo[:12]]
