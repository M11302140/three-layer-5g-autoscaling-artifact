#!/usr/bin/env python3
"""(docstring removed)"""
import sys, os, math, json
Q='/home/user/experiment/qsim'; sys.path.insert(0,Q); sys.path.insert(0,Q+'/s5')
import v8sim11 as V, s5core as C
from v8sim11 import FMAX, FMIN, TICK, DT
class CtlSigmaQ:
    """(docstring removed)"""
    def __init__(s, cfg, prior, L, K=None, lock_up=300, lock_vm=600, idle_min=600, variant='independent_full', margin='quantile'):
        s.indep = variant in ('independent','independent_full'); s.indep_rel = variant=='independent_full'; s.margin = margin
        s.cfg, s.pr, s.L = cfg, prior, L; s.K = K or {"up": 0, "vy": 0, "wk": 0}
        s.W = {k: int(round(cfg.win[k])) for k in cfg.h}; s.LOCK = {"up": lock_up, "vy": lock_vm, "wk": lock_vm}; s.Dd = dict(cfg.d)
        s.last_out = {k: -1e9 for k in cfg.h}; s.last_in = {k: -1e9 for k in cfg.h}; s.idle_min = idle_min; s.hist = []
    def need(s, k, x): return float(s.cfg.need(k, x))
    def mg(s, kind, k, D): return (s.pr.quant(kind, k, D, s.L[k]) if s.margin == 'quantile' else s.L[k] * s.pr.sigma(kind, k, D)) + s.K[k]
    def ut(s, kind, D): return (s.pr.quant(kind, "wk", D, s.L["up"]) if s.margin == 'quantile' else s.L["up"] * s.pr.sigma(kind, "wk", D)) + s.K["up"]
    def want_wk(s, D):
        if s.indep: return s.need("wk", D + s.mg("win", "wk", D))
        return max(s.need("wk", D + s.mg("win", "wk", D)), math.ceil(s.need("up", D + s.ut("win", D)) / s.cfg.spw))
    def tick(s, ph, ob):
        t = ph.t; D = float(ob["D"]); s.hist.append((t, D))
        wants = {"up": s.need("up", D + s.mg("win", "up", D)), "vy": s.need("vy", D + s.mg("win", "vy", D)), "wk": s.want_wk(D)}
        decided = False
        for k in ("vy", "wk", "up"):
            ob = ph.observe()
            eff = {"up": ob["rep_up"] - ob["drain_up"], "vy": ob["vy_vm"], "wk": ob["wk_vm"]}
            boot = {"up": ob["boot_up"], "vy": ob["vy_boot"], "wk": ob["wk_boot"]}
            if not (wants[k] > eff[k] and eff[k] < FMAX[k]): continue
            if k == "wk" and boot["wk"] > 0: continue
            if k == "up":
                if ob["drain_up"] > 0: ph.cancel_drain(); decided = True; continue
                if boot["up"] > 0: continue
                if ob["rep_up"] >= ob["wk_ready"] * s.cfg.spw: continue
                r = ph.scale_out_up()
                if r[0] == "ok": s.last_out[k] = t; decided = True
                continue
            ok = ph.deploy_vy() if k == "vy" else ph.create_wk()
            if ok: s.last_out[k] = t; decided = True
        for k in ("up", "vy", "wk"):
            ob = ph.observe()
            eff = {"up": ob["rep_up"] - ob["drain_up"], "vy": ob["vy_vm"], "wk": ob["wk_vm"]}
            boot = {"up": ob["boot_up"], "vy": ob["vy_boot"], "wk": ob["wk_boot"]}; drn = {"up": ob["drain_up"], "vy": 0, "wk": 0}
            if eff[k] <= FMIN[k] + 1e-9 or boot[k] > 0: continue
            if drn[k] > 0 or t - s.last_in[k] < s.Dd[k]: continue
            if k == "wk" and (drn["up"] > 0 or t - s.last_in["up"] < s.Dd["up"]): continue
            if t - s.last_out[k] < s.LOCK[k]: continue
            if t < 2 * s.W[k]: continue
            peak = max(d for (tt, d) in s.hist if tt >= t - s.W[k])
            def rel_need(level):
                x = level + s.mg("run", k, level)
                if k == "wk":
                    nn = s.need("up", x) if s.indep_rel else max(s.need("up", x), math.ceil(s.need("up", level + s.ut("run", level)) / s.cfg.spw) * s.cfg.spw)
                    return max(nn, eff["up"])
                return s.need(k, x)
            if k == "wk":
                if not (rel_need(D) <= (eff["wk"] - 1) * s.cfg.spw and rel_need(peak) <= (eff["wk"] - 1) * s.cfg.spw): continue
                if eff["up"] > (eff["wk"] - 1) * s.cfg.spw: continue
                i = ob["idle_wk"]
                if i is None or ph.t - ph.workers[i]["ready"] < s.idle_min: continue
                if ph.delete_wk(i): s.last_in[k] = t; decided = True
            else:
                if not (rel_need(D) <= eff[k] - 1 and rel_need(peak) <= eff[k] - 1): continue
                ok = ph.scale_in_up() if k == "up" else ph.delete_vy()
                if ok: s.last_in[k] = t; decided = True
        return decided

_QP=None
def qprior():
    global _QP
    if _QP is None:
        cfg,_=V.cfg_prior(); _QP=C.QPrior(json.load(open(f"{Q}/prior_traces.json")),cfg)
    return _QP
def initial_fleet_s5(d0, P, margin='quantile', prior=None):
    cfg,_=V.cfg_prior(); pr=prior or qprior(); d0=float(d0)
    m=lambda k: (pr.quant("win",k,d0,P[k]) if margin=='quantile' else P[k]*pr.sigma("win",k,d0))
    up=cfg.need("up",d0+m("up")); vy=cfg.need("vy",d0+m("vy"))
    up=int(min(8,max(2,up))); vy=int(min(3,max(1,vy))); wk=int(min(4,max(1,math.ceil(up/2))))
    return (up,vy,wk)
def run_s5(ue, P, variant='independent_full', margin='quantile', prior=None, start=None, phys=None):
    cfg,_=V.cfg_prior(); pr=prior or qprior()
    if start is None: start=initial_fleet_s5(ue[0],P,margin,pr)
    ph=V.Phys(ue,start=start,p=phys); ctl=CtlSigmaQ(cfg,pr,P,variant=variant,margin=margin)
    n=60*60//DT
    for i in range(n):
        ph.advance_units()
        if ph.t%TICK==0:
            ob=ph.observe(); decided=ctl.tick(ph,ob)
            ph.hot_relief(getattr(ph,"_over",{}))
            if not decided and ph.t-ph.last_pool_relief>=ph.p["pool_relief_s"]:
                ph.enqueue_pool_relief(); ph.last_pool_relief=ph.t
        ph.step()
    return ph.result()
