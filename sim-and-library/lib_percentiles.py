#!/usr/bin/env python3
"""(docstring removed)"""
import json, hashlib, os, sys, time
import numpy as np

Q = os.path.dirname(os.path.abspath(__file__))
E = "/home/user/experiment"
LIB = f"{Q}/prior_traces.json"
CSV = "/home/user/Downloads/3b4c9b89-c976-49e7-8358-075fe3699297.csv"
OUT_JSON = f"{Q}/t6t7_thresholds.json"
TRACES = {"t1": "trace_ue_60min_v3_40.json", "t2": "trace_ue_60min_v3_pm.json", "t3": "trace_ue_60min_v3_t3.json",
          "t4": "trace_ue_60min_v3_t4.json", "t5": "trace_ue_60min_v3_t5.json"}
LIB18 = {3, 4, 6, 14, 21, 24, 30, 35, 41, 45, 47, 49, 56, 58, 63, 65, 66, 79}
TSENS = {35, 84, 5, 41, 4}
TLOCDAYS = {(35, "2024-06-12"), (84, "2024-06-18"), (5, "2024-06-15"), (41, "2024-06-13"), (4, "2024-06-14")}
MIN_PEAK, MIN_ROWS, MAXUE = 20.0, 1200, 40
STATS = ["mp", "f36", "minue", "rise10"]
QS = [10, 25, 50, 75, 90]

if os.path.exists(OUT_JSON) and "--force" not in sys.argv:
    sys.exit(f"REFUSE: {OUT_JSON} already exists (thresholds are frozen; run once only)")

def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()

def stats(ue):
    u = np.asarray(ue, float); n = len(u)
    rise = max(u[j] - u[i] for i in range(n) for j in range(i + 1, min(n - 1, i + 10) + 1))
    return dict(mp=float(u.mean() / u.max()), f36=float((u >= 36).mean()), minue=float(u.min()),
                rise10=float(rise), start=float(u[0]), end=float(u[-1]))

def prank(vals, x):
    v = np.asarray(vals); return 100.0 * ((v < x).sum() + 0.5 * (v == x).sum()) / len(v)

ts = time.strftime("%Y-%m-%d %H:%M:%S")
lib = json.load(open(LIB))
L = [stats(t["ue"]) for t in lib]
N = len(L)
pct = {k: {str(q): float(np.percentile([l[k] for l in L], q, method="linear")) for q in QS} for k in STATS}
thr = {"i_mp_lo": pct["mp"]["25"], "i_mp_hi": pct["mp"]["75"], "ii_f36_max": pct["f36"]["75"],
       "iii_minue_min": max(6.0, pct["minue"]["10"]), "iii_P10": pct["minue"]["10"], "iii_floor": 6.0,
       "iv_rise10_max": pct["rise10"]["90"], "v_start_max": 30.0, "v_end_max": 30.0}

def passes(s):
    f = []
    if not (thr["i_mp_lo"] <= s["mp"] <= thr["i_mp_hi"]): f.append("i")
    if s["f36"] > thr["ii_f36_max"]: f.append("ii")
    if s["minue"] < thr["iii_minue_min"]: f.append("iii")
    if s["rise10"] > thr["iv_rise10_max"]: f.append("iv")
    if s["start"] > thr["v_start_max"] or s["end"] > thr["v_end_max"]: f.append("v")
    return f

lines = []
P = lines.append
P(f"# lib_percentiles.py run {ts}")
P(f"library {LIB}: n={N} traces, {len({t['loc'] for t in lib})} sensors; sha256 {sha(LIB)}")
P(f"script sha256 {sha(os.path.abspath(__file__))}")
P("")
P("## 五個統計量在先驗庫的分佈(P10/P25/P50/P75/P90)")
P("| 統計量 | P10 | P25 | P50 | P75 | P90 |")
P("|---|---|---|---|---|---|")
for k in STATS:
    P(f"| {k} | " + " | ".join(f"{pct[k][str(q)]:.3f}" for q in QS) + " |")
P("")
P("## 門檻(寫死)")
P(f"(i) {thr['i_mp_lo']:.3f} <= mp <= {thr['i_mp_hi']:.3f};(ii) f36 <= {thr['ii_f36_max']:.3f};"
  f"(iii) minue >= {thr['iii_minue_min']:.0f}(P10={thr['iii_P10']:.1f} vs 6 取較嚴);(iv) rise10 <= {thr['iv_rise10_max']:.1f};(v) start,end <= 30")
P("")
P("## t1-t5 各統計量與百分位落點")
P("| trace | mp (pct) | f36 (pct) | minue (pct) | rise10 (pct) | start/end | 依 v2 門檻 |")
P("|---|---|---|---|---|---|---|")
tstats = {}
for t, fn in TRACES.items():
    s = stats(json.load(open(f"{E}/{fn}"))["ue"]); tstats[t] = s
    f = passes(s)
    P(f"| {t} | {s['mp']:.3f} ({prank([l['mp'] for l in L], s['mp']):.0f}) | {s['f36']:.3f} ({prank([l['f36'] for l in L], s['f36']):.0f}) | "
      f"{s['minue']:.0f} ({prank([l['minue'] for l in L], s['minue']):.0f}) | {s['rise10']:.0f} ({prank([l['rise10'] for l in L], s['rise10']):.0f}) | "
      f"{s['start']:.0f}/{s['end']:.0f} | {'通過' if not f else '不過:' + ','.join(f)} |")
