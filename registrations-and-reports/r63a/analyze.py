#!/usr/bin/env python3
"""r63a analyze: out/*.jsonl -> report_tables.md + results.json (tables for REPORT.md). No simulation.
usage: cd /home/user/experiment/qsim/r63a && nice -n 19 taskset -c 13,14 python3 analyze.py"""
import json, os, numpy as np
R='/home/user/experiment/qsim/r63a'; OLD=json.load(open('/home/user/experiment/qsim/r62ab/results.json'))
TGT=(0.02,0.005); MD=[]; OUT={}
def P(s=""): MD.append(s)
def jl(f): return [json.loads(l) for l in open(f'{R}/out/{f}')] if os.path.exists(f'{R}/out/{f}') else []
ms=lambda a,f="{:.2f}": f"{f.format(np.mean(a))} ± {f.format(np.std(a))}"
# ---------------- task 1
sp=sorted(jl('split.jsonl'),key=lambda r:r['seed'])
if sp:
    P("## Task 1: six-split calibration, σ̂ from the calibration groups only"); P()
    P("Old = full-library σ̂ (r62ab lookup = frozen v8sim10_FULL, split by split). New = Prior(calibration groups' traces, cfg_measured), used for both calibration and held-out evaluation of that split. ho alloc = held-out vmexist core-min (dispatch in brackets)."); P()
    P("| target | split | Prior traces | λ new | λ old | cal risk new | ho risk new | ho risk old | ho alloc new | ho alloc old | σ̂ fallback D-buckets (new Prior) |"); P("|---|---|---|---|---|---|---|---|---|---|---|")
    verdict={}
    for tg in TGT:
        old=np.array(OLD['std_splits'][str(tg)]); new=[]
        for r in sp:
            x=r['rows'][str(tg)]; o=old[r['seed']]; new.append((x['lam_vm'],x['lam_up'],x['ho']['risk'],x['ho']['alloc_d'],x['ho']['alloc_vm'],x['cal_risk'],x['infeasible']))
            fb=", ".join(f"{k}:{v}" for k,v in r['prior_fallback'].items()) or "none"
            P(f"| {tg} | {r['seed']} | {r['n_prior']} | {x['lam_vm']}/{x['lam_up']}{' (INF)' if x['infeasible'] else ''} | {o[0]}/{o[1]} | {x['cal_risk']:.4f} | {x['ho']['risk']:.4f} | {o[2]:.4f} | {x['ho']['alloc_vm']:.1f} ({x['ho']['alloc_d']:.1f}) | {o[4]:.1f} ({o[3]:.1f}) | {fb} |")
        a=np.array(new,dtype=float); n=len(a); se_new=a[:,2].std()/np.sqrt(n); se_old=old[:,2].std()/np.sqrt(len(old))
        dvm=a[:,0].mean()-old[:,0].mean(); dup=a[:,1].mean()-old[:,1].mean(); dr=a[:,2].mean()-old[:,2].mean()
        ok=abs(dvm)<=0.25 and abs(dup)<=0.25 and abs(dr)<=se_new
        verdict[tg]=dict(d_lam_vm=dvm,d_lam_up=dup,d_risk=dr,se_new=se_new,se_old=se_old,ok=bool(ok),
                         new=dict(lam_vm=(a[:,0].mean(),a[:,0].std()),lam_up=(a[:,1].mean(),a[:,1].std()),risk=(a[:,2].mean(),a[:,2].std()),alloc_vm=(a[:,4].mean(),a[:,4].std()),alloc_d=a[:,3].mean(),cal=a[:,5].mean(),ninf=int(a[:,6].sum())),
                         old=dict(lam_vm=(old[:,0].mean(),old[:,0].std()),lam_up=(old[:,1].mean(),old[:,1].std()),risk=(old[:,2].mean(),old[:,2].std()),alloc_vm=(old[:,4].mean(),old[:,4].std()),alloc_d=old[:,3].mean()))
    P(); P("Summary (mean ± std over 6 splits, std ddof=0; SE = std/√6):"); P()
    P("| target | σ̂ | λ_VM | λ_UP | ho risk | SE | ho alloc vmexist (dispatch) |"); P("|---|---|---|---|---|---|---|")
    for tg in TGT:
        v=verdict[tg]
        for nm in ("old","new"):
            x=v[nm]; P(f"| {tg} | {'full library (old)' if nm=='old' else 'calibration groups (new)'} | {x['lam_vm'][0]:.2f} ± {x['lam_vm'][1]:.2f} | {x['lam_up'][0]:.2f} ± {x['lam_up'][1]:.2f} | {x['risk'][0]:.4f} ± {x['risk'][1]:.4f} | {v['se_'+nm]:.4f} | {x['alloc_vm'][0]:.1f} ± {x['alloc_vm'][1]:.1f} ({x['alloc_d']:.1f}) |")
    P(); P("Rule (§4.107 A): |Δλ_VM mean| ≤ 0.25 and |Δλ_UP mean| ≤ 0.25 and |Δ ho risk mean| ≤ SE_new, both targets."); P()
    P("| target | Δλ_VM | Δλ_UP | Δ ho risk | SE_new | pass |"); P("|---|---|---|---|---|---|")
    for tg in TGT:
        v=verdict[tg]; P(f"| {tg} | {v['d_lam_vm']:+.3f} | {v['d_lam_up']:+.3f} | {v['d_risk']:+.4f} | {v['se_new']:.4f} | {'yes' if v['ok'] else 'NO'} |")
    allok=all(verdict[t]['ok'] for t in TGT); OUT['task1']=dict(verdict={str(k):v for k,v in verdict.items()},pass_=allok)
    P(); P(f"**Rule verdict: {'PASS — leakage has no detectable effect' if allok else 'FAIL'}**"); P()
