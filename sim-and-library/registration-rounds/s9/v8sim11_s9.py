#!/usr/bin/env python3
"""qsim/s9/v8sim11_s9.py (10-27, spec §4.132): per-slot simulator v8sim11 with the S9 controller.
CtlS9 = v8sim11.CtlSigma verbatim + regime-conditional lambda/sigma, burst trend (replenishment side) and R2 (same as s9core.sim_s9).
Physics and runner are the frozen v8sim11. run_s9(ue, L, Lb=None, thr=None, trend=False, w=None, cond=True, force_reg=None, prior=None, start=None).
thr = None and w = None -> CtlSigma bit for bit (s9/equiv.py). Result adds 'reg' = regime at the first tick of each minute."""
import sys, os, math, json
Q='/home/user/experiment/qsim'; sys.path.insert(0,Q); sys.path.insert(0,Q+'/s9')
import v8sim11 as V, s9core as C
from v8sim11 import FMAX, FMIN, TICK, DT
class CtlS9:
    def __init__(s, cfg, prior, L, K=None, lock_up=300, lock_vm=600, idle_min=600, w=None, Lb=None, thr=None, trend=False, cond=True, force_reg=None):
        s.cfg, s.pr, s.L = cfg, prior, L; s.K = K or {"up": 0, "vy": 0, "wk": 0}; s.w = w
        s.W = {k: int(round(cfg.win[k])) for k in cfg.h}; s.LOCK = {"up": lock_up, "vy": lock_vm, "wk": lock_vm}; s.Dd = dict(cfg.d)
        s.last_out = {k: -1e9 for k in cfg.h}; s.last_in = {k: -1e9 for k in cfg.h}; s.idle_min = idle_min; s.hist = []
        s.Lb, s.thr, s.trend, s.cond, s.force = Lb, thr, trend, cond, force_reg
        s.rg = C.Regime(thr) if thr is not None else None; s.reg = force_reg or "calm"; s.sh = 0.0; s.regmin = []
        s.HZ = {k: C.horizon(cfg, k) for k in cfg.h}
        if thr is not None: s.L = Lb[s.reg]
    def need(s, k, x): return float(s.cfg.need(k, x))
    def sg(s, kind, k, D):
        if s.thr is not None and s.cond: return s.pr.sigma_c(s.reg, kind, k, D)
        return s.pr.sigma(kind, k, D)
    def tr(s, kind, k): return s.sh * s.HZ[k] if (s.thr is not None and kind == "win" and s.trend and s.reg == "burst") else 0.0
    def mg(s, kind, k, D): return s.tr(kind, k) + s.L[k] * s.sg(kind, k, D) + s.K[k]
    def want_wk(s, D): return max(s.need("wk", D + s.mg("win", "wk", D)), math.ceil(s.need("up", D + s.tr("win", "wk") + s.L["up"] * s.sg("win", "wk", D) + s.K["up"]) / s.cfg.spw))
    def tick(s, ph, ob):
        t = ph.t; D = float(ob["D"]); s.hist.append((t, D))
        if s.thr is not None:
            s.rg.step(D); s.reg = s.force or s.rg.cur; s.L = s.Lb[s.reg]
            s.sh = max(0.0, C.slope([d for (_, d) in s.hist[-3:]]))
            if t % 60 == 0: s.regmin.append(s.reg)
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
                x = level + s.L[k] * s.sg("run", k, level) + s.K[k]
                if k == "wk":
                    nn = max(s.need("up", x), math.ceil(s.need("up", level + s.L["up"] * s.sg("run", "wk", level) + s.K["up"]) / s.cfg.spw) * s.cfg.spw)
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
                if k == "up" and s.w is not None and not s.pr.r2_ok(s.cfg, D, eff["up"], eff["wk"], s.w): continue      # R2
                ok = ph.scale_in_up() if k == "up" else ph.delete_vy()
                if ok: s.last_in[k] = t; decided = True
        return decided

_P=None
def s9prior(thr):
    global _P
    if _P is None or _P.thr!=thr:
        cfg,_=V.cfg_prior(); _P=C.S9Prior(json.load(open(f"{Q}/prior_traces.json")),cfg,thr=thr)
    return _P
def start_of(ue, L, pr, Lb=None, thr=None, cond=True, force_reg=None):
    """S start = own convergence (v8sim11.initial_fleet 'S' formula, same clamps); with regime on: the start regime's lambda and sigma"""
    if thr is None: return V.initial_fleet("S", ue[0], L=L)
    cfg,_=V.cfg_prior(); r=force_reg or "calm"; Lr=Lb[r]; d0=float(ue[0])
    sg=(lambda k: pr.sigma_c(r,"win",k,d0)) if cond else (lambda k: pr.sigma("win",k,d0))
    up=cfg.need("up", d0+Lr["up"]*sg("up")); vy=cfg.need("vy", d0+Lr["vy"]*sg("vy"))
    up=int(min(8,max(2,up))); vy=int(min(3,max(1,vy))); wk=int(min(4,max(1,math.ceil(up/2))))
    return (up, vy, wk)
def run_s9(ue, L=None, Lb=None, thr=None, trend=False, w=None, cond=True, force_reg=None, prior=None, start=None, phys=None):
    cfg,_=V.cfg_prior(); pr=prior or s9prior(thr)
    if start is None: start=start_of(ue, L, pr, Lb=Lb, thr=thr, cond=cond, force_reg=force_reg)
    ph=V.Phys(ue,start=start,p=phys); ctl=CtlS9(cfg,pr,L,w=w,Lb=Lb,thr=thr,trend=trend,cond=cond,force_reg=force_reg)
    n=60*60//DT
    for i in range(n):
        ph.advance_units()
        if ph.t%TICK==0:
            ob=ph.observe(); decided=ctl.tick(ph,ob)
            ph.hot_relief(getattr(ph,"_over",{}))
            if not decided and ph.t-ph.last_pool_relief>=ph.p["pool_relief_s"]:
                ph.enqueue_pool_relief(); ph.last_pool_relief=ph.t
        ph.step()
    r=ph.result(); r['reg']=ctl.regmin; return r
