#!/usr/bin/env python3
"""v8sim10.py(10-05,審查第十四輪):qsim 對 daemon 物理/觀測語義的忠實化(決策等價測試對出來的差異),供重校準與重登記預測。
sim_nest2 = sim_nest(NEST 不變量 + 實測 lead)+ 下列實機約束(全部可關,預設開):
  release_serial   同層同時只能有一個縮容在飛:槽 drain 期間(d_UP)不再派第二個縮容、也不刪 worker(daemon:in-flight SCALE_IN_UP 擋 DELETE_WORKER、
                   release 候選要求 eff.NUP == Cfg.NUP)
  reversible_drain 槽層補貨撞上還在 drain 的縮容 → 取消 drain、槽保留(不派新槽)
  worker_serial    同時只能有一台 worker 在開機(workerCreateInfraOnly:vm > ready → 擋)
  slot_serial      有槽在開機(ReadyUP < RepUP)時不派下一個槽(Tick 物理閘)
  idle_min         worker 就緒 ≥ 600 s 才可刪(IdleWorker = Ready >10 min)
  position_wait    槽訂單要有「就緒 worker 上的空位」才派(執行層 DeployUPF);否則等(不計費)
σ̂ 用 v8sim2.Prior(已改桶間插值)。D = 整數 UE(= daemon v7.1.3 用 agent UE 數)。
用法:python3 v8sim10.py [S3a|S3b] [t1|t2]  → 逐分鐘;import 用 sim_nest2(ue,cfg,prior,L,**flags)"""
import sys, math, json, numpy as np
sys.path.insert(0,'/home/cyy/experiment/qsim')
import v8sim2 as S, v8sim7 as M
DT=S.DT; FMAX=S.FMAX; FMIN=S.FMIN
E="/home/cyy/experiment"
TR={"t1":json.load(open(f"{E}/trace_ue_60min_v3_40.json"))["ue"][:60],"t2":json.load(open(f"{E}/trace_ue_60min_v3_pm.json"))["ue"][:60]}
LAM={"S3a":{"vy":2.50,"wk":2.50,"up":3.25},"S3b":{"vy":1.42,"wk":1.42,"up":2.25}}
def sim_nest2(ue, cfg, prior, L, release_serial=True, reversible_drain=True, worker_serial=True, slot_serial=True, idle_min=600, position_wait=True, episode_hold=True, start=None, drain_sec=None, lock_up=300, lock_vm=600, lead_scale=1.0, win_scale=1.0, d_scale=1.0, acct='dispatch'):
    """acct:'dispatch' = 派出起燒、拆除 lead 後停(登記口徑);'vmexist' = VM 實測存在期(QEMU 在建立派出 +30 s 出現、刪除派出 +5 s 消失;pod 不變)= rq alloc_vm 口徑"""
    """drain_sec:槽縮容後 pod 消失的秒數(None = d_UP 150 s 滿槽 drain;30 = 空槽立即刪)"""
    d=S.expand(ue)*cfg.scale; n=len(d); H={k:v*lead_scale for k,v in cfg.h.items()}; Dd={k:v*d_scale for k,v in cfg.d.items()}; LOCK={"up":lock_up,"vy":lock_vm,"wk":lock_vm}
    need=lambda k,x: float(cfg.need(k,x)); mg=lambda kind,k,D: L[k]*prior.sigma(kind,k,D)
    W={"up":0, "vy":0, "wk":0}   # 暴露窗(daemon qCommitWindow,sigma 模式):由 cfg.win 給(v8sim7 cfg_measured)
    W={k:int(round(cfg.win[k]*win_scale)) for k in cfg.h}
    def want_wk(D): return max(need("wk",D+mg("win","wk",D)), math.ceil(need("up",D+L["up"]*prior.sigma("win","wk",D))/cfg.spw))
    cur={k:need(k,d[0]+mg("win",k,d[0])) for k in cfg.h}; cur["wk"]=max(want_wk(d[0]), math.ceil(cur["up"]/cfg.spw))
    if start: cur={"up":float(start[0]),"vy":float(start[1]),"wk":float(start[2])}
    units=[]
    for k in ("up","vy","wk"):
        for _ in range(int(cur[k])): units.append(dict(k=k,dispatch=-1e9,ready=-1e9,gone=1e18,draining=False))
    last_out={k:-1e9 for k in cur}; last_in={k:-1e9 for k in cur}; alloc=0.0; ev=[]; lossmin=np.zeros(60); offmin=np.zeros(60); permin=np.zeros(60); traj=[]; ticks=[]
    t=0.0
    def cnt(k,f): return sum(1 for u in units if u["k"]==k and u["gone"]>t and f(u))
    def observe():
        rep={k:cnt(k,lambda u:u["dispatch"]<=t) for k in cfg.h}
        ready={k:cnt(k,lambda u:u["ready"]<=t) for k in cfg.h}
        drn={k:cnt(k,lambda u:u["draining"]) for k in cfg.h}
        booting={k:rep[k]-ready[k] for k in cfg.h}
        return rep,ready,drn,booting
    for i in range(n):
        t=i*DT; D=d[i]
        nUP=cnt("up",lambda u:u["ready"]<=t and not u["draining"]); nVY=cnt("vy",lambda u:u["ready"]<=t and not u["draining"]); nWK=cnt("wk",lambda u:u["ready"]<=t and not u["draining"])
        cur={"up":nUP,"vy":nVY,"wk":nWK}
        l=S.loss_step(cfg,cur,D); lossmin[i*DT//60]+=l*D*DT; offmin[i*DT//60]+=D*DT
        if acct=='vmexist':
            burn={k:sum(1 for u in units if u["k"]==k and (u["dispatch"]+(30 if k!="up" else 0))<=t and (u["gone"] if k=="up" else u.get("bend",u["gone"]))>t) for k in cur}
        else:
            burn={k:cnt(k,lambda u:u["dispatch"]<=t) for k in cur}
        c=sum(cfg.cores[k]*burn[k] for k in burn)*DT/60; alloc+=c; permin[i*DT//60]+=c
        if t%60==0: traj.append((t//60,int(D),nUP,nVY,nWK,burn["up"],burn["vy"],burn["wk"]))
        if t%S.TICK!=0: continue
        rep,ready,drn,booting=observe()
        # daemon configAt:就緒計數(含 draining 的 pod 仍存在 → RepUP 含它)− 縮容在飛 + 擴容在飛
        eff={k:rep[k]-drn[k] for k in cfg.h}          # = 存在 − draining(+booting 已含在 rep)
        wants={"up":need("up",D+mg("win","up",D)),"vy":need("vy",D+mg("win","vy",D)),"wk":want_wk(D)}
        ticks.append((t,D,wants["up"],wants["vy"],wants["wk"],rep["up"],ready["up"],rep["vy"],ready["vy"],rep["wk"]))
        # ---- 補貨(每 tick 重評,不排隊)
        for k in ("vy","wk","up"):
            rep,ready,drn,booting=observe(); eff={kk:rep[kk]-drn[kk] for kk in cfg.h}
            if not (wants[k]>eff[k] and eff[k]<FMAX[k]): continue
            if k=="wk" and worker_serial and booting["wk"]>0: ev.append((t,"blocked-wkboot",k)); continue
            if k=="up":
                draining_up=[u for u in units if u["k"]=="up" and u["draining"] and u["gone"]>t]
                if reversible_drain and draining_up:
                    u=draining_up[-1]; u["draining"]=False; u["gone"]=1e18; ev.append((t,"cancel-drain","up")); continue
                if slot_serial and booting["up"]>0: ev.append((t,"blocked-slotboot",k)); continue
                if position_wait and rep["up"]>=ready["wk"]*cfg.spw:
                    ev.append((t,"wait-position","up")); continue
            units.append(dict(k=k,dispatch=t,ready=t+H[k],gone=1e18,draining=False)); last_out[k]=t; ev.append((t,"out",k))
        # ---- 釋放(planner 候選:現值 D;controller hold:窗內峰值、σ̂ 取峰值水位、計數扣縮容在飛)
        for k in ("up","vy","wk"):
            rep,ready,drn,booting=observe(); eff={kk:rep[kk]-drn[kk] for kk in cfg.h}
            if eff[k]<=FMIN[k]+1e-9 or booting[k]>0: continue
            # daemon:縮容 in-flight 至少活一個 lead(計數先降也要等 lead 滿),期間 hold 把它再扣一次 → 同層下一個縮容
            # 與(槽縮容在飛時的)worker 刪除都要等 lead 過;pod 早刪(空槽 30 s)不會縮短這段
            if release_serial and (drn[k]>0 or t-last_in[k]<Dd[k]): continue
            if k=="wk" and release_serial and (drn["up"]>0 or t-last_in["up"]<Dd["up"]): continue
            if t-last_out[k]<LOCK[k]: continue
            if episode_hold and t<2*W[k]: continue
            j0=max(0,i-W[k]//DT); peak=d[j0:i+1].max()
            def rel_need(level):
                x=level+mg("run",k,level)
                if k=="wk":
                    nn=max(need("up",x), math.ceil(need("up",level+L["up"]*prior.sigma("run","wk",level))/cfg.spw)*cfg.spw)
                    return max(nn, eff["up"])
                return need(k,x)
            if k=="wk":
                if not (rel_need(D)<=(eff["wk"]-1)*cfg.spw and rel_need(peak)<=(eff["wk"]-1)*cfg.spw): continue
            else:
                if not (rel_need(D)<=eff[k]-1 and rel_need(peak)<=eff[k]-1): continue
            cands=[u for u in units if u["k"]==k and u["ready"]<=t and not u["draining"] and u["gone"]>t]
            if k=="wk" and idle_min: cands=[u for u in cands if u["ready"]<=t-idle_min]
            if k=="wk" and eff["up"]>(eff["wk"]-1)*cfg.spw: continue   # IdleWorker:要有空 worker
            if not cands: ev.append((t,"blocked-idle",k)); continue
            u=cands[-1]; u["draining"]=True; u["gone"]=t+(drain_sec if (k=="up" and drain_sec) else Dd[k]); u["bend"]=t+5; last_in[k]=t; ev.append((t,"in",k))
    pct=100*lossmin/np.maximum(offmin,1e-9)
    return dict(slo=int((pct<=0.1).sum()), alloc=alloc, pct=pct, traj=traj, ev=ev, permin=permin, ticks=ticks, lostfrac=float(lossmin.sum()/max(offmin.sum(),1e-9)))
if __name__=="__main__":
    grp=sys.argv[1] if len(sys.argv)>1 else "S3b"; tn=sys.argv[2] if len(sys.argv)>2 else "t1"
    lib=json.load(open("/home/cyy/experiment/qsim/prior_traces.json")); cfg=M.cfg_measured(); pr=S.Prior(lib,cfg)
    r=sim_nest2(TR[tn],cfg,pr,LAM[grp])
    print(f"=== {grp} {tn} nest2: SLO {r['slo']}/60 alloc {r['alloc']:.0f}")
    print(" events:", [(int(t)//60,a,k) for t,a,k in r["ev"]])
