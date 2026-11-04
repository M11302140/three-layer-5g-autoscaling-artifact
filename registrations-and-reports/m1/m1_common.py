"""m1_common.py — shared definitions for spec §4.99 Task A (M1 conditional risk of ε).
Feature definitions (per 60-minute UE sequence u[0..59]):
  mp     = mean(u)/max(u)                              (t6t7_thresholds.json stat_defs)
  f36    = #{t : u[t] >= 36}/60                        (idem)
  minUE  = min(u)                                      (idem, 'minue')
  rise10 = max{u[j]-u[i] : 0 < j-i <= 10}              (idem; same loop as lib_percentiles.py)
  rise1  = max{u[i+1]-u[i]}                            (max one-minute rise)
  lag1   = sample lag-1 autocorrelation
           = sum_{t<59}(u[t]-ubar)(u[t+1]-ubar) / sum_t (u[t]-ubar)^2
  stat   = mean(u[30:60]) - mean(u[0:30])              (stationarity / drift)
Percentile rank of a value x in the library (lib_percentiles.py prank):
  100*(#{v<x} + 0.5*#{v==x})/N   (mid-rank for ties)
"""
import json, os
import numpy as np

Q = "/home/user/experiment/qsim"
E = "/home/user/experiment"
M1 = f"{Q}/m1"
FIGS = "/home/user/docs/paper/figs"
LIB = f"{Q}/prior_traces.json"
# t1/t2 file names follow lib_percentiles.py / t6t7_thresholds.json (t1 = v3_40, t2 = v3_pm)
TRACES = {"t1": "trace_ue_60min_v3_40.json", "t2": "trace_ue_60min_v3_pm.json", "t3": "trace_ue_60min_v3_t3.json",
          "t4": "trace_ue_60min_v3_t4.json", "t5": "trace_ue_60min_v3_t5.json", "t6": "trace_ue_60min_v3_t6.json",
          "t7": "trace_ue_60min_v3_t7.json"}
FEATS = ["mp", "f36", "minUE", "rise10", "rise1", "lag1", "stat"]
FEAT_LABEL = {"mp": "mp = mean/max", "f36": "f36 = frac. minutes with UE >= 36", "minUE": "min UE",
              "rise10": "rise10 = max rise within 10 min (UE)", "rise1": "rise1 = max 1-min rise (UE)",
              "lag1": "lag-1 autocorrelation", "stat": "stationarity = mean(30-59) - mean(0-29) (UE)"}
LAM = {"S4a": {"vy": 2.83, "wk": 2.83, "up": 3.08}, "S4b": {"vy": 1.83, "wk": 1.83, "up": 2.00}}
ARMS = ["S4a", "S4b", "v6"]
# measured hardware risk, violation minutes over 3 runs x 60 min (spec §4.99 A.2, given in the task)
MEASURED_VIOL = {"S4b": {"t3": 14, "t4": 10, "t6": 0, "t7": 0},
                 "S4a": {"t3": 7, "t4": 3, "t6": 0, "t7": 1},
                 "v6":  {"t3": 17, "t4": 5, "t6": 5, "t7": 0}}
MEASURED_DEN = 180

def load_lib():
    return json.load(open(LIB))

def load_traces():
    return {t: json.load(open(f"{E}/{fn}"))["ue"][:60] for t, fn in TRACES.items()}

def features(ue):
    u = np.asarray(ue, float); n = len(u)
    assert n == 60, n
    rise10 = max(u[j] - u[i] for i in range(n) for j in range(i + 1, min(n - 1, i + 10) + 1))
    rise1 = float(np.max(np.diff(u)))
    d = u - u.mean(); den = float((d * d).sum())
    lag1 = float((d[:-1] * d[1:]).sum() / den) if den > 0 else float("nan")
    return {"mp": float(u.mean() / u.max()), "f36": float((u >= 36).mean()), "minUE": float(u.min()),
            "rise10": float(rise10), "rise1": rise1, "lag1": lag1, "stat": float(u[30:60].mean() - u[0:30].mean())}

def prank(vals, x):
    v = np.asarray(vals, float)
    return 100.0 * ((v < x).sum() + 0.5 * (v == x).sum()) / len(v)

def decile_of_prank(p):
    """percentile rank (0..100) -> decile index 0..9 (ties share a decile)."""
    return min(9, int(p // 10))
