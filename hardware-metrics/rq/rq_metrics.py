#!/usr/bin/env python3
"""(docstring removed)"""
import csv, json, math, re, sys, os, datetime as dt
E="/home/user/experiment"; P=f"{E}/p2"
PER_UE=250_000; CAP_VY=4.45e6*0.93; CAP_UP=1.35e6*0.93; STEP=5
FLEET_MAX=dict(vyos=3, worker=4, eupf=8)
W=dict(worker=3.0, vyos=2.0, eupf=0.8)
def slots_for(ue): return max(1, math.ceil(ue/math.floor(CAP_UP/PER_UE)))
def vy_for(ue): return max(1, math.ceil(ue*PER_UE/CAP_VY))
def bounds(ue):
    cap=dict(vyos=vy_for(ue), eupf=slots_for(ue)); cap["worker"]=math.ceil(cap["eupf"]/2)
    fl=dict(vyos=vy_for(ue+STEP), eupf=slots_for(ue+STEP)); fl["worker"]=math.ceil(fl["eupf"]/2)
    return {k:min(FLEET_MAX[k],v) for k,v in cap.items()}, {k:min(FLEET_MAX[k],v) for k,v in fl.items()}
def f(s,d=0.0):
    try: return float(s)
    except: return d
def clamp(v,hi): return 0.0 if v<0 else (hi if v>hi else v)
def t0_of(run):
    for line in open(f"{P}/trace_v7_{run}.log"):
        m=re.match(r"\[(\d\d):(\d\d):(\d\d)\] start:", line)
        if m: return ((int(m[1])-8)%24)*3600+int(m[2])*60+int(m[3])
    raise SystemExit(run)
