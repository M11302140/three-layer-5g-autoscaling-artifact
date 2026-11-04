#!/usr/bin/env python3
"""mad_t12_s10.py — spec §4.101 S10 (NOT ADOPTED): mad_t12.py applied to madrid_s10_lib.json. Original: mad_t12.py — spec §4.99 B1 item 7, T1/T2 over the Madrid kept libraries (1:1 main = madrid_lib.json; compressed = madrid_compressed_lib.json).
T1: frozen nest2 exactly as v8_predict_t67.py: cfg = v8sim10.M.cfg_measured(); Prior = v8sim10.S.Prior(Melbourne prior_traces.json, cfg)
    (deployed λ and calibration unchanged); λ S4b {vy 1.83, wk 1.83, up 2.00} (ε = 0.02), S4a {2.83, 2.83, 3.08} (ε = 0.005); acct='vmexist'.
T2: v8sim2.sim_v6(ue, v8sim7.cfg_measured()).  risk = (60-slo)/60; library risk = mean over traces.
Verdict (T1): risk in [ε, 1.5ε] -> 'λ transfers directly'; < ε -> 'conservative, transfers'; > 1.5ε -> 'needs recalibration'.
Outputs: t12_per_trace_<lib>.csv, t12_summary.json, t12_table.md.  Run: nice -n 19 taskset -c 13,14 python3 mad_t12.py"""
import csv, json, os, sys, time
import numpy as np
from multiprocessing import Pool
sys.path.insert(0, "/home/user/experiment/qsim")
D = os.path.dirname(os.path.abspath(__file__))
import v8sim10 as M10, v8sim2 as S, v8sim7 as M
LAM = {"S4a": {"vy": 2.83, "wk": 2.83, "up": 3.08}, "S4b": {"vy": 1.83, "wk": 1.83, "up": 2.00}}
EPS = {"S4a": 0.005, "S4b": 0.02}
V6_MELB = {"risk": 0.02388, "alloc": 1262.0}                       # Melbourne whole-library v6 (spec §4.100 A / m1 REPORT)
S4_MELB = {"S4a": (0.00467, None), "S4b": (0.01886, None)}        # Melbourne whole-library risk (m1 REPORT), for reference
t0 = time.time()
lib_melb = json.load(open("/home/user/experiment/qsim/prior_traces.json"))
cfg = M10.M.cfg_measured(); pr = M10.S.Prior(lib_melb, cfg); cfg2 = M.cfg_measured()
print(f"Melbourne prior built ({len(lib_melb)} traces) {time.time()-t0:.1f} s; affinity {sorted(os.sched_getaffinity(0))}", flush=True)

def one(ue):
    out = {}
    for arm in ("S4a", "S4b"):
        r = M10.sim_nest2(ue, cfg, pr, LAM[arm], acct="vmexist"); out[arm] = (int(r["slo"]), float(r["alloc"]))
    r = S.sim_v6(ue, cfg2); out["v6"] = (int(r["slo"]), float(r["alloc"]))
    return out
def one_dispatch(ue):   # check that acct only changes alloc, not slo
    return {arm: int(M10.sim_nest2(ue, cfg, pr, LAM[arm])["slo"]) for arm in ("S4a", "S4b")}

summary = {"generated": time.strftime("%F %T"), "lam": LAM, "eps": EPS, "libs": {}}
rows_md = ["| library | n | arm | mean risk | frac traces >=1 viol | mean alloc (vmexist) | ε | risk/ε | verdict / change vs Melbourne |", "|---|---|---|---|---|---|---|---|---|"]
for name, fn in (("madrid_s10_1to1", "madrid_s10_lib.json"),):
    lib = json.load(open(f"{D}/{fn}")); jobs = [e["ue"][:60] for e in lib]; assert all(len(u) == 60 for u in jobs)
    t1 = time.time()
    with Pool(2) as p:
        res = p.map(one, jobs, chunksize=10)
        chk = p.map(one_dispatch, jobs[:20], chunksize=5)
    dt = time.time() - t1
    assert all(chk[i][a] == res[i][a][0] for i in range(20) for a in ("S4a", "S4b")), "acct changed slo"
    with open(f"{D}/s10_t12_per_trace_{name}.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["index", "bs", "date", "start_epoch"] + [f"{a}_{m}" for a in ("S4a", "S4b", "v6") for m in ("slo", "risk", "alloc")])
        for i, (e, r) in enumerate(zip(lib, res)):
            w.writerow([i, e["bs"], e["date"], e["start_epoch"]] + sum(([r[a][0], f"{(60-r[a][0])/60:.6f}", f"{r[a][1]:.2f}"] for a in ("S4a", "S4b", "v6")), []))
    info = {"n": len(lib), "sim_seconds": dt, "arms": {}}
    for a in ("S4a", "S4b", "v6"):
        rk = np.array([(60 - r[a][0]) / 60 for r in res]); al = np.array([r[a][1] for r in res])
        d = {"risk": float(rk.mean()), "risk_se": float(rk.std(ddof=1) / np.sqrt(len(rk))), "frac_viol": float((rk > 0).mean()), "alloc": float(al.mean()), "alloc_se": float(al.std(ddof=1) / np.sqrt(len(al)))}
        if a in EPS:
            e = EPS[a]; ratio = d["risk"] / e
            d["verdict"] = "λ transfers directly" if e <= d["risk"] <= 1.5 * e else ("conservative, transfers" if d["risk"] < e else "needs recalibration")
            d["ratio_to_eps"] = ratio; d["melbourne_lib_risk"] = S4_MELB[a][0]
            txt = f"{d['verdict']} (Melbourne lib risk {S4_MELB[a][0]*100:.3f}%)"
            eps_txt = f"{e}"
        else:
            d["melbourne_lib_risk"] = V6_MELB["risk"]; d["melbourne_lib_alloc"] = V6_MELB["alloc"]
            d["risk_change_abs"] = d["risk"] - V6_MELB["risk"]; d["risk_change_rel"] = d["risk"] / V6_MELB["risk"] - 1
            d["alloc_change_abs"] = d["alloc"] - V6_MELB["alloc"]; d["alloc_change_rel"] = d["alloc"] / V6_MELB["alloc"] - 1
            txt = f"risk {V6_MELB['risk']*100:.3f}% -> {d['risk']*100:.3f}% ({d['risk_change_abs']*100:+.3f} pp, {d['risk_change_rel']*100:+.1f}%); alloc {V6_MELB['alloc']:.0f} -> {d['alloc']:.0f} ({d['alloc_change_rel']*100:+.1f}%)"
            ratio = float("nan"); eps_txt = "-"
        info["arms"][a] = d
        rows_md.append(f"| {name} | {len(lib)} | {a} | {d['risk']*100:.3f}% ± {d['risk_se']*100:.3f} | {d['frac_viol']*100:.1f}% | {d['alloc']:.1f} ± {d['alloc_se']:.1f} | {eps_txt} | {ratio:.2f} | {txt} |")
        print(f"[{name}] {a}: risk {d['risk']*100:.3f}% frac>=1 {d['frac_viol']*100:.1f}% alloc {d['alloc']:.1f}  {txt}", flush=True)
    summary["libs"][name] = info
summary["runtime_s"] = time.time() - t0
json.dump(summary, open(f"{D}/s10_t12_summary.json", "w"), indent=1)
open(f"{D}/s10_t12_table.md", "w").write("\n".join(rows_md) + "\n"); print("\n".join(rows_md)); print(f"runtime {time.time()-t0:.1f} s")
