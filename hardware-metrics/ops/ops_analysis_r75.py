#!/usr/bin/env python3
"""Task D (§4.99): ops-cost table + flap decomposition from daemon logs (read-only)."""
import json,re,csv,collections,statistics,datetime as dt,os
P="/home/user/experiment/p2"; OUT="/home/user/experiment/paper_out_new/ops/r75"
VOID={"r302","r304","r307","r309","r368","r370","r376","r379"}
BLOCKS={"t3","t4","t5","t6","t7"}
ARM={"S4a":"S4a","S4b":"S4b","HHRO":"v6","B4c2_slo":"B4c2","B5c1_slo":"B5c1","B6c4_slo":"B6","B1_static":"B1"}
ARMORD=["S4a","S4b","v6","B4c2","B5c1","B6","B1"]; TRORD=["t3","t4","t5","t6","t7"]
# ---- ledger
led={}
for line in open(f"{P}/main_exp_ledger.tsv"):
    if not line.startswith("r"): continue
    f=line.rstrip("\n").split("\t"); run,block,arm,flags=f[0],f[1],f[2],f[5]
    if run in led and re.search(r"void",led[run][2],re.I) is None: continue   # keep first non-void row
    led[run]=(block,arm,flags)
# R75 (spec §4.125): run set from the single source valid_runs.tsv (runset.py)
ARMBACK={"S4a":"S4a","S4b":"S4b","v6":"HHRO","B4c2":"B4c2_slo","B5c1":"B5c1_slo","B6":"B6c4_slo","B1":"B1_static"}
valid=[]; confirm=[]
for l in list(open("/home/user/experiment/paper_out_new/valid_runs.tsv"))[1:]:
    run,block,arm,flag=l.rstrip("\n").split("\t")
    led[run]=(block,ARMBACK[arm],flag)
    (confirm if flag.startswith("confirm") else valid).append(run)
valid.sort(key=lambda r:int(r[1:])); confirm.sort()
def ts(s):
    return float(int(_ts(s)))   # integer seconds (truncate), same resolution as rq_metrics (d["time"][11:19])
def _ts(s):
    return dt.datetime.strptime(s[:26].rstrip("Z")[:26],"%Y-%m-%dT%H:%M:%S.%f").replace(tzinfo=dt.timezone.utc).timestamp() if "." in s[:26] else dt.datetime.strptime(s[:19],"%Y-%m-%dT%H:%M:%S").replace(tzinfo=dt.timezone.utc).timestamp()
def load(run):
    rows=[]
    for line in open(f"{P}/v7{run}_daemon.log"):
        if '"time"' not in line: continue
        try: d=json.loads(line)
        except Exception: continue
        rows.append(d)
    return rows
def window(rows):
    en=None; dis=None
    for i,d in enumerate(rows):
        if d.get("msg")=="autoscale toggled" and d.get("enabled") is True: en=i; dis=None
        elif d.get("msg")=="autoscale toggled" and d.get("enabled") is False and en is not None and dis is None: dis=i
    assert en is not None
    return en,(dis if dis is not None else len(rows))
EXACT={"hbo deploy_vyos":"vy_create","hbo delete_vyos":"vy_delete","hbo create_worker":"wk_create","hbo delete_worker":"wk_delete",
       "hbo scale_out_up (eupf)":"slot_start","hbo scale_in_up (eupf)":"slot_stop","drain: plan":"drains","v6 emergency force":"emergency"}
