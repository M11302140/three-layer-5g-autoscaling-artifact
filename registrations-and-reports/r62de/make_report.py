#!/usr/bin/env python3
"""Builds r62de/REPORT_tables.md from out/*.json and E_leads.json (tables only; prose is in REPORT.md)."""
import json, os, glob, sys, numpy as np
sys.path.insert(0,'/home/user/experiment/qsim/r62de'); import eng
CFG=eng.M.cfg_measured()
def floor(lib, loads=None):
    """need-floor cost (core-min/run): Σ_minutes Σ_layer cores·need_l(D_t) with zero margin/lead (instantaneous exact sizing)"""
    c=CFG; tot=[]
    for tr in lib:
        f=0.0
        for D in tr['ue'][:60]: f+=c.cores['up']*c.need('up',D)+c.cores['vy']*c.need('vy',D)+c.cores['wk']*c.need('wk',D)
        tot.append(f)
    return float(np.mean(tot))
FL={}
R='/home/user/experiment/qsim/r62de'
def J(n):
    p=f'{R}/out/{n}.json'
    return json.load(open(p)) if os.path.exists(p) else None
BASE={'0.02':dict(lv=1.83,lu=2.00,risk=0.0194,al=1282.5),'0.005':dict(lv=2.67,lu=3.12,risk=0.0051,al=1338.6)}
def row(label,j,t,extra=''):
    if j is None: return f"| {label} | {t} | (not run) |||||||"
    sm=j['summary'][t]
    if not sm.get('n'): return f"| {label} | {t} | infeasible in all splits ({sm.get('ninf')}) |||||||"
    b=BASE[t]; d=100*(sm['alloc_vm'][0]-b['al'])/b['al']
    inf=f" ({sm['ninf']} split(s) infeasible)" if sm['ninf'] else ''
    return (f"| {label}{extra} | {t} | {sm['lam_vm'][0]:.2f} ± {sm['lam_vm'][1]:.2f} | {sm['lam_up'][0]:.2f} ± {sm['lam_up'][1]:.2f} | {sm['cal_risk'][0]:.4f} | "
            f"{sm['risk'][0]:.4f} ± {sm['risk'][1]:.4f} | {sm['alloc_vm'][0]:.1f} ± {sm['alloc_vm'][1]:.1f} ({sm['alloc_d'][0]:.1f}) | {d:+.2f}% | {sm['n']}{inf} |")
H="| variant | target | λ_VM | λ_UP | cal risk | held-out risk | held-out alloc vmexist (dispatch) | Δalloc vs e | splits |\n|---|---|---|---|---|---|---|---|---|"
L=[]
e=json.load(open(f'{R}/E_leads.json'))
L+=["## E1 lead distributions (s)","","| layer | definition | n | min | p50 | p90 | p95 | p99 | max |","|---|---|---|---|---|---|---|---|---|"]
names={'vy':('VY','deploy_vyos → harness pool admission'),'up':('UP','scale_out_up → eupf rehome (scale-out) done'),'wk':('WK','create_worker → eupf worker provisioned')}
for k in ('vy','up','wk'):
    s=e['primary'][k]; L.append(f"| {names[k][0]} | {names[k][1]} | {s['n']} | {s['min']:.1f} | {s['p50']:.1f} | {s['p90']:.1f} | {s['p95']:.1f} | {s['p99']:.1f} | {s['max']:.1f} |")
for k in ('vy','up','wk'):
    s=e['inflight'][k]; L.append(f"| {names[k][0]} | daemon 'v6 inflight done' elapsed_s (censored ≥ T_ready) | {s['n']} | {s['min']:.0f} | {s['p50']:.0f} | {s['p90']:.0f} | {s['p95']:.0f} | {s['p99']:.0f} | {s['max']:.0f} |")
L+=["","## E2 recalibration with H_l = lead + g","",H]
for n,lab in (('E_base_p90','(e) baseline h 30/150/120 (cfg_measured, p90 G2 in-flight)'),('E_ready_p95','ready-signal p95 → h UP/VY/WK 125/85/65'),('E_ready_p99','ready-signal p99 → h 155/90/70'),('E_inflight_p95p99','in-flight-done p95 = p99 → h 60/180/150')):
    j=J(n)
    for t in ('0.02','0.005'): L.append(row(lab,j,t))
L+=["","## D1 library variants","","| variant (smooth min, compression, deadband) | traces | (loc,date) groups | rise1 P10/P50/P90 | rise10 P10/P50/P90 | σ̂_win at D=20 VY/UP/WK | need-floor core-min/run |","|---|---|---|---|---|---|---|"]
DV=[(s,c,d) for s in (1,5,10) for c in (1,2,4) for d in (0,2)]
def dj(s,c,d): return J('E_base_p90') if (s,c,d)==(5,4,2) else J(f'D_s{s}_c{c}_d{d}')
for s,c,d in DV:
    j=dj(s,c,d)
    if j is None: L.append(f"| {s} / {c}:1 / {d} | (not run) ||||| "); continue
    ls=j['libstats']; sg=j['sigma20']; FL[(s,c,d)]=floor(json.load(open(f"{R}/libs/lib_s{s}_c{c}_d{d}.json")))
    L.append(f"| {s} / {c}:1 / {d}{' (= frozen library)' if (s,c,d)==(5,4,2) else ''} | {ls['n']} | {ls['groups']} | {'/'.join(f'{x:.0f}' for x in ls['rise1'])} | {'/'.join(f'{x:.0f}' for x in ls['rise10'])} | {sg['win_vy@20']:.2f}/{sg['win_up@20']:.2f}/{sg['win_wk@20']:.2f} | {FL[(s,c,d)]:.1f} |")
L+=["","## D2 six-split recalibration per library variant (own Prior σ̂, own grouped splits)","",H.replace("| splits |","| splits | alloc / need-floor |").replace("|---|---|---|---|---|---|---|---|---|","|---|---|---|---|---|---|---|---|---|---|")]
for s,c,d in DV:
    j=dj(s,c,d)
    for t in ('0.02','0.005'):
        x=row(f"{s} / {c}:1 / {d}",j,t)
        if j is not None and j['summary'][t].get('n') and (s,c,d) in FL: x+=f" {j['summary'][t]['alloc_vm'][0]/FL[(s,c,d)]:.3f} |"
        L.append(x)
L+=["","## D3 per-UE rate model (rates {150,250,350} kpps, seed 20261021) — simulation only; not validated on hardware","",H]
for t in ('0.02','0.005'): L.append(row('(e) standard (250 kpps/UE)',J('E_base_p90'),t))
for t in ('0.02','0.005'): L.append(row('per-UE random rate',J('D_rates'),t))
L+=["","## runtimes","","| run | total s | trace-sims |","|---|---|---|"]
for p in sorted(glob.glob(f'{R}/out/*.json')):
    j=json.load(open(p)); L.append(f"| {j['name']} | {j['total_s']:.0f} | {j['nsim']} |")
open(f'{R}/REPORT_tables.md','w').write('\n'.join(L)+'\n'); print('\n'.join(L))
