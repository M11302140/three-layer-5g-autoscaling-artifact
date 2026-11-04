"""analyze.py (r62ab, spec §4.104 A+B): all analyses on the step-0 matrix (lookup) + the few fresh simulations they need.
usage: cd /home/user/experiment/qsim/r62ab && nice -n 19 taskset -c 13,14 python3 analyze.py  -> results.json + report_tables.md"""
import timeit  # noqa: stdlib before qsim/timeit.py shadows it (v8sim11 note)
import sys, os, re, json, csv, time, random, itertools, numpy as np
sys.path.insert(0,'/home/user/experiment/qsim/r62ab')
import look as Lk
from look import lib, cfg, pr, D, S, M, Q2, calibrate, heldout, cols, groups_of
sys.path.insert(0,'/home/user/experiment/qsim')
from v8sim3 import grouped_split
import v8sim11 as V; V.cfg_prior()
R=Lk.R; E='/home/user/experiment'; T0=time.time(); OUT={}; MD=[]
def P(s=""): MD.append(s); print(s,flush=True)
TGT=(0.02,0.005); TNAME={0.02:"2 % (S4b)",0.005:"0.5 % (S4a)"}
DEP={"S4b":(1.83,2.00),"S4a":(2.83,3.08)}
ms=lambda a,f="{:.2f}": (f.format(np.mean(a))+" ± "+f.format(np.std(a))) if len(a) else "-"
# ================= step 0 verification =================
P("## Step 0 verification"); P()
rnd=random.Random(5); vt=sorted(rnd.sample(range(len(lib)),5)); bad=0; t=time.time()
for i in vt:
    for (lv,lu),p in Lk.PIDX.items():
        L={"vy":lv,"wk":lv,"up":lu}; a=Q2.sim_nest2(lib[i]["ue"][:60],cfg,pr,L); b=Q2.sim_nest2(lib[i]["ue"][:60],cfg,pr,L,acct='vmexist')
        vb=Lk.vbits_to_mat(Lk.VB[i,p])
        ok=(a["slo"]==Lk.SLO[i,p] and a["alloc"]==Lk.AD[i,p] and b["alloc"]==Lk.AV[i,p] and np.array_equal(vb,a["pct"]>0.1) and D.flaps(a["ev"])==Lk.FL[i,p])
        bad+=not ok
P(f"Lookup vs fresh frozen `v8sim10.sim_nest2` (acct dispatch and vmexist), traces {vt} x all 221 points = {5*221} pairs: **{bad} mismatches** (slo, minute vector, alloc dispatch, alloc vmexist, flaps compared exactly) [{time.time()-t:.0f}s]")
OUT["verify_lookup"]=dict(traces=vt,pairs=5*221,mismatches=bad)
frozen={}
for ln in open('/home/user/experiment/qsim/v8sim10_FULL_2026-10-06.txt'):
    m=re.match(r"\s+target (\S+) split(\d): λ (\S+)/(\S+) cal (\S+) \| ho risk (\S+) alloc (\S+)",ln)
    if m: frozen[(float(m[1]),int(m[2]))]=tuple(float(x) for x in m.group(3,4,5,6,7))
P(); P("Six-split calibration on the matrix vs frozen v8sim10_FULL_2026-10-06.txt (grouped_split seeds 0-5, cal[:300], coarse 6x7 + ±0.25):"); P()
P("| target | split | λ lookup | λ frozen | cal risk lookup / frozen | ho risk lookup / frozen | ho alloc dispatch lookup / frozen | ho alloc vmexist |"); P("|---|---|---|---|---|---|---|---|")
STD={}
for tg in TGT:
    rows=[]
    for s in range(6):
        c,h=grouped_split(s); c=c[:300]; res,_=calibrate(c,tg); hr,ha,hv=heldout(h,res["lam_vm"],res["lam_up"]); f=frozen[(tg,s)]
        rows.append((res["lam_vm"],res["lam_up"],hr,ha,hv))
        P(f"| {tg} | {s} | {res['lam_vm']}/{res['lam_up']} | {f[0]}/{f[1]} | {res['cal_risk']:.4f} / {f[2]:.4f} | {hr:.4f} / {f[3]:.4f} | {ha:.1f} / {f[4]:.1f} | {hv:.1f} |")
    a=np.array(rows); STD[tg]=a
    P(f"| {tg} | mean | {a[:,0].mean():.2f}±{a[:,0].std():.2f} / {a[:,1].mean():.2f}±{a[:,1].std():.2f} | | | {a[:,2].mean():.4f}±{a[:,2].std():.4f} | {a[:,3].mean():.1f} | {a[:,4].mean():.1f} |")
