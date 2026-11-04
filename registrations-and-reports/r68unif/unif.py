#!/usr/bin/env python3
"""spec §4.136: tables U1 (uniformity), U2 (per-layer decomposition), T6, S4p, the A-PL attribution and the four S4' checks; fig_risk_by_band.pdf; REPORT.md.
Buckets: r67band thresholds (out/tables.json, not recomputed). Bootstrap: numpy default_rng(20261027), 1000 resamples of traces (paired across arms)."""
import sys, os, json, hashlib, numpy as np
from scipy.stats import spearmanr
Q='/home/user/experiment/qsim'; RB=f'{Q}/r67band'; R=f'{Q}/r68unif'; E='/home/user/experiment'
LIB=json.load(open(f'{Q}/prior_traces.json')); N=len(LIB)
TB=json.load(open(f'{RB}/out/tables.json'))
def load(fn): return json.load(open(fn))['rows']
ROWS={n:load(f'{RB}/out/{n}.json') for n in ("S4b","S1_2.25","B4_3.75_300","B5_4.0_L2","B6_0.775","S4a","S1_3.25","B4_3.0_300","B5_3.5_L1","B6_0.7","v6","B1")}
for n in ("APL_2","APL_05","S4p_2","S4p_05"):
    if os.path.exists(f'{R}/out/{n}.json'): ROWS[n]=load(f'{R}/out/{n}.json')
DEP=json.load(open(f'{R}/out/deployed.json')) if os.path.exists(f'{R}/out/deployed.json') else {}
GR={"2 %":dict(S="S4b",arms=["S4b","S1_2.25","B4_3.75_300","B5_4.0_L2","B6_0.775","v6","B1","APL_2","S4p_2"],base={"B4c2":"B4_3.75_300","B5c1":"B5_4.0_L2","B6":"B6_0.775"},apl="APL_2",s4p="S4p_2"),
    "0.5 %":dict(S="S4a",arms=["S4a","S1_3.25","B4_3.0_300","B5_3.5_L1","B6_0.7","v6","B1","APL_05","S4p_05"],base={"B4c2":"B4_3.0_300","B5c1":"B5_3.5_L1","B6":"B6_0.7"},apl="APL_05",s4p="S4p_05")}
LAB={"S4b":"S4b","S1_2.25":"S single 2.25","B4_3.75_300":"B4c2 3.75/300","B5_4.0_L2":"B5c1 4.0/L2","B6_0.775":"B6 0.775","S4a":"S4a","S1_3.25":"S single 3.25","B4_3.0_300":"B4c2 3.0/300",
     "B5_3.5_L1":"B5c1 3.5/L1","B6_0.7":"B6 0.70","v6":"v6","B1":"B1","APL_2":"A-PL","APL_05":"A-PL","S4p_2":"S4′","S4p_05":"S4′"}
mpf=lambda u: float(np.mean(u)/max(u)); r1f=lambda u: float(max(u[k]-u[k-1] for k in range(1,len(u))))
X={"mp":np.array([mpf(t["ue"][:60]) for t in LIB]),"rise1":np.array([r1f(t["ue"][:60]) for t in LIB])}
def bk_of(feat,v):
    thr=TB[feat]['thr']; merge={int(k):v2 for k,v2 in TB[feat]['merge'].items()}
    d=next((i+1 for i,th in enumerate(thr) if v<=th),10); return merge[d]
BK={f:np.array([bk_of(f,v) for v in X[f]]) for f in X}
risk=lambda a: np.array([(60-r['slo'])/60 for r in ROWS[a]])
rng=np.random.default_rng(20261027); BOOT=rng.integers(0,N,size=(1000,N))
def bstats(rv,feat,idx=None):
    idx=np.arange(N) if idx is None else idx; b=BK[feat][idx]; r=rv[idx]; bs=sorted(set(BK[feat]))
    br=np.array([r[b==k].mean() if (b==k).any() else np.nan for k in bs]); br=br[~np.isnan(br)]
    mx,mn=br.max(),br.min(); nz=br[br>0]
    return dict(br=br,maxmin=(mx/mn if mn>0 else np.inf),maxmin_nz=(mx/nz.min() if len(nz) else np.nan),std=float(np.std(br)))
