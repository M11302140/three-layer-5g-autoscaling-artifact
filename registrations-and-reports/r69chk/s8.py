#!/usr/bin/env python3
"""spec §4.137 item 3: S8 = S4 + R2 (w 1600). Deployed lambda = six-split mean of out/cal_s8.jsonl; whole-library per-slot (v8sim11 R38 off, CtlGen(w=1600),
whole-library S7Prior); Table B (mp, rise1; r67band format), U1 (same statistics as r68unif), paired bootstrap of S8 - S4 std, U2, library flaps,
dcost / drisk vs S4; t3-t8 per trace: per-slot R38 off, per-slot R38 on (frozen default physics), fleet nest2. Output out/S8_*.json, out/s8.json"""
import timeit  # noqa
import sys, os, json, numpy as np
Q='/home/user/experiment/qsim'; R=f'{Q}/r69chk'; RB_=f'{Q}/r67band'; E='/home/user/experiment'
for p in (Q,Q+'/r67band',Q+'/r68unif',Q+'/s7'): sys.path.insert(0,p)
os.chdir(Q)
import v8sim11 as V, v8sim7 as M, s7core as C7, nest2gen as G, ctlgen as CG, run as RB
from concurrent.futures import ProcessPoolExecutor
from scipy.stats import spearmanr
LIB=RB.LIB; N=len(LIB)
cal=[json.loads(l) for l in open(f'{R}/out/cal_s8.jsonl')]
DEP={tn:dict(a=round(float(np.mean([r['a'] for r in cal if r['target']==tg])),2),b=round(float(np.mean([r['b'] for r in cal if r['target']==tg])),2),inf=sum(r['infeasible'] for r in cal if r['target']==tg),
             ho_risk=float(np.mean([r['ho']['risk'] for r in cal if r['target']==tg])),ho_alloc=float(np.mean([r['ho']['alloc'] for r in cal if r['target']==tg])),ho_flaps=float(np.mean([r['ho']['flaps'] for r in cal if r['target']==tg]))) for tg,tn in ((0.02,"2"),(0.005,"05"))}
_SP=[None]
def sp():
    if _SP[0] is None: cfg,_=V.cfg_prior(); _SP[0]=C7.S7Prior(LIB,cfg)
    return _SP[0]