OUT["std_splits"]={str(k):v.tolist() for k,v in STD.items()}
# ================= fresh: deployed λ on whole library (dual) + v6 =================
t=time.time(); FR={}
for arm,(lv,lu) in DEP.items():
    rs=[D.sim_nest2_dual(tr["ue"][:60],cfg,pr,{"vy":lv,"wk":lv,"up":lu}) for tr in lib]
    FR[arm]=dict(v=np.array([r["pct"]>0.1 for r in rs]),ad=np.array([r["alloc"] for r in rs]),av=np.array([r["alloc_vm"] for r in rs]))
rs=[D.sim_v6_pm(tr["ue"][:60],cfg) for tr in lib]
FR["v6"]=dict(v=np.array([r["pct"]>0.1 for r in rs]),ad=np.array([r["alloc"] for r in rs]),av=np.array([np.nan]*len(rs)),slo=np.array([r["slo"] for r in rs]))
assert all(int(60-FR["v6"]["v"][i].sum())==FR["v6"]["slo"][i] for i in range(len(lib)))
T_FRESH=time.time()-t
# ================= Task A =================
P(); P("## Task A: conditional λ by rise1 decile"); P()
rise1=np.array([float(np.max(np.diff(np.asarray(tr["ue"][:60],float)))) for tr in lib])
thr=np.percentile(rise1,np.arange(10,100,10))
dec=np.array([next((j for j in range(9) if x<=thr[j]),9) for x in rise1])
P(f"rise1 thresholds P10..P90 (numpy linear): {thr.tolist()}"); P()
P("| decile | rise1 range | n |"); P("|---|---|---|")
for j in range(10):
    m=dec==j; P(f"| D{j+1} | {('%g-%g'%(rise1[m].min(),rise1[m].max())) if m.any() else '-'} | {int(m.sum())} |")
# merge empty deciles with the next one
buckets=[]; pend=[]
for j in range(10):
    pend.append(j)
    if (dec==j).any(): buckets.append(list(pend)); pend=[]
if pend: buckets[-1]+=pend
bname=lambda b: "D"+"+".join(str(j+1) for j in b)
P(); P("Merged buckets (empty decile joined to the next non-empty one): "+", ".join(bname(b) for b in buckets)); P()
TR={t:json.load(open(f"{E}/trace_ue_60min_v3_{t}.json"))["ue"][:60] for t in ("t3","t4","t5","t6","t7")}
trise={t:float(np.max(np.diff(np.asarray(u,float)))) for t,u in TR.items()}
tbuck={t:next(k for k,b in enumerate(buckets) if (next((j for j in range(9) if trise[t]<=thr[j]),9)) in b) for t in TR}
P("Test-trace rise1 and bucket: "+", ".join(f"{t} {trise[t]:g} → {bname(buckets[tbuck[t]])}" for t in TR)); P()
A={}
for k,b in enumerate(buckets):
    idx=[i for i in range(len(lib)) if dec[i] in b]; g=groups_of(idx); keys=sorted(g)
    for tg in TGT:
        rows=[]; notes=[]
        for s in range(6):
            kk=list(keys); random.Random(s).shuffle(kk); nc=int(0.6*len(kk))
            c=[i for q in kk[:nc] for i in g[q]][:300]; h=[i for q in kk[nc:] for i in g[q]]
            if len(c)<30: notes.append(f"s{s}: cal {len(c)}<30")
            if not h: notes.append(f"s{s}: no held-out"); continue
            res,info=calibrate(c,tg); inf=res is None; res=res or info
            hr,ha,hv=heldout(h,res["lam_vm"],res["lam_up"])
            rows.append(dict(lv=res["lam_vm"],lu=res["lam_up"],cal=res["cal_risk"],ho=hr,hv=hv,nc=len(c),nh=len(h),inf=inf,off=res.get("offgrid",False)))
        A[(k,tg)]=dict(b=b,n=len(idx),ng=len(keys),rows=rows,notes=notes)