def slope(rv,x,idx): xx=x[idx]; yy=rv[idx]; xm=xx.mean(); return float(((xx-xm)*(yy-yy.mean())).sum()/((xx-xm)**2).sum())
out=[]
def P(s=""): print(s); out.append(s)
md5=lambda f: hashlib.md5(open(f,'rb').read()).hexdigest()[:8]
P("# r68unif (spec §4.136)\n"); P("Simulation only. Per-slot v8sim11, R38 off, whole library, r67band runner and bucket thresholds. "+open(f'{R}/out/equiv.txt').read().replace("\n"," ")+"\n")
P("Frozen-file md5 after: "+", ".join(f"{f} {md5(f'{Q}/{f}')}" for f in ("v8sim10.py","v8sim10_abl.py","v8sim11.py","v8sim2.py","v8sim_b6.py","prior_traces.json"))+" (before: 3daf1387, 7a2b02ec, ecdfff61, 4697713c, b24eae16, edb8e00c).\n")
if DEP: P("Deployed (six-split mean of the nest2 calibration, out/cal.jsonl): "+"; ".join(f"{k} λ {v['a']}/{v['b']} (infeasible splits {v['inf']}/6)" for k,v in DEP.items())+"\n")
J={}
for feat in ("mp","rise1"):
    P(f"## Table U1 ({feat}): bucket risk, max/min, std across buckets, Spearman(risk, {feat}) per trace, OLS slope of per-trace risk on {feat} with 95 % bootstrap CI\n")
    P(f"| group | arm | bucket risk (%) | max/min | max/min (min non-zero) | std (pp) | Spearman ρ | slope (pp per unit) | 95 % CI |\n|---|---|---|---|---|---|---|---|---|")
    for gn,g in GR.items():
        for a in [x for x in g["arms"] if x in ROWS]:
            rv=risk(a); st=bstats(rv,feat); rho=spearmanr(rv,X[feat]).correlation; sl=slope(rv,X[feat],np.arange(N))
            bsl=np.array([slope(rv,X[feat],ix) for ix in BOOT]); ci=(float(np.percentile(bsl,2.5)),float(np.percentile(bsl,97.5)))
            bst=np.array([bstats(rv,feat,ix)['std'] for ix in BOOT]); bmm=np.array([bstats(rv,feat,ix)['maxmin_nz'] for ix in BOOT])
            J[(feat,gn,a)]=dict(maxmin=st['maxmin'],maxmin_nz=st['maxmin_nz'],std=st['std'],rho=float(rho),slope=sl,ci=ci,bstd=bst,bmm=bmm,br=st['br'])
            P(f"| {gn} | {LAB[a]} | {' / '.join(f'{100*x:.1f}' for x in st['br'])} | {st['maxmin']:.2f} | {st['maxmin_nz']:.2f} | {100*st['std']:.2f} | {rho:+.3f} | {100*sl:+.2f} | [{100*ci[0]:+.2f}, {100*ci[1]:+.2f}] |")
    P("")
    P(f"Rule (S more uniform than a baseline = S max/min and std both smaller and slope CIs disjoint; max/min uses the min-non-zero version when a bucket risk is 0):\n")
    for gn,g in GR.items():
        s=J[(feat,gn,g["S"])]
        for bn,an in g["base"].items():
            b=J[(feat,gn,an)]; mmS=s['maxmin'] if np.isfinite(s['maxmin']) and np.isfinite(b['maxmin']) else s['maxmin_nz']; mmB=b['maxmin'] if np.isfinite(s['maxmin']) and np.isfinite(b['maxmin']) else b['maxmin_nz']
            disj=s['ci'][1]<b['ci'][0] or b['ci'][1]<s['ci'][0]; ok=mmS<mmB and s['std']<b['std'] and disj
            P(f"- {feat}, {gn}: {g['S']} vs {bn}: max/min {mmS:.2f} vs {mmB:.2f}, std {100*s['std']:.2f} vs {100*b['std']:.2f} pp, slope CI disjoint {disj} -> {'S MORE UNIFORM' if ok else 'not more uniform'}")
            J[(feat,gn,'rule',bn)]=ok
    P("")
