#!/usr/bin/env python3
"""r65slot analysis (spec §4.112 A items 4-6)."""
import sys, os, json, math, numpy as np
from multiprocessing import Pool
sys.path.insert(0, '/home/user/experiment/qsim/r65slot'); sys.path.insert(0, '/home/user/experiment/qsim')
import run as R
V = R.V; S = R.S; LIB = R.LIB; CFG = R.CFG
OUT = R.OUT
sp = [json.load(open(f'{OUT}/split_{s}.json')) for s in range(6)]
N2 = {0.02: dict(lv=1.88, lu=2.00, risk=0.0196, se=0.0007, cost=1282.1), 0.005: dict(lv=2.75, lu=3.12, risk=0.0045, se=0.0003, cost=1339.2)}
L = []
L.append('| target | split | λ_slot VM/UP | flags | cal risk | ho risk (v8sim11) | ho alloc_vm | v8sim11 @ nest2 λ: ho risk / alloc_vm |')
L.append('|---|---|---|---|---|---|---|---|')
agg = {}
for tg in (0.02, 0.005):
    rr = [s['rows'][str(tg)] for s in sp]
    for s, r in zip(sp, rr):
        fl = ','.join(x for x in ('INFEASIBLE' if r['infeasible'] else '', 'EDGE' if r['edge'] else '') if x) or '-'
        L.append(f"| {tg} | {s['seed']} | {r['lam_vm']}/{r['lam_up']} | {fl} | {r['cal_risk']:.4f} | {r['ho_risk']:.4f} | {r['ho_alloc_vm']:.1f} | {r['v11_at_nest2_lam']['ho_risk']:.4f} / {r['v11_at_nest2_lam']['ho_alloc_vm']:.1f} |")
    a = lambda k: np.array([r[k] for r in rr])
    hv = a('ho_risk'); ha = a('ho_alloc_vm'); nr = np.array([r['v11_at_nest2_lam']['ho_risk'] for r in rr]); na = np.array([r['v11_at_nest2_lam']['ho_alloc_vm'] for r in rr])
    agg[tg] = dict(lv=a('lam_vm').mean(), lvs=a('lam_vm').std(), lu=a('lam_up').mean(), lus=a('lam_up').std(), risk=hv.mean(), se=hv.std() / math.sqrt(6), cost=ha.mean(), costs=ha.std(),
                   n_inf=int(sum(r['infeasible'] for r in rr)), n_edge=int(sum(r['edge'] for r in rr)), v11n_risk=nr.mean(), v11n_cost=na.mean())
L.append('')
L.append('| target | calibration | λ_VM | λ_UP | held-out risk (SE) | held-out alloc_vm | infeasible / edge splits |')
L.append('|---|---|---|---|---|---|---|')
for tg in (0.02, 0.005):
    g = agg[tg]; n = N2[tg]
    L.append(f"| {tg} | nest2, leakage-free (r63a; nest2 risk) | {n['lv']:.2f} | {n['lu']:.2f} | {n['risk']:.4f} ({n['se']:.4f}) | {n['cost']:.1f} | - |")
    L.append(f"| {tg} | per-slot v8sim11 (this run; per-slot risk) | {g['lv']:.2f} ± {g['lvs']:.2f} | {g['lu']:.2f} ± {g['lus']:.2f} | {g['risk']:.4f} ({g['se']:.4f}) | {g['cost']:.1f} ± {g['costs']:.1f} | {g['n_inf']} / {g['n_edge']} |")
    L.append(f"| {tg} | nest2 λ evaluated in v8sim11 (per-slot risk) | per split | per split | {g['v11n_risk']:.4f} | {g['v11n_cost']:.1f} | - |")
L.append('')
L.append('R3 cost increase:')
for tg in (0.02, 0.005):
    g = agg[tg]; n = N2[tg]
    L.append(f"* {tg}: λ_slot vs nest2 λ: VM {g['lv']:.2f} vs {n['lv']:.2f}, UP {g['lu']:.2f} vs {n['lu']:.2f}. Cross-physics (each calibrated in its own simulator): {g['cost']:.1f} / {n['cost']:.1f} − 1 = {100*(g['cost']/n['cost']-1):+.2f} %. Same physics (v8sim11): {g['cost']:.1f} / {g['v11n_cost']:.1f} − 1 = {100*(g['cost']/g['v11n_cost']-1):+.2f} % (nest2 λ in v8sim11 has per-slot risk {g['v11n_risk']:.4f}).")
