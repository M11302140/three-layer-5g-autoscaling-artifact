#!/usr/bin/env python3
"""r63r task 3: test traces t3/t4/t6/t7 under the leakage-free bucket λ (r63a out/bucket.jsonl, bucket-internal σ̂).
Bucket λ = mean of the bucket's six split λ, rounded to 0.01 (as r62ab). Buckets by rise1 with the r62ab/r63a thresholds.
Priors: PRIMARY = v8sim2.Prior(all library traces of the bucket, cfg_measured) (the deployed analogue: the test traces are not in
the library, so every bucket group is a calibration group); SENSITIVITY = each of the bucket's six split calibration-group Priors
(the Priors the six λ were calibrated with), reported as mean [min, max] over the six.
nest2 = frozen v8sim10.sim_nest2(ue,cfg,pr,L,acct='vmexist'). v8sim11 = V.run(ue,'S',L=L) after V.cfg_prior(); run twice:
(i) literal call (V's own full-library Prior), (ii) V._PRIOR replaced by the bucket Prior (v8sim11 reads the Prior only via cfg_prior()).
Also writes out/bucket_A.json = r63a bucket results in the r62ab results.json "A" schema (for the figure scripts; full_risk copied
from r62ab: bucket risk under the deployed λ with the full-library Prior, unchanged by the σ̂ fix).
Run: cd /home/user/experiment/qsim/r63r && nice -n 19 taskset -c 13,14 python3 testtr.py"""
import timeit  # noqa: stdlib before qsim/timeit.py shadows it
import os, sys, json, time, random, numpy as np
Q = "/home/user/experiment/qsim"; R = f"{Q}/r63r"; E = "/home/user/experiment"; sys.path.insert(0, Q); os.chdir(Q)
import v8sim10 as Q2, v8sim2 as S, v8sim7 as M
import v8sim11 as V; V.cfg_prior()
from multiprocessing import Pool
t0 = time.time()
LIB = json.load(open(f"{Q}/prior_traces.json")); cfg = M.cfg_measured()
OLD = json.load(open(f"{Q}/r62ab/results.json"))
# ---- buckets (identical to r63a run.rise1_buckets / r62ab)
rise1 = np.array([float(np.max(np.diff(np.asarray(tr["ue"][:60], float)))) for tr in LIB])
thr = np.percentile(rise1, np.arange(10, 100, 10)); dec = np.array([next((j for j in range(9) if x <= thr[j]), 9) for x in rise1])
buckets = []; pend = []
for j in range(10):
    pend.append(j)
    if (dec == j).any(): buckets.append(list(pend)); pend = []
if pend: buckets[-1] += pend
bname = lambda b: "D" + "+".join(str(j + 1) for j in b)
TR = {t: json.load(open(f"{E}/trace_ue_60min_v3_{t}.json"))["ue"][:60] for t in ("t3", "t4", "t6", "t7")}
trise = {t: float(np.max(np.diff(np.asarray(u, float)))) for t, u in TR.items()}
tb = {t: next(k for k, b in enumerate(buckets) if next((j for j in range(9) if trise[t] <= thr[j]), 9) in b) for t in TR}
# ---- r63a bucket results -> A schema
BJ = [json.loads(l) for l in open(f"{Q}/r63a/out/bucket.jsonl")]
A = {}
for k, b in enumerate(buckets):
    bn = bname(b)
    for tg in (0.02, 0.005):
        rs = sorted([r for r in BJ if r["bucket"] == bn], key=lambda r: r["seed"]); assert len(rs) == 6, (bn, len(rs))
        rows = [dict(lv=r["rows"][str(tg)]["lam_vm"], lu=r["rows"][str(tg)]["lam_up"], cal=r["rows"][str(tg)]["cal_risk"], ho=r["rows"][str(tg)]["ho"]["risk"],
                     hv=r["rows"][str(tg)]["ho"]["alloc_vm"], nc=r["n_cal"], nh=r["n_ho"], inf=r["rows"][str(tg)]["infeasible"], off=r["rows"][str(tg)]["offgrid"], seed=r["seed"]) for r in rs]
        ho = np.array([x["ho"] for x in rows]); se = ho.std() / np.sqrt(6)
        A[f"{bn}|{tg}"] = dict(b=b, n=rs[0]["n_bucket"], ng=rs[0]["n_groups"], ho_mean=float(ho.mean()), ho_std=float(ho.std()), se=float(se),
                               valid=bool(abs(ho.mean() - tg) <= se), ne=bool(ho.mean() <= tg + se), lv=float(np.mean([x["lv"] for x in rows])), lu=float(np.mean([x["lu"] for x in rows])),
                               hv=float(np.mean([x["hv"] for x in rows])), full_risk=OLD["A"][f"{bn}|{tg}"]["full_risk"], rows=rows, sigma="bucket-internal (calibration groups), r63a")