# U2
P("## Table U2: per-layer VM-minutes relative to B1 (slot 480 / worker 240 / VyOS 180), mp deciles\n")
P("| group | arm | "+" | ".join(f"D{k}" for k in range(1,11))+" |\n|---|---|"+"---|"*10)
for gn,g in GR.items():
    for a in [x for x in g["arms"] if x in ROWS and x!="B1"]:
        cells=[]
        for k in range(1,11):
            ix=np.where(BK['mp']==k)[0]; m=lambda f: np.mean([ROWS[a][i][f] for i in ix])
            cells.append(f"{m('slot_min')/480:.2f}/{m('wk_min')/240:.2f}/{m('vy_min')/180:.2f}")
        P(f"| {gn} | {LAB[a]} | "+" | ".join(cells)+" |")
P("\n(cell = slot / worker / VyOS share of B1)\n")
# T6
T=json.load(open(f'{R}/out/t6t7.json')); sim,hw=T['sim'],T['hw']; mean=lambda v: float(np.mean(v))
P("## Table T6: t6 / t7 per trace, per-slot simulation (R38 off, own initial fleet; r62cf registered no per-layer t6/t7 predictions, recomputed) against hardware (rq_metrics.csv)\n")
P("| trace | arm / knob | sim alloc_vm | sim viol | sim worker / VyOS / slot min | hardware runs | hw alloc_vm (mean) | hw viol | hw worker / VyOS / slot min (mean) |\n|---|---|---|---|---|---|---|---|---|")
HWK={"S4b":"S4b","S4a":"S4a","B4_3.5_600":"B4c2 3.5/600 (deployed)","B5_4.0_L2":"B5c1 4.0/L2 (deployed)","B6_0.7":"B6 0.70 (deployed)","B6_0.775":"B6 0.775 (offline knob)"}
for tn in ("t6","t7"):
    for k in ("S4b","S4a","B4_3.75_300","B4_3.0_300","B4_3.5_600","B5_4.0_L2","B5_3.5_L1","B6_0.775","B6_0.7"):
        s=sim[f"{tn}|{k}"]; h=hw.get(f"{tn}|{HWK.get(k,'')}")
        hs=(f"{','.join(h['runs'])} | {mean(h['alloc_vm']):.1f} | {sum(h['viol'])}/{len(h['viol'])} runs | {mean(h['wk']):.0f} / {mean(h['vy']):.0f} / {mean(h['slot']):.0f}") if h else "— | — | — | —"
        P(f"| {tn} | {k} | {s['alloc_vm']:.1f} | {s['viol']} | {s['wk']:.1f} / {s['vy']:.1f} / {s['slot']:.1f} | {hs} |")
P("")
for tn in ("t6","t7"):
    s4=sim[f"{tn}|S4b"]['alloc_vm']; hs4=mean(hw[f"{tn}|S4b"]['alloc_vm'])
    for k,hk in (("B6_0.775","B6 0.775 (offline knob)"),("B6_0.7","B6 0.70 (deployed)"),("B5_4.0_L2","B5c1 4.0/L2 (deployed)")):
        ds=100*(s4/sim[f"{tn}|{k}"]['alloc_vm']-1); h=hw.get(f"{tn}|{hk}"); dh=100*(hs4/mean(h['alloc_vm'])-1) if h else None
        P(f"- (a) {tn}: S4b vs {k}: sim {ds:+.2f} %"+(f", hardware {dh:+.2f} %" if dh is not None else ", hardware n/a"))
P(f"- (b) t6 S4b worker-min: sim {sim['t6|S4b']['wk']:.1f}; hardware (rq_metrics) {mean(hw['t6|S4b']['wk']):.1f}; user value 228; B4c2 / B6 hardware 240.")
lo,hi=TB['mp']['thr'][6],TB['mp']['thr'][7]
for tn in ("t6","t7"):
    u=json.load(open(f"{E}/trace_ue_60min_v3_{tn}.json"))["ue"][:60]; v=mpf(u); pos=(v-lo)/(hi-lo)
    ix=np.where(BK['mp']==8)[0]
    for k in ("B4_3.75_300","B5_4.0_L2","B6_0.775"):
        bm=100*(np.mean([ROWS['S4b'][i]['alloc_vm'] for i in ix])/np.mean([ROWS[k][i]['alloc_vm'] for i in ix])-1); tr=100*(sim[f"{tn}|S4b"]['alloc_vm']/sim[f"{tn}|{k}"]['alloc_vm']-1)
        P(f"- (c) {tn} mp {v:.4f} at {100*pos:.0f} % of D8 ({lo:.4f}, {hi:.4f}]; S4b vs {k}: trace {tr:+.2f} %, D8 mean {bm:+.2f} %, difference {tr-bm:+.2f} pp")