P("")
P("## 庫內依門檻的通過比例")
fails = [passes(l) for l in L]
for c in ["i", "ii", "iii", "iv", "v"]:
    P(f"- 條件 ({c}) 不過:{sum(c in f for f in fails)}/{N} = {100 * sum(c in f for f in fails) / N:.1f}%")
npass = sum(not f for f in fails)
P(f"- **全部通過:{npass}/{N} = {100 * npass / N:.1f}%**")
P("")

import pandas as pd
P("## 候選池(§4.53 v2 定義:計數器 ∉ 庫 18 ∉ {35,84,5,41,4};日期 06-06..06-19;loc-day >=1200 分鐘;視窗 5-min 峰值 >=20)")
P(f"CSV {CSV} sha256 {sha(CSV)}")
df = pd.read_csv(CSV, usecols=['location_id', 'sensing_date', 'sensing_time', 'total_of_directions'])
df['min'] = df.sensing_time.str.slice(0, 2).astype(int) * 60 + df.sensing_time.str.slice(3, 5).astype(int)
df = df.groupby(['location_id', 'sensing_date', 'min'], as_index=False).total_of_directions.sum()
dates = sorted(df.sensing_date.unique())
P(f"CSV: {df.location_id.nunique()} sensors, dates {dates[0]} .. {dates[-1]} ({len(dates)} days), {len(df)} sensor-minutes")
qual_sensors_nonT = set()
pool = {}       # sensor -> dict(days_ge1200, max_peak5, win20, win15, win10)
for (loc, date), g in df.groupby(['location_id', 'sensing_date']):
    loc = int(loc)
    if not ("2024-06-06" <= date <= "2024-06-19"): continue
    s = g.set_index('min').total_of_directions.reindex(range(1440)).interpolate(limit_direction='both').fillna(0)
    rows_ok = len(g) >= MIN_ROWS
    wins = {20: 0, 15: 0, 10: 0}
    for start in range(6 * 60, 20 * 60 + 1, 60):
        raw = s.iloc[start:start + 240].values
        if len(raw) < 240: continue
        pk = pd.Series(raw).rolling(5, center=True, min_periods=1).mean().max()
        for th in wins:
            if pk >= th: wins[th] += 1
    if rows_ok and wins[20] > 0 and (loc, date) not in TLOCDAYS: qual_sensors_nonT.add(loc)
    if loc in LIB18 or loc in TSENS: continue
    d = pool.setdefault(loc, dict(days_ge1200=0, max_peak5=0.0, win20=0, win15=0, win10=0))
    d["max_peak5"] = max(d["max_peak5"], float(s.rolling(5, center=True, min_periods=1).mean().max()))
    if rows_ok:
        d["days_ge1200"] += 1; d["win20"] += wins[20]; d["win15"] += wins[15]; d["win10"] += wins[10]
P(f"實證:非 t-日有任一合格視窗的計數器集合 = {sorted(qual_sensors_nonT)} (n={len(qual_sensors_nonT)}); 等於庫 18 個? {qual_sensors_nonT == LIB18}")
pool_windows = sum(d["win20"] for d in pool.values())
pool_locdays = sum(d["days_ge1200"] for d in pool.values())
P(f"**池大小(v2 定義):計數器 {len(pool)} 個(非庫、非 t)、loc-day(>=1200 分鐘){pool_locdays}、合格視窗(峰值>=20){pool_windows}**")
P("")
P("### 非庫計數器計數診斷(供池定義裁決;不含形狀)")
P("| sensor | days>=1200 | max 5-min peak (兩週) | windows peak>=20 | >=15 | >=10 |")
P("|---|---|---|---|---|---|")
for loc in sorted(pool):
    d = pool[loc]
    P(f"| {loc} | {d['days_ge1200']} | {d['max_peak5']:.1f} | {d['win20']} | {d['win15']} | {d['win10']} |")
P("")
P(f"# end {time.strftime('%Y-%m-%d %H:%M:%S')}")

txt = "\n".join(lines)
out_txt = f"{Q}/lib_percentiles_{time.strftime('%Y-%m-%d_%H%M')}.txt"
open(out_txt, "w").write(txt + "\n")
json.dump({"frozen_at": ts, "rule": "spec §4.53 v2 (2026-10-11); thresholds from prior library percentiles; fixed before sampling; do not edit",
           "library": LIB, "library_sha256": sha(LIB), "library_n": N, "script_sha256": sha(os.path.abspath(__file__)),
           "stat_defs": {"mp": "mean(u)/max(u)", "f36": "#{u>=36}/60", "minue": "min(u)", "rise10": "max{u[j]-u[i]: 0<j-i<=10}"},
           "percentile_method": "numpy.percentile linear", "percentiles": pct, "thresholds": thr,
           "library_pass_fraction": npass / N, "t1_t5_stats": tstats, "report": out_txt},
          open(OUT_JSON, "w"), indent=1)
print(txt)
print("\nwrote", out_txt, "and", OUT_JSON)
