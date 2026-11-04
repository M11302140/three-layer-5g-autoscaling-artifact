#!/usr/bin/env python3
"""qsim/r72hw/ctlgen_d.py (spec §4.140 A″): copy of r68unif/ctlgen.py + three daemon-fidelity diagnostic flags (all off = CtlGen bit for bit):
  excl_left  peak look-back window excludes its left endpoint (daemon PeakOfferedSince: T.After(now-W)) -> hist tt > t-W instead of tt >= t-W
  quant_d    daemon capacity quantisation (model.go vyNeeded / slotsNeededUP): VyOS n = min n with max(1,ceil(x-0.25))*250e3/(n*4.45e6*0.93) <= thetaVY;
             slots n = min n with max(x*250e3/(n*1.35e6*0.93), ceil(max(1,ceil(x-0.25))/n)*250e3/(1.35e6*0.93)) <= thetaUP; worker = ceil(slots/2)
  no_serial  no fixed Dd wait after a same-layer scale-in (v6shadow in-flight semantics): while the previous scale-in of the layer is still in flight
             (t - last_in < Dd) the release test is re-run with the count reduced once more (holdQuantile subtracts the in-flight move again)
Version (d) = all three on. Original docstring:
qsim/r68unif/ctlgen.py (spec §4.136): per-slot v8sim11 controller CtlGen = v8sim11.CtlSigma verbatim + flags:
indep (worker target only its own margin, no WK > UP coupling), indep_rel (independent release), plain (v6-type release: target <= n - 1, locks kept),
w (R2 net-benefit slot scale-in, S7Prior.r2_ok). All flags off -> CtlSigma bit for bit (equiv.py)."""
import sys, math
Q='/home/user/experiment/qsim'; sys.path.insert(0,Q)
import v8sim11 as V
from v8sim11 import FMAX, FMIN
PER = 250e3; CAPUP = 1.35e6 * 0.93; CAPVY = 4.45e6 * 0.93; THUP = 1.0099975008330198; THVY = 1.0005002501250626   # daemon calib (zz probe 10-28)
class CtlGen:
    def __init__(s, cfg, prior, L, K=None, lock_up=300, lock_vm=600, idle_min=600, indep=False, indep_rel=False, plain=False, w=None, excl_left=False, quant_d=False, no_serial=False):
        s.cfg, s.pr, s.L = cfg, prior, L; s.K = K or {"up": 0, "vy": 0, "wk": 0}
        s.W = {k: int(round(cfg.win[k])) for k in cfg.h}; s.LOCK = {"up": lock_up, "vy": lock_vm, "wk": lock_vm}; s.Dd = dict(cfg.d)
        s.last_out = {k: -1e9 for k in cfg.h}; s.last_in = {k: -1e9 for k in cfg.h}; s.idle_min = idle_min; s.hist = []
        s.indep, s.indep_rel, s.plain, s.w = indep, indep_rel, plain, w
        s.excl_left, s.quant_d, s.no_serial = excl_left, quant_d, no_serial
    def need(s, k, x):
        if not s.quant_d: return float(s.cfg.need(k, x))
        if k == "wk": return float(min(FMAX["wk"], max(FMIN["wk"], math.ceil(s.need("up", x) / s.cfg.spw))))
        ues = max(1.0, math.ceil(x - 0.25))
        for n in range(1, 64):
            if k == "vy":
                if ues * PER / (n * CAPVY) <= THVY: break
            else:
                if max(x * PER / (n * CAPUP), math.ceil(ues / n) * PER / CAPUP) <= THUP: break
        return float(min(FMAX[k], max(FMIN[k], n)))
    def mg(s, kind, k, D): return s.L[k] * s.pr.sigma(kind, k, D) + s.K[k]
    def want_wk(s, D):
        if s.indep: return s.need("wk", D + s.mg("win", "wk", D))
        return max(s.need("wk", D + s.mg("win", "wk", D)), math.ceil(s.need("up", D + s.L["up"] * s.pr.sigma("win", "wk", D) + s.K["up"]) / s.cfg.spw))
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
                if ob["rep_up"] >= ob["wk_ready"] * s.cfg.spw: continue   # position_wait (executor rule kept)
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
            red = 0
            if drn[k] > 0: continue
            if t - s.last_in[k] < s.Dd[k]:
                if not s.no_serial: continue
                red = 1   # daemon: in-flight scale-in subtracted again by the hold

            if k == "wk" and (drn["up"] > 0 or t - s.last_in["up"] < s.Dd["up"]): continue
            if t - s.last_out[k] < s.LOCK[k]: continue
            if t < 2 * s.W[k]: continue
            peak = max(d for (tt, d) in s.hist if (tt > t - s.W[k] if s.excl_left else tt >= t - s.W[k]))
            def rel_need(level):
                x = level + s.L[k] * s.pr.sigma("run", k, level) + s.K[k]
                if k == "wk":
                    nn = s.need("up", x) if s.indep_rel else max(s.need("up", x), math.ceil(s.need("up", level + s.L["up"] * s.pr.sigma("run", "wk", level) + s.K["up"]) / s.cfg.spw) * s.cfg.spw)
                    return max(nn, eff["up"])
                return s.need(k, x)
            if k == "wk":
                if s.plain:
                    if not (wants["wk"] <= eff["wk"] - 1): continue
                elif not (rel_need(D) <= (eff["wk"] - 1 - red) * s.cfg.spw and rel_need(peak) <= (eff["wk"] - 1 - red) * s.cfg.spw): continue
                if eff["up"] > (eff["wk"] - 1) * s.cfg.spw: continue
                i = ob["idle_wk"]
                if i is None or ph.t - ph.workers[i]["ready"] < s.idle_min: continue
                if ph.delete_wk(i): s.last_in[k] = t; decided = True
            else:
                if s.plain:
                    if not (wants[k] <= eff[k] - 1): continue
                elif not (rel_need(D) <= eff[k] - 1 - red and rel_need(peak) <= eff[k] - 1 - red): continue
                if k == "up" and s.w is not None and not s.pr.r2_ok(s.cfg, D, eff["up"], eff["wk"], s.w): continue      # R2
                ok = ph.scale_in_up() if k == "up" else ph.delete_vy()
                if ok: s.last_in[k] = t; decided = True
        return decided