P("")
# A-PL attribution
P("## Item 3: A-PL attribution (paired bootstrap of A-PL minus S, mp buckets)\n")
J3={}
for gn,g in GR.items():
    if g["apl"] not in ROWS: continue
    a=J[('mp',gn,g['apl'])]; s=J[('mp',gn,g['S'])]
    dstd=a['bstd']-s['bstd']; dmm=a['bmm']-s['bmm']; cs=(np.percentile(dstd,2.5),np.percentile(dstd,97.5)); cm=(np.nanpercentile(dmm,2.5),np.nanpercentile(dmm,97.5))
    bstd=[J[('mp',gn,an)]['std'] for an in g['base'].values()]; bmm=[J[('mp',gn,an)]['maxmin_nz'] for an in g['base'].values()]
    same=cs[0]<=0<=cs[1] and cm[0]<=0<=cm[1]; worse=cs[0]>0 and cm[0]>0; inrange=min(bstd)<=a['std']<=max(bstd) and min(bmm)<=a['maxmin_nz']<=max(bmm)
    v="attributed to the additive margin" if same else ("attributed to the joint" if (worse and inrange) else "in between")
    J3[gn]=v
    P(f"- {gn}: A-PL std {100*a['std']:.2f} pp vs S {100*s['std']:.2f} (diff CI [{100*cs[0]:+.2f}, {100*cs[1]:+.2f}]); max/min (non-zero) {a['maxmin_nz']:.2f} vs {s['maxmin_nz']:.2f} (diff CI [{cm[0]:+.2f}, {cm[1]:+.2f}]); baselines std {', '.join(f'{100*x:.2f}' for x in bstd)} pp, max/min {', '.join(f'{x:.2f}' for x in bmm)}; A-PL library risk {100*risk(g['apl']).mean():.2f} % cost {np.mean([r['alloc_vm'] for r in ROWS[g['apl']]]):.1f} -> {v}")
P("")
# S4p
P("## Table S4p: S4′ against each baseline per bucket (r67band Table B format)\n")
J4={}
def verdict(dc,dr): return "cheaper" if (dc<=-2 and dr<=0.2) else ("more expensive" if (dc>=2 and dr>=-0.2) else "same level")
for feat in ("mp","rise1"):
    for gn,g in GR.items():
        if g["s4p"] not in ROWS: continue
        P(f"### {feat}, {gn}\n\n| bucket | baseline | Δcost % | Δrisk pp | Δworker-min | verdict |\n|---|---|---|---|---|---|")
        for k in sorted(set(BK[feat]))+["all"]:
            ix=np.arange(N) if k=="all" else np.where(BK[feat]==k)[0]
            s=ROWS[g['s4p']]; m=lambda rows,f: np.mean([rows[i][f] for i in ix]); rr=lambda rows: np.mean([(60-rows[i]['slo'])/60 for i in ix])
            for bn,an in g['base'].items():
                b=ROWS[an]; dc=100*(m(s,'alloc_vm')/m(b,'alloc_vm')-1); dr=100*(rr(s)-rr(b)); dw=m(s,'wk_min')-m(b,'wk_min')
                J4[(feat,gn,k,bn)]=dict(dc=dc,dr=dr,dw=dw)
                P(f"| {('D'+str(k)) if k!='all' else 'library'} | {bn} | {dc:+.2f} | {dr:+.2f} | {dw:+.1f} | {verdict(dc,dr)} |")
        P("")