LAYER={"vy_create":("vyos",1),"vy_delete":("vyos",-1),"wk_create":("worker",1),"wk_delete":("worker",-1),"slot_start":("eupf",1),"slot_stop":("eupf",-1)}
COLS=["vy_create","vy_delete","wk_create","wk_delete","slot_start","slot_stop","slot_stop_cancelled","drains","drain_moves","relief_moves","hotslot_moves","emergency"]
def analyse(run):
    rows=load(run); a,b=window(rows); t_en=ts(rows[a]["time"]); t_dis=ts(rows[b]["time"]) if b<len(rows) else ts(rows[-1]["time"])
    c=collections.Counter(); ev=[]; other=collections.Counter()
    for d in rows[a:b]:
        m=d.get("msg","")
        if m in EXACT:
            k=EXACT[m]; c[k]+=1
            if k in LAYER: ev.append((ts(d["time"]),)+LAYER[k]+(d.get("slot") or d.get("name"),))
            if k=="drains": c["drain_moves"]+=len(re.findall(r"\{",d.get("moves","")))
        elif m=="hbo scale_in_up (eupf) cancelled: slot retained (reversible scale-in)": c["slot_stop_cancelled"]+=1
        elif m=="v6 pool relief": c["relief_moves"]+=int(d.get("moves",0)); c["relief_calls"]+=1
        elif m=="v6 hot slot relief": c["hotslot_moves"]+=int(d.get("moves",0))
        elif m.startswith("hbo ") or m.startswith("drain") or m.startswith("v6 emergency"): other[m]+=1
    ev.sort()
    # flaps (rq_metrics definition, 10-min = 600 s)
    flaps=0; flap_pairs=[]
    for i,(t,l,dr,_) in enumerate(ev):
        for j in range(i+1,len(ev)):
            t2,l2,d2,_=ev[j]
            if l2==l and t2-t<=600 and d2==-dr: flaps+=1; flap_pairs.append((i,j)); break
    # lock-expiry scale-ins on slot layer
    lock_idx=set(); rel_idx=set(); lock_same=0
    for i,(t,l,dr,sl) in enumerate(ev):
        if l!="eupf" or dr!=-1: continue
        prev=[ev[j][0] for j in range(i) if ev[j][1]=="eupf" and ev[j][2]==1]
        if not prev: continue
        gap=t-prev[-1]
        nxt=[ev[j][0] for j in range(i+1,len(ev)) if ev[j][1]=="eupf" and ev[j][2]==1 and ev[j][0]-t<=600]
        if 300<=gap<=360: rel_idx.add(i)
        if 300<=gap<=360 and nxt: lock_idx.add(i)
        prev_same=[ev[j][0] for j in range(i) if ev[j][1]=="eupf" and ev[j][2]==1 and ev[j][3]==sl]
        if prev_same and 300<=t-prev_same[-1]<=360 and nxt: lock_same+=1
    slot_flaps=sum(1 for i,j in flap_pairs if ev[i][1]=="eupf")
    lock_flaps=sum(1 for i,j in flap_pairs if i in lock_idx or j in lock_idx)
    lock_in_flaps=sum(1 for i,j in flap_pairs if i in lock_idx)       # the in->out half
    rel_out_in=sum(1 for i,j in flap_pairs if j in rel_idx)            # out->in half where the scale-in is a 300-360 s release (refilled or not)
    rel_any=sum(1 for i,j in flap_pairs if j in rel_idx or i in rel_idx)
    gaps=[]  # all slot scale-in gaps for diagnostics
    for i,(t,l,dr,_) in enumerate(ev):
        if l=="eupf" and dr==-1:
            prev=[ev[j][0] for j in range(i) if ev[j][1]=="eupf" and ev[j][2]==1]
            if prev: gaps.append(round(t-prev[-1]))
    return dict(run=run,win_s=round(t_dis-t_en),counts=c,ev=ev,flaps=flaps,slot_flaps=slot_flaps,lock_in=len(lock_idx),lock_rel=len(rel_idx),lock_same=lock_same,rel_out_in=rel_out_in,rel_any=rel_any,lock_flaps=lock_flaps,lock_in_flaps=lock_in_flaps,gaps=gaps,other=other,t_en=t_en,t_dis=t_dis,rows=rows)
# ---- rq_metrics replica (its parsing rules + its t0 window) for cross-check
ACT=dict(deploy_vyos=("vyos",+1),delete_vyos=("vyos",-1),create_worker=("worker",+1),delete_worker=("worker",-1))
def t0_of(run):
    for line in open(f"{P}/trace_v7_{run}.log"):
        m=re.match(r"\[(\d\d):(\d\d):(\d\d)\] start:", line)
        if m: return ((int(m[1])-8)%24)*3600+int(m[2])*60+int(m[3])
def rq_flaps(rows,run,exact=False,win=None):
    t0=t0_of(run); ev=[]
    for d in rows:
        if win is not None and not (win[0]<=ts(d["time"])<=win[1]): continue
        hh,mm,ss=d["time"][11:19].split(":"); t=int(hh)*3600+int(mm)*60+int(ss)-t0; t=((t+43200)%86400)-43200
        if t<0 or t>3600: continue
        msg=d.get("msg","")
        if exact:
            if msg in EXACT and EXACT[msg] in LAYER: ev.append((t/60,)+LAYER[EXACT[msg]])
        elif msg.startswith("hbo "):
            k=msg[4:].split(" ")[0]
            if k in ACT: ev.append((t/60,)+ACT[k])
            elif k=="scale_out_up" and "rejected" not in msg and "worker" not in msg: ev.append((t/60,"eupf",+1))
            elif k=="scale_in_up" and "failed" not in msg: ev.append((t/60,"eupf",-1))
    flaps=0; evs=sorted(ev)
    for i,(t,l,dr) in enumerate(evs):
        for t2,l2,d2 in evs[i+1:]:
            if l2==l and t2-t<=10 and d2==-dr: flaps+=1; break
    return flaps,evs
