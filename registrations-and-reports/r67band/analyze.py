#!/usr/bin/env python3
"""qsim/r67band/analyze.py (spec §4.135 item 3): buckets (mp and rise1 deciles, m1 rule), tables A/B/C, fig_band_cost.pdf, REPORT.md.
Reads out/<config>.json from run.py. Reading rules exactly as registered: cheaper = dcost <= -2 % and drisk <= +0.2 pp; more expensive =
dcost >= +2 % and drisk >= -0.2 pp; else same level; mechanism support (only when dcost < 0) = S worker-min below the baseline and the
worker core-min difference (3 x d worker-min) at least half of dcost (core-min)."""
import sys, os, json, hashlib, numpy as np
Q='/home/user/experiment/qsim'; R=f'{Q}/r67band'; E='/home/user/experiment'
LIB=json.load(open(f'{Q}/prior_traces.json')); N=len(LIB)
D={n:json.load(open(f'{R}/out/{n}.json'))['rows'] for n in ("S4b","S1_2.25","B4_3.75_300","B5_4.0_L2","B6_0.775","S4a","S1_3.25","B4_3.0_300","B5_3.5_L1","B6_0.7","v6","B1","B5_3.25_L1","B6_0.675")}
G={"2 %":dict(S="S4b",arms=["S4b","S1_2.25","B4_3.75_300","B5_4.0_L2","B6_0.775","v6","B1"],base={"B4c2":"B4_3.75_300","B5c1":"B5_4.0_L2","B6":"B6_0.775"}),
   "0.5 %":dict(S="S4a",arms=["S4a","S1_3.25","B4_3.0_300","B5_3.5_L1","B6_0.7","v6","B1"],base={"B4c2":"B4_3.0_300","B5c1":"B5_3.5_L1","B6":"B6_0.7"},
              sens={"B5c1 (mode 3.25/L1)":"B5_3.25_L1","B6 (mode 0.675)":"B6_0.675"})}
LABEL={"S4b":"S4b 1.83/2.00","S1_2.25":"S single 2.25","B4_3.75_300":"B4c2 3.75/300","B5_4.0_L2":"B5c1 4.0/L2","B6_0.775":"B6 0.775","S4a":"S4a 2.83/3.08","S1_3.25":"S single 3.25",
       "B4_3.0_300":"B4c2 3.0/300","B5_3.5_L1":"B5c1 3.5/L1","B6_0.7":"B6 0.70","v6":"v6","B1":"B1 (8/3/4)","B5_3.25_L1":"B5c1 3.25/L1","B6_0.675":"B6 0.675"}
mp=lambda u: float(np.mean(u)/max(u)); rise1=lambda u: float(max(u[k]-u[k-1] for k in range(1,len(u))))
FEAT={"mp":mp,"rise1":rise1}
TT={"t1":"40","t2":"pm","t3":"t3","t4":"t4","t5":"t5","t6":"t6","t7":"t7","t8":"t8"}
TUE={t:json.load(open(f"{E}/trace_ue_60min_v3_{f}.json"))["ue"][:60] for t,f in TT.items()}
def bucketer(vals):
    thr=[float(np.percentile(vals,q)) for q in range(10,100,10)]
    def dec(v):
        for d,th in enumerate(thr):
            if v<=th: return d+1
        return 10
    raw=[dec(v) for v in vals]; occ=sorted(set(raw)); merge={}
    for d in range(1,11):
        tgt=next((x for x in occ if x>=d),occ[-1]); merge[d]=tgt
    return thr,(lambda v: merge[dec(v)]),merge
