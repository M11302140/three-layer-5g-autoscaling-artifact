#!/usr/bin/env python3
"""r62cf Task C (spec §4.104 C): equal-risk calibration of the baselines.
Every grid point is simulated once on the whole 1615-trace library (deterministic per trace) and cached;
calibration / held-out evaluation for the six grouped splits is a lookup on that matrix (same as §4.104 shared computation).
Procedure per (baseline, target, seed): cal = grouped_split(seed)[0][:300], ho = grouped_split(seed)[1];
coarse grid -> feasible (cal risk <= target) -> cheapest (cal cost) -> refine neighbours of the continuous knob by one fine step
-> feasible cheapest among all evaluated points; if no coarse point is feasible: pick the minimum cal-risk point (ties: cheaper),
refine around it the same way, report as 'infeasible (lowest achievable)'. risk = mean violating-minute fraction; cost = mean alloc.
Usage: nice -n 19 taskset -c 13,14 python3 calib_c.py PHASE [PHASE ...]   PHASE in B4on B5on B6b6 B6on Son B4off B5off B6off Soff
"""
import timeit  # stdlib first: /home/user/experiment/qsim/timeit.py would shadow it
import sys, os, json, math, time, itertools
import numpy as np
Q = '/home/user/experiment/qsim'; R = f'{Q}/r62cf'
os.chdir(Q); sys.path.insert(0, Q)
import v8sim11 as V, v8sim_b6 as B, v8sim7 as M
from v8sim3 import grouped_split
LIB = json.load(open(f'{Q}/prior_traces.json'))
T0 = time.time(); BUDGET_S = float(os.environ.get("BUDGET_S", 3.6 * 3600))
LOG = open(f'{R}/calib_progress.log', 'a')
def P(x):
    s = f"[{time.strftime('%H:%M:%S')} +{time.time()-T0:6.0f}s] {x}"; print(s, flush=True); LOG.write(s + "\n"); LOG.flush()

