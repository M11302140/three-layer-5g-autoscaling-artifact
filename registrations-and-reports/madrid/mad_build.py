#!/usr/bin/env python3
"""mad_build.py — spec §4.99 B1 steps 1-3 (completeness, 1:1 library, thresholds, compressed contrast library).
Input : madrid/users_<zone><freq>_s.csv (columns second,user_unique,timestamp,date); rows with timestamp >1e11 or <1e9 dropped.
Second index = authors' integer `second` column (strictly monotone); epoch of a second = floor(timestamp of first row of
the segment) + (second - second_first).  Segments = cuts where diff(second) > 60 s.
Completeness (B1 item 9): missing = sum over segments of (last-first+1 - rows); station fraction = missing/total.
  < 1 %  -> fill missing seconds by linear interpolation of user_unique (pandas 'linear') and build;
  >= 1 % -> STOP for that station (no zero fill), report only.
Per-minute mean = mean of the 60 (interpolated) seconds of each wall-clock minute (epoch//60) fully inside a segment.
Cmax (station) = numpy.percentile(all per-minute means of the station, 99, method='linear').
UE = clip(round(40*C/Cmax), 0, 40) then 2-UE deadband (make_newtraces.deadband, band=2; np.round = half-to-even, same as pipeline).
1:1 windows: 60 contiguous minutes within a segment, stride 60 (main) / 30 (sensitivity).
Compressed (B1 item 11, Melbourne pipeline of make_prior.py/make_newtraces.py): 240 contiguous minutes, stride 240,
  roll = Series(raw240).rolling(5, center=True, min_periods=1).mean(); c = roll.reshape(60,4).mean(axis=1); same UE scaling
  (station Cmax, NOT the per-window peak used by Melbourne — see REPORT) and deadband.
Thresholds (item 5, same form as spec §4.53): keep iff P10<=mp<=P90, f36<=P90, minUE>=P10, percentiles numpy linear over
  the library itself (recomputed separately for each library variant).
Group = (bs, local date Europe/Madrid of the window's first minute).
Outputs: madrid_1to1.json (all windows, stride 60, with 'keep' flag), madrid_lib.json (kept), madrid_1to1_stride30.json,
  madrid_compressed.json (all, with 'keep'), madrid_compressed_lib.json (kept), build_summary.json, build_tables.md."""
import json, os, sys, time, hashlib
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import numpy as np, pandas as pd
D = os.path.dirname(os.path.abspath(__file__))
STATIONS = [("BS1", "I796"), ("BS2", "I1815"), ("BS3", "I2650"), ("BS4", "II816"), ("BS5", "II1835"), ("BS6", "II2650")]
MAXUE = 40; GAP = 60; TZ = ZoneInfo("Europe/Madrid")
t0 = time.time()

def deadband(ue, band=2):                     # make_newtraces.py / make_prior.py, verbatim
    out = [ue[0]]
    for v in ue[1:]: out.append(v if abs(v - out[-1]) >= band else out[-1])
    return out
def to_ue(c, cmax):
    return deadband(np.clip(np.round(MAXUE * np.asarray(c, float) / cmax), 0, MAXUE).astype(int).tolist())
def stats(ue):
    u = np.asarray(ue, float)
    return dict(mp=float(u.mean() / u.max()) if u.max() > 0 else float("nan"), f36=float((u >= 36).mean()), minUE=float(u.min()))
def sha(p):
    h = hashlib.sha256(); h.update(open(p, "rb").read()); return h.hexdigest()

