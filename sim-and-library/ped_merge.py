#!/usr/bin/env python3
"""(docstring removed)"""
import sys, glob, hashlib, os
import pandas as pd
d, out = sys.argv[1], sys.argv[2]
fs = sorted(glob.glob(f"{d}/snap_*.csv"))
cols = ["location_id", "sensing_datetime", "sensing_date", "sensing_time", "direction_1", "direction_2", "total_of_directions"]
snaps = []
print("| snapshot (UTC fetch) | rows | min sensing_datetime | max sensing_datetime | overlap with previous (min) |")
print("|---|---|---|---|---|")
prev_max = None
for f in fs:
    s = pd.read_csv(f, encoding="utf-8-sig")[cols]
    ts = pd.to_datetime(s.sensing_datetime, utc=True)
    lo, hi = ts.min(), ts.max()
    ov = "" if prev_max is None else f"{(prev_max - lo).total_seconds() / 60:.0f}" + ("" if prev_max >= lo else "  **GAP**")
    print(f"| {os.path.basename(f)} | {len(s)} | {lo} | {hi} | {ov} |")
    prev_max = hi if prev_max is None else max(prev_max, hi)
    snaps.append(s)
df = pd.concat(snaps, ignore_index=True).drop_duplicates(["location_id", "sensing_datetime"]).sort_values(["location_id", "sensing_datetime"]).reset_index(drop=True)
# (②) local-time field consistency
loc = pd.to_datetime(df.sensing_datetime, utc=True).dt.tz_convert("Australia/Melbourne")
mism = int(((loc.dt.strftime("%Y-%m-%d") != df.sensing_date.astype(str)) | (loc.dt.strftime("%H:%M") != df.sensing_time.astype(str))).sum())
print(f"\n(②) local-time consistency: {mism} rows where Australia/Melbourne(sensing_datetime) != sensing_date/sensing_time (expect 0); "
      f"utc offsets seen: {sorted(df.sensing_datetime.astype(str).str[-6:].unique().tolist())}")
df.insert(0, "_id", range(1, len(df) + 1)); df.to_csv(out, index=False)
h = hashlib.sha256(open(out, "rb").read()).hexdigest()
print(f"merged: snapshots {len(fs)}; rows {len(df)}; sensors {df.location_id.nunique()}; local dates {df.sensing_date.min()}..{df.sensing_date.max()}; sha256 {h}")
per_day = df.groupby(["location_id", "sensing_date"]).size().unstack(fill_value=0)
print("\nrows per (sensor, local date), sensors with any day >= 1200 rows (counts only):")
print(per_day[(per_day >= 1200).any(axis=1)].to_string())