P("Per bucket, six grouped 60/40 splits over the bucket's (loc,date) groups (seed s: sorted keys, random.Random(s).shuffle, first int(0.6·G) groups = calibration, capped at 300 traces), calibrated by lookup; held-out = the bucket's remaining groups. ε ± SE rule: valid if |mean ho risk − ε| ≤ SE, SE = std/√6 (std ddof=0, as in the frozen reports). 'Not exceeding' = mean ho ≤ ε + SE. Full-λ risk = bucket mean risk under the deployed full-library λ (fresh sim, whole bucket)."); P()
for tg in TGT:
    arm="S4b" if tg==0.02 else "S4a"
    P(f"### target {TNAME[tg]}"); P()
    P("| bucket | n | groups | cal n (mean) | ho n (mean) | λ_VM | λ_UP | cal risk | ho risk (mean ± std) | SE | ho alloc vmexist | full-λ risk (bucket) | valid (ε±SE) | not exceeding | notes |")
    P("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    nv=0; nne=0
    for k,b in enumerate(buckets):
        a=A[(k,tg)]; r=a["rows"]; ho=np.array([x["ho"] for x in r]); se=ho.std()/np.sqrt(len(ho)); valid=abs(ho.mean()-tg)<=se; ne=ho.mean()<=tg+se; nv+=valid; nne+=ne
        idx=[i for i in range(len(lib)) if dec[i] in b]; fr=float(FR[arm]["v"][idx].sum()/(60*len(idx)))
        nt=a["notes"]+([f"{sum(x['inf'] for x in r)} split(s) infeasible on coarse grid → min-risk point"] if any(x['inf'] for x in r) else [])+([f"{sum(x['off'] for x in r)} split(s) refined off-matrix (fresh sim)"] if any(x['off'] for x in r) else [])
        a.update(valid=bool(valid),ne=bool(ne),ho_mean=float(ho.mean()),ho_std=float(ho.std()),se=float(se),lv=float(np.mean([x['lv'] for x in r])),lu=float(np.mean([x['lu'] for x in r])),hv=float(np.mean([x['hv'] for x in r])),full_risk=fr)
        P(f"| {bname(b)} | {a['n']} | {a['ng']} | {np.mean([x['nc'] for x in r]):.0f} | {np.mean([x['nh'] for x in r]):.0f} | {ms([x['lv'] for x in r])} | {ms([x['lu'] for x in r])} | {np.mean([x['cal'] for x in r]):.4f} | {ho.mean():.4f} ± {ho.std():.4f} | {se:.4f} | {a['hv']:.1f} | {fr:.4f} | {'yes' if valid else 'no'} | {'yes' if ne else 'no'} | {'; '.join(nt)} |")
    P(); P(f"**Valid buckets (ε ± SE), target {tg}: {nv}/{len(buckets)}**; not exceeding ε+SE: {nne}/{len(buckets)}."+(f" ({10-len(buckets)} empty decile(s) merged; count is out of {len(buckets)} non-empty buckets.)" if len(buckets)<10 else "")); P()
    OUT[f"A_valid_{tg}"]=(int(nv),len(buckets)); OUT[f"A_notexceed_{tg}"]=(int(nne),len(buckets))
OUT["A"]={f"{bname(A[k]['b'])}|{k[1]}":{kk:vv for kk,vv in A[k].items() if kk!='rows'}|{"rows":A[k]["rows"]} for k in A}
# trace table
HW={"S4b":{"t3":"14/3","t4":"10/3","t6":"0/3","t7":"0/3"},"S4a":{"t3":"7/3","t4":"3/3","t6":"0/3","t7":"1/3"}}
M1={"S4a":{"t3":3,"t4":2,"t6":3,"t7":0},"S4b":{"t3":5,"t4":4,"t6":5,"t7":0}}   # m1/REPORT.md Supplement R58-2 (v8sim11 @ full λ)
REG={"S4a":{"t3":3,"t4":0,"t6":0,"t7":0},"S4b":{"t3":3,"t4":1,"t6":0,"t7":0}}  # m1 registered nest2 @ full λ
P("### Test traces under decile λ"); P()
P("Decile λ = mean of the bucket's six split λ (rounded to 0.01), target 0.5 % for S4a and 2 % for S4b. nest2 = frozen `v8sim10.sim_nest2(ue,cfg,pr,L,acct='vmexist')`; v8sim11 = `V.run(ue,'S',L=L)` (CtlSigma with the given λ, start=None → initial_fleet with the same λ, PHYS defaults, R38 on). Full-library λ columns: registered nest2 and v8sim11 values from m1/REPORT.md Supplement R58-2, re-simulated here (fresh value in brackets when it differs). Units: violating minutes per run (alloc vmexist in parentheses)."); P()
P("| trace | rise1 | bucket | arm | decile λ | full λ: nest2 | full λ: v8sim11 | decile λ: nest2 | decile λ: v8sim11 | hardware (total/runs) |"); P("|---|---|---|---|---|---|---|---|---|---|")
TT=[]
for tn in ("t3","t4","t6","t7"):
    for arm,tg in (("S4a",0.005),("S4b",0.02)):
        a=A[(tbuck[tn],tg)]; Ld=(round(a["lv"],2),round(a["lu"],2)); ue=TR[tn]
        f2=Q2.sim_nest2(ue,cfg,pr,{"vy":DEP[arm][0],"wk":DEP[arm][0],"up":DEP[arm][1]},acct='vmexist'); f11=V.run(ue,arm)
        d2=Q2.sim_nest2(ue,cfg,pr,{"vy":Ld[0],"wk":Ld[0],"up":Ld[1]},acct='vmexist'); d11=V.run(ue,"S",L={"vy":Ld[0],"wk":Ld[0],"up":Ld[1]})
        x=lambda reg,fresh: f"{reg}"+("" if reg==fresh else f" [fresh {fresh}]")
        row=dict(trace=tn,arm=arm,lam=Ld,full_n2=60-f2["slo"],full_11=60-f11["slo"],dec_n2=60-d2["slo"],dec_11=60-d11["slo"],dec_n2_alloc=d2["alloc"],dec_11_alloc=d11["alloc_vm"],full_n2_alloc=f2["alloc"],full_11_alloc=f11["alloc_vm"],hw=HW[arm][tn])
        TT.append(row)
        P(f"| {tn} | {trise[tn]:g} | {bname(buckets[tbuck[tn]])} | {arm} | {Ld[0]}/{Ld[1]} | {x(REG[arm][tn],row['full_n2'])} ({f2['alloc']:.0f}) | {x(M1[arm][tn],row['full_11'])} ({f11['alloc_vm']:.0f}) | {row['dec_n2']} ({d2['alloc']:.0f}) | {row['dec_11']} ({d11['alloc_vm']:.0f}) | {HW[arm][tn]} |")
OUT["A_traces"]=TT
# monotonicity
P(); P("### Knob monotonicity (realised risk ordering S4a ≤ S4b ≤ v6)"); P()
rq=[r for r in csv.DictReader(open(f"{E}/paper_out_new/rq/rq_metrics.csv")) if r.get("group")]
def hw(tn,arm):
    rr=[r for r in rq if r["group"]==f"MAIN {tn} {arm}"]; return sum(60-int(r["slo"]) for r in rr),len(rr),[r["run"] for r in rr]
P("Hardware: groups exactly 'MAIN tX S4a' / 'MAIN tX S4b' / 'MAIN tX v6' in rq_metrics.csv (VOID runs and 'v6 confirm post-IRQ' r381 excluded; r381 noted). Violating minutes per run = 60 − slo. Simulation rows: nest2 (S4a/S4b at deployed λ) and v8sim2.sim_v6 on the same trace; Madrid from qsim/madrid/t12_table.md; Melbourne library = fresh deployed-λ sims over all 1615 traces."); P()
P("| setting | S4a | S4b | v6 | order | reversal? |"); P("|---|---|---|---|---|---|")
def judge(a,b,c):
    rev=[]
    if a>b+1e-12: rev.append("S4a > S4b")
    if b>c+1e-12: rev.append("S4b > v6")
    return ", ".join(rev) if rev else "none"
MONO=[]
for tn in ("t3","t4","t5","t6","t7"):
    h={arm:hw(tn,arm) for arm in ("S4a","S4b","v6")}; rr={arm:h[arm][0]/h[arm][1] for arm in h}
    order=" < ".join(sorted(rr,key=lambda k:rr[k])) if len(set(rr.values()))==3 else " ≤ ".join(sorted(rr,key=lambda k:rr[k]))
    j=judge(rr["S4a"],rr["S4b"],rr["v6"]); MONO.append((f"hardware {tn}",j))
    P(f"| hardware {tn} | {h['S4a'][0]}/{h['S4a'][1]} ({rr['S4a']:.2f}) | {h['S4b'][0]}/{h['S4b'][1]} ({rr['S4b']:.2f}) | {h['v6'][0]}/{h['v6'][1]} ({rr['v6']:.2f}) | {order} | **{j}** |")
for tn in ("t3","t4","t5","t6","t7"):
    ue=TR[tn]; s=[60-Q2.sim_nest2(ue,cfg,pr,{"vy":DEP[a][0],"wk":DEP[a][0],"up":DEP[a][1]})["slo"] for a in ("S4a","S4b")]+[60-S.sim_v6(ue,cfg)["slo"]]
    j=judge(*s); MONO.append((f"nest2 {tn}",j)); P(f"| sim nest2/sim_v6 {tn} | {s[0]} | {s[1]} | {s[2]} | | {j} |")
for ln in open('/home/user/experiment/qsim/madrid/t12_table.md'):
    pass
mad={}
for ln in open('/home/user/experiment/qsim/madrid/t12_table.md'):
    m=re.match(r"\| (madrid_\w+) \| \d+ \| (S4a|S4b|v6) \| ([\d.]+)%",ln)
    if m: mad.setdefault(m[1],{})[m[2]]=float(m[3])
for lb,v in mad.items():
    j=judge(v["S4a"],v["S4b"],v["v6"]); MONO.append((lb,j)); P(f"| {lb} (sim, mean risk %) | {v['S4a']:.3f} | {v['S4b']:.3f} | {v['v6']:.3f} | | {j} |")
mel={a:100*FR[a]["v"].mean() for a in ("S4a","S4b","v6")}; j=judge(mel["S4a"],mel["S4b"],mel["v6"]); MONO.append(("melbourne lib",j))
P(f"| Melbourne library 1615 (sim, mean risk %) | {mel['S4a']:.3f} | {mel['S4b']:.3f} | {mel['v6']:.3f} | | {j} |")
r381=[r for r in rq if r["run"]=="r381"]; P(); P(f"(r381 'MAIN t4 v6 confirm post-IRQ': {60-int(r381[0]['slo'])} violating minutes; including it, hardware t4 v6 = {(hw('t4','v6')[0]+60-int(r381[0]['slo']))}/{hw('t4','v6')[1]+1}.)" if r381 else "")
OUT["mono"]=MONO
# ================= Task B =================
P(); P("## Task B: uncertainty"); P()
G=groups_of(); KEYS=sorted(G); NG=len(KEYS); P(f"(loc,date) groups in library: {NG}"); P()
rng=np.random.default_rng(20261021); B1={tg:[] for tg in TGT}; B1all={tg:[] for tg in TGT}
for b in range(200):
    draw=rng.integers(0,NG,size=NG); drawn=set(int(x) for x in draw)
    tr=[i for q in draw for i in G[KEYS[int(q)]]]; h=[i for q in range(NG) if q not in drawn for i in G[KEYS[q]]]
    for tg in TGT:
        for cal,store in ((tr[:300],B1),(tr,B1all)):
            res,info=calibrate(cal,tg); inf=res is None; res=res or info; hr,ha,hv=heldout(h,res["lam_vm"],res["lam_up"])
            store[tg].append((res["lam_vm"],res["lam_up"],hr,hv,inf,len(h)))
P("### B1 cluster bootstrap (200 resamples of the 125 groups with replacement, numpy default_rng(20261021).integers; calibration = first 300 resampled traces in draw order (primary, = the cal[:300] convention) or all resampled traces (secondary); held-out = groups never drawn)"); P()
P("| target | calibration | λ_VM mean [2.5, 97.5] | λ_UP mean [2.5, 97.5] | ho risk mean [2.5, 97.5] | P(ho risk > ε) | ho alloc vmexist mean [2.5, 97.5] | ho n (mean) | infeasible |"); P("|---|---|---|---|---|---|---|---|---|")
q=lambda a,f: f"{f.format(np.mean(a))} [{f.format(np.percentile(a,2.5))}, {f.format(np.percentile(a,97.5))}]"
for tg in TGT:
    for nm,st in (("300 (primary)",B1),("all resampled",B1all)):
        a=np.array(st[tg],dtype=float)
        P(f"| {tg} | {nm} | {q(a[:,0],'{:.2f}')} | {q(a[:,1],'{:.2f}')} | {q(a[:,2],'{:.4f}')} | {np.mean(a[:,2]>tg):.2f} | {q(a[:,3],'{:.1f}')} | {a[:,5].mean():.0f} | {int(a[:,4].sum())} |")
OUT["B1"]={str(tg):B1[tg] for tg in TGT}; OUT["B1all"]={str(tg):B1all[tg] for tg in TGT}
P(); P("### B2 library size (calibration group budget)"); P()
P("125 = the standard six splits (grouped_split seeds 0-5: 75 calibration groups, 50 held-out groups). 60 / 30 = six random group subsets (seed s: sorted keys, random.Random(s).shuffle, first 60 / 30 groups), held-out = all groups not in the subset. 'cap 300' = calibration traces truncated to the first 300 (the frozen convention; with ≈13 traces per group this binds for 125 and 60 and nearly for 30), 'uncapped' = all traces of the calibration groups."); P()
P("| target | groups | cap | cal n (mean) | λ_VM mean ± std | λ_UP mean ± std | ho risk mean ± std | ho alloc vmexist mean ± std |"); P("|---|---|---|---|---|---|---|---|")
B2={}
for tg in TGT:
    for size in (125,60,30):
        for cap in (300,None):
            rows=[]
            for s in range(6):
                if size==125:
                    c,h=grouped_split(s)
                else:
                    kk=list(KEYS); random.Random(s).shuffle(kk); sub=set(kk[:size]); c=[i for q2 in kk[:size] for i in G[q2]]; h=[i for q2 in KEYS if q2 not in sub for i in G[q2]]
                c=c[:cap] if cap else c
                res,info=calibrate(c,tg); res=res or info; hr,ha,hv=heldout(h,res["lam_vm"],res["lam_up"]); rows.append((res["lam_vm"],res["lam_up"],hr,hv,len(c)))
            a=np.array(rows); B2[(tg,size,cap)]=rows
            P(f"| {tg} | {size} | {cap or 'uncapped'} | {a[:,4].mean():.0f} | {a[:,0].mean():.2f} ± {a[:,0].std():.2f} | {a[:,1].mean():.2f} ± {a[:,1].std():.2f} | {a[:,2].mean():.4f} ± {a[:,2].std():.4f} | {a[:,3].mean():.1f} ± {a[:,3].std():.1f} |")
OUT["B2"]={f"{k[0]}|{k[1]}|{k[2]}":v for k,v in B2.items()}
P(); P("### B3 event rate (consecutive violating minutes collapsed into one event)"); P()
P("Deployed points simulated fresh on all 1615 traces (dual-accounting copy of frozen nest2; 1.83 and 2.83 are off the 0.25 grid). v6 = frozen `v8sim2.sim_v6` does **not** expose per-minute violations (returns slo, alloc, acts, flaps only), so it was run through `dual.sim_v6_pm`, a copy generated from the frozen source whose only change is to also return the per-minute loss vector pct; slo/alloc/acts/flaps verified identical on 60 random traces (verify_dual.py) and violating minutes = 60 − slo checked on all 1615 traces. Grid points 1.75/2.00 and 2.75/3.00 from the matrix shown for reference."); P()
P("| controller | λ | minute rate | events / 60-min trace | events / minute | mean event length (min) | max length | traces with ≥ 1 event | mean alloc vmexist |"); P("|---|---|---|---|---|---|---|---|---|")
def evstats(v):
    v=np.asarray(v,bool); st=v&~np.concatenate([np.zeros((v.shape[0],1),bool),v[:,:-1]],axis=1); ne=st.sum(); nm=v.sum()
    # max length
    mx=0
    for row in v:
        c=0
        for x in row: c=c+1 if x else 0; mx=max(mx,c)
    return dict(minute_rate=float(nm/v.size),ev_per_trace=float(ne/v.shape[0]),ev_per_min=float(ne/v.size),mean_len=float(nm/ne) if ne else float('nan'),max_len=int(mx),frac_traces=float((v.sum(1)>0).mean()))
B3={}
rowsB3=[("S4b (deployed)","1.83/2.00",FR["S4b"]["v"],FR["S4b"]["av"].mean()),("S4a (deployed)","2.83/3.08",FR["S4a"]["v"],FR["S4a"]["av"].mean()),("v6","fixed constants",FR["v6"]["v"],float('nan'))]
for nm,(lv,lu) in (("grid ref (≈S4b)",(1.75,2.0)),("grid ref (≈S4a)",(2.75,3.0))):
    p=Lk.PIDX[(lv,lu)]; rowsB3.append((nm,f"{lv}/{lu}",Lk.vbits_to_mat(Lk.VB[:,p]),Lk.AV[:,p].mean()))
for nm,lam,v,al in rowsB3:
    e=evstats(v); B3[nm]=e|{"lam":lam}
    P(f"| {nm} | {lam} | {100*e['minute_rate']:.3f} % | {e['ev_per_trace']:.3f} | {e['ev_per_min']:.5f} | {e['mean_len']:.2f} | {e['max_len']} | {100*e['frac_traces']:.1f} % | {'-' if al!=al else f'{al:.1f}'} |")
OUT["B3"]=B3
Lk.save_cache(); OUT["fresh_offgrid_sims"]=Lk.NFRESH[0]; OUT["runtime_s"]=time.time()-T0; OUT["fresh_deployed_s"]=T_FRESH
P(); P(f"(off-matrix fresh sims for refinement: {Lk.NFRESH[0]}; analyze.py runtime {time.time()-T0:.0f} s)")
json.dump(OUT,open(f'{R}/results.json','w'),default=lambda o: o.tolist() if hasattr(o,'tolist') else str(o),indent=1)
open(f'{R}/report_tables.md','w').write("\n".join(MD)+"\n")
