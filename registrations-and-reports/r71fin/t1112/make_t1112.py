#!/usr/bin/env python3
"""r71fin/t1112/make_t1112.py (2026-10-28, spec §4.139 item 2 / §4.132 item 4): copy of t910/make_t910.py; draws t11 (general band) and t12 (stress band; fallback high-load band). RUNS ONCE.
Pipeline, deadband, stats and the output format are copied from make_gtrace2.py (itself a copy of make_newtraces.py / make_prior.py).
Pool = r71fin/t1112/pool.json (one source: live 2026-10-26..27); thresholds = t6t7_thresholds.json (general), gtrace/g_thresholds.json (stress), t910/highload_thresholds.json.
Candidates sorted -> random.Random(seed).shuffle -> each candidate evaluated against the three bands in rank order (all logged);
t11 = first general passer; t12 = first stress passer with (loc,date) != t11; none -> first high-load passer with (loc,date) != t11.
No manual choice, no looking at shapes, no change of seed or thresholds; no general passer -> report, do not relax."""
import json, hashlib, os, random, sys, time, math
import numpy as np, pandas as pd
Q = "/home/user/experiment/qsim"; E = "/home/user/experiment"
MAXUE, PPS = 40, 125000
POOL = json.load(open(f"{Q}/r71fin/t1112/pool.json"))
TG = json.load(open(f"{Q}/t6t7_thresholds.json"))["thresholds"]
TS = json.load(open(f"{Q}/gtrace/g_thresholds.json"))["thresholds"]
TH = json.load(open(f"{Q}/t910/highload_thresholds.json"))["thresholds"]
LOG = f"{Q}/r71fin/t1112/sampling_log.txt"
for fn in [f"{E}/trace_ue_60min_v3_t11.json", f"{E}/trace_ue_60min_v3_t12.json", LOG]:
    if os.path.exists(fn): sys.exit(f"REFUSE: {fn} exists (sampling runs once)")
def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()
def deadband(ue, band=2):
    out = [ue[0]]
    for v in ue[1:]: out.append(v if abs(v - out[-1]) >= band else out[-1])
    return out
def stats(ue):
    u = np.asarray(ue, float); n = len(u)
    rise = max(u[j] - u[i] for i in range(n) for j in range(i + 1, min(n - 1, i + 10) + 1))
    return dict(mp=float(u.mean() / u.max()), f36=float((u >= 36).mean()), minue=float(u.min()), rise10=float(rise), start=float(u[0]), end=float(u[-1]))
def general(s):
    f = []
    if not (TG["i_mp_lo"] <= s["mp"] <= TG["i_mp_hi"]): f.append(f"(i) mp={s['mp']:.3f}")
    if s["f36"] > TG["ii_f36_max"]: f.append(f"(ii) f36={s['f36']:.3f}")
    if s["minue"] < TG["iii_minue_min"]: f.append(f"(iii) minue={s['minue']:.0f}")
    if s["rise10"] > TG["iv_rise10_max"]: f.append(f"(iv) rise10={s['rise10']:.0f}")
    if s["start"] > TG["v_start_max"] or s["end"] > TG["v_end_max"]: f.append(f"(v) start/end={s['start']:.0f}/{s['end']:.0f}")
    return f
def stress(s):
    f = []
    if s["mp"] > TS["mp_max"]: f.append(f"(i') mp={s['mp']:.3f}")
    if s["rise10"] < TS["rise10_min"]: f.append(f"(iv') rise10={s['rise10']:.0f}")
    if s["minue"] < TS["minue_min"]: f.append(f"(iii) minue={s['minue']:.0f}")
    if s["start"] > TS["start_max"] or s["end"] > TS["end_max"]: f.append(f"(v) start/end={s['start']:.0f}/{s['end']:.0f}")
    return f
