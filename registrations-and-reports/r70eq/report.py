#!/usr/bin/env python3
"""spec §4.138: E1 (equal per-slot risk), frontier figure, I1, I2, prefill, library re-calibration; REPORT.md"""
import timeit  # noqa
import sys, os, json, glob, collections, hashlib, numpy as np
Q='/home/user/experiment/qsim'; R=f'{Q}/r70eq'; E='/home/user/experiment'
for p in (Q,Q+'/r67band',Q+'/r70eq'): sys.path.insert(0,p)
os.chdir(Q)
from scipy.stats import spearmanr
import scan as SC
LIB=SC.LIB; N=len(LIB); TGT=SC.TGT
TB=json.load(open(f'{Q}/r67band/out/tables.json'))
mpf=lambda u: float(np.mean(u)/max(u)); r1f=lambda u: float(max(u[k]-u[k-1] for k in range(1,len(u))))
X={"mp":np.array([mpf(t["ue"][:60]) for t in LIB]),"rise1":np.array([r1f(t["ue"][:60]) for t in LIB])}
def bkf(f,v):
    thr=TB[f]['thr']; mg={int(k):x for k,x in TB[f]['merge'].items()}; d=next((i+1 for i,th in enumerate(thr) if v<=th),10); return mg[d]
BK={f:np.array([bkf(f,v) for v in X[f]]) for f in X}
BOOT=np.random.default_rng(20261027).integers(0,N,size=(1000,N))
def bst(rv,f,ix=None):
    ix=np.arange(N) if ix is None else ix; b=BK[f][ix]; r=rv[ix]; br=np.array([r[b==k].mean() for k in sorted(set(BK[f])) if (b==k).any()]); nz=br[br>0]
    return br,(br.max()/br.min() if br.min()>0 else np.inf),(br.max()/nz.min() if len(nz) else np.nan),float(np.std(br))
def slope(rv,x,ix): xx=x[ix]; yy=rv[ix]; xm=xx.mean(); return float(((xx-xm)*(yy-yy.mean())).sum()/((xx-xm)**2).sum())
def u1(rows,f):
    rv=np.array([(60-r['slo'])/60 for r in rows]); br,mm,mmz,sd=bst(rv,f); bs=[slope(rv,X[f],ix) for ix in BOOT]
    return dict(rv=rv,br=br,mm=mm,mmz=mmz,sd=sd,slope=slope(rv,X[f],np.arange(N)),ci=(float(np.percentile(bs,2.5)),float(np.percentile(bs,97.5))),bsd=np.array([bst(rv,f,ix)[3] for ix in BOOT]))
def more_uniform(s,b):
    fin=np.isfinite(s['mm']) and np.isfinite(b['mm']); ms,mb=(s['mm'],b['mm']) if fin else (s['mmz'],b['mmz'])
    dis=s['ci'][1]<b['ci'][0] or b['ci'][1]<s['ci'][0]; return ms<mb and s['sd']<b['sd'] and dis,ms,mb,dis
BASEK={"2":{"B4c2":"B4_3.75_300","B5c1":"B5_4.0_L2","B6":"B6_0.775"},"05":{"B4c2":"B4_3.0_300","B5c1":"B5_3.5_L1","B6":"B6_0.7"}}
BROWS={n:json.load(open(f'{Q}/r67band/out/{n}.json'))['rows'] for g in BASEK.values() for n in g.values()}
out=[]; P=lambda s="": (print(s),out.append(s))
md5=lambda f: hashlib.md5(open(f,'rb').read()).hexdigest()[:8]
P("# r70eq (spec §4.138)\n"); P("Simulation only; frozen-file md5 after: "+" ".join(md5(f'{Q}/{f}') for f in ("v8sim10.py","v8sim10_abl.py","v8sim11.py","v8sim2.py","v8sim_b6.py","prior_traces.json"))+" (before 3daf1387 7a2b02ec ecdfff61 4697713c b24eae16 edb8e00c).\n")
# ---------- item 1
pts=collections.defaultdict(list)
for fn in glob.glob(f'{R}/out/scan/*.json'):
    d=json.load(open(fn)); pts[(d['arm'],d['g'])].append(d)