rq={}
for r in csv.DictReader(open("/home/user/experiment/paper_out_new/rq/rq_metrics.csv")):
    if r["group"].startswith("MAIN"): rq[r["run"]]=int(r["flaps"])
# ---- run everything
res={}
for run in valid+confirm:
    R=analyse(run); R["rq_csv"]=rq.get(run); R["rq_replica"],R["rq_ev"]=rq_flaps(R["rows"],run); R["rqparse_scoredwin"],_=rq_flaps(R["rows"],run,win=(R["t_en"],R["t_dis"])); R["exact_rqwin"],_=rq_flaps(R["rows"],run,exact=True); res[run]=R
# per-run csv
with open(f"{OUT}/ops_per_run.csv","w",newline="") as fh:
    w=csv.writer(fh); w.writerow(["run","trace","arm","role","scored_window_s"]+COLS+["relief_calls","flaps","slot_flaps","slot_scalein_300_360s","lock_expiry_scale_in","lock_expiry_same_slot","flaps_lock_attrib","flaps_lock_in_half","flaps_release_out_in_half","flaps_release_any","flaps_rq_csv","flaps_rq_replica","flaps_rqparse_scoredwin","flaps_exact_rqwin","slot_scalein_gaps_s"])
    for run in valid+confirm:
        R=res[run]; block,arm,_=led[run]; c=R["counts"]
        w.writerow([run,block,ARM[arm],"confirm" if run in confirm else "valid",R["win_s"]]+[c[k] for k in COLS]+[c["relief_calls"],R["flaps"],R["slot_flaps"],R["lock_rel"],R["lock_in"],R["lock_same"],R["lock_flaps"],R["lock_in_flaps"],R["rel_out_in"],R["rel_any"],R["rq_csv"],R["rq_replica"],R["rqparse_scoredwin"],R["exact_rqwin"]," ".join(map(str,R["gaps"]))])
# group table
def fmt(vals):
    if not vals: return "–"
    m=statistics.mean(vals); return f"{m:.1f} ({min(vals)}–{max(vals)})" if (min(vals)!=max(vals)) else f"{m:.1f}"
groups=collections.defaultdict(list)
for run in valid: block,arm,_=led[run]; groups[(ARM[arm],block)].append(run)
LAB={"slot_stop_cancelled":"reversible scale-in cancelled (slot retained)","drain_moves":"drain UE moves","vy_create":"VyOS create","vy_delete":"VyOS delete","wk_create":"worker create","wk_delete":"worker delete","slot_start":"slot start","slot_stop":"slot stop","drains":"drain plans","relief_moves":"relief UE moves (pool)","hotslot_moves":"hot-slot relief UE moves","emergency":"emergency firings"}
md=[]
md.append("# Ops-cost table (§4.99 D) — per scored hour, mean (min–max) over runs\n")
md.append("Scored segment = last `autoscale toggled enabled=true` → next `enabled=false` (or EOF). Counters are exact-msg matches: `hbo deploy_vyos`, `hbo delete_vyos`, `hbo create_worker`, `hbo delete_worker`, `hbo scale_out_up (eupf)`, `hbo scale_in_up (eupf)`, `drain: plan`, Σ`moves` of `v6 pool relief` (and, separately, Σ`moves` of `v6 hot slot relief`), `v6 emergency force`. No PFCP re-association log line exists in any daemon log (grep -i assoc|pfcp = 0 lines), so that column is omitted.\n")
hdr="| arm | trace | n | "+" | ".join(LAB[k] for k in COLS)+" | flaps |"
md.append(hdr); md.append("|"+"---|"*(hdr.count("|")-1))
for arm in ARMORD:
    for tr in TRORD:
        runs=groups.get((arm,tr))
        if not runs: continue
        cells=[fmt([res[r]["counts"][k] for r in runs]) for k in COLS]+[fmt([res[r]["flaps"] for r in runs])]
        md.append(f"| {arm} | {tr} | {len(runs)} | "+" | ".join(cells)+" |")
# all-trace pooled per arm
md.append("\n## Pooled over traces (per arm, mean (min–max) per run)\n")
md.append(hdr); md.append("|"+"---|"*(hdr.count("|")-1))
for arm in ARMORD:
    runs=[r for (a,t),rs in groups.items() if a==arm for r in rs]
    cells=[fmt([res[r]["counts"][k] for r in runs]) for k in COLS]+[fmt([res[r]["flaps"] for r in runs])]
    md.append(f"| {arm} | all | {len(runs)} | "+" | ".join(cells)+" |")
