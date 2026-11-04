#!/usr/bin/env python3
"""(docstring removed)"""
import json, hashlib, os, random, sys, time, math
import numpy as np, pandas as pd

Q = os.path.dirname(os.path.abspath(__file__)); E = "/home/user/experiment"
CSV_DEFAULT = "/home/user/Downloads/3b4c9b89-c976-49e7-8358-075fe3699297.csv"
MAXUE, PPS = 40, 125000
THR = json.load(open(f"{Q}/t6t7_thresholds.json"))
POOL = json.load(open(f"{Q}/t6t7_pool.json")); CSV = POOL.get("csv", CSV_DEFAULT)   # (C′) 2026-10 merged CSV
LOG = f"{Q}/t6t7_sampling_log.txt"
for fn in [f"{E}/trace_ue_60min_v3_t6.json", f"{E}/trace_ue_60min_v3_t7.json", LOG]:
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
    return dict(mp=float(u.mean() / u.max()), f36=float((u >= 36).mean()), minue=float(u.min()),
                rise10=float(rise), start=float(u[0]), end=float(u[-1]))
def check(s):
    t = THR["thresholds"]; f = []
    if not (t["i_mp_lo"] <= s["mp"] <= t["i_mp_hi"]): f.append(f"(i) mp={s['mp']:.3f} not in [{t['i_mp_lo']:.3f},{t['i_mp_hi']:.3f}]")
    if s["f36"] > t["ii_f36_max"]: f.append(f"(ii) f36={s['f36']:.3f} > {t['ii_f36_max']:.3f}")
    if s["minue"] < t["iii_minue_min"]: f.append(f"(iii) minue={s['minue']:.0f} < {t['iii_minue_min']:.0f}")
    if s["rise10"] > t["iv_rise10_max"]: f.append(f"(iv) rise10={s['rise10']:.0f} > {t['iv_rise10_max']:.0f}")
    if s["start"] > t["v_start_max"] or s["end"] > t["v_end_max"]: f.append(f"(v) start/end={s['start']:.0f}/{s['end']:.0f} > 30")
    return f

log = []
def L(x): log.append(x); print(x)
L(f"# make_newtraces.py run {time.strftime('%Y-%m-%d %H:%M:%S')}  seed={POOL['seed']}")
L(f"thresholds frozen_at {THR['frozen_at']} (library sha {THR['library_sha256'][:16]}…); pool ruled_at {POOL.get('ruled_at')} mode={POOL['mode']}")
L(f"CSV sha256 {sha(CSV)}")
df = pd.read_csv(CSV, usecols=['location_id', 'sensing_date', 'sensing_time', 'total_of_directions'])
df['min'] = df.sensing_time.str.slice(0, 2).astype(int) * 60 + df.sensing_time.str.slice(3, 5).astype(int)
df = df.groupby(['location_id', 'sensing_date', 'min'], as_index=False).total_of_directions.sum()
excl_ld = {(int(a), b) for a, b in POOL["locdays_excluded"]}
allowed = set(POOL["sensors_allowed"]) if POOL.get("sensors_allowed") else None
excluded = set(POOL["sensors_excluded"])
series = {}; cands = []
for (loc, date), g in df.groupby(['location_id', 'sensing_date']):
    loc = int(loc)
    if not (POOL["date_lo"] <= date <= POOL["date_hi"]): continue
    if loc in excluded or (allowed is not None and loc not in allowed) or (loc, date) in excl_ld: continue
    if len(g) < POOL["min_rows"]: continue
    s = g.set_index('min').total_of_directions.reindex(range(1440)).interpolate(limit_direction='both').fillna(0)
    series[(loc, date)] = s
    for start in POOL["starts"]:
        raw = s.iloc[start:start + 240].values
        if len(raw) < 240: continue
        roll = pd.Series(raw).rolling(5, center=True, min_periods=1).mean().values
        if roll.max() < POOL["min_peak"]: continue
        cands.append((loc, date, start))