EQ={}
for (arm,g),ps in pts.items():
    ps=sorted(ps,key=lambda d:d['c']); t=TGT[g]; br=[(x,y) for x,y in zip(ps,ps[1:]) if (x['risk']-t)*(y['risk']-t)<=0]
    if not br: EQ[(arm,g)]=None; continue
    x,y=min(br,key=lambda p:p[1]['c']-p[0]['c']); w=(t-x['risk'])/(y['risk']-x['risk']) if y['risk']!=x['risk'] else 0.0
    near=x if abs(x['risk']-t)<=abs(y['risk']-t) else y
    cvec=(1-w)*np.array([r['alloc_vm'] for r in x['rows']])+w*np.array([r['alloc_vm'] for r in y['rows']])
    lay={k:(1-w)*np.mean([r[k] for r in x['rows']])+w*np.mean([r[k] for r in y['rows']]) for k in ('wk_min','vy_min','slot_min','flaps')}
    EQ[(arm,g)]=dict(lo=x,hi=y,w=w,near=near,cvec=cvec,cost=float(cvec.mean()),lay=lay,within=[abs(z['risk']-t)<=0.0005 for z in (x,y)])
P("## Item 1: equal per-slot risk (v8sim11 R38 off, own initial_fleet)\n")
P(f"Targets: 2 % group {100*TGT['2']:.3f} % (S4b 1.83/2.00), 0.5 % group {100*TGT['05']:.3f} % (S4a 2.83/3.08).\n")
P("### Table E1\n\n| group | arm | bracket c (risk %) | within ±0.05 pp | equal-risk alloc_vm | Δcost vs S4 % [95 % CI] | flaps | worker / VyOS / slot min | U1 mp max/min, std (pp), slope [CI] | std − S4 [CI] | more uniform than B4c2 / B5c1 / B6 | verdicts |\n|---|---|---|---|---|---|---|---|---|---|---|---|")
E1={}
for g in ("2","05"):
    s4=EQ[("S4",g)]; s4u=u1(s4['near']['rows'],'mp')
    for arm in ("S4","APL","S8","S4p"):
        e=EQ.get((arm,g))
        if e is None: P(f"| {g} | {arm} | target outside the frontier | | | | | | | | | |"); continue
        dc=100*(e['cost']/s4['cost']-1); bd=[100*(e['cvec'][ix].mean()/s4['cvec'][ix].mean()-1) for ix in BOOT]; ci=(np.percentile(bd,2.5),np.percentile(bd,97.5))
        uu=u1(e['near']['rows'],'mp'); dsd=uu['bsd']-s4u['bsd']; sci=(np.percentile(dsd,2.5),np.percentile(dsd,97.5))
        mus=[more_uniform(uu,u1(BROWS[BASEK[g][b]],'mp')) for b in ("B4c2","B5c1","B6")]
        notworse=(ci[1]<=0) or (ci[0]<=0<=ci[1] and dc<=0); cheaper=ci[1]<0; keep=(sci[0]<=0) and all(m[0] for m in mus)
        E1[(g,arm)]=dict(dc=dc,ci=ci,flaps=e['lay']['flaps'],keep=keep,notworse=notworse,cheaper=cheaper,sci=sci)
        P(f"| {g} | {arm} | {e['lo']['c']:.2f} ({100*e['lo']['risk']:.3f}) – {e['hi']['c']:.2f} ({100*e['hi']['risk']:.3f}) | {e['within']} | {e['cost']:.1f} | {dc:+.2f} [{ci[0]:+.2f}, {ci[1]:+.2f}] | {e['lay']['flaps']:.2f} | {e['lay']['wk_min']:.1f} / {e['lay']['vy_min']:.1f} / {e['lay']['slot_min']:.1f} | {uu['mmz']:.2f}, {100*uu['sd']:.2f}, {100*uu['slope']:+.2f} [{100*uu['ci'][0]:+.2f}, {100*uu['ci'][1]:+.2f}] | {100*(uu['sd']-s4u['sd']):+.2f} [{100*sci[0]:+.2f}, {100*sci[1]:+.2f}] | {' / '.join('yes' if m[0] else 'no' for m in mus)} | {'not worse' if notworse else 'worse'}{', cheaper' if cheaper else ''}; uniformity {'kept' if keep else 'not kept'} |")
