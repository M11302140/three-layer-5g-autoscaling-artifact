#!/usr/bin/env python3
"""qsim/s4t/v8sim11_s4t.py (10-27, spec §4.133): per-slot simulator v8sim11 with the S4T controller (CtlS4T = CtlSigma verbatim + R3).
Physics and runner are the frozen v8sim11. run_s4t(ue, L, k3=None, prior=None, start=None). k3 = None -> CtlSigma bit for bit."""
import sys, os, math, json
Q='/home/user/experiment/qsim'; sys.path.insert(0,Q); sys.path.insert(0,Q+'/s4t')
import v8sim11 as V
from v8sim11 import FMAX, FMIN, TICK, DT
class CtlS4T:
    """S4T (spec §4.133): verbatim copy of v8sim11.CtlSigma + R3 arrival trigger (a = positive tick increment of D; own 300 s cooldown)."""
    def __init__(s, cfg, prior, L, K=None, lock_up=300, lock_vm=600, idle_min=600, k3=None, r3_cool=300):
        s.cfg, s.pr, s.L = cfg, prior, L; s.K = K or {"up": 0, "vy": 0, "wk": 0}; s.k3 = k3; s.r3_cool = r3_cool; s.last_r3 = -1e9; s.r3 = []
        s.W = {k: int(round(cfg.win[k])) for k in cfg.h}; s.LOCK = {"up": lock_up, "vy": lock_vm, "wk": lock_vm}; s.Dd = dict(cfg.d)
        s.last_out = {k: -1e9 for k in cfg.h}; s.last_in = {k: -1e9 for k in cfg.h}; s.idle_min = idle_min; s.hist = []
    def need(s, k, x): return float(s.cfg.need(k, x))
    def mg(s, kind, k, D): return s.L[k] * s.pr.sigma(kind, k, D) + s.K[k]
    def want_wk(s, D): return max(s.need("wk", D + s.mg("win", "wk", D)), math.ceil(s.need("up", D + s.L["up"] * s.pr.sigma("win", "wk", D) + s.K["up"]) / s.cfg.spw))
    def tick(s, ph, ob):
        t = ph.t; D = float(ob["D"]); s.hist.append((t, D))
        wants = {"up": s.need("up", D + s.mg("win", "up", D)), "vy": s.need("vy", D + s.mg("win", "vy", D)), "wk": s.want_wk(D)}
        if s.k3 is not None:   # R3 arrival trigger
            a3 = max(0.0, D - s.hist[-2][1]) if len(s.hist) >= 2 else 0.0
            if t - s.last_r3 >= s.r3_cool:
                ob0 = ph.observe(); nrdy = ob0["ready_up"] - ob0["drain_up"]
                if a3 >= s.k3 and nrdy * 5 - D < s.k3:
                    r3 = float(min(FMAX["up"], ob0["rep_up"] - ob0["drain_up"] + 1))
                    if r3 > wants["up"]:
                        wants["up"] = r3; s.last_r3 = t; s.r3.append(t)
                        wk3 = float(min(FMAX["wk"], math.ceil(wants["up"] / s.cfg.spw)))
                        if wk3 > wants["wk"]: wants["wk"] = wk3
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
                x = level + s.L[k] * s.pr.sigma("run", k, level) + s.K[k]
                if k == "wk":
                    nn = max(s.need("up", x), math.ceil(s.need("up", level + s.L["up"] * s.pr.sigma("run", "wk", level) + s.K["up"]) / s.cfg.spw) * s.cfg.spw)
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

def run_s4t(ue, L, k3=None, prior=None, start=None, phys=None):
    cfg,pr0=V.cfg_prior(); pr=prior or pr0
    if start is None: start=V.initial_fleet("S",ue[0],L=L)
    ph=V.Phys(ue,start=start,p=phys); ctl=CtlS4T(cfg,pr,L,k3=k3)
    n=60*60//DT
    for i in range(n):
        ph.advance_units()
        if ph.t%TICK==0:
            ob=ph.observe(); decided=ctl.tick(ph,ob)
            ph.hot_relief(getattr(ph,"_over",{}))
            if not decided and ph.t-ph.last_pool_relief>=ph.p["pool_relief_s"]:
                ph.enqueue_pool_relief(); ph.last_pool_relief=ph.t
        ph.step()
    r=ph.result(); r['r3']=ctl.r3; return r