def one(args):
    tn,i,ue,phys=args; d=DEP[tn]; cfg,_=V.cfg_prior(); L={"vy":d['a'],"wk":d['a'],"up":d['b']}
    ue=ue if ue is not None else LIB[i]["ue"][:60]; st=V.initial_fleet("S",ue[0],L=L)
    ph=V.Phys(ue,start=st,p=phys); ctl=CG.CtlGen(cfg,sp(),L,w=1600)
    for _ in range(3600//V.DT):
        ph.advance_units()
        if ph.t%V.TICK==0:
            ob=ph.observe(); dec=ctl.tick(ph,ob); ph.hot_relief(getattr(ph,"_over",{}))
            if not dec and ph.t-ph.last_pool_relief>=ph.p["pool_relief_s"]: ph.enqueue_pool_relief(); ph.last_pool_relief=ph.t
        ph.step()
    r=ph.result(); ab=r['alloc_by']
    return i,dict(slo=int(r['slo']),viol=[int(x) for x in r['viol']],alloc_vm=r['alloc_vm'],wk_min=ab['wk']/3,vy_min=ab['vy']/2,slot_min=ab['up']/0.8,flaps=int(RB.flaps(r['events'])))
if __name__=="__main__":
    for tn in DEP:
        fn=f'{R}/out/S8_{tn}.json'
        if not os.path.exists(fn):
            with ProcessPoolExecutor(2) as pool: res=dict(pool.map(one,[(tn,i,None,RB.PH) for i in range(N)],chunksize=8))
            json.dump(dict(dep=DEP[tn],rows=[res[i] for i in range(N)]),open(fn,'w'))
    ROWS={n:json.load(open(f'{RB_}/out/{n}.json'))['rows'] for n in ("S4b","B4_3.75_300","B5_4.0_L2","B6_0.775","S4a","B4_3.0_300","B5_3.5_L1","B6_0.7")}
    ROWS["S8_2"]=json.load(open(f'{R}/out/S8_2.json'))['rows']; ROWS["S8_05"]=json.load(open(f'{R}/out/S8_05.json'))['rows']
    TB=json.load(open(f'{RB_}/out/tables.json'))
    mpf=lambda u: float(np.mean(u)/max(u)); r1f=lambda u: float(max(u[k]-u[k-1] for k in range(1,len(u))))
    X={"mp":np.array([mpf(t["ue"][:60]) for t in LIB]),"rise1":np.array([r1f(t["ue"][:60]) for t in LIB])}
    def bk(f,v):
        thr=TB[f]['thr']; mg={int(k):x for k,x in TB[f]['merge'].items()}; d=next((i+1 for i,th in enumerate(thr) if v<=th),10); return mg[d]
    BK={f:np.array([bk(f,v) for v in X[f]]) for f in X}
    risk=lambda a: np.array([(60-r['slo'])/60 for r in ROWS[a]])
    BOOT=np.random.default_rng(20261027).integers(0,N,size=(1000,N))
    def bst(rv,f,ix=None):
        ix=np.arange(N) if ix is None else ix; b=BK[f][ix]; r=rv[ix]; br=np.array([r[b==k].mean() for k in sorted(set(BK[f])) if (b==k).any()])
        nz=br[br>0]; return br,(br.max()/br.min() if br.min()>0 else np.inf),(br.max()/nz.min() if len(nz) else np.nan),float(np.std(br))
    def slope(rv,x,ix): xx=x[ix]; yy=rv[ix]; xm=xx.mean(); return float(((xx-xm)*(yy-yy.mean())).sum()/((xx-xm)**2).sum())
    GR={"2 %":dict(S="S4b",S8="S8_2",base={"B4c2":"B4_3.75_300","B5c1":"B5_4.0_L2","B6":"B6_0.775"}),"0.5 %":dict(S="S4a",S8="S8_05",base={"B4c2":"B4_3.0_300","B5c1":"B5_3.5_L1","B6":"B6_0.7"})}
    out=[]; P=lambda s="": (print(s),out.append(s)); O={}
    P("## Item 3: S8 = S4 + R2 (w 1600)\n"); P("Deployed (nest2 six-split mean): "+"; ".join(f"{k}: λ {v['a']}/{v['b']}, infeasible splits {v['inf']}/6, nest2 held-out risk {100*v['ho_risk']:.2f} % vmexist {v['ho_alloc']:.1f} flaps {v['ho_flaps']:.2f}" for k,v in DEP.items())+"\n")
    for f in ("mp","rise1"):
        P(f"### U1 ({f})\n\n| group | arm | bucket risk (%) | max/min | max/min (non-zero min) | std (pp) | Spearman | slope [95 % CI] |\n|---|---|---|---|---|---|---|---|")
        for gn,g in GR.items():
            for a in [g['S'],g['S8']]+list(g['base'].values()):
                rv=risk(a); br,mm,mmz,sd=bst(rv,f); bs=[slope(rv,X[f],ix) for ix in BOOT]; ci=(np.percentile(bs,2.5),np.percentile(bs,97.5))
                O[(f,gn,a)]=dict(mm=mm,mmz=mmz,sd=sd,ci=ci,bsd=np.array([bst(rv,f,ix)[3] for ix in BOOT]))
                P(f"| {gn} | {a} | {' / '.join(f'{100*x:.1f}' for x in br)} | {mm:.2f} | {mmz:.2f} | {100*sd:.2f} | {spearmanr(rv,X[f]).correlation:+.3f} | {100*slope(rv,X[f],np.arange(N)):+.2f} [{100*ci[0]:+.2f}, {100*ci[1]:+.2f}] |")
        P("")
    P("### (a) uniformity kept? (mp; r68unif rule vs three baselines, and S8 - S4 std paired-bootstrap CI)\n")
    A={}
    for gn,g in GR.items():
        s=O[('mp',gn,g['S8'])]; ok=[]
        for bn,an in g['base'].items():
            b=O[('mp',gn,an)]; fin=np.isfinite(s['mm']) and np.isfinite(b['mm']); ms,mb=(s['mm'],b['mm']) if fin else (s['mmz'],b['mmz'])
            dis=s['ci'][1]<b['ci'][0] or b['ci'][1]<s['ci'][0]; ok.append(ms<mb and s['sd']<b['sd'] and dis)
            P(f"- {gn}: S8 vs {bn}: max/min {ms:.2f} vs {mb:.2f}, std {100*s['sd']:.2f} vs {100*b['sd']:.2f} pp, slope CI disjoint {dis} -> {'more uniform' if ok[-1] else 'not'}")
        d=s['bsd']-O[('mp',gn,g['S'])]['bsd']; ci=(np.percentile(d,2.5),np.percentile(d,97.5)); inc=ci[0]<=0<=ci[1]
        P(f"- {gn}: S8 - {g['S']} std {100*(s['sd']-O[('mp',gn,g['S'])]['sd']):+.2f} pp, paired 95 % CI [{100*ci[0]:+.2f}, {100*ci[1]:+.2f}] -> {'contains 0' if inc else 'excludes 0'}")
        A[gn]=all(ok) and inc
    P("")
    lib=lambda a,k: float(np.mean([r[k] for r in ROWS[a]]))
    P("### (b)(c) library\n")
    for gn,g in GR.items():
        P(f"- {gn}: S8 flaps {lib(g['S8'],'flaps'):.2f} ({g['S']} {lib(g['S'],'flaps'):.2f}); alloc_vm {lib(g['S8'],'alloc_vm'):.1f} vs {lib(g['S'],'alloc_vm'):.1f} ({100*(lib(g['S8'],'alloc_vm')/lib(g['S'],'alloc_vm')-1):+.2f} %); risk {100*risk(g['S8']).mean():.2f} % vs {100*risk(g['S']).mean():.2f} % ({100*(risk(g['S8']).mean()-risk(g['S']).mean()):+.2f} pp); worker / VyOS / slot min {lib(g['S8'],'wk_min'):.1f} / {lib(g['S8'],'vy_min'):.1f} / {lib(g['S8'],'slot_min'):.1f} vs {lib(g['S'],'wk_min'):.1f} / {lib(g['S'],'vy_min'):.1f} / {lib(g['S'],'slot_min'):.1f}")
    P("")
    def verdict(dc,dr): return "cheaper" if (dc<=-2 and dr<=0.2) else ("more expensive" if (dc>=2 and dr>=-0.2) else "same level")
    for f in ("mp","rise1"):
        for gn,g in GR.items():
            P(f"### Table B ({f}, {gn}): S8 against each baseline\n\n| bucket | baseline | Δcost % | Δrisk pp | Δworker-min | verdict |\n|---|---|---|---|---|---|")
            for k in sorted(set(BK[f]))+["all"]:
                ix=np.arange(N) if k=="all" else np.where(BK[f]==k)[0]; m=lambda a,c: np.mean([ROWS[a][i][c] for i in ix]); rr=lambda a: np.mean([(60-ROWS[a][i]['slo'])/60 for i in ix])
                for bn,an in g['base'].items():
                    dc=100*(m(g['S8'],'alloc_vm')/m(an,'alloc_vm')-1); dr=100*(rr(g['S8'])-rr(an)); P(f"| {('D'+str(k)) if k!='all' else 'library'} | {bn} | {dc:+.2f} | {dr:+.2f} | {m(g['S8'],'wk_min')-m(an,'wk_min'):+.1f} | {verdict(dc,dr)} |")
            P("")
    P("### U2: S8 per-layer share of B1 (slot / worker / VyOS), mp deciles\n\n| group | arm | "+" | ".join(f"D{k}" for k in range(1,11))+" |\n|---|---|"+"---|"*10)
    for gn,g in GR.items():
        for a in (g['S'],g['S8']):
            P(f"| {gn} | {a} | "+" | ".join(f"{np.mean([ROWS[a][i]['slot_min'] for i in np.where(BK['mp']==k)[0]])/480:.2f}/{np.mean([ROWS[a][i]['wk_min'] for i in np.where(BK['mp']==k)[0]])/240:.2f}/{np.mean([ROWS[a][i]['vy_min'] for i in np.where(BK['mp']==k)[0]])/180:.2f}" for k in range(1,11))+" |")
    P("\n### t3-t8 per trace (violation minutes / alloc_vm / flaps)\n\n| trace | arm | per-slot R38 off | per-slot R38 on (frozen default) | fleet nest2 (vmexist) |\n|---|---|---|---|---|")
    cfgM=M.cfg_measured(); TR={}
    for t in ("t3","t4","t5","t6","t7","t8"):
        ue=json.load(open(f"{E}/trace_ue_60min_v3_{t}.json"))["ue"][:60]
        for gn,tn,Sname,LS in (("2 %","2","S4b",{"vy":1.83,"wk":1.83,"up":2.00}),("0.5 %","05","S4a",{"vy":2.83,"wk":2.83,"up":3.08})):
            d=DEP[tn]; L8={"vy":d['a'],"wk":d['a'],"up":d['b']}
            _,a=one((tn,-1,ue,RB.PH)); _,b=one((tn,-1,ue,None)); fl=G.sim_s7(ue,cfgM,sp(),L8,w=1600,acct='vmexist')
            cfg,pr=V.cfg_prior(); st=V.initial_fleet("S",ue[0],L=LS)
            sa=RB.run_ctl(ue,V.CtlSigma(cfg,pr,LS),st); sb=V.run(ue,"S",L=LS); sf=G.sim_s7(ue,cfgM,pr,LS,acct='vmexist')
            TR[f"{t}|{gn}"]=dict(S8=dict(off=a,on=dict(slo=b['slo'],viol=b['viol'],alloc_vm=b['alloc_vm'],flaps=b['flaps']),fleet=dict(slo=int(fl['slo']),alloc=fl['alloc'])),
                                 S4=dict(off=dict(viol=[int(x) for x in sa['viol']],alloc_vm=sa['alloc_vm'],flaps=int(RB.flaps(sa['events']))),on=dict(viol=[int(x) for x in sb['viol']],alloc_vm=sb['alloc_vm'],flaps=int(RB.flaps(sb['events']))),fleet=dict(slo=int(sf['slo']),alloc=sf['alloc'])))
            for arm,x in (("S8",TR[f"{t}|{gn}"]["S8"]),(Sname,TR[f"{t}|{gn}"]["S4"])):
                P(f"| {t} | {gn} {arm} | {x['off']['viol']} / {x['off']['alloc_vm']:.0f} / {x['off']['flaps']} | {x['on']['viol']} / {x['on']['alloc_vm']:.0f} / {x['on']['flaps']} | {60-x['fleet']['slo']} min / {x['fleet']['alloc']:.0f} |")
    P("\n### Four verdicts\n")
    for gn,g in GR.items():
        fl=lib(g['S8'],'flaps'); t4=TR[f"t4|{gn}"]; t8=TR[f"t8|{gn}"]
        P(f"- {gn}: (a) {'yes' if A[gn] else 'no'}; (b) {'yes' if fl<=4.0 else 'no'} ({fl:.2f}); (c) Δcost {100*(lib(g['S8'],'alloc_vm')/lib(g['S'],'alloc_vm')-1):+.2f} %, Δrisk {100*(risk(g['S8']).mean()-risk(g['S']).mean()):+.2f} pp; (d) t4 per-slot R38 on {t4['S4']['on']['viol']} -> {t4['S8']['on']['viol']} ({'became [20, 21]' if t4['S8']['on']['viol']==[20,21] else 'not [20, 21]'}), t8 per-slot R38 off alloc_vm {t8['S4']['off']['alloc_vm']:.0f} -> {t8['S8']['off']['alloc_vm']:.0f}")
    json.dump(dict(dep=DEP,tr=TR,A=A),open(f'{R}/out/s8.json','w'),indent=1,default=str)
    open(f'{R}/out/s8_report.md','w').write("\n".join(out)+"\n")