md.append("\n## v6 confirmation run (reported separately)\n")
md.append(hdr); md.append("|"+"---|"*(hdr.count("|")-1))
for run in confirm:
    block,arm,_=led[run]; c=res[run]["counts"]
    md.append(f"| {ARM[arm]} ({run} confirm) | {block} | 1 | "+" | ".join(str(c[k]) for k in COLS)+f" | {res[run]['flaps']} |")
open(f"{OUT}/ops_table.md","w").write("\n".join(md)+"\n")
# flap decomposition
fd=[]; fd.append("| arm | trace | n | flaps total (mean, Σ) | slot-layer flaps (Σ) | slot scale-ins 300–360 s after prior slot scale-out (Σ) | …of which re-scale-out ≤10 min = lock-expiry type (Σ) | same-slot variant (Σ) | flaps attributable to lock-expiry episodes (Σ) | of which in→out half (Σ) | flaps involving any 300–360 s release (refilled or not) (Σ) | flaps as published in rq_metrics.csv (mean, Σ) |")
fd.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
for arm in ["S4a","S4b","v6"]:
    for tr in TRORD:
        runs=groups.get((arm,tr))
        if not runs: continue
        F=[res[r]["flaps"] for r in runs]
        Q=[res[r]['rq_csv'] for r in runs]
        fd.append(f"| {arm} | {tr} | {len(runs)} | {statistics.mean(F):.1f}, {sum(F)} | {sum(res[r]['slot_flaps'] for r in runs)} | {sum(res[r]['lock_rel'] for r in runs)} | {sum(res[r]['lock_in'] for r in runs)} | {sum(res[r]['lock_same'] for r in runs)} | {sum(res[r]['lock_flaps'] for r in runs)} | {sum(res[r]['lock_in_flaps'] for r in runs)} | {sum(res[r]['rel_any'] for r in runs)} | {statistics.mean(Q):.1f}, {sum(Q)} |")
    runs=[r for (a,t),rs in groups.items() if a==arm for r in rs]; F=[res[r]["flaps"] for r in runs]
    Q=[res[r]['rq_csv'] for r in runs]
    fd.append(f"| **{arm}** | **all** | {len(runs)} | {statistics.mean(F):.1f}, {sum(F)} | {sum(res[r]['slot_flaps'] for r in runs)} | {sum(res[r]['lock_rel'] for r in runs)} | {sum(res[r]['lock_in'] for r in runs)} | {sum(res[r]['lock_same'] for r in runs)} | {sum(res[r]['lock_flaps'] for r in runs)} | {sum(res[r]['lock_in_flaps'] for r in runs)} | {sum(res[r]['rel_any'] for r in runs)} | {statistics.mean(Q):.1f}, {sum(Q)} |")
# cross-check
xc=[]; xc.append("| run | arm | trace | flaps (this: exact msgs, scored window) | rq_metrics.csv | replica (rq parsing, trace-t0 window) | rq parsing, scored window | exact msgs, trace-t0 window | cancelled reversible scale-ins in run |"); xc.append("|---|---|---|---|---|---|---|---|---|")
mism=0
for run in valid+confirm:
    R=res[run]; block,arm,_=led[run]
    if R["rq_csv"]!=R["flaps"]:
        mism+=1; xc.append(f"| {run} | {ARM[arm]} | {block} | {R['flaps']} | {R['rq_csv']} | {R['rq_replica']} | {R['rqparse_scoredwin']} | {R['exact_rqwin']} | {R['counts']['slot_stop_cancelled']} |")
print("valid",len(valid),"confirm",confirm,"mismatch",mism)
print("\n".join(md)); print("\nFLAP DECOMP"); print("\n".join(fd)); print("\nMISMATCH"); print("\n".join(xc))
print("\nOTHER MSGS (in window, all valid runs):")
oth=collections.Counter()
for run in valid: oth.update(res[run]["other"])
for k,v in sorted(oth.items()): print(v,k)
print("\nwindow lengths:",sorted(res[r]["win_s"] for r in valid)[:3],sorted(res[r]["win_s"] for r in valid)[-3:])
json.dump({r:dict(flaps=res[r]["flaps"],rq=res[r]["rq_csv"],rep=res[r]["rq_replica"],ev=[(round(t-res[r]["t_en"]),l,d,sl) for t,l,d,sl in res[r]["ev"]],rq_ev=[(round(t*60),l,d) for t,l,d in res[r]["rq_ev"]],gaps=res[r]["gaps"],lock_in=res[r]["lock_in"]) for r in valid+confirm},open("events.json","w"),indent=0)
open("flap_decomp.md","w").write("\n".join(fd)+"\n"); open("xcheck.md","w").write("\n".join(xc)+"\n")