NT=json.load(open(f'{R}/out/new_traces.json')) if os.path.exists(f'{R}/out/new_traces.json') else {}
P("## Item 4: the four S4′ checks\n")
for gn,g in GR.items():
    if g["s4p"] not in ROWS: continue
    lw=[J4[('mp',gn,k,bn)]['dw'] for k in (1,2,3) for bn in g['base']]; hr=[J4[('mp',gn,k,bn)]['dr'] for k in (8,9,10) for bn in g['base']]
    fl=np.mean([r['flaps'] for r in ROWS[g['s4p']]]); flS=np.mean([r['flaps'] for r in ROWS[g['S']]])
    P(f"- {gn} (1) low-load D1–D3 Δworker-min vs the three baselines: {', '.join(f'{x:+.1f}' for x in lw)} -> {'all within ±2' if all(abs(x)<=2 for x in lw) else 'NOT all within ±2'} (S {g['S']}: "+", ".join(f"{J4b:+.1f}" for J4b in [np.mean([ROWS[g['S']][i]['wk_min'] for i in np.where(BK['mp']==k)[0]])-np.mean([ROWS[an][i]['wk_min'] for i in np.where(BK['mp']==k)[0]]) for k in (1,2,3) for an in g['base'].values()])+")")
    P(f"- {gn} (2) high-load D8–D10 Δrisk: {', '.join(f'{x:+.2f}' for x in hr)} pp -> {'all within ±0.5 pp' if all(abs(x)<=0.5 for x in hr) else 'NOT all within ±0.5 pp'}")
    P(f"- {gn} (3) library mean flaps (per-slot): S4′ {fl:.2f} vs {g['S']} {flS:.2f} -> {'<= 4' if fl<=4 else '> 4'}")
    nm=g['s4p'].replace('S4p','S4p');
    for tn in ("t4","t8"):
        e=NT.get(f"{tn}|{g['s4p']}")
        if e:
            base=ROWS  # per-slot S reference from r67band runner on the trace is in t6t7 only for t6/t7; recompute S per-slot here
            sr=NT[f"{tn}|{g['S']}"]
            P(f"- {gn} (4) {tn}: S4′ per-slot viol {60-e['ps']['slo']} {e['ps']['viol']} alloc_vm {e['ps']['alloc_vm']:.0f} vs {g['S']} per-slot {60-sr['ps']['slo']} {sr['ps']['viol']} {sr['ps']['alloc_vm']:.0f}; fleet S4′ {60-e['fl']['slo']} / {e['fl']['alloc']:.0f} vs {g['S']} {60-sr['fl']['slo']} / {sr['fl']['alloc']:.0f}")
open(f'{R}/REPORT.md','w').write("\n".join(out)+"\n")
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
COL={"S":"#1b4f9c","S1":"#7aa6e0","B4c2":"#d9822b","B5c1":"#b8442f","B6":"#3a9a5b","v6":"#777777","B1":"#bbbbbb","APL":"#8e44ad","S4p":"#0e8a8a"}
MK={"S":"o","S1":"o","B4c2":"s","B5c1":"D","B6":"^","v6":"v","B1":"x","APL":"P","S4p":"*"}
def key(a): return "S" if a in ("S4b","S4a") else "S1" if a.startswith("S1") else "B4c2" if a.startswith("B4") else "B5c1" if a.startswith("B5") else "B6" if a.startswith("B6") else "APL" if a.startswith("APL") else "S4p" if a.startswith("S4p") else a
for feat in ("mp","rise1"):
    fig,axs=plt.subplots(1,2,figsize=(10,3.6),sharey=True); bs=sorted(set(BK[feat]))
    for ax,(gn,g) in zip(axs,GR.items()):
        for a in [x for x in g["arms"] if x in ROWS and x!="B1"]:
            ax.plot(range(len(bs)),100*J[(feat,gn,a)]['br'],marker=MK[key(a)],color=COL[key(a)],lw=1.8,ms=5,label=LAB[a])
        ax.set_xticks(range(len(bs))); ax.set_xticklabels([f"D{b}" for b in bs]); ax.set_title(f"{gn} group",fontsize=9); ax.set_xlabel(f"{feat} bucket"); ax.grid(axis="y",lw=0.3)
        ax.legend(fontsize=6.5,frameon=False,ncol=2)
    axs[0].set_ylabel("realised risk (% of minutes)"); fig.tight_layout(); fig.savefig(f'{R}/fig_risk_by_band_{feat}.pdf'); plt.close(fig)
print("written")
