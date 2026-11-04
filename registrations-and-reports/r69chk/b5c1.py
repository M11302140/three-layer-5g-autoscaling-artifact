#!/usr/bin/env python3
"""spec §4.137 item 2: B5c1 (4.0 / L2) per-minute fleet, hardware t6 (r406/r412/r417) and t7 (r434/r440/r445) against per-slot v8sim11 R38 off
(r67band runner) from initial_fleet and from the hardware minute-0 fleet. Hardware: trace CSV worker_n / vyos_n / active_ue, slots from
rq_metrics.daemon (kube_pod_info), HPA from daemon log 'baseline hpa'. Output out/b5c1.json, fig_t6_b5c1_trace.pdf, fig_t7_b5c1_trace.pdf"""
import timeit  # noqa
import sys, os, json, csv, io, contextlib, re, math
Q='/home/user/experiment/qsim'; P2='/home/user/experiment/p2'; E='/home/user/experiment'; R=f'{Q}/r69chk'
sys.path.insert(0,Q); sys.path.insert(0,Q+'/r67band'); sys.path.insert(0,'/home/user/experiment/paper_out_new'); os.chdir(Q)
import v8sim11 as V, run as RB
with contextlib.redirect_stdout(io.StringIO()):
    import rq_metrics as RQ
RUNS={"t6":["r406","r412","r417"],"t7":["r434","r440","r445"]}
def hw(run):
    rows=list(csv.DictReader(open(f'{P2}/trace_v7_{run}.csv')))[:60]
    with contextlib.redirect_stdout(io.StringIO()):
        eupf,_=RQ.daemon(run)
    hpa=[]
    for l in open(f'{P2}/v7{run}_daemon.log',errors='replace'):
        if '"baseline hpa"' not in l: continue
        j=json.loads(l); m=re.search(r"cur=(\d+) raw=(\d+) eff=(\d+)",j['reason']); hpa.append(tuple(int(x) for x in m.groups()))
    blocked=sum(1 for c,r,e in hpa if r<c and e==c)
    return dict(ue=[int(x['active_ue']) for x in rows],wk=[int(x['worker_n']) for x in rows],vy=[int(x['vyos_n']) for x in rows],slot=[float(x) for x in eupf[:60]],
                hpa_ticks=len(hpa),hpa_blocked=blocked,hpa_raw_below=sum(1 for c,r,e in hpa if r<c))
