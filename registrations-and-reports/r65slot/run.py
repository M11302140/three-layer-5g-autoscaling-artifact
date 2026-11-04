#!/usr/bin/env python3
"""r65slot (spec §4.112 A): per-slot (v8sim11, R38 on) calibration of S, leakage-free σ̂, six grouped splits.
Same arithmetic as r63a/core.run_context; only the simulator (v8sim11) and the grid range differ; selection on alloc_vm."""
import sys, os, json, time, itertools, math, numpy as np
from multiprocessing import Pool
sys.path.insert(0, '/home/user/experiment/qsim'); sys.path.insert(0, '/home/user/experiment/qsim/r63a')
os.chdir('/home/user/experiment/qsim')
import v8sim11 as V
import core as C          # r63a: LIB, CFG, grouped_split
S = V.S; LIB = C.LIB; CFG = C.CFG
OUT = '/home/user/experiment/qsim/r65slot'
GRID_VM = [1.0 + 0.5 * i for i in range(9)]    # 1.0 .. 5.0
GRID_UP = [1.5 + 0.5 * i for i in range(12)]   # 1.5 .. 7.0
TGT = (0.02, 0.005)
NEST2 = {0.02: [(1.75, 2.0), (2.0, 2.0), (1.75, 2.0), (2.0, 2.0), (1.75, 2.0), (2.0, 2.0)],      # r63a Task 1 "λ new" per split
         0.005: [(3.0, 3.0), (2.75, 3.25), (2.5, 3.0), (2.5, 3.25), (2.75, 3.25), (3.0, 3.0)]}

def start_of(ue0, pr, L):
    d0 = float(ue0)
    up = CFG.need("up", d0 + L["up"] * pr.sigma("win", "up", d0)); vy = CFG.need("vy", d0 + L["vy"] * pr.sigma("win", "vy", d0))
    up = int(min(8, max(2, up))); vy = int(min(3, max(1, vy))); wk = int(min(4, max(1, math.ceil(up / 2))))
    return (up, vy, wk)

def run1(ue, pr, lv, lu, phys=None):
    L = {"vy": lv, "wk": lv, "up": lu}
    ph = V.Phys(ue, start=start_of(ue[0], pr, L), p=phys); ctl = V.CtlSigma(CFG, pr, L)
    for _ in range(60 * 60 // V.DT):
        ph.advance_units()
        if ph.t % V.TICK == 0:
            ob = ph.observe(); decided = ctl.tick(ph, ob)
            ph.hot_relief(getattr(ph, "_over", {}))
            if not decided and ph.t - ph.last_pool_relief >= ph.p["pool_relief_s"]:
                ph.enqueue_pool_relief(); ph.last_pool_relief = ph.t
        ph.step()
    r = ph.result(); return (int(r["slo"]), float(r["alloc_vm"]))

def log(msg):
    with open(f'{OUT}/progress.log', 'a') as f: f.write(time.strftime('[%H:%M:%S] ') + msg + '\n')

def context(seed):
    t0 = time.time()
    cal_tr, ho_idx = C.grouped_split(seed)
    prior_idx = cal_tr; cal = cal_tr[:300]
    pr = S.Prior([LIB[i] for i in prior_idx], CFG)
    cache = {}
    def res(i, lv, lu):
        k = (i, lv, lu)
        if k not in cache: cache[k] = run1(LIB[i]["ue"][:60], pr, lv, lu)
        return cache[k]
    def ev(idx, lv, lu):
        rr = [res(i, lv, lu) for i in idx]
        return float(np.mean([(60 - r[0]) / 60 for r in rr])), float(np.mean([r[1] for r in rr]))
    coarse = {}
    for n, (lv, lu) in enumerate(itertools.product(GRID_VM, GRID_UP)):
        coarse[(lv, lu)] = ev(cal, lv, lu)
        if n % 12 == 11: log(f'seed {seed} coarse {n+1}/108  {time.time()-t0:.0f}s')
    out = dict(seed=seed, n_prior=len(prior_idx), n_cal=len(cal), n_ho=len(ho_idx), coarse={f'{k[0]}/{k[1]}': v for k, v in coarse.items()}, rows={})
    for tg in TGT:
        table = dict(coarse); feas = [(k, v) for k, v in table.items() if v[0] <= tg]
        if not feas:
            (lv, lu), (risk, al) = min(table.items(), key=lambda kv: (kv[1][0], kv[1][1])); inf = True
        else:
            inf = False; (lv, lu), _ = min(feas, key=lambda kv: kv[1][1])
            ref = [(round(lv + dv, 2), round(lu + du, 2)) for dv, du in itertools.product((-0.25, 0, 0.25), (-0.25, 0, 0.25))
                   if (round(lv + dv, 2), round(lu + du, 2)) not in table and lv + dv > 0 and lu + du > 0]
            for k in ref: table[k] = ev(cal, *k)
            feas = [(k, v) for k, v in table.items() if v[0] <= tg]
            (lv, lu), (risk, al) = min(feas, key=lambda kv: kv[1][1])
        hr, ha = ev(ho_idx, lv, lu)
        nv, nu = NEST2[tg][seed]; nr, na = ev(ho_idx, nv, nu)
        edge = (lv >= max(GRID_VM) or lu >= max(GRID_UP))
        out["rows"][str(tg)] = dict(lam_vm=lv, lam_up=lu, cal_risk=risk, cal_alloc=al, infeasible=inf, edge=edge,
                                    ho_risk=hr, ho_alloc_vm=ha, nest2_lam=[nv, nu], v11_at_nest2_lam=dict(ho_risk=nr, ho_alloc_vm=na))
        log(f'seed {seed} target {tg}: pick {lv}/{lu} cal {risk:.4f}/{al:.1f} ho {hr:.4f}/{ha:.1f} {"INFEASIBLE" if inf else ""}{" EDGE" if edge else ""} | v11@nest2 {nv}/{nu}: ho {nr:.4f}/{na:.1f}')
    out.update(nsim=len(cache), t=time.time() - t0)
    json.dump(out, open(f'{OUT}/split_{seed}.json', 'w'))
    return out

if __name__ == '__main__':
    if sys.argv[1:] == ['verify']:
        pr = S.Prior(LIB, CFG); mis = 0
        for i in range(0, 1615, 100):
            a = run1(LIB[i]["ue"][:60], pr, 1.83, 2.0); r = V.run(LIB[i]["ue"][:60], "S4b")
            mis += (a[0] != r["slo"] or abs(a[1] - r["alloc_vm"]) > 1e-9)
        print('verify custom runner vs V.run S4b on 17 traces: mismatches', mis); sys.exit(0)
    log('start');
    with Pool(2) as p: res = p.map(context, range(6), chunksize=1)
    log('all splits done')