json.dump(A, open(f"{R}/out/bucket_A.json", "w"), indent=1)
# ---- Priors per needed bucket
def prior_all(k): return S.Prior([LIB[i] for i in range(len(LIB)) if dec[i] in buckets[k]], cfg)
def prior_split(k, s):
    """the split-s calibration-group Prior of bucket k, exactly as r63a run.bucket_jobs"""
    idx = [i for i in range(len(LIB)) if dec[i] in buckets[k]]; g = {}
    for i in idx: g.setdefault((LIB[i]["loc"], LIB[i]["date"]), []).append(i)
    kk = sorted(g); random.Random(s).shuffle(kk); nc = int(0.6 * len(kk))
    return S.Prior([LIB[i] for q in kk[:nc] for i in g[q]], cfg), sum(len(g[q]) for q in kk[:nc])
DEP = {"S4b": (1.83, 2.00), "S4a": (2.83, 3.08)}; HW = {"S4b": {"t3": "14/3", "t4": "10/3", "t6": "0/3", "t7": "0/3"}, "S4a": {"t3": "7/3", "t4": "3/3", "t6": "0/3", "t7": "1/3"}}
OLDT = {(r["trace"], r["arm"]): r for r in OLD["A_traces"]}
def job(args):
    tn, arm, tg = args; k = tb[tn]; a = A[f"{bname(buckets[k])}|{tg}"]; Ld = (round(a["lv"], 2), round(a["lu"], 2)); L = {"vy": Ld[0], "wk": Ld[0], "up": Ld[1]}; ue = TR[tn]
    out = dict(trace=tn, arm=arm, target=tg, bucket=bname(buckets[k]), rise1=trise[tn], lam=Ld)
    pa = prior_all(k); out["n_prior_all"] = sum(1 for i in range(len(LIB)) if dec[i] in buckets[k])
    r = Q2.sim_nest2(ue, cfg, pa, L, acct="vmexist"); out["n2"] = (60 - r["slo"], r["alloc"])
    r = V.run(ue, "S", L=L); out["v11_fullprior"] = (60 - r["slo"], r["alloc_vm"])
    full = V._PRIOR; V._PRIOR = pa
    r = V.run(ue, "S", L=L); out["v11"] = (60 - r["slo"], r["alloc_vm"])
    sens = []
    for s in range(6):
        ps, npr = prior_split(k, s); r1 = Q2.sim_nest2(ue, cfg, ps, L, acct="vmexist"); V._PRIOR = ps; r2 = V.run(ue, "S", L=L)
        sens.append(dict(seed=s, n_prior=npr, n2=(60 - r1["slo"], r1["alloc"]), v11=(60 - r2["slo"], r2["alloc_vm"])))
    V._PRIOR = full; out["split_priors"] = sens
    # old decile-λ (r62ab) rows re-checked with the full-library Prior
    o = OLDT[(tn, arm)]; out["old"] = o
    pf = V._PRIOR; Lo = {"vy": o["lam"][0], "wk": o["lam"][0], "up": o["lam"][1]}
    r = Q2.sim_nest2(ue, cfg, pf, Lo, acct="vmexist"); out["old_recheck_n2"] = (60 - r["slo"], r["alloc"])
    return out
if __name__ == "__main__":
    jobs = [(tn, arm, tg) for tn in ("t3", "t4", "t6", "t7") for arm, tg in (("S4a", 0.005), ("S4b", 0.02))]
    with Pool(2) as p: res = p.map(job, jobs)
    json.dump(dict(thr=thr.tolist(), buckets=[bname(b) for b in buckets], trise=trise, tbucket={t: bname(buckets[k]) for t, k in tb.items()}, rows=res, runtime_s=time.time() - t0),
              open(f"{R}/out/testtr.json", "w"), indent=1, default=float)
    for x in res:
        sp = x["split_priors"]; f = lambda key, j: [s[key][j] for s in sp]
        print(x["trace"], x["arm"], x["bucket"], "λ", x["lam"], "old λ", x["old"]["lam"], "| nest2", x["n2"][0], f"({x['n2'][1]:.0f})", "old", x["old"]["dec_n2"], f"({x['old']['dec_n2_alloc']:.0f})", "recheck", x["old_recheck_n2"][0],
              "| v11", x["v11"][0], f"({x['v11'][1]:.0f})", "v11 fullprior", x["v11_fullprior"][0], f"({x['v11_fullprior'][1]:.0f})", "old", x["old"]["dec_11"], f"({x['old']['dec_11_alloc']:.0f})",
              "| split priors n2", f("n2", 0), "v11", f("v11", 0), flush=True)
    print(f"runtime {time.time()-t0:.0f} s")