out=[]; J={}
def P(s=""): print(s); out.append(s)
md5=lambda f: hashlib.md5(open(f,'rb').read()).hexdigest()
P("# r67band: load-band equal-risk cost decomposition (spec §4.135)\n")
P("Simulation only: v8sim11 per-slot, R38 off (knee38 = 5), whole library (1615 traces, ue[:60]), each arm from its own initial_fleet (B1 = static full fleet 8/3/4). Runner = r62cf run_ctl. Consistency: "+open(f'{R}/out/check.txt').read().strip().splitlines()[-1]+".\n")
P("Frozen-file md5 after the run: "+", ".join(f"{f} {md5(f'{Q}/{f}')[:8]}" for f in ("v8sim10.py","v8sim10_abl.py","v8sim11.py","v8sim2.py","v8sim_b6.py","prior_traces.json"))+" (before: 3daf1387, 7a2b02ec, ecdfff61, 46977131, b24eae16, edb8e00c).\n")
def stats(name,idx):
    rs=[D[name][i] for i in idx]; m=lambda k: float(np.mean([r[k] for r in rs]))
    return dict(n=len(rs),cost=m('alloc_vm'),risk=float(np.mean([(60-r['slo'])/60 for r in rs])),wk=m('wk_min'),vy=m('vy_min'),slot=m('slot_min'),wkc=m('wk_core'),fl=m('flaps'))
def verdict(dc,dr):
    if dc<=-2 and dr<=0.2: return "cheaper"
    if dc>=2 and dr>=-0.2: return "more expensive"
    return "same level"
for fname,f in FEAT.items():
    vals=[f(tr["ue"][:60]) for tr in LIB]; thr,bk,merge=bucketer(vals); B=[bk(v) for v in vals]; buckets=sorted(set(B))
    tb={t:bk(f(u)) for t,u in TUE.items()}
    P(f"## Buckets by {fname}\n\nThresholds P10..P90 (numpy linear): {[round(x,4) for x in thr]}. Merged deciles: {[f'D{d}->D{t}' for d,t in merge.items() if d!=t] or 'none'}. Buckets: {buckets}, n = {[B.count(b) for b in buckets]}.\n")
    P("Test traces: "+", ".join(f"{t} {fname} {f(TUE[t]):.3f} -> D{tb[t]}" for t in TT)+"\n")
    J[fname]=dict(thr=thr,merge=merge,tb=tb,rows={})
    for gname,g in G.items():
        P(f"### Table {'A' if fname=='mp' else 'C'} ({fname}, {gname} group): per bucket and arm — n, mean alloc_vm, mean risk, worker / VyOS / slot VM-minutes, flaps\n")
        P("| bucket | arm | n | alloc_vm | risk | worker-min | VyOS-min | slot-min | flaps |\n|---|---|---|---|---|---|---|---|---|")
        for b in buckets+["all"]:
            idx=[i for i in range(N) if b=="all" or B[i]==b]
            for a in g["arms"]:
                s=stats(a,idx); P(f"| {('D'+str(b)) if b!='all' else 'library'} | {LABEL[a]} | {s['n']} | {s['cost']:.1f} | {100*s['risk']:.2f} % | {s['wk']:.1f} | {s['vy']:.1f} | {s['slot']:.1f} | {s['fl']:.2f} |")
        P("")
        P(f"### Table {'B' if fname=='mp' else 'C-B'} ({fname}, {gname} group): {g['S']} against each baseline per bucket\n")
        P("| bucket | baseline | Δcost % | Δrisk pp | Δworker-min | worker share of Δcost | verdict | mechanism support |\n|---|---|---|---|---|---|---|---|")
        pairs=list(g["base"].items())+list(g.get("sens",{}).items())
        for b in buckets+["all"]:
            idx=[i for i in range(N) if b=="all" or B[i]==b]; s=stats(g["S"],idx)
            for bn,an in pairs:
                o=stats(an,idx); dc=100*(s['cost']/o['cost']-1); dr=100*(s['risk']-o['risk']); dw=s['wk']-o['wk']; dcc=s['cost']-o['cost']; share=(3*dw/dcc) if dcc!=0 else float('nan')
                v=verdict(dc,dr); mech=("yes" if (dw<0 and 3*dw<=0.5*dcc) else "no") if dcc<0 else "—"
                tag=" (sensitivity, not judged)" if bn.startswith(("B5c1 (","B6 (")) else ""
                J[fname]['rows'][f"{gname}|{b}|{bn}"]=dict(dc=dc,dr=dr,dw=dw,share=share,v=v,mech=mech)
                P(f"| {('D'+str(b)) if b!='all' else 'library'} | {bn}{tag} | {dc:+.2f} | {dr:+.2f} | {dw:+.1f} | {share:.2f} | {v} | {mech} |")
        P("")