def sim(ue,start=None):
    cfg,_=V.cfg_prior(); T,x=4.0,"L2"; mu=RB.mu_of("B5",T)
    ctl=V.CtlB4(predictive=True,mu=mu,target=T,tol=0.05,down=600,margin=0.8,lead=RB.LEADS[x]); st=start or V.initial_fleet("B4",ue[0],target=T,mu=mu)
    rec=dict(hpa=[]); orig=ctl.hpa.step
    def step(now,cur,avg):
        c=max(1,cur); ratio=avg/ctl.hpa.target; raw=c
        if abs(ratio-1)>ctl.hpa.tol: raw=int(math.ceil(c*ratio-1e-12))
        raw=min(ctl.hpa.mx,max(ctl.hpa.mn,raw)); e=orig(now,cur,avg); rec['hpa'].append((c,raw,e)); return e
    ctl.hpa.step=step
    ph=V.Phys(ue,start=st,p=RB.PH); traj=dict(ue=[],wk=[],vy=[],slot=[])
    for i in range(3600//V.DT):
        ph.advance_units()
        if ph.t%60==0:
            ob=ph.observe(); traj['ue'].append(ob['D']); traj['wk'].append(ob['wk_vm']); traj['vy'].append(ob['vy_vm']); traj['slot'].append(ob['rep_up'])
        if ph.t%V.TICK==0:
            ob=ph.observe(); decided=ctl.tick(ph,ob); ph.hot_relief(getattr(ph,"_over",{}))
            if not decided and ph.t-ph.last_pool_relief>=ph.p["pool_relief_s"]: ph.enqueue_pool_relief(); ph.last_pool_relief=ph.t
        ph.step()
    r=ph.result(); h=rec['hpa']
    return dict(**traj,start=list(st),alloc_vm=r['alloc_vm'],viol=60-int(r['slo']),hpa_ticks=len(h),hpa_blocked=sum(1 for c,rw,e in h if rw<c and e==c),hpa_raw_below=sum(1 for c,rw,e in h if rw<c),events=[(t,a,k) for (t,a,k,*_) in r['events']])
def diverge(h,s):
    out={}
    for k in ("wk","vy","slot"):
        d=[i for i in range(60) if abs(h[k][i]-s[k][i])>=0.5]
        if not d: out[k]=None; continue
        m0=d[0]; sign="hardware holds more" if h[k][m0]>s[k][m0] else "hardware holds less"; m1=m0
        while m1+1<60 and abs(h[k][m1+1]-s[k][m1+1])>=0.5 and ((h[k][m1+1]>s[k][m1+1])==(h[k][m0]>s[k][m0])): m1+=1
        out[k]=dict(first=m0,direction=sign,until=m1,minutes_diff=len(d))
    return out
J={}
for tn,runs in RUNS.items():
    ue=json.load(open(f"{E}/trace_ue_60min_v3_{tn}.json"))["ue"][:60]
    H={r:hw(r) for r in runs}; S0=sim(ue); h0=H[runs[0]]; S1=sim(ue,start=(int(round(h0['slot'][0])),h0['vy'][0],h0['wk'][0]))
    same=all(H[r]['wk']==H[runs[0]]['wk'] and H[r]['vy']==H[runs[0]]['vy'] for r in runs)
    J[tn]=dict(hw=H,sim_init=S0,sim_hwstart=S1,hw_runs_identical_wk_vy=same,div_init={r:diverge(H[r],S0) for r in runs},div_hwstart={r:diverge(H[r],S1) for r in runs})
    print(f"== {tn}: sim initial_fleet start {S0['start']} alloc {S0['alloc_vm']:.1f} viol {S0['viol']}; sim hardware-start {S1['start']} alloc {S1['alloc_vm']:.1f} viol {S1['viol']}; hw runs wk/vy identical {same}")
    for r in runs: print(f"   {r}: hw min0 slot/vy/wk {H[r]['slot'][0]:.0f}/{H[r]['vy'][0]}/{H[r]['wk'][0]}; HPA ticks {H[r]['hpa_ticks']} raw<cur {H[r]['hpa_raw_below']} blocked by window {H[r]['hpa_blocked']}; div(initial) {J[tn]['div_init'][r]}; div(hw start) {J[tn]['div_hwstart'][r]}")
    print(f"   sim(initial) HPA ticks {S0['hpa_ticks']} raw<cur {S0['hpa_raw_below']} blocked {S0['hpa_blocked']}; events {S0['events'][:12]}")
    print(f"   sim(hw start) HPA raw<cur {S1['hpa_raw_below']} blocked {S1['hpa_blocked']}; events {S1['events'][:12]}")
json.dump(J,open(f'{R}/out/b5c1.json','w'),indent=1,default=str)
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
for tn in RUNS:
    fig,axs=plt.subplots(1,3,figsize=(11,3.2)); d=J[tn]
    for ax,(k,lab) in zip(axs,(("wk","workers"),("vy","VyOS"),("slot","slots"))):
        for r in RUNS[tn]: ax.plot(range(60),d['hw'][r][k],lw=0.9,color="#888",alpha=0.8,label=f"hardware {r}")
        ax.plot(range(60),d['sim_init'][k],lw=2.4,color="#1b4f9c",label="sim, initial_fleet start")
        ax.plot(range(60),d['sim_hwstart'][k],lw=1.6,ls="--",color="#d9822b",label="sim, hardware minute-0 start")
        ax.set_title(f"{tn} B5c1 4.0/L2: {lab}",fontsize=9); ax.set_xlabel("minute"); ax.grid(lw=0.3)
    axs[0].legend(fontsize=6.5,frameon=False,loc="lower left"); fig.tight_layout(); fig.savefig(f'{R}/fig_{tn}_b5c1_trace.pdf'); plt.close(fig)
print("figures written")
