#!/usr/bin/env python3
"""t910/merge.py (2026-10-26, spec §4.127 §3): merge ped_poll snapshots into qsim/t910/ped2026_merged_1026.csv for the t9/t10 pool.
Same columns, dedupe key and checks as ped_merge.py; streaming (one snapshot at a time) and restricted to the pool's 20 allowed sensors and
Melbourne local dates 2026-10-15..10-25 (memory: the full 1354-snapshot concat does not fit comfortably next to the calibration).
Prints counts only (rows per sensor/day, gaps, local-time consistency); no shapes, no statistics."""
import glob, hashlib, json, os
import pandas as pd
Q="/home/user/experiment/qsim"; OUT=f"{Q}/t910/ped2026_merged_1026.csv"
ALLOWED={3,4,6,14,21,24,30,35,41,45,47,49,56,58,63,65,66,79,84,5}; LO,HI="2026-10-15","2026-10-25"
fs=[f for f in sorted(glob.glob(f"{Q}/ped2026/snap_*.csv")) if "20261014T000000Z"<=os.path.basename(f)[5:21]<="20261026T000000Z"]
cols=["location_id","sensing_datetime","sensing_date","sensing_time","direction_1","direction_2","total_of_directions"]
acc=None; nbad=0; nsnap=0
for f in fs:
    try: s=pd.read_csv(f,encoding="utf-8-sig")
    except Exception as e: nbad+=1; print("unreadable",os.path.basename(f),type(e).__name__); continue
    if not set(cols)<=set(s.columns) or len(s)==0: nbad+=1; continue
    s=s[cols]; s=s[s.location_id.isin(ALLOWED)&(s.sensing_date.astype(str)>=LO)&(s.sensing_date.astype(str)<=HI)]; nsnap+=1
    acc=s if acc is None else pd.concat([acc,s],ignore_index=True).drop_duplicates(["location_id","sensing_datetime"])
df=acc.sort_values(["location_id","sensing_datetime"]).reset_index(drop=True)
loc=pd.to_datetime(df.sensing_datetime,utc=True).dt.tz_convert("Australia/Melbourne")
mism=int(((loc.dt.strftime("%Y-%m-%d")!=df.sensing_date.astype(str))|(loc.dt.strftime("%H:%M")!=df.sensing_time.astype(str))).sum())
df.insert(0,"_id",range(1,len(df)+1)); df.to_csv(OUT,index=False)
h=hashlib.sha256(open(OUT,"rb").read()).hexdigest()
print(f"snapshots read {nsnap} (unreadable/empty {nbad}) of {len(fs)}; rows {len(df)}; sensors {df.location_id.nunique()}; local dates {df.sensing_date.min()}..{df.sensing_date.max()}")
print(f"local-time consistency mismatches: {mism} (expect 0); sha256 {h}")
per=df.groupby(["location_id","sensing_date"]).size().unstack(fill_value=0)
print("rows per (sensor, local date):"); print(per.to_string())
json.dump(dict(csv=OUT,sha256=h,rows=len(df),snapshots=nsnap,unreadable=nbad,mismatch=mism),open(f"{Q}/t910/merge_result.json","w"),indent=1)