# conclusions (rules only)
P("## Conclusions (registered reading rules only)\n")
for fname in FEAT:
    tb=J[fname]['tb']; buckets=sorted(set(int(k.split('|')[1]) for k in J[fname]['rows'] if k.split('|')[1]!='all'))
    for gname,g in G.items():
        for bn in g["base"]:
            cl={v:[f"D{b}" for b in buckets if J[fname]['rows'][f"{gname}|{b}|{bn}"]['v']==v] for v in ("cheaper","same level","more expensive")}
            mech=[f"D{b}" for b in buckets if J[fname]['rows'][f"{gname}|{b}|{bn}"]['mech']=="yes"]
            lib=J[fname]['rows'][f"{gname}|all|{bn}"]
            P(f"- {fname}, {gname}, {g['S']} vs {bn}: cheaper {cl['cheaper'] or 'none'}; same level {cl['same level'] or 'none'}; more expensive {cl['more expensive'] or 'none'}; mechanism support in {mech or 'no bucket'}; library {lib['dc']:+.2f} % / {lib['dr']:+.2f} pp -> {lib['v']}.")
P("")
tb=J['mp']['tb']
for t,hw in (("t6","cheaper by 3.0–4.5 %"),("t7","cheaper by 1.8–4.4 %")):
    b=tb[t]; rows={bn:J['mp']['rows'][f"2 %|{b}|{bn}"] for bn in G["2 %"]["base"]}
    P(f"- {t} lies in mp D{b} (rise1 D{J['rise1']['tb'][t]}); hardware S4b {hw}. Simulated S4b in that mp bucket: "+"; ".join(f"vs {bn} {r['dc']:+.2f} % ({r['v']})" for bn,r in rows.items())+" -> direction "+("consistent (S4b cheaper than all three)" if all(r['dc']<0 for r in rows.values()) else "not consistent with all three")+".")
json.dump(J,open(f'{R}/out/tables.json','w'),indent=1,default=str)
open(f'{R}/REPORT.md','w').write("\n".join(out)+"\n")
# figure
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
fig,axs=plt.subplots(1,2,figsize=(9,3.4),sharey=True)
col={"B4c2":"#2a6fdb","B5c1":"#d9822b","B6":"#3a9a5b"}; mk={"B4c2":"o","B5c1":"s","B6":"^"}
bks=sorted(set(int(k.split('|')[1]) for k in J['mp']['rows'] if k.split('|')[1]!='all'))
for ax,(gname,g) in zip(axs,G.items()):
    for bn in g["base"]:
        ax.plot(bks,[J['mp']['rows'][f"{gname}|{b}|{bn}"]['dc'] for b in bks],marker=mk[bn],color=col[bn],lw=2,ms=6,label=f"{g['S']} vs {bn}")
    ax.axhline(0,color="#888",lw=0.8); ax.axhspan(-2,2,color="#ddd",alpha=0.5,lw=0)
    lab={}
    for t in ("t3","t4","t6","t7","t8"): lab.setdefault(J['mp']['tb'][t],[]).append(t)
    for b,ts in lab.items(): ax.text(b,0.03,"/".join(ts),transform=ax.get_xaxis_transform(),ha="center",va="bottom",fontsize=7,color="#444")
    ax.set_title(f"{gname} group ({g['S']})",fontsize=9); ax.set_xlabel("mp decile (mean/peak)"); ax.set_xticks(bks); ax.grid(axis="y",lw=0.3)
axs[0].set_ylabel("Δcost S − baseline (% of baseline)")
for ax in axs: ax.legend(fontsize=7,frameon=False,loc="upper right")
fig.tight_layout(); fig.savefig(f'{R}/fig_band_cost.pdf'); print("figure written")