cands.sort()
L(f"pool: sensors={len({c[0] for c in cands})} locdays={len({c[:2] for c in cands})} windows={len(cands)}")
rng = random.Random(POOL["seed"]); rng.shuffle(cands)
picked = []
for k, (loc, date, start) in enumerate(cands, 1):
    raw = series[(loc, date)].iloc[start:start + 240].values
    roll = pd.Series(raw).rolling(5, center=True, min_periods=1).mean().values
    c = roll.reshape(60, 4).mean(axis=1)
    ue = deadband(np.clip(np.round(MAXUE * c / c.max()), 1, MAXUE).astype(int).tolist())
    st = stats(ue); f = check(st)
    if picked and loc == picked[0]["loc"] and not f: f = ["same sensor as t6 (rule: t7 must differ)"]
    if f:
        L(f"rank {k}: sensor {loc} {date} {start // 60:02d}:00 REJECT " + "; ".join(f)); continue
    name = "t6" if not picked else "t7"
    L(f"rank {k}: sensor {loc} {date} {start // 60:02d}:00 **ACCEPT = {name}** mp={st['mp']:.3f} f36={st['f36']:.3f} minue={st['minue']:.0f} rise10={st['rise10']:.0f} start/end={st['start']:.0f}/{st['end']:.0f}")
    picked.append(dict(name=name, loc=loc, date=date, start=start, rank=k, ue=ue, stats=st))
    if len(picked) == 2: break
if len(picked) < 2:
    L(f"**只有 {len(picked)} 條通過 → 回報審查者,不自行放寬**")
open(LOG, "w").write("\n".join(log) + "\n")

res = {"seed": POOL["seed"], "pool_mode": POOL["mode"], "thresholds_frozen_at": THR["frozen_at"], "files": {}}
for p in picked:
    ue0 = p["ue"][0]
    js = {"ue": p["ue"], "pps_per_ue": PPS, "max_ue": MAXUE, "phases": [],
          "source": {"dataset": "Melbourne Pedestrian Counting System (per-minute), resource 3b4c9b89", "location_id": p["loc"],
                     "window_local": f"sensor {p['loc']}, {p['date']} {p['start'] // 60:02d}:00-{p['start'] // 60 + 4:02d}:00",
                     "selection_rule": f"spec §4.53 v2, pool mode {POOL['mode']}, seed {POOL['seed']}, pool rank {p['rank']}; thresholds frozen {THR['frozen_at']}",
                     "stats": p["stats"],
                     "pipeline": "per-minute counts -> 1min resample+interp -> 5min centered rolling mean -> 4:1 compression (mean of 4) -> UE=clip(round(40*C/Cmax),1,40) -> 2-UE deadband quantization"}}
    fn = f"{E}/trace_ue_60min_v3_{p['name']}.json"; json.dump(js, open(fn, "w")); res["files"][fn] = sha(fn)

    ramp = []; v = 6
    while v < ue0: ramp.append(v); v += 4
    ramp.append(ue0)
    for suffix, plateau in [("", 32), ("_static", 5)]:
        w = {"pps_per_ue": PPS, "max_ue": MAXUE, "ue": ramp + [ue0] * plateau, "phases": [],
             "source": {"note": f"warm-in for {p['name']}: +4 UE/min ramp to {ue0} UE then plateau (not scored)"}}
        fn = f"{E}/trace_warmin_{p['name']}{suffix}.json"; json.dump(w, open(fn, "w")); res["files"][fn] = sha(fn)
    rep = min(8, math.ceil(ue0 / 4)); wk = math.ceil(rep / 2); vy = math.ceil(ue0 * 0.125 / 1.5)
    res[p["name"]] = dict(loc=p["loc"], date=p["date"], start=p["start"], rank=p["rank"], ue0=ue0, stats=p["stats"],
                          start_fleet=dict(rep=rep, wk=wk, vy=vy, rule="rep=min(8,ceil(UE0/4)); wk=ceil(rep/2); vy=ceil(UE0*0.125Mpps/1.5Mpps) — same as t3 6/3/2, t4 5/3/2, t5 8/4/3"))
res["log_sha256"] = sha(LOG)
json.dump(res, open(f"{Q}/t6t7_result.json", "w"), indent=1)
print(json.dumps({k: v for k, v in res.items() if k != "files"}, indent=1)); print("files:", json.dumps(res["files"], indent=1))