P("\nU1 rise1 at the nearer point (max/min non-zero min, std pp, slope):\n")
for g in ("2","05"):
    for arm in ("S4","APL","S8","S4p"):
        e=EQ.get((arm,g))
        if e: uu=u1(e['near']['rows'],'rise1'); P(f"- {g} {arm} (c {e['near']['c']:.2f}): {uu['mmz']:.2f}, {100*uu['sd']:.2f}, {100*uu['slope']:+.3f} [{100*uu['ci'][0]:+.3f}, {100*uu['ci'][1]:+.3f}]")
P("\nt3–t8 per trace at the nearer point (per-slot R38 off: violation minutes / alloc_vm):\n\n| group | arm | c | t3 | t4 | t5 | t6 | t7 | t8 |\n|---|---|---|---|---|---|---|---|---|")
for g in ("2","05"):
    for arm in ("S4","APL","S8","S4p"):
        e=EQ.get((arm,g))
        if not e: continue
        a,b=SC.BASE[g][arm]; c=e['near']['c']; L={"vy":round(c*a,4),"wk":round(c*a,4),"up":round(c*b,4)}; cells=[]
        for tn in ("t3","t4","t5","t6","t7","t8"):
            ue=json.load(open(f"{E}/trace_ue_60min_v3_{tn}.json"))["ue"][:60]; r=SC.sim_one(arm,L,ue); cells.append(f"{r['viol']} / {r['alloc_vm']:.0f}")
        P(f"| {g} | {arm} | {c:.2f} | "+" | ".join(cells)+" |")
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
fig,axs=plt.subplots(1,2,figsize=(10,3.8)); COL={"S4":"#1b4f9c","APL":"#8e44ad","S8":"#d9822b","S4p":"#0e8a8a"}; MK={"S4":"o","APL":"P","S8":"s","S4p":"*"}
for ax,g in zip(axs,("2","05")):
    for arm in ("S4","APL","S8","S4p"):
        ps=sorted(pts[(arm,g)],key=lambda d:d['c']); ax.plot([100*d['risk'] for d in ps],[d['cost'] for d in ps],marker=MK[arm],ms=4,lw=1.6,color=COL[arm],label={"S4":"S4","APL":"A-PL","S8":"S8","S4p":"S4′"}[arm])
    ax.axvline(100*TGT[g],color="#888",lw=0.9,ls="--"); ax.set_xlabel("per-slot library risk (%)"); ax.set_title(f"{'2 %' if g=='2' else '0.5 %'} group (target {100*TGT[g]:.2f} %)",fontsize=9); ax.grid(lw=0.3); ax.legend(fontsize=7,frameon=False)
axs[0].set_ylabel("library mean alloc_vm (core-min)"); fig.tight_layout(); fig.savefig(f'{R}/fig_frontier_perslot.pdf'); plt.close(fig)
# ---------- item 2
A=json.load(open(f'{R}/out/audit.json'))
P(f"\n## Item 2: start-fleet audit\n\nEquivalence: {A['equiv']}.\n\n### Table I1 (hardware minute-0 fleet vs simulator initial_fleet; slot / VyOS / worker)\n\n| trace | arm | run | hardware | simulator | same |\n|---|---|---|---|---|---|")
for r in A['I1']: P(f"| {r['trace']} | {r['arm']} | {r['run']} | {'/'.join(map(str,r['hw']))} | {'/'.join(map(str,r['sim']))} | {'yes' if r['same'] else 'no'} |")
bytr=collections.defaultdict(set)
for r in A['I1']: bytr[r['trace']].add(tuple(r['hw']))
same_n=sum(1 for r in A['I1'] if r['same']); P(f"\nSame start: {same_n} of {len(A['I1'])} runs. Distinct hardware starts per trace: "+"; ".join(f"{t} {sorted(v)}" for t,v in sorted(bytr.items()))+". Arm-independent per trace: "+("yes" if all(len(v)==1 for v in bytr.values()) else "no")+".\n")
P("### Table I2 (alloc_vm; error % = prediction / hardware − 1)\n\n| trace | arm | hardware | per-slot orig → new (err %) | fleet orig → new (err %) |\n|---|---|---|---|---|")
mv=collections.Counter(); out2=collections.Counter(); outA=collections.Counter()
for c in A['I2']:
    h=c['hw']; e=lambda v: 100*(v/h-1)
    s=f"{c['ps_orig']:.1f} ({e(c['ps_orig']):+.2f}) → {c['ps_new']:.1f} ({e(c['ps_new']):+.2f})"
    f=(f"{c['fl_orig']:.1f} ({e(c['fl_orig']):+.2f}) → {c['fl_new']:.1f} ({e(c['fl_new']):+.2f})" if c['fl_orig'] is not None else "—")
    P(f"| {c['trace']} | {c['arm']} | {h:.1f} | {s} | {f} |")
    for ver,o,n in (("per-slot",c['ps_orig'],c['ps_new']),("fleet",c['fl_orig'],c['fl_new'])):
        if o is None: continue
        if abs(n/o-1)>0.01: mv[ver]+=1
        if abs(o/h-1)<=0.02 and abs(n/h-1)>0.02: out2[ver]+=1
        if abs(n/h-1)>0.02: outA[ver]+=1