def highload(s):
    f = []
    if s["mp"] < TH["mp_min"]: f.append(f"(h) mp={s['mp']:.3f}")
    if s["minue"] < TH["minue_min"]: f.append(f"(iii) minue={s['minue']:.0f}")
    if s["start"] > TH["start_max"] or s["end"] > TH["end_max"]: f.append(f"(v) start/end={s['start']:.0f}/{s['end']:.0f}")
    return f
log = []
def L(x): log.append(x); print(x)
L(f"# make_t1112.py run {time.strftime('%Y-%m-%d %H:%M:%S')} seed={POOL['seed']}; pool ruled_at {POOL['ruled_at']}")
for p in (f"{Q}/r71fin/t1112/pool.json", f"{Q}/t6t7_thresholds.json", f"{Q}/gtrace/g_thresholds.json", f"{Q}/t910/highload_thresholds.json", os.path.abspath(__file__)):
    L(f"sha256 {os.path.basename(p)} {sha(p)}")
allowed = set(POOL["sensors_allowed"]); series = {}; cands = []
for src in POOL["sources"]:
    h = sha(src["csv"]); L(f"source {src['name']}: csv sha256 {h} (pool says {src['csv_sha256']}) {'OK' if h == src['csv_sha256'] else 'MISMATCH'}")
    if h != src["csv_sha256"]: sys.exit("REFUSE: csv hash mismatch")
    df = pd.read_csv(src["csv"], usecols=['location_id', 'sensing_date', 'sensing_time', 'total_of_directions'])
    df['min'] = df.sensing_time.str.slice(0, 2).astype(int) * 60 + df.sensing_time.str.slice(3, 5).astype(int)
    df = df.groupby(['location_id', 'sensing_date', 'min'], as_index=False).total_of_directions.sum()
    excl = {(int(a), b) for a, b in src["locdays_excluded"]}; n0 = len(cands)
    for (loc, date), g in df.groupby(['location_id', 'sensing_date']):
        loc = int(loc)
        if not (src["date_lo"] <= date <= src["date_hi"]): continue
        if loc not in allowed or (loc, date) in excl: continue
        if len(g) < POOL["min_rows"]: continue
        s = g.set_index('min').total_of_directions.reindex(range(1440)).interpolate(limit_direction='both').fillna(0)
        series[(loc, date)] = s
        for start in POOL["starts"]:
            raw = s.iloc[start:start + 240].values
            if len(raw) < 240: continue
            roll = pd.Series(raw).rolling(5, center=True, min_periods=1).mean().values
            if roll.max() < POOL["min_peak"]: continue
            cands.append((loc, date, start))
    sub = cands[n0:]; L(f"  {src['name']}: sensors={len({c[0] for c in sub})} locdays={len({c[:2] for c in sub})} windows={len(sub)}")
cands.sort()
L(f"pool total: sensors={len({c[0] for c in cands})} locdays={len({c[:2] for c in cands})} windows={len(cands)}")
rng = random.Random(POOL["seed"]); rng.shuffle(cands)
ev = []
for k, (loc, date, start) in enumerate(cands, 1):
    raw = series[(loc, date)].iloc[start:start + 240].values
    roll = pd.Series(raw).rolling(5, center=True, min_periods=1).mean().values
    c = roll.reshape(60, 4).mean(axis=1)
    ue = deadband(np.clip(np.round(MAXUE * c / c.max()), 1, MAXUE).astype(int).tolist())
    st = stats(ue); ev.append(dict(rank=k, loc=loc, date=date, start=start, ue=ue, stats=st, g=general(st), s=stress(st), h=highload(st)))
t9 = next((e for e in ev if not e["g"]), None)
if t9 is None:
    t10 = None; mode = None
else:
    t10 = next((e for e in ev if not e["s"] and (e["loc"], e["date"]) != (t9["loc"], t9["date"])), None); mode = "stress"
    if t10 is None:
        t10 = next((e for e in ev if not e["h"] and (e["loc"], e["date"]) != (t9["loc"], t9["date"])), None); mode = "highload (fallback: no stress-band passer)"
