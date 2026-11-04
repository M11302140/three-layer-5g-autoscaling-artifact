#!/usr/bin/env python3
"""qsim/serial/ps.py (spec §4.134): per-slot v8sim11 with an executor slot-boot concurrency cap, applied to every arm.
setting = None -> frozen v8sim11.run (P1, must be bit-identical). setting = (C, delta): C in {1, 2, 4, None=inf}, delta = extra lead (s) of a slot
dispatched while another slot is booting (slot_api and relief both shifted).
  executor (PhysC.scale_out_up): refuses when booting slots >= C (counted in ph.queue as one queued slot-tick per refusal).
  S arms and v6: their own one-per-tick / wait-for-booting gate is replaced by requesting the whole deficit each tick (positions, FMAX unchanged).
  baselines: control logic unchanged (maxbatch 3, inflight 90 s), only the executor cap applies.
Mechanism metric 'queue' = queued slot-ticks (x 30 s = queued slot-seconds): P1 S / v6 = deficit not requested because of their own
serialization; PC = executor refusals + deficit not requested after the first refusal."""
import sys, math, json
Q='/home/user/experiment/qsim'; sys.path.insert(0,Q)
import v8sim11 as V
from v8sim11 import FMAX, TICK, DT
class PhysC(V.Phys):
    def __init__(s, ue, start=None, p=None, C=None, delta=0):
        super().__init__(ue, start=start, p=p); s.C=C; s.delta=delta; s.queue=0
    def nboot(s): return sum(1 for o in V.SLOT_ORDER if s.slots[o]["state"]=="boot")
    def scale_out_up(s):
        nb=s.nboot()
        if s.C is not None and nb>=s.C: s.queue+=1; return ("cap",None)
        r=super().scale_out_up()
        if r[0]=="ok" and nb>=1 and s.delta:
            sl=s.slots[r[1]]; sl["api"]+=s.delta; sl["relief"]+=s.delta
        return r
def queue_p1_S(ctl, ph, ob, wants_up):
    """P1 S: deficit beyond what the one-slot-at-a-time gate lets through this tick"""
    return max(0, int(math.ceil(wants_up-(ob["rep_up"]-ob["drain_up"])-1e-9)))
class CtlSigmaP1(V.CtlSigma):
    """frozen CtlSigma + queue metric only"""
    def tick(s, ph, ob):
        D=float(ob["D"]); w=s.need("up", D+s.mg("win","up",D)); before=ph.observe(); r=super().tick(ph,ob); after=ph.observe()
        disp=(after["rep_up"]-after["drain_up"])-(before["rep_up"]-before["drain_up"])
        if before["drain_up"]==0: ph.queue+=max(0,queue_p1_S(s,ph,before,w)-max(0,disp))
        return r
class CtlV6P1(V.CtlV6):
    def tick(s, ph, ob):
        D=float(ob["D"]); want=s.cfg.need("up", D+s.b); b=ph.observe(); r=super().tick(ph,ob); a=ph.observe()
        cur=b["ready_up"]-b["drain_up"]+b["boot_up"]; disp=a["rep_up"]-b["rep_up"]
        if b["drain_up"]==0: ph.queue+=max(0,int(want-cur)-max(0,disp))
        return r
class CtlSigmaC(V.CtlSigma):
    """CtlSigma with the slot branch replaced: request the whole deficit, executor cap decides"""
    def tick(s, ph, ob):
        t=ph.t; D=float(ob["D"]); s.hist.append((t,D))
        wants={"up": s.need("up", D+s.mg("win","up",D)), "vy": s.need("vy", D+s.mg("win","vy",D)), "wk": s.want_wk(D)}
        decided=False
        for k in ("vy","wk","up"):
            ob=ph.observe()
            eff={"up": ob["rep_up"]-ob["drain_up"], "vy": ob["vy_vm"], "wk": ob["wk_vm"]}
            boot={"up": ob["boot_up"], "vy": ob["vy_boot"], "wk": ob["wk_boot"]}
            if not (wants[k]>eff[k] and eff[k]<FMAX[k]): continue
            if k=="wk" and boot["wk"]>0: continue
            if k=="up":
                if ob["drain_up"]>0: ph.cancel_drain(); decided=True; continue
                nreq=int(math.ceil(wants["up"]-eff["up"]-1e-9)); done=0
                for j in range(nreq):
                    o2=ph.observe()
                    if o2["rep_up"]>=o2["wk_ready"]*s.cfg.spw or o2["rep_up"]-o2["drain_up"]>=FMAX["up"]: break
                    r=ph.scale_out_up()
                    if r[0]=="cap": ph.queue+=nreq-j-1; break
                    if r[0]!="ok": break
                    s.last_out[k]=t; decided=True; done+=1
                continue
            ok=ph.deploy_vy() if k=="vy" else ph.create_wk()
            if ok: s.last_out[k]=t; decided=True
        return s.release(ph,t,D,decided)
    def release(s, ph, t, D, decided):
        for k in ("up","vy","wk"):
            ob=ph.observe()
            eff={"up": ob["rep_up"]-ob["drain_up"], "vy": ob["vy_vm"], "wk": ob["wk_vm"]}
            boot={"up": ob["boot_up"], "vy": ob["vy_boot"], "wk": ob["wk_boot"]}; drn={"up": ob["drain_up"], "vy": 0, "wk": 0}
            if eff[k]<=V.FMIN[k]+1e-9 or boot[k]>0: continue
            if drn[k]>0 or t-s.last_in[k]<s.Dd[k]: continue
            if k=="wk" and (drn["up"]>0 or t-s.last_in["up"]<s.Dd["up"]): continue
            if t-s.last_out[k]<s.LOCK[k]: continue
            if t<2*s.W[k]: continue
            peak=max(d for (tt,d) in s.hist if tt>=t-s.W[k])
            def rel_need(level):
                x=level+s.L[k]*s.pr.sigma("run",k,level)+s.K[k]
                if k=="wk":
                    nn=max(s.need("up",x), math.ceil(s.need("up",level+s.L["up"]*s.pr.sigma("run","wk",level)+s.K["up"])/s.cfg.spw)*s.cfg.spw)
                    return max(nn,eff["up"])
                return s.need(k,x)
            if k=="wk":
                if not (rel_need(D)<=(eff["wk"]-1)*s.cfg.spw and rel_need(peak)<=(eff["wk"]-1)*s.cfg.spw): continue
                if eff["up"]>(eff["wk"]-1)*s.cfg.spw: continue
                i=ob["idle_wk"]
                if i is None or ph.t-ph.workers[i]["ready"]<s.idle_min: continue
                if ph.delete_wk(i): s.last_in[k]=t; decided=True
            else:
                if not (rel_need(D)<=eff[k]-1 and rel_need(peak)<=eff[k]-1): continue
                ok=ph.scale_in_up() if k=="up" else ph.delete_vy()
                if ok: s.last_in[k]=t; decided=True
        return decided