summary = {"generated": time.strftime("%F %T"), "gap_s": GAP, "stations": {}, "inputs": {}}
tables = []
minute_series = {}      # bs -> list of segments, each = (epoch_minute array, mean array), only for stations that pass
for bs, code in STATIONS:
    fn = f"{D}/users_{code}_s.csv"; summary["inputs"][bs] = {"file": fn, "sha256": sha(fn)}
    df = pd.read_csv(fn)
    bad = (df.timestamp > 1e11) | (df.timestamp < 1e9); nbad = int(bad.sum())
    df = df[~bad].sort_values("second").reset_index(drop=True)
    sec = df.second.values.astype(np.int64); assert (np.diff(sec) > 0).all(), f"{bs}: second column not strictly monotone"
    cut = np.where(np.diff(sec) > GAP)[0] + 1
    segs = np.split(np.arange(len(df)), cut)
    tot = miss = 0; seg_info = []
    for ix in segs:
        s0, s1 = sec[ix[0]], sec[ix[-1]]; n = s1 - s0 + 1; tot += n; miss += n - len(ix)
        seg_info.append((ix, s0, s1))
    frac = miss / tot
    st = {"rows": int(len(df)), "bad_rows_dropped": nbad, "segments": len(segs), "total_s": int(tot), "missing_s": int(miss),
          "missing_frac": float(frac), "status": "fill (<1%)" if frac < 0.01 else "STOP (>=1%)"}
    # sensitivity (report only): missing fraction if segments were cut at gaps > 10 s instead of > 60 s
    cut10 = np.where(np.diff(sec) > 10)[0] + 1; t10 = m10 = 0
    for ix in np.split(np.arange(len(df)), cut10):
        n = sec[ix[-1]] - sec[ix[0]] + 1; t10 += n; m10 += n - len(ix)
    st["missing_frac_if_gap10"] = float(m10 / t10); st["segments_if_gap10"] = int(len(cut10) + 1)
    summary["stations"][bs] = st
    print(f"{bs} {code}: rows {len(df)} bad {nbad} segs {len(segs)} total_s {tot} missing_s {miss} frac {frac*100:.3f}% -> {st['status']}  [{time.time()-t0:.0f}s]", flush=True)
    if frac >= 0.01: continue
    # ---- fill + per-minute means
    segs_min = []; nmin = 0
    for ix, s0, s1 in seg_info:
        ep0 = int(np.floor(df.timestamp.values[ix[0]]))                      # epoch of second s0
        ser = pd.Series(df.user_unique.values[ix].astype(float), index=sec[ix]).reindex(np.arange(s0, s1 + 1))
        ser = ser.interpolate(method="linear")                               # interior gaps only (ends are present rows)
        assert not ser.isna().any()
        ep = ep0 + (ser.index.values - s0); mins = ep // 60
        m0 = mins[0] + (1 if ep[0] % 60 else 0); m1 = mins[-1] - (1 if (ep[-1] + 1) % 60 else 0)   # fully covered minutes
        if m1 < m0: continue
        vals = ser.values[(mins >= m0) & (mins <= m1)].reshape(-1, 60).mean(axis=1)
        segs_min.append((np.arange(m0, m1 + 1), vals)); nmin += len(vals)
    allmin = np.concatenate([v for _, v in segs_min])
    cmax = float(np.percentile(allmin, 99, method="linear"))
    st.update({"minutes": int(nmin), "minute_segments": len(segs_min), "Cmax_p99": cmax, "minute_mean_p50": float(np.median(allmin)), "minute_max": float(allmin.max())})
    minute_series[bs] = (segs_min, cmax)
    print(f"   minutes {nmin} in {len(segs_min)} segments; Cmax(P99 of per-minute mean) = {cmax:.2f}", flush=True)

def local_date(epoch): return datetime.fromtimestamp(int(epoch), tz=TZ).strftime("%Y-%m-%d")
def windows_1to1(stride):
    out = []
    for bs, (segs_min, cmax) in minute_series.items():
        for si, (mins, vals) in enumerate(segs_min):
            for k in range(0, len(vals) - 60 + 1, stride):
                c = vals[k:k + 60]; ep = int(mins[k] * 60)
                out.append({"bs": bs, "loc": bs, "date": local_date(ep), "start_epoch": ep, "seg": si, "ue": to_ue(c, cmax), "cmean": float(c.mean()), "cmax_station": cmax})
    return out
def windows_compressed():
    out = []
    for bs, (segs_min, cmax) in minute_series.items():
        for si, (mins, vals) in enumerate(segs_min):
            for k in range(0, len(vals) - 240 + 1, 240):
                raw = vals[k:k + 240]; ep = int(mins[k] * 60)
                roll = pd.Series(raw).rolling(5, center=True, min_periods=1).mean().values   # make_prior.py line 29
                c = roll.reshape(60, 4).mean(axis=1)                                          # make_prior.py line 31
                out.append({"bs": bs, "loc": bs, "date": local_date(ep), "start_epoch": ep, "seg": si, "ue": to_ue(c, cmax), "cmean": float(c.mean()), "cmax_station": cmax,
                            "ue_window_peak": to_ue(c, c.max()) if c.max() > 0 else None})     # Melbourne per-window-peak variant, for reference only
    return out