# ---------------- runner identical to v8sim11.run, but with an explicit controller instance ----------------
def run_ctl(ue, ctl, start, phys=None):
    ph = V.Phys(ue, start=start, p=phys)
    for i in range(60 * 60 // V.DT):
        ph.advance_units()
        if ph.t % V.TICK == 0:
            ob = ph.observe(); decided = ctl.tick(ph, ob)
            ph.hot_relief(getattr(ph, "_over", {}))
            if not decided and ph.t - ph.last_pool_relief >= ph.p["pool_relief_s"]:
                ph.enqueue_pool_relief(); ph.last_pool_relief = ph.t
        ph.step()
    return ph.result()

PHYS = {"on": None, "off": {"knee38": 5}}   # on = frozen default (R38 placement-overflow rule on); off = counterfactual knee38=5
def mu_of(fam, T): return (12.0 / 3.5 if fam == "B4" else 14.0 / 4.0) * T   # DASA mu tied to HPA target at the deployed ratio
LEADS = {"L1": (1, 3, 3), "L2": (2, 5, 5), "L4": (4, 10, 10)}
def sim_point(fam, phys, key):
    """returns (risk_vec, cost_vec) over the whole library"""
    rv, cv = [], []
    if fam == "B6b6":
        cfg = M.cfg_measured(); mk = B.load_models(); u = key[0]
        for tr in LIB:
            r = B.sim_b6(tr["ue"][:60], cfg, u, mk); rv.append((60 - r["slo"]) / 60.0); cv.append(r["alloc"])
        return rv, cv
    cfg, pr = V.cfg_prior(); ph = PHYS[phys]
    for tr in LIB:
        ue = tr["ue"][:60]
        if fam in ("B4", "B5"):
            T, x = key; mu = mu_of(fam, T)
            if fam == "B4": ctl = V.CtlB4(predictive=False, mu=mu, target=T, tol=0.05, down=int(x), margin=0.8)
            else: ctl = V.CtlB4(predictive=True, mu=mu, target=T, tol=0.05, down=600, margin=0.8, lead=LEADS[x])
            st = V.initial_fleet("B4", ue[0], target=T, mu=mu)
        elif fam == "B6":
            u = key[0]; ctl = V.CtlB6(cfg, u=u); st = V.initial_fleet("B6", ue[0], u=u)
        elif fam == "S":
            l = key[0]; L = {"vy": l, "wk": l, "up": l}; ctl = V.CtlSigma(cfg, pr, L); st = V.initial_fleet("S", ue[0], L=L)
        r = run_ctl(ue, ctl, st, ph); rv.append((60 - r["slo"]) / 60.0); cv.append(r["alloc_vm"])
    return rv, cv

CACHE = {}
def get(fam, phys, key):
    nm = f"{fam}_{phys}_" + "_".join(str(k) for k in key)
    if nm in CACHE: return CACHE[nm]
    fn = f"{R}/cache/{nm}.json"
    if os.path.exists(fn): CACHE[nm] = json.load(open(fn)); return CACHE[nm]
    t0 = time.time(); rv, cv = sim_point(fam, phys, key); dt = time.time() - t0
    d = dict(fam=fam, phys=phys, key=list(key), risk_vec=rv, cost_vec=cv, risk=float(np.mean(rv)), cost=float(np.mean(cv)), secs=dt)
    json.dump(d, open(fn, "w")); CACHE[nm] = d
    P(f"sim {nm}: lib risk {d['risk']:.4f} cost {d['cost']:.1f} ({dt:.0f}s, {dt/len(LIB)*1000:.1f} ms/trace)")
    return d

# ---------------- grids (written into REPORT before running) ----------------
def r2(x): return round(x, 4)
GRIDS = {
  # fam: (coarse continuous values, fine step, lower bound, upper bound, discrete values)
  "B4":   ([2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0], 0.25, 1.75, 5.25, [300, 600, 900]),
  "B5":   ([2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0], 0.25, 1.75, 5.25, ["L1", "L2", "L4"]),
  "B6":   ([0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95], 0.025, 0.375, 0.975, [None]),
  "B6b6": ([0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95], 0.025, 0.375, 0.975, [None]),
  "S":    ([1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0], 0.25, 1.0, 7.0, [None]),
}
def mk_key(fam, c, x): return (r2(c), x) if fam in ("B4", "B5") else (r2(c),)
def calibrate(fam, phys, target, seed):
    cal, ho = grouped_split(seed); cal = cal[:300]
    coarse, step, lo, hi, disc = GRIDS[fam]
    def stat(key, idx):
        d = get(fam, phys, key); return float(np.mean([d["risk_vec"][i] for i in idx])), float(np.mean([d["cost_vec"][i] for i in idx]))
    table = {mk_key(fam, c, x): stat(mk_key(fam, c, x), cal) for c in coarse for x in disc}
    feas = [(k, v) for k, v in table.items() if v[0] <= target + 1e-12]
    infeasible = not feas
    if feas: k0 = min(feas, key=lambda kv: kv[1][1])[0]
    else: k0 = min(table.items(), key=lambda kv: (kv[1][0], kv[1][1]))[0]
    for dc in (-step, step):
        c = r2(k0[0] + dc)
        if lo - 1e-9 <= c <= hi + 1e-9:
            k = (c,) + tuple(k0[1:])
            if k not in table: table[k] = stat(k, cal)
    feas = [(k, v) for k, v in table.items() if v[0] <= target + 1e-12]
    if feas: kbest, (cr, cc) = min(feas, key=lambda kv: kv[1][1]); infeasible = False
    else: kbest, (cr, cc) = min(table.items(), key=lambda kv: (kv[1][0], kv[1][1]))
    hr, hc = stat(kbest, ho)
    return dict(fam=fam, phys=phys, target=target, seed=seed, key=list(kbest), cal_risk=cr, cal_cost=cc, ho_risk=hr, ho_cost=hc, n_cal=len(cal), n_ho=len(ho), infeasible=infeasible)

PHASES = {"B4on": ("B4", "on"), "B5on": ("B5", "on"), "B6b6": ("B6b6", "-"), "B6on": ("B6", "on"), "Son": ("S", "on"),
          "B4off": ("B4", "off"), "B5off": ("B5", "off"), "B6off": ("B6", "off"), "Soff": ("S", "off")}
if __name__ == "__main__":
    out = f"{R}/calib_results.json"; res = json.load(open(out)) if os.path.exists(out) else []
    for ph in sys.argv[1:]:
        if time.time() - T0 > BUDGET_S: P(f"budget exhausted, skip phase {ph}"); continue
        fam, phys = PHASES[ph]; P(f"=== phase {ph} ({fam}, R38 {phys})")
        for target in (0.02, 0.005):
            for seed in range(6):
                r = calibrate(fam, phys, target, seed)
                res = [x for x in res if not (x["fam"] == fam and x["phys"] == phys and x["target"] == target and x["seed"] == seed)] + [r]
                json.dump(res, open(out, "w"), indent=0)
                P(f"  {ph} target {target} seed {seed}: pick {r['key']} cal {r['cal_risk']:.4f}/{r['cal_cost']:.1f} ho {r['ho_risk']:.4f}/{r['ho_cost']:.1f}{' INFEASIBLE' if r['infeasible'] else ''}")
    P("done")