ACT=dict(deploy_vyos=("vyos",+1),delete_vyos=("vyos",-1),create_worker=("worker",+1),delete_worker=("worker",-1))
def daemon(run):
    """(docstring removed)"""
    t0=t0_of(run); rep={}; ev=[]
    for line in open(f"{P}/v7{run}_daemon.log"):
        if '"time"' not in line: continue
        try: d=json.loads(line)
        except: continue
        hh,mm,ss=d["time"][11:19].split(":"); t=int(hh)*3600+int(mm)*60+int(ss)-t0
        t=((t+43200)%86400)-43200
        if t<0 or t>3600: continue
        msg=d.get("msg","")
        if msg=="mid": rep.setdefault(int(t//60),[]).append(d["up_rep"])
        elif msg.startswith("hbo "):
            k=msg[4:].split(" ")[0]
            if k in ACT: ev.append((t/60,)+ACT[k])
            elif k=="scale_out_up" and "rejected" not in msg and "worker" not in msg: ev.append((t/60,"eupf",+1))
            elif k=="scale_in_up" and "failed" not in msg: ev.append((t/60,"eupf",-1))
    eupf=[ (sum(rep[m])/len(rep[m]) if m in rep else None) for m in range(60)]
    last=None
    for i,v in enumerate(eupf):
        if v is None: eupf[i]=last if last is not None else 2
        else: last=v
    return eupf, ev

def alloc_vm_of(run, eupf):
    """(docstring removed)"""
    import collections, datetime as dt
    try:
        rows=[(int(r['ts']),r['vm']) for r in csv.DictReader(open(f"{P}/host_vmcpu_v7{run}.csv")) if r.get('ts','').isdigit()]
    except FileNotFoundError: return None
    if not rows: return None
    ends={}
    for line in open(f"{P}/trace_v7_{run}.log"):
        m=re.match(r"\[(\d\d):(\d\d):(\d\d)\] min(\d+): target=",line)
        if m: ends[int(m.group(4))]=(int(m.group(1)),int(m.group(2)),int(m.group(3)))
    tz=dt.timezone(dt.timedelta(hours=8)); d0=dt.datetime.fromtimestamp(rows[0][0],tz).replace(hour=0,minute=0,second=0,microsecond=0)
    byts=collections.defaultdict(set)
    for ts,vm in rows: byts[ts].add(vm)
    wk=[];vy=[];last=(0,0)
    for mi in range(60):
        if mi not in ends: wk.append(last[0]); vy.append(last[1]); continue
        h,m_,s_=ends[mi]; t=d0.replace(hour=h,minute=m_,second=s_)
        if t.timestamp()<rows[0][0]-3600: t=t+dt.timedelta(days=1)
        e=int(t.timestamp()); tss=[x for x in byts if e-60<=x<e]
        if not tss: wk.append(last[0]); vy.append(last[1]); continue
        a=sum(sum(1 for v in byts[x] if v.startswith('worker')) for x in tss)/len(tss); b=sum(sum(1 for v in byts[x] if v.startswith('vyos')) for x in tss)/len(tss)
        wk.append(a); vy.append(b); last=(a,b)
    return round(sum(W["worker"]*a+W["vyos"]*b+W["eupf"]*c for a,b,c in zip(wk,vy,eupf)))

def metrics(run, trace):
    tr=json.load(open(f"{E}/{trace}")); UE=tr["ue"][:60]
    rows=list(csv.DictReader(open(f"{P}/trace_v7_{run}.csv")))[:60]
    eupf, ev=daemon(run)
    n=len(rows); ok=[]; streak=0; maxstreak=0; lost=0.0; deliv_ok=0.0; deliv=0.0
    p99s=[]; worst=0.0
    for r in rows:
        loss=f(r["e2e_pct"]); p99=f(r["lat_p99_us"],1e9); off=f(r["offered_pps"])
        good = loss<=0.1 and p99<=1000; ok.append(good)
        streak = 0 if good else streak+1; maxstreak=max(maxstreak,streak)
        lost += loss/100*off*60; deliv += off*60*(1-loss/100)
        if good: deliv_ok += off*60*(1-loss/100)
        if p99<1e9: p99s.append(p99)
        worst=max(worst,loss)
    wk=[int(r["worker_n"]) for r in rows]; vy=[int(r["vyos_n"]) for r in rows]
    alloc=sum(W["worker"]*a+W["vyos"]*b+W["eupf"]*c for a,b,c in zip(wk,vy,eupf))
    alloc_vm=alloc_vm_of(run, eupf)
    if alloc_vm is None: alloc_vm=round(alloc)
    caps=[bounds(u) for u in UE[:n]]
    oracle=sum(W["worker"]*c["worker"]+W["vyos"]*c["vyos"]+W["eupf"]*c["eupf"] for c,_ in caps)
    floor=sum(W["worker"]*c["worker"]+W["vyos"]*c["vyos"]+W["eupf"]*c["eupf"] for _,c in caps)
    hw=sum(sum(clamp(f(r.get('host_w%d'%i,'')),8.0) for i in range(4)) for r in rows)
    hv=sum(clamp(f(r.get('host_vyos_sum','')),12.0) for r in rows)
    # RQ3
    series=dict(worker=wk, vyos=vy, eupf=eupf)
    acts={l:sum(1 for e in ev if e[1]==l) for l in series}
    flaps=0; evs=sorted(ev)
    for i,(t,l,dr) in enumerate(evs):
        for t2,l2,d2 in evs[i+1:]:
            if l2==l and t2-t<=10 and d2==-dr: flaps+=1; break
    under={l:sum(1 for m in range(n) if series[l][m]<caps[m][0][l]) for l in series}
    over={l:sum(1 for m in range(n) if series[l][m]>caps[m][1][l]) for l in series}
    lags=[]
    for l in series:
        for m in range(1,n):
            need=caps[m][0][l]
            if need>caps[m-1][0][l]:
                lag=None
                for k in range(m,n):
                    if series[l][k]>=need: lag=k-m; break
                lags.append(lag if lag is not None else n-m)
    return dict(run=run, trace=trace.replace("trace_ue_60min_v3_","").replace(".json",""),
        slo=sum(ok), worst=round(worst,2), p99max=round(max(p99s)) if p99s else 0, p99avg=round(sum(p99s)/len(p99s)) if p99s else 0,
        maxstreak=maxstreak, lost_Mpkt=round(lost/1e6,2), deliv_Gpkt=round(deliv/1e9,2),
        wk_min=sum(wk), vy_min=sum(vy), slot_min=round(sum(eupf)), alloc=round(alloc), alloc_vm=alloc_vm, oracle=round(oracle), floor=round(floor),
        waste=round(alloc-oracle), waste_pct=round(100*(alloc-oracle)/oracle,1),
        burned=round(hw+hv), burned_wk=round(hw), burned_vy=round(hv),
        eff_Gpkt_per_kcoremin=round(deliv_ok/1e9/((hw+hv)/1000),2),
        acts_vy=acts["vyos"], acts_wk=acts["worker"], acts_up=acts["eupf"], flaps=flaps,
        under_vy=under["vyos"], under_up=under["eupf"], over_vy=over["vyos"], over_up=over["eupf"],
        lag_mean=round(sum(lags)/len(lags),2) if lags else 0)
GROUPS=[("HHRO t1","trace_ue_60min_v3_40.json",["r108","r110","r112","r114","r119"]),
        ("HHRO t2","trace_ue_60min_v3_pm.json",["r107","r109","r115","r117","r118"]),
        ("B1 static t1","trace_ue_60min_v3_40.json",["r147","r154","r155"]),("B1 static t2","trace_ue_60min_v3_pm.json",["r149","r156","r157"]),
        ("B4 DASA+HPA t1","trace_ue_60min_v3_40.json",["r145","r150","r151"]),("B4 DASA+HPA t2","trace_ue_60min_v3_pm.json",["r148","r152","r153"]),
        ("B5 predictive t1","trace_ue_60min_v3_40.json",["r186","r187","r188"]),("B5 predictive t2","trace_ue_60min_v3_pm.json",["r189","r190","r191"]),
        ("B2 DASA-only t1","trace_ue_60min_v3_40.json",["r158","r159","r160"]),("B2 DASA-only t2","trace_ue_60min_v3_pm.json",["r162","r163","r170"]),
        ("B3 HPA-only t1","trace_ue_60min_v3_40.json",["r164","r165","r166"]),("B3 HPA-only t2","trace_ue_60min_v3_pm.json",["r167","r168","r169"]),
        ("HHRO t3","trace_ue_60min_v3_t3.json",["r171","r175","r176"]),("HHRO t3 eq-start(5 slots)","trace_ue_60min_v3_t3.json",["r174"]),("B1 static t3","trace_ue_60min_v3_t3.json",["r173"]),("B4 DASA+HPA t3","trace_ue_60min_v3_t3.json",["r172","r177","r178"]),
        ("HHRO-Q e05 r0 t1","trace_ue_60min_v3_40.json",["r180"]),("HHRO-Q e05 r0 t2","trace_ue_60min_v3_pm.json",["r181"]),
        ("HHRO-Q e10 r0 t1","trace_ue_60min_v3_40.json",["r182"]),("HHRO-Q e10 r0 t2","trace_ue_60min_v3_pm.json",["r183"]),
        ("HHRO-Q e10 r1 t1","trace_ue_60min_v3_40.json",["r184"]),("HHRO-Q e10 r1 t2","trace_ue_60min_v3_pm.json",["r185"]),
        ("HHRO-Q v7.0.4 rho05 t1","trace_ue_60min_v3_40.json",["r192"]),("HHRO-Q v7.0.4 rho05 t2","trace_ue_60min_v3_pm.json",["r193"]),
        ("HHRO-Q v7.0.4 t1","trace_ue_60min_v3_40.json",["r194"]),("HHRO-Q v7.0.4 t2","trace_ue_60min_v3_pm.json",["r195"]),
        ("HHRO-Q v7.0.5 t2","trace_ue_60min_v3_pm.json",["r196"]),("HHRO-Q final t1 (r200)","trace_ue_60min_v3_40.json",["r200"]),("HHRO-Q final t2 (r198)","trace_ue_60min_v3_pm.json",["r198"]),
        ("A1 hold-off t1","trace_ue_60min_v3_40.json",["r129","r130","r131"]),
        ("A2 lead2 t1","trace_ue_60min_v3_40.json",["r120","r121","r122"]),
        ("A3a lambda x4 t1","trace_ue_60min_v3_40.json",["r123","r124","r125"]),("A3b lambda /4 t1","trace_ue_60min_v3_40.json",["r126","r127","r128"]),("A3c lambda x16 t1","trace_ue_60min_v3_40.json",["r135","r136","r137"]),
        ("A4 layered t1","trace_ue_60min_v3_40.json",["r132","r133","r134"]),("A4 layered t2","trace_ue_60min_v3_pm.json",["r141","r142","r143"]),
        ("S1 sigma 1.5/3.5 t1","trace_ue_60min_v3_40.json",["r201","r203","r205"]),("S1 sigma 1.5/3.5 t2","trace_ue_60min_v3_pm.json",["r202","r204","r206"]),
                        ("S2a 0.5% t1","trace_ue_60min_v3_40.json",["r207","r215","r219","r223","r227"]),("S2a 0.5% t2","trace_ue_60min_v3_pm.json",["r208","r216","r220","r224","r228"]),
                        ("HHRO ctrl 10-04 t1","trace_ue_60min_v3_40.json",["r231"]),("HHRO ctrl 10-04 t2","trace_ue_60min_v3_pm.json",["r232"]),
        ("HHRO ctrl restored t1","trace_ue_60min_v3_40.json",["r233"]),("HHRO ctrl restored t2","trace_ue_60min_v3_pm.json",["r234"]),
        ("S2a 0.5% restored-extra t1","trace_ue_60min_v3_40.json",["r235"]),("S2a 0.5% restored-extra t2","trace_ue_60min_v3_pm.json",["r236"]),("S2b 2% restored-extra t1","trace_ue_60min_v3_40.json",["r237"]),("S2b 2% restored-extra t2","trace_ue_60min_v3_pm.json",["r238"]),
        ("S3a 0.5% final t1","trace_ue_60min_v3_40.json",["r239","r245"]),("S3a 0.5% final t2","trace_ue_60min_v3_pm.json",["r240","r246"]),
        ("S3b 2% final t1","trace_ue_60min_v3_40.json",["r241"]),("S3b 2% final t2","trace_ue_60min_v3_pm.json",["r242"]),
        ("HHRO ctrl final t1","trace_ue_60min_v3_40.json",["r243"]),("HHRO ctrl final t2","trace_ue_60min_v3_pm.json",["r244"]),

        ("HHRO ctrl G2b t1","trace_ue_60min_v3_40.json",["r247","r257"]),("HHRO ctrl G2b t2","trace_ue_60min_v3_pm.json",["r248","r258"]),
        ("S4a 0.5% G2b t1","trace_ue_60min_v3_40.json",["r249","r253","r259","r263"]),("S4a 0.5% G2b t2","trace_ue_60min_v3_pm.json",["r250","r254","r260"]),
        ("S4b 2% G2b t1","trace_ue_60min_v3_40.json",["r251","r255","r261"]),("S4b 2% G2b t2","trace_ue_60min_v3_pm.json",["r252","r256","r262"]),
        ("HHRO ctrl G2c t1 (post-fix v9)","trace_ue_60min_v3_40.json",["r267","r268"]),("S4a 0.5% G2c t1 (post-fix v9)","trace_ue_60min_v3_40.json",["r264","r265","r266"]),
        ("B4 DASA+HPA G2d t1 (post-fix v9)","trace_ue_60min_v3_40.json",["r269"]),("B5 predictive G2d t1 (post-fix v9)","trace_ue_60min_v3_40.json",["r270"]),
        ("B4c1 SLO-tune 4.0/14 t1","trace_ue_60min_v3_40.json",["r271"]),("B4c2 SLO-tune 3.5/12 t1","trace_ue_60min_v3_40.json",["r272"]),("B4c3 SLO-tune 3.0/11 t1","trace_ue_60min_v3_40.json",["r273"]),("B5c1 SLO-tune 4.0/14 t1","trace_ue_60min_v3_40.json",["r274"]),("B5c2 SLO-tune 3.5/12 t1","trace_ue_60min_v3_40.json",["r275"]),
        ("B4c2 SLO-tune t2 (reverify)","trace_ue_60min_v3_pm.json",["r276"]),("B4c3 SLO-tune t2 VOID r277 (CP rule)","trace_ue_60min_v3_pm.json",["r277"]),("B5c1 SLO-tune t2 (reverify)","trace_ue_60min_v3_pm.json",["r278"]),("B6 Toka u=0.78 t1 (q7)","trace_ue_60min_v3_40.json",["r279"]),("B6 Toka u=0.85 t1 VOID r280 (worker-4)","trace_ue_60min_v3_40.json",["r280"]),("B4c3 SLO-tune t2 (rerun)","trace_ue_60min_v3_pm.json",["r281"]),("B6 Toka u=0.85 t1 VOID r282 (q8, same race)","trace_ue_60min_v3_40.json",["r282"]),("B6 Toka u=0.85 t1 (q9)","trace_ue_60min_v3_40.json",["r283"]),("B6 Toka u=0.78 t1 (q9)","trace_ue_60min_v3_40.json",["r284"]),("B6 Toka u=0.70 t1 (q9)","trace_ue_60min_v3_40.json",["r285"]),("B6 Toka u=0.70 t2 (q9)","trace_ue_60min_v3_pm.json",["r286"]),("B5c1 SLO-tune t2 (extra, clean start)","trace_ue_60min_v3_pm.json",["r287"]),
        # ---- main experiment t4 block (10-09/10; ids per main_exp_ledger.tsv) ----

        ("MAIN t4 S4a","trace_ue_60min_v3_t4.json",["r502","r312","r317"]),("MAIN t4 S4a VOID r300 (drain-residue rule K4; VY-layer cause; replaced by r502)","trace_ue_60min_v3_t4.json",["r300"]),("MAIN t4 v6","trace_ue_60min_v3_t4.json",["r301","r318","r321"]),("MAIN t4 v6 VOID r307 (compute overlap)","trace_ue_60min_v3_t4.json",["r307"]),
        ("MAIN t4 B4c2","trace_ue_60min_v3_t4.json",["r308","r313","r320"]),("MAIN t4 B4c2 r302 (start transient; replaced by r320)","trace_ue_60min_v3_t4.json",["r302"]),
        ("MAIN t4 S4b","trace_ue_60min_v3_t4.json",["r303","r314","r322"]),("MAIN t4 S4b VOID r309 (harness gNB-8; rerun r322)","trace_ue_60min_v3_t4.json",["r309"]),
        ("MAIN t4 B5c1 (q11)","trace_ue_60min_v3_t4.json",["r310","r315","r319"]),("MAIN t4 B5c1 VOID r304 (q6 crash)","trace_ue_60min_v3_t4.json",["r304"]),
        ("MAIN t4 B6 u=0.70","trace_ue_60min_v3_t4.json",["r305","r311"]),("MAIN t4 B6 VOID r316 (session audit median +8; no replacement)","trace_ue_60min_v3_t4.json",["r316"]),("MAIN t4 B1","trace_ue_60min_v3_t4.json",["r306"]),
        # ---- main experiment t5 block (10-11; round 1 only per round 29) ----
        ("MAIN t4 v6 confirm post-IRQ","trace_ue_60min_v3_t4.json",["r381"]),
        # ---- main experiment t3 block (10-12/13; 3 rounds; actual rotation per main_exp_ledger.tsv: round 3 = r373 B4c2, r374 S4b, r375 B5c1, r376 B6, r377 S4a, r378 v6; r379 = B4c2 retry (r368 void: TRex crash), r380 = B5c1 replacement (r370 void: gNB-8 NG)) ----
        ("MAIN t3 S4a","trace_ue_60min_v3_t3.json",["r360","r372","r377"]),("MAIN t3 v6","trace_ue_60min_v3_t3.json",["r361","r367","r378"]),
        ("MAIN t3 B4c2","trace_ue_60min_v3_t3.json",["r362","r373","r382"]),("MAIN t3 B4c2 VOID r368 (TRex crash, no finish)","trace_ue_60min_v3_t3.json",["r368"]),("MAIN t3 B4c2 VOID r379 (network outage; rerun r382)","trace_ue_60min_v3_t3.json",["r379"]),
        ("MAIN t3 S4b","trace_ue_60min_v3_t3.json",["r363","r369","r374"]),
        ("MAIN t3 B5c1 (q11)","trace_ue_60min_v3_t3.json",["r364","r375","r380"]),("MAIN t3 B5c1 VOID r370 (harness gNB-8 NG; replaced by r380)","trace_ue_60min_v3_t3.json",["r370"]),
        ("MAIN t3 B6 u=0.70","trace_ue_60min_v3_t3.json",["r365","r371","r503"]),("MAIN t3 B6 VOID r383 (drain-residue rule; replaced by r503)","trace_ue_60min_v3_t3.json",["r383"]),("MAIN t3 B6 VOID r376 (formal NG events; replaced by r383)","trace_ue_60min_v3_t3.json",["r376"]),("MAIN t3 B1","trace_ue_60min_v3_t3.json",["r366"]),
        ("B2 DASA-only t1 (post-IRQ)","trace_ue_60min_v3_40.json",["r390","r391","r392"]),("B2 DASA-only t2 (post-IRQ)","trace_ue_60min_v3_pm.json",["r393","r394","r395"]),
        ("B3 HPA-only t1 (post-IRQ)","trace_ue_60min_v3_40.json",["r396","r397","r398"]),("B3 HPA-only t2 (post-IRQ)","trace_ue_60min_v3_pm.json",["r399","r400","r401"]),
        ("MAIN t5 S4a","trace_ue_60min_v3_t5.json",["r330"]),("MAIN t5 v6","trace_ue_60min_v3_t5.json",["r331"]),("MAIN t5 B4c2","trace_ue_60min_v3_t5.json",["r332"]),
        # ---- main experiment t6 block (10-15/16; 3 rounds, rotation per main_exp_ledger.tsv; warm-in interventions in r407/r413/r417/r418 warm-ins only, formal segments clean; see spec §4.79-4.82)
        ("MAIN t6 S4a","trace_ue_60min_v3_t6.json",["r402","r414","r419"]),("MAIN t6 v6","trace_ue_60min_v3_t6.json",["r403","r409","r420"]),
        ("MAIN t6 B4c2","trace_ue_60min_v3_t6.json",["r404","r410","r415"]),("MAIN t6 S4b","trace_ue_60min_v3_t6.json",["r405","r411","r416"]),
        ("MAIN t6 B5c1 (q11)","trace_ue_60min_v3_t6.json",["r406","r412","r417"]),("MAIN t6 B6 u=0.70","trace_ue_60min_v3_t6.json",["r413","r418"]),("MAIN t6 B6 VOID r407 (session audit median +18; no replacement)","trace_ue_60min_v3_t6.json",["r407"]),
        ("MAIN t6 B1","trace_ue_60min_v3_t6.json",["r408"]),
        # ---- main experiment t7 block (10-16/17; 3 rounds; warm-in interventions in baseline/v6 warm-ins only, formal segments clean; see spec §4.83-4.86)
        ("MAIN t7 S4a","trace_ue_60min_v3_t7.json",["r430","r442","r447"]),("MAIN t7 v6","trace_ue_60min_v3_t7.json",["r431","r437","r448"]),
        ("MAIN t7 B4c2","trace_ue_60min_v3_t7.json",["r432","r438","r443"]),("MAIN t7 S4b","trace_ue_60min_v3_t7.json",["r433","r439","r444"]),
        ("MAIN t7 B5c1 (q11)","trace_ue_60min_v3_t7.json",["r434","r440","r445"]),("MAIN t7 B6 u=0.70","trace_ue_60min_v3_t7.json",["r435","r441","r446"]),
        ("MAIN t7 B1","trace_ue_60min_v3_t7.json",["r436"]),
        ("MAIN t5 S4b","trace_ue_60min_v3_t5.json",["r333"]),("MAIN t5 B5c1 (q11)","trace_ue_60min_v3_t5.json",["r334"]),("MAIN t5 B6 u=0.70","trace_ue_60min_v3_t5.json",["r335"]),("MAIN t5 B1","trace_ue_60min_v3_t5.json",["r336"]),
        # ---- r72hw (10-28..31, spec §4.140): S4′ (image 6.0-s4p) C block + t11/t12 generalisation D block (A-group baselines); r566/r567 harness-fault → r580/r581
        ("R72 t4 S4p2","trace_ue_60min_v3_t4.json",["r532","r533","r536"]),("R72 t4 S4p05","trace_ue_60min_v3_t4.json",["r541","r544","r546"]),
        ("R72 t6 S4p2","trace_ue_60min_v3_t6.json",["r531","r538","r539"]),("R72 t6 S4p05","trace_ue_60min_v3_t6.json",["r530","r537","r540"]),
        ("R72 t8 S4p2","trace_ue_60min_v3_t8.json",["r534","r535","r547"]),("R72 t8 S4p05","trace_ue_60min_v3_t8.json",["r542","r543","r545"]),
        ("R72 t11 S4p2","trace_ue_60min_v3_t11.json",["r562","r564"]),("R72 t11 S4b","trace_ue_60min_v3_t11.json",["r569","r577"]),("R72 t11 A:B4 3.75/300","trace_ue_60min_v3_t11.json",["r561","r568"]),("R72 t11 A:B5 4.0/L2","trace_ue_60min_v3_t11.json",["r563","r573"]),("R72 t11 A:B6 0.775","trace_ue_60min_v3_t11.json",["r574","r580"]),("R72 t11 A:B6 VOID r566 (TRex died in warm-in; replaced by r580)","trace_ue_60min_v3_t11.json",["r566"]),
        ("R72 t12 S4p2","trace_ue_60min_v3_t12.json",["r570","r575"]),("R72 t12 S4b","trace_ue_60min_v3_t12.json",["r572","r579"]),("R72 t12 A:B4 3.75/300","trace_ue_60min_v3_t12.json",["r571","r576"]),("R72 t12 A:B5 4.0/L2","trace_ue_60min_v3_t12.json",["r560","r565"]),("R72 t12 A:B6 0.775","trace_ue_60min_v3_t12.json",["r578","r581"]),("R72 t12 A:B6 VOID r567 (chain abort after r566; replaced by r581)","trace_ue_60min_v3_t12.json",["r567"]),
        # ---- r73fill (10-31..11-02, spec §4.141): planner t3/t5/t7 + same-target B4 3.75/300, B6 0.775 on t4/t8; r585 (ng-dead) → r604, r591 (chain-abort in warm-in) → r605
        ("R73 t3 S4p2","trace_ue_60min_v3_t3.json",["r584","r589","r596"]),("R73 t3 S4p05","trace_ue_60min_v3_t3.json",["r590","r598","r600"]),
        ("R73 t5 S4p2","trace_ue_60min_v3_t5.json",["r582"]),("R73 t5 S4p05","trace_ue_60min_v3_t5.json",["r593"]),
        ("R73 t7 S4p2","trace_ue_60min_v3_t7.json",["r586","r599","r605"]),("R73 t7 S4p05","trace_ue_60min_v3_t7.json",["r583","r594","r601"]),
        ("R73 t4 A:B4 3.75/300","trace_ue_60min_v3_t4.json",["r597","r602"]),("R73 t4 A:B6 0.775","trace_ue_60min_v3_t4.json",["r587","r603"]),
        ("R73 t8 A:B4 3.75/300","trace_ue_60min_v3_t8.json",["r592","r604"]),("R73 t8 A:B6 0.775","trace_ue_60min_v3_t8.json",["r588","r595"]),
        ("R73 t8 A:B4 VOID r585 (ng-dead; replaced by r604)","trace_ue_60min_v3_t8.json",["r585"]),
        ("S2b 2% t1","trace_ue_60min_v3_40.json",["r212","r217","r221","r225","r229"]),("S2b 2% t2","trace_ue_60min_v3_pm.json",["r214","r218","r222","r226","r230"])]
out=[]
for g,tr,runs in GROUPS:
    for r in runs:
        try: m=metrics(r,tr); m["group"]=g; out.append(m)
        except Exception as e: print("skip",r,e, file=sys.stderr)
keys=["group","run","slo","worst","p99max","p99avg","maxstreak","lost_Mpkt","deliv_Gpkt","wk_min","vy_min","slot_min","alloc","alloc_vm","oracle","floor","waste","waste_pct","burned","burned_wk","burned_vy","eff_Gpkt_per_kcoremin","acts_vy","acts_wk","acts_up","flaps","under_vy","under_up","over_vy","over_up","lag_mean"]
os.makedirs(f"{E}/paper_out_new/rq",exist_ok=True)
with open(f"{E}/paper_out_new/rq/rq_metrics.csv","w") as fh:
    w=csv.DictWriter(fh,fieldnames=keys); w.writeheader(); [w.writerow({k:m[k] for k in keys}) for m in out]
# group means
import statistics as st
def mean(xs): return st.mean(xs) if xs else 0
lines=["| group | n | SLO/60 | worst% | p99max | maxstreak | lost Mpkt | alloc | oracle | floor | waste% | burned | eff Gpkt/kcore-min | acts vy/wk/up | flaps | under vy/up | over vy/up | lag |","|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
for g,_,_ in GROUPS:
    ms=[m for m in out if m["group"]==g]
    if not ms: continue
    a=lambda k: mean([m[k] for m in ms])
    lines.append(f"| {g} | {len(ms)} | {a('slo'):.1f} | {a('worst'):.2f} | {a('p99max'):.0f} | {a('maxstreak'):.1f} | {a('lost_Mpkt'):.2f} | {a('alloc'):.0f} | {a('oracle'):.0f} | {a('floor'):.0f} | {a('waste_pct'):.1f} | {a('burned'):.0f} | {a('eff_Gpkt_per_kcoremin'):.2f} | {a('acts_vy'):.1f}/{a('acts_wk'):.1f}/{a('acts_up'):.1f} | {a('flaps'):.1f} | {a('under_vy'):.1f}/{a('under_up'):.1f} | {a('over_vy'):.1f}/{a('over_up'):.1f} | {a('lag_mean'):.2f} |")
open(f"{E}/paper_out_new/rq/rq_metrics.md","w").write("\n".join(lines)+"\n\nper-run: rq_metrics.csv\n")
print("\n".join(lines))