class CtlV6C(V.CtlV6):
    """CtlV6 with the slot branch requesting the whole deficit (cur + pend < want) each tick; executor cap decides"""
    def tick(s, ph, ob):
        t=ph.t; D=float(ob["D"]); s.hist.append((t,D)); decided=False
        cur={"up": ob["ready_up"]-ob["drain_up"], "vy": ob["vy_adm"], "wk": ob["wk_ready"]}
        pend={"up": ob["boot_up"], "vy": ob["vy_boot"], "wk": ob["wk_boot"]}
        for k in ("vy","wk","up"):
            want=s.cfg.need(k, D+s.b)
            if want>cur[k]+pend[k] and cur[k]+pend[k]<FMAX[k]:
                if k=="up":
                    if ob["drain_up"]>0: ph.cancel_drain(); decided=True; continue
                    nreq=int(want-cur["up"]-pend["up"])
                    for j in range(nreq):
                        if cur["up"]+pend["up"]+1>(cur["wk"]+pend["wk"])*s.cfg.spw or cur["up"]+pend["up"]>=FMAX["up"]: break
                        r=ph.scale_out_up()
                        if r[0]=="cap": ph.queue+=nreq-j-1; break
                        if r[0]!="ok": break
                        s.last_out[k]=t; decided=True; pend["up"]+=1
                    continue
                ok=ph.deploy_vy() if k=="vy" else ph.create_wk()
                if ok: s.last_out[k]=t; decided=True; pend[k]+=1
        for k in ("up","vy","wk"):
            if cur[k]<=V.FMIN[k] or pend[k]>0: continue
            if k=="up" and ob["drain_up"]>0: continue
            if k=="wk" and (cur["wk"]-1)*s.cfg.spw<cur["up"]+pend["up"]: continue
            peak=max(d for (tt,d) in s.hist if tt>=t-s.W6[k])
            if not (s.cfg.need(k,peak+s.b)<=cur[k]-1): continue
            if t-s.last_out[k]<s.VMDW[k]: continue
            if k=="up": ok=ph.scale_in_up()
            elif k=="vy": ok=ph.delete_vy()
            else: ok=ph.delete_wk()
            if ok: decided=True
        return decided
def ctl_for(arm, setting):
    cfg,pr=V.cfg_prior()
    if setting is None:
        if arm in ("S4a","S4b"): return CtlSigmaP1(cfg,pr,V.LAM[arm])
        if arm=="v6": return CtlV6P1(cfg)
        return V.make_ctl(arm)
    if arm in ("S4a","S4b"): return CtlSigmaC(cfg,pr,V.LAM[arm])
    if arm=="v6": return CtlV6C(cfg)
    return V.make_ctl(arm)
def flaps(events):
    ev=sorted((t/60.0,k,(+1 if a=='out' else -1)) for (t,a,k,*_) in events if a in ('out','in'))
    n=0
    for i,(t,l,dr) in enumerate(ev):
        for t2,l2,d2 in ev[i+1:]:
            if l2==l and t2-t<=10 and d2==-dr: n+=1; break
    return n
def run(ue, arm, setting=None):
    start=V.initial_fleet(arm, ue[0])
    C,delta=(setting if setting is not None else (None,0))
    ph=PhysC(ue,start=start,C=C,delta=delta); ctl=ctl_for(arm,setting)
    for i in range(60*60//DT):
        ph.advance_units()
        if ph.t%TICK==0 and ctl is not None:
            ob=ph.observe(); decided=ctl.tick(ph,ob)
            ph.hot_relief(getattr(ph,"_over",{}))
            if not decided and ph.t-ph.last_pool_relief>=ph.p["pool_relief_s"]:
                ph.enqueue_pool_relief(); ph.last_pool_relief=ph.t
        elif ph.t%TICK==0 and ctl is None:
            ph.hot_relief(getattr(ph,"_over",{}))
            if ph.t-ph.last_pool_relief>=ph.p["pool_relief_s"]: ph.enqueue_pool_relief(); ph.last_pool_relief=ph.t
        ph.step()
    r=ph.result(); r['queue']=ph.queue; r['flaps']=flaps(r['events']); return r