# ---------------- task 2
bt=sorted(jl('boot.jsonl'),key=lambda r:int(r['tag'][1:]))
if bt:
    nb=len(bt); P(f"## Task 2: nested cluster bootstrap ({nb} resamples)"); P()
    oldB={tg:np.array(OLD['B1'][str(tg)],dtype=float)[:nb] for tg in TGT}   # same draws, σ̂ fixed (first nb resamples)
    oldBall={tg:np.array(OLD['B1'][str(tg)],dtype=float) for tg in TGT}
    q=lambda a,f: f"{f.format(np.mean(a))} [{f.format(np.percentile(a,2.5))}, {f.format(np.percentile(a,97.5))}]"
    P("| target | σ̂ | resamples | λ_VM mean [2.5, 97.5] | λ_UP mean [2.5, 97.5] | ho risk mean [2.5, 97.5] | P(ho risk > ε) | ho alloc vmexist mean [2.5, 97.5] | ho n (mean) | infeasible |"); P("|---|---|---|---|---|---|---|---|---|---|")
    B={}
    for tg in TGT:
        a=np.array([(r['rows'][str(tg)]['lam_vm'],r['rows'][str(tg)]['lam_up'],r['rows'][str(tg)]['ho']['risk'],r['rows'][str(tg)]['ho']['alloc_vm'],r['rows'][str(tg)]['infeasible'],r['n_ho']) for r in bt],dtype=float)
        B[tg]=a
        rows=[("re-estimated per resample (new)",a,nb)]
        if nb<200: rows.append((f"fixed full-library (r62ab, same first {nb} draws)",oldB[tg],nb))
        rows.append(("fixed full-library (r62ab, all 200)",oldBall[tg],200))
        for nm,x,n in rows:
            P(f"| {tg} | {nm} | {n} | {q(x[:,0],'{:.2f}')} | {q(x[:,1],'{:.2f}')} | {q(x[:,2],'{:.4f}')} | {np.mean(x[:,2]>tg):.2f} | {q(x[:,3],'{:.1f}')} | {x[:,5].mean():.0f} | {int(x[:,4].sum())} |")
    P(); P("Paired (same draw) differences new − fixed-σ̂, mean [2.5, 97.5]:"); P()
    P("| target | Δλ_VM | Δλ_UP | Δ ho risk | Δ ho alloc vmexist | resamples with a different λ |"); P("|---|---|---|---|---|---|")
    for tg in TGT:
        d=B[tg][:,:4]-oldB[tg][:,:4]
        P(f"| {tg} | {q(d[:,0],'{:+.2f}')} | {q(d[:,1],'{:+.2f}')} | {q(d[:,2],'{:+.4f}')} | {q(d[:,3],'{:+.1f}')} | {int(((d[:,0]!=0)|(d[:,1]!=0)).sum())}/{nb} |")
    ts=[r['t_total'] for r in bt]; P(); P(f"Per-resample context time: mean {np.mean(ts):.0f} s, sims {np.mean([r['nsim'] for r in bt]):.0f}; unique cal traces {np.mean([r['n_cal_unique'] for r in bt]):.0f}/300; Prior traces {np.mean([r['n_prior'] for r in bt]):.0f}; groups drawn {np.mean([r['n_groups_drawn'] for r in bt]):.1f}/125.")
    nfb=sum(1 for r in bt if r['prior_fallback']); P(f"Resample Priors with any (kind, layer, 10-UE D-bucket) below 30 samples → global σ̂ fallback: {nfb}/{nb}" + (": "+"; ".join(sorted(set(json.dumps(r['prior_fallback']) for r in bt if r['prior_fallback']))) if nfb else "."))
    OUT['task2']={str(tg):B[tg].tolist() for tg in TGT}