ncell={v:sum(1 for c in A['I2'] if (v=="per-slot" or c['fl_orig'] is not None)) for v in ("per-slot","fleet")}
P("\n"+"; ".join(f"{v}: {ncell[v]} cells, moved > 1 % {mv[v]}, moved out of ±2 % {out2[v]}, outside ±2 % after the move {outA[v]}" for v in ("per-slot","fleet"))+".\n")
P("### HPA prefill (B4c2 / B5c1 hardware cells; per-slot default physics unless noted)\n\n| trace | arm | hardware | own start | hardware start | hardware start + prefill | + prefill, R38 off |\n|---|---|---|---|---|---|---|")
for c in A['prefill']: P(f"| {c['trace']} | {c['arm']} | {c['hw']:.1f} | {c['ps_orig']:.1f} | {c['ps_hwstart']:.1f} | {c['ps_hwstart_prefill']:.1f} ({100*(c['ps_hwstart_prefill']/c['hw']-1):+.2f} %) | {c['ps_hwstart_prefill_r38off']:.1f} ({100*(c['ps_hwstart_prefill_r38off']/c['hw']-1):+.2f} %) |")
# ---------- library
P("\n### Library re-calibration under unified start rules\n")
orig=[r for r in json.load(open(f'{Q}/r62cf/calib_results.json')) if r['phys']=='off' and r['fam'] in ("B4","B5","B6","S")]
STEP={"B4":0.25,"B5":0.25,"B6":0.025,"S":0.25}; USER={("B4",0.02):[3.75,300],("B5",0.02):[4.0,"L2"],("B6",0.02):[0.775],("S",0.02):[2.25],("B4",0.005):[3.0,300],("B5",0.005):[3.5,"L1"],("B6",0.005):[0.7],("S",0.005):[3.25]}
LIBV={}
for rule in ("s4b","b1"):
    fn=f'{R}/out/libcal/{rule}/calib.json'
    if not os.path.exists(fn): P(f"- rule {rule}: not finished"); continue
    new=json.load(open(fn)); P(f"#### rule '{rule}' ({'all arms at initial_fleet(S4b)' if rule=='s4b' else 'all arms at 8/3/4'})\n\n| family | target | original picks (6 splits) | new picks | max grid-step change | discrete changed | mode |\n|---|---|---|---|---|---|---|")
    mode={}; maxstep=0; dchg=False
    for fam in ("B4","B5","B6","S"):
        for tg in (0.02,0.005):
            o=sorted([r for r in orig if r['fam']==fam and r['target']==tg],key=lambda r:r['seed']); n=sorted([r for r in new if r['fam']==fam and r['target']==tg],key=lambda r:r['seed'])
            st=max(abs(a['key'][0]-b['key'][0])/STEP[fam] for a,b in zip(o,n)); dc=any(len(a['key'])>1 and a['key'][1]!=b['key'][1] for a,b in zip(o,n)); maxstep=max(maxstep,st); dchg|=dc
            cnt=collections.Counter(tuple(r['key']) for r in n); top=max(cnt.values()); tied=[k for k,v in cnt.items() if v==top]; u=tuple(USER[(fam,tg)])
            m=u if u in tied else sorted(tied,key=lambda k:k[0])[0]; mode[(fam,tg)]=m
            P(f"| {fam} | {tg} | {', '.join('/'.join(map(str,r['key'])) for r in o)} | {', '.join('/'.join(map(str,r['key'])) for r in n)} | {st:.0f} | {dc} | {'/'.join(map(str,m))} |")
    rows=lambda fam,key: json.load(open(f"{R}/out/libcal/{rule}/{fam}_{'_'.join(str(k) for k in key)}.json"))['rows']
    flips=[]
    for g,tg,Sk in (("2",0.02,(1.83,2.0)),("05",0.005,(2.83,3.08))):
        S=rows("S2",Sk); sr=np.mean([(60-r['slo'])/60 for r in S]); sc=np.mean([r['alloc_vm'] for r in S]); su=u1(S,'mp')
        for bn,fam in (("B4c2","B4"),("B5c1","B5"),("B6","B6")):
            k=mode[(fam,tg)]; fnb=f"{R}/out/libcal/{rule}/{fam}_{'_'.join(str(x) for x in k)}.json"
            if not os.path.exists(fnb): P(f"- {g} {bn}: mode knob {k} not cached"); continue
            Bw=rows(fam,k); br_=np.mean([(60-r['slo'])/60 for r in Bw]); bc=np.mean([r['alloc_vm'] for r in Bw]); dcost=100*(sc/bc-1); drisk=100*(sr-br_)
            v="cheaper" if (dcost<=-2 and drisk<=0.2) else ("more expensive" if (dcost>=2 and drisk>=-0.2) else "same level")  # r67band table-B rule
            mu,ms,mb,dis=more_uniform(su,u1(Bw,'mp')); origmu={"2":{"B4c2":True,"B5c1":True,"B6":True},"05":{"B4c2":False,"B5c1":True,"B6":True}}[g][bn]
            P(f"- {g}: S vs {bn} {'/'.join(map(str,k))}: library Δcost {dcost:+.2f} %, Δrisk {drisk:+.2f} pp -> {v}; mp more uniform {mu} (max/min {ms:.2f} vs {mb:.2f}, std {100*su['sd']:.2f} vs {100*u1(Bw,'mp')['sd']:.2f} pp, slope CI [{100*su['ci'][0]:+.2f}, {100*su['ci'][1]:+.2f}] vs [{100*u1(Bw,'mp')['ci'][0]:+.2f}, {100*u1(Bw,'mp')['ci'][1]:+.2f}], disjoint {dis}; originally {origmu})")
            if v!="same level": flips.append(f"{g} {bn} library verdict {v}")
            if mu!=origmu: flips.append(f"{g} {bn} uniformity {origmu}->{mu}")
    LIBV[rule]=dict(maxstep=maxstep,dchg=dchg,flips=flips)
    P(f"\nRule '{rule}': max continuous-knob change {maxstep:.0f} grid step(s), discrete knob changed {dchg}; flipped verdicts: {flips or 'none'}\n")
