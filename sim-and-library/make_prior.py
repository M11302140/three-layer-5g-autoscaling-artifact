#!/usr/bin/env python3
"""(docstring removed)"""
import json, sys
import numpy as np, pandas as pd
F='/home/user/Downloads/3b4c9b89-c976-49e7-8358-075fe3699297.csv'
MAXUE=40

EXCLUDE={(35,"2024-06-12"),(84,"2024-06-18"),(5,"2024-06-15")}
HELDOUT=json.load(open("heldout.json")) if len(sys.argv)>1 and sys.argv[1]=="--with-heldout" else []
for h in HELDOUT: EXCLUDE.add((h["loc"],h["date"]))
MIN_PEAK=20.0
MIN_ROWS=1200
def deadband(ue, band=2):
    out=[ue[0]]
    for v in ue[1:]: out.append(v if abs(v-out[-1])>=band else out[-1])
    return out
df=pd.read_csv(F, usecols=['location_id','sensing_date','sensing_time','total_of_directions'])
df['min']=df.sensing_time.str.slice(0,2).astype(int)*60+df.sensing_time.str.slice(3,5).astype(int)
df=df.groupby(['location_id','sensing_date','min'],as_index=False).total_of_directions.sum()
out=[]
for (loc,date),g in df.groupby(['location_id','sensing_date']):
    if (loc,date) in EXCLUDE or len(g)<MIN_ROWS: continue
    s=g.set_index('min').total_of_directions.reindex(range(1440)).interpolate(limit_direction='both').fillna(0)
    for start in range(6*60, 20*60+1, 60):
        raw=s.iloc[start:start+240].values
        if len(raw)<240: continue
        roll=pd.Series(raw).rolling(5,center=True,min_periods=1).mean().values
        if roll.max()<MIN_PEAK: continue
        c=roll.reshape(60,4).mean(axis=1)
        ue=deadband(np.clip(np.round(MAXUE*c/c.max()),1,MAXUE).astype(int).tolist())
        out.append(dict(loc=int(loc),date=date,start=start,ue=ue))
json.dump(out,open("prior_traces.json","w"))
locs=sorted({o["loc"] for o in out}); print("prior traces:",len(out),"locs:",len(locs),locs)
