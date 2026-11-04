#!/usr/bin/env python3
"""(docstring removed)"""
import json
import numpy as np, pandas as pd
F='/home/user/Downloads/3b4c9b89-c976-49e7-8358-075fe3699297.csv'; MAXUE=40; PPS=125000
def deadband(ue, band=2):
    out=[ue[0]]
    for v in ue[1:]: out.append(v if abs(v-out[-1])>=band else out[-1])
    return out
df=pd.read_csv(F, usecols=['location_id','sensing_date','sensing_time','total_of_directions'])
df['min']=df.sensing_time.str.slice(0,2).astype(int)*60+df.sensing_time.str.slice(3,5).astype(int)
df=df.groupby(['location_id','sensing_date','min'],as_index=False).total_of_directions.sum()
for h in json.load(open("heldout.json")):
    g=df[(df.location_id==h["loc"])&(df.sensing_date==h["date"])].set_index('min').total_of_directions
    s=g.reindex(range(1440)).interpolate(limit_direction='both').fillna(0)
    raw=s.iloc[h["start"]:h["start"]+240].values
    roll=pd.Series(raw).rolling(5,center=True,min_periods=1).mean().values
    c=roll.reshape(60,4).mean(axis=1)
    ue=deadband(np.clip(np.round(MAXUE*c/c.max()),1,MAXUE).astype(int).tolist())
    js={"ue":ue,"pps_per_ue":PPS,"max_ue":MAXUE,"phases":[],
        "source":{"dataset":"Melbourne Pedestrian Counting System (per-minute), resource 3b4c9b89","location_id":h["loc"],
                  "window_local":h["label"],"selection_rule":h["rule"],
                  "pipeline":"per-minute counts -> 1min resample+interp -> 5min centered rolling mean -> 4:1 compression (mean of 4) -> UE=clip(round(40*C/Cmax),1,40) -> 2-UE deadband quantization"}}
    json.dump(js,open(f"/home/user/experiment/trace_ue_60min_v3_{h['name']}.json","w"))
    print(h["name"],"ue:",ue,"min",min(ue),"max",max(ue),"mean %.1f"%np.mean(ue))