# ---------- conclusions
P("## Conclusions (registered rules only)\n")
for g in ("2","05"):
    for arm in ("S4","APL","S8","S4p"):
        if (g,arm) in E1:
            e=E1[(g,arm)]; P(f"- {'2 %' if g=='2' else '0.5 %'} {arm}: Δcost {e['dc']:+.2f} % [{e['ci'][0]:+.2f}, {e['ci'][1]:+.2f}], flaps {e['flaps']:.2f}, {'not worse than S4' if e['notworse'] else 'worse than S4'}{' (cheaper)' if e['cheaper'] else ''}, uniformity {'kept' if e['keep'] else 'not kept'}.")
P(f"- Registered predictions: per-slot moved > 1 % in {mv['per-slot']} cells, moved out of ±2 % in {out2['per-slot']}; fleet {mv['fleet']} and {out2['fleet']} -> "+("start deviation does not affect the fidelity claim" if (mv['per-slot']+mv['fleet']<=2 and out2['per-slot']+out2['fleet']==0) else "affected cells listed in Table I2; the fidelity table switches to the hardware-start version"))
for rule,v in LIBV.items(): P(f"- Library, rule '{rule}': knob change {v['maxstep']:.0f} grid step(s) (discrete changed {v['dchg']}), flips {v['flips'] or 'none'} -> "+("start does not affect calibration and parity conclusions" if (v['maxstep']<=1 and not v['dchg'] and not v['flips']) else "affected"))
open(f'{R}/REPORT.md','w').write("\n".join(out)+"\n")
