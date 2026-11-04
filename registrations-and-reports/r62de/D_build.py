#!/usr/bin/env python3
"""Task D library builder: generalisation of make_prior.py (frozen; not modified).
Identical steps: per-minute counts (sum over directions, grouped by loc/date/minute) → reindex 0..1439 + linear interpolation
(limit_direction='both') → loc-day kept if ≥1200 minutes with data → windows start 06:00..20:00 every 60 min (same 15 starts) →
smoothing: centred rolling mean of `smooth` minutes (min_periods=1, applied inside the window, as in make_prior) →
rejection: smoothed window peak < 20 /min → drop (same rule, applied to the variant's smoothed series) →
compression k:1: window length = 60·k real minutes, mean of k consecutive real minutes per experiment minute (k=1 → 60 real
minutes, k=2 → 120, k=4 → 240) → UE = clip(round(40·C/Cmax),1,40) → deadband (band 2 = make_prior; band 0 = none).
EXCLUDE = evaluation loc-days of make_prior (traces 1-3); with --with-heldout also heldout.json (t4/t5), as make_prior.
Usage: python3 D_build.py → libs/lib_s{smooth}_c{k}_d{band}.json for the 18 variants (+ reproduction check vs prior_traces.json)"""
import json, sys, os, itertools, numpy as np, pandas as pd
Q='/home/user/experiment/qsim'; OUT=f'{Q}/r62de/libs'; os.makedirs(OUT,exist_ok=True)
F='/home/user/Downloads/3b4c9b89-c976-49e7-8358-075fe3699297.csv'
MAXUE=40; MIN_PEAK=20.0; MIN_ROWS=1200
def deadband(ue, band=2):
    out=[ue[0]]
    for v in ue[1:]: out.append(v if abs(v-out[-1])>=band else out[-1])
    return out
def build(series_by_day, smooth, k, band, exclude):
    out=[]
    for (loc,date),s in series_by_day:
        if (loc,date) in exclude: continue
        for start in range(6*60, 20*60+1, 60):
            raw=s.iloc[start:start+60*k].values
            if len(raw)<60*k: continue
            roll=pd.Series(raw).rolling(smooth,center=True,min_periods=1).mean().values
            if roll.max()<MIN_PEAK: continue
            c=roll.reshape(60,k).mean(axis=1)
            ue=np.clip(np.round(MAXUE*c/c.max()),1,MAXUE).astype(int).tolist()
            if band>0: ue=deadband(ue,band)
            out.append(dict(loc=int(loc),date=date,start=start,ue=ue))
    return out
if __name__=="__main__":
    df=pd.read_csv(F, usecols=['location_id','sensing_date','sensing_time','total_of_directions'])
    df['min']=df.sensing_time.str.slice(0,2).astype(int)*60+df.sensing_time.str.slice(3,5).astype(int)
    df=df.groupby(['location_id','sensing_date','min'],as_index=False).total_of_directions.sum()
    days=[]
    for (loc,date),g in df.groupby(['location_id','sensing_date']):
        if len(g)<MIN_ROWS: continue
        days.append(((loc,date), g.set_index('min').total_of_directions.reindex(range(1440)).interpolate(limit_direction='both').fillna(0)))
    EX={(35,"2024-06-12"),(84,"2024-06-18"),(5,"2024-06-15")}
    EXH=EX|{(h["loc"],h["date"]) for h in json.load(open(f'{Q}/heldout.json'))}
    ref=json.load(open(f'{Q}/prior_traces.json'))
    for name,ex in (("no-heldout-exclusion",EX),("with-heldout-exclusion",EXH)):
        lib=build(days,5,4,2,ex); print(f"reproduction ({name}): n {len(lib)} vs ref {len(ref)}; identical: {lib==ref}", flush=True)
        if lib==ref: EXC=ex; tag=name
    print("using exclusion set:", tag, sorted(EXC))
    for smooth,k,band in itertools.product((1,5,10),(1,2,4),(0,2)):
        lib=build(days,smooth,k,band,EXC); json.dump(lib,open(f'{OUT}/lib_s{smooth}_c{k}_d{band}.json','w'))
        print(f"s{smooth} c{k}:1 d{band}: n {len(lib)} groups {len(set((t['loc'],t['date']) for t in lib))}", flush=True)