q = lambda x: round(x * 4) / 4
LS = {tg: (q(agg[tg]['lv']), q(agg[tg]['lu'])) for tg in agg}
PRF = S.Prior(LIB, CFG)
def wl(args):
    i, lv, lu = args; return R.run1(LIB[i]['ue'][:60], PRF, lv, lu)
TR = {t: json.load(open(f'/home/user/experiment/trace_ue_60min_v3_{t}.json'))['ue'][:60] for t in ('t3', 't4', 't6', 't7')}
def tr1(args):
    t, lv, lu = args; s, a = R.run1(TR[t], PRF, lv, lu); return (t, lv, lu, 60 - s, a)
if __name__ == '__main__':
    with Pool(2) as p:
        whole = {}
        for tg, (lv, lu) in LS.items():
            rr = p.map(wl, [(i, lv, lu) for i in range(len(LIB))], chunksize=20)
            whole[tg] = (float(np.mean([(60 - r[0]) / 60 for r in rr])), float(np.mean([r[1] for r in rr])))
        jobs = [(t, lv, lu) for t in TR for (lv, lu) in list(LS.values()) + [(2.83, 3.08), (1.83, 2.00)]]
        pt = p.map(tr1, jobs)
    L.append('')
    L.append('Whole library (full-library Prior, λ = split mean rounded to 0.25):')
    for tg, (lv, lu) in LS.items(): L.append(f"* {tg}: λ {lv}/{lu}: per-slot risk {whole[tg][0]:.4f}, alloc_vm {whole[tg][1]:.1f}")
    MEAS = {('t3', 'S4a'): 2.33, ('t3', 'S4b'): 4.67, ('t4', 'S4a'): 1.00, ('t4', 'S4b'): 3.33, ('t6', 'S4a'): 0.0, ('t6', 'S4b'): 0.0, ('t7', 'S4a'): 0.33, ('t7', 'S4b'): 0.0}
    REG = {('t3', 'S4a'): 3, ('t3', 'S4b'): 3, ('t4', 'S4a'): 0, ('t4', 'S4b'): 1, ('t6', 'S4a'): 0, ('t6', 'S4b'): 0, ('t7', 'S4a'): 0, ('t7', 'S4b'): 0}
    DEP = {'S4a': (2.83, 3.08), 'S4b': (1.83, 2.00)}; TGA = {'S4a': 0.005, 'S4b': 0.02}
    P = {(t, lv, lu): (v, a) for t, lv, lu, v, a in pt}
    L.append('')
    L.append('Per trace (violating minutes per run / alloc_vm). Ratios pred/measured only at deployed λ (hardware never ran λ_slot).')
    L.append('| trace | arm | nest2 registered | v8sim11 @ deployed λ | measured | reg / meas | v8sim11 / meas | v8sim11 @ λ_slot (min / alloc_vm) |')
    L.append('|---|---|---|---|---|---|---|---|')
    def rat(a, b): return 'n/a' if a == 0 and b == 0 else ('∞' if b == 0 else f'{a/b:.2f}')
    r1 = []; e_v = 0; e_n = 0
    for t in ('t3', 't4', 't6', 't7'):
        for arm in ('S4a', 'S4b'):
            v, a = P[(t, *DEP[arm])]; m = MEAS[(t, arm)]; g = REG[(t, arm)]; sv, sa = P[(t, *LS[TGA[arm]])]
            L.append(f"| {t} | {arm} | {g} | {v} ({a:.0f}) | {m:.2f} | {rat(g, m)} | {rat(v, m)} | {sv} / {sa:.0f} |")
            if t in ('t3', 't4'): r1.append(None if m == 0 else v / m)
            else: e_v += abs(v - m); e_n += abs(g - m)
    ok1 = all(x is not None and 0.5 <= x <= 2 for x in r1); ok2 = e_v <= e_n
    L.append('')
    L.append(f"R1 (t3/t4 S4a,S4b v8sim11/measured in [0.5,2]): {['%.2f' % x if x is not None else 'inf' for x in r1]} -> {'PASS' if ok1 else 'FAIL'}")
    L.append(f"R2 (t6/t7 sum |pred-meas|, v8sim11 <= nest2): {e_v:.2f} vs {e_n:.2f} -> {'PASS' if ok2 else 'FAIL'}")
    L.append(f"Verdict sentence 'placement-aware calibration brings the mismatch within a factor of two': {'WRITE' if ok1 and ok2 else 'NOT WRITTEN'}")
    open(f'{OUT}/tables.md', 'w').write('\n'.join(L) + '\n'); print('\n'.join(L))