def apply_thresholds(lib, name):
    S = [stats(e["ue"]) for e in lib]
    mp = np.array([s["mp"] for s in S]); f36 = np.array([s["f36"] for s in S]); mn = np.array([s["minUE"] for s in S])
    ok = ~np.isnan(mp)
    thr = {"mp_lo_P10": float(np.percentile(mp[ok], 10, method="linear")), "mp_hi_P90": float(np.percentile(mp[ok], 90, method="linear")),
           "f36_max_P90": float(np.percentile(f36, 90, method="linear")), "minUE_min_P10": float(np.percentile(mn, 10, method="linear"))}
    rej = {"mp": 0, "f36": 0, "minUE": 0, "nan_mp": 0}; kept = 0
    for e, s in zip(lib, S):
        f = []
        if np.isnan(s["mp"]): f.append("nan_mp")
        else:
            if not (thr["mp_lo_P10"] <= s["mp"] <= thr["mp_hi_P90"]): f.append("mp")
            if s["f36"] > thr["f36_max_P90"]: f.append("f36")
            if s["minUE"] < thr["minUE_min_P10"]: f.append("minUE")
        e.update(s); e["keep"] = not f; e["reject"] = f
        for x in f: rej[x] += 1
        kept += not f
    groups = {}
    for e in lib:
        if e["keep"]: groups.setdefault((e["bs"], e["date"]), 0); groups[(e["bs"], e["date"])] += 1
    per_bs = {bs: {"windows": sum(1 for e in lib if e["bs"] == bs), "kept": sum(1 for e in lib if e["bs"] == bs and e["keep"]),
                   "groups": len({k for k in groups if k[0] == bs})} for bs in minute_series}
    gw = np.array(list(groups.values())) if groups else np.array([0])
    info = {"name": name, "windows": len(lib), "kept": kept, "rejected": len(lib) - kept, "rejected_by": rej, "thresholds": thr,
            "groups_kept": len(groups), "windows_per_group_mean": float(gw.mean()), "windows_per_group_min": int(gw.min()), "windows_per_group_max": int(gw.max()),
            "groups_all": len({(e["bs"], e["date"]) for e in lib}), "per_bs": per_bs}
    print(f"[{name}] windows {len(lib)} kept {kept} rejected {len(lib)-kept} {rej}; thr {thr}; groups kept {len(groups)} (all {info['groups_all']}), win/group {gw.mean():.2f} [{gw.min()}-{gw.max()}]", flush=True)
    return info

lib60 = windows_1to1(60); lib30 = windows_1to1(30); libC = windows_compressed()
summary["lib_1to1_stride60"] = apply_thresholds(lib60, "1:1 stride 60 (main)")
summary["lib_1to1_stride30"] = apply_thresholds(lib30, "1:1 stride 30 (sensitivity)")
summary["lib_compressed"] = apply_thresholds(libC, "compressed 4:1 stride 240 (contrast P)")
json.dump(lib60, open(f"{D}/madrid_1to1.json", "w")); json.dump([e for e in lib60 if e["keep"]], open(f"{D}/madrid_lib.json", "w"))
json.dump(lib30, open(f"{D}/madrid_1to1_stride30.json", "w"))
json.dump(libC, open(f"{D}/madrid_compressed.json", "w")); json.dump([e for e in libC if e["keep"]], open(f"{D}/madrid_compressed_lib.json", "w"))
summary["runtime_s"] = time.time() - t0
json.dump(summary, open(f"{D}/build_summary.json", "w"), indent=1)

# markdown tables
L = ["## Completeness (B1 item 9; gap cut > 60 s; missing = seconds inside segments without a row)", "",
     "| station | file | rows | bad rows dropped | segments | total s | missing s | missing % | rule | (if cut at >10 s: segments / missing %) |", "|---|---|---|---|---|---|---|---|---|---|"]
for bs, code in STATIONS:
    s = summary["stations"][bs]
    L.append(f"| {bs} | users_{code}_s.csv | {s['rows']} | {s['bad_rows_dropped']} | {s['segments']} | {s['total_s']} | {s['missing_s']} | {s['missing_frac']*100:.3f} | {s['status']} | {s['segments_if_gap10']} / {s['missing_frac_if_gap10']*100:.3f} |")
L += ["", "## Stations built (per-minute series)", "", "| station | full minutes | minute segments | Cmax = P99 per-minute mean | P50 | max |", "|---|---|---|---|---|---|"]
for bs in minute_series:
    s = summary["stations"][bs]; L.append(f"| {bs} | {s['minutes']} | {s['minute_segments']} | {s['Cmax_p99']:.2f} | {s['minute_mean_p50']:.2f} | {s['minute_max']:.2f} |")
for key in ("lib_1to1_stride60", "lib_1to1_stride30", "lib_compressed"):
    i = summary[key]; t = i["thresholds"]
    L += ["", f"## Library: {i['name']}", "", f"windows {i['windows']}, kept {i['kept']}, rejected {i['rejected']} (by mp {i['rejected_by']['mp']}, f36 {i['rejected_by']['f36']}, minUE {i['rejected_by']['minUE']}, nan {i['rejected_by']['nan_mp']}; a window may fail several)",
          f"thresholds: mp in [{t['mp_lo_P10']:.4f}, {t['mp_hi_P90']:.4f}] (P10,P90), f36 <= {t['f36_max_P90']:.4f} (P90), minUE >= {t['minUE_min_P10']:.1f} (P10)",
          f"(bs, date) groups: kept {i['groups_kept']} (all windows {i['groups_all']}); windows per kept group mean {i['windows_per_group_mean']:.2f}, min {i['windows_per_group_min']}, max {i['windows_per_group_max']}", "",
          "| station | windows | kept | groups kept |", "|---|---|---|---|"]
    for bs, v in i["per_bs"].items(): L.append(f"| {bs} | {v['windows']} | {v['kept']} | {v['groups']} |")
open(f"{D}/build_tables.md", "w").write("\n".join(L) + "\n")
print("\n".join(L)); print(f"runtime {time.time()-t0:.1f} s")