# ---------------- task 3
bk=jl('bucket.jsonl')
if bk:
    P("## Task 3: conditional (rise1-bucket) calibration, bucket-internal σ̂"); P()
    names=[]; [names.append(r['bucket']) for r in sorted(bk,key=lambda r:(r['bk'],r['seed'])) if r['bucket'] not in names]
    T3={}
    for tg in TGT:
        P(f"### target {tg}"); P()
        P("| bucket | n | groups | Prior traces (mean) | cal n (mean) | ho n (mean) | λ_VM new | λ_UP new | λ old | ho risk new (mean ± std) | SE new | ho risk old (± std) | ho alloc vm new | old | valid new | valid old | infeasible / off-grid | σ̂ fallback (splits with < 30 in a D-bucket) |")
        P("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        nv=0; nne=0
        for bn in names:
            rr=sorted([r for r in bk if r['bucket']==bn],key=lambda r:r['seed']); x=[r['rows'][str(tg)] for r in rr]
            ho=np.array([y['ho']['risk'] for y in x]); se=ho.std()/np.sqrt(len(ho)); valid=abs(ho.mean()-tg)<=se; ne=ho.mean()<=tg+se; nv+=valid; nne+=ne
            o=OLD['A'][f"{bn}|{tg}"]
            fbs=[(r['seed'],r['prior_fallback']) for r in rr if r['prior_fallback']]
            fbtxt="; ".join(f"s{s}: "+", ".join(f"{k}{v}" for k,v in f.items()) for s,f in fbs) or "none"
            ninf=sum(y['infeasible'] for y in x); noff=sum(y['offgrid'] for y in x)
            T3[(bn,tg)]=dict(lv=float(np.mean([y['lam_vm'] for y in x])),lu=float(np.mean([y['lam_up'] for y in x])),ho=float(ho.mean()),ho_std=float(ho.std()),se=float(se),valid=bool(valid),ne=bool(ne),hv=float(np.mean([y['ho']['alloc_vm'] for y in x])),ninf=int(ninf),fallback=fbs,old_valid=o['valid'],old_ho=o['ho_mean'],old_lv=o['lv'],old_lu=o['lu'])
            P(f"| {bn} | {rr[0]['n_bucket']} | {rr[0]['n_groups']} | {np.mean([r['n_prior'] for r in rr]):.0f} | {np.mean([r['n_cal'] for r in rr]):.0f} | {np.mean([r['n_ho'] for r in rr]):.0f} | {ms([y['lam_vm'] for y in x])} | {ms([y['lam_up'] for y in x])} | {o['lv']:.2f}/{o['lu']:.2f} | {ho.mean():.4f} ± {ho.std():.4f} | {se:.4f} | {o['ho_mean']:.4f} ± {o['ho_std']:.4f} | {T3[(bn,tg)]['hv']:.1f} | {o['hv']:.1f} | {'yes' if valid else 'no'} | {'yes' if o['valid'] else 'no'} | {ninf} / {noff} | {fbtxt} |")
        ov=OLD[f"A_valid_{tg}"]; one=OLD[f"A_notexceed_{tg}"]
        P(); P(f"**Valid (ε ± SE), target {tg}: new {nv}/{len(names)} (old {ov[0]}/{ov[1]}); not exceeding ε + SE: new {nne}/{len(names)} (old {one[0]}/{one[1]}).**"); P()
        OUT[f'task3_valid_{tg}']=(int(nv),len(names)); OUT[f'task3_ne_{tg}']=(int(nne),len(names))
    OUT['task3']={f"{k[0]}|{k[1]}":v for k,v in T3.items()}
json.dump(OUT,open(f'{R}/results.json','w'),indent=1,default=lambda o: o.tolist() if hasattr(o,'tolist') else (bool(o) if isinstance(o,np.bool_) else str(o)))
open(f'{R}/report_tables.md','w').write("\n".join(MD)+"\n"); print("\n".join(MD))