for e in ev:
    st = e["stats"]; tag = []
    if t9 is not None and e is t9: tag.append("**ACCEPT = t11**")
    if t10 is not None and e is t10: tag.append(f"**ACCEPT = t12 ({mode})**")
    L(f"rank {e['rank']}: sensor {e['loc']} {e['date']} {e['start'] // 60:02d}:00 mp={st['mp']:.3f} f36={st['f36']:.3f} minue={st['minue']:.0f} rise10={st['rise10']:.0f} start/end={st['start']:.0f}/{st['end']:.0f} | general: {'PASS' if not e['g'] else '; '.join(e['g'])} | stress: {'PASS' if not e['s'] else '; '.join(e['s'])} | highload: {'PASS' if not e['h'] else '; '.join(e['h'])} {' '.join(tag)}")
L(f"general passers {sum(1 for e in ev if not e['g'])}, stress passers {sum(1 for e in ev if not e['s'])}, high-load passers {sum(1 for e in ev if not e['h'])} of {len(ev)}")
if t9 is None: L("**no general-band passer (t11) -> report, do not relax**")
if t10 is None: L("**no t12 (stress or high-load) passer -> report, do not relax**")
open(LOG, "w").write("\n".join(log) + "\n")
res = {"seed": POOL["seed"], "pool_ruled_at": POOL["ruled_at"], "files": {}, "t12_band": mode}
for name, p in (("t11", t9), ("t12", t10)):
    if p is None: continue
    ue0 = p["ue"][0]; band = "general band (§4.53 thresholds)" if name == "t11" else f"{mode} band"
    js = {"ue": p["ue"], "pps_per_ue": PPS, "max_ue": MAXUE, "phases": [],
          "source": {"dataset": "Melbourne Pedestrian Counting System (per-minute)" + (", live collection 2026-10 (ped_poll)" if p["date"].startswith("2026") else ", resource 3b4c9b89 (2024)"),
                     "location_id": p["loc"], "window_local": f"sensor {p['loc']}, {p['date']} {p['start'] // 60:02d}:00-{p['start'] // 60 + 4:02d}:00",
                     "selection_rule": f"spec §4.139 / §4.132 item 4, {band}, seed {POOL['seed']}, pool rank {p['rank']}", "stats": p["stats"],
                     "pipeline": "per-minute counts -> 1min resample+interp -> 5min centered rolling mean -> 4:1 compression (mean of 4) -> UE=clip(round(40*C/Cmax),1,40) -> 2-UE deadband quantization"}}
    fn = f"{E}/trace_ue_60min_v3_{name}.json"; json.dump(js, open(fn, "w")); res["files"][fn] = sha(fn)
    ramp = []; v = 6
    while v < ue0: ramp.append(v); v += 4
    ramp.append(ue0)
    for suffix, plateau in [("", 32), ("_static", 5)]:
        w = {"pps_per_ue": PPS, "max_ue": MAXUE, "ue": ramp + [ue0] * plateau, "phases": [],
             "source": {"note": f"warm-in for {name}: +4 UE/min ramp to {ue0} UE then plateau (not scored)"}}
        fn = f"{E}/trace_warmin_{name}{suffix}.json"; json.dump(w, open(fn, "w")); res["files"][fn] = sha(fn)
    rep = min(8, math.ceil(ue0 / 4)); wk = math.ceil(rep / 2); vy = math.ceil(ue0 * 0.125 / 1.5)
    res[name] = dict(loc=p["loc"], date=p["date"], start=p["start"], rank=p["rank"], ue0=ue0, stats=p["stats"], band=band,
                     start_fleet=(dict(rep=rep, wk=wk, vy=vy, rule="t3/t8 rule: rep=min(8,ceil(UE0/4)); wk=ceil(rep/2); vy=ceil(UE0*0.125/1.5)") if name == "t12" else "general band: t6/t7 start rule"))
res["log_sha256"] = sha(LOG)
json.dump(res, open(f"{Q}/r71fin/t1112/result.json", "w"), indent=1)
print(json.dumps({k: v for k, v in res.items() if k != "files"}, indent=1))
