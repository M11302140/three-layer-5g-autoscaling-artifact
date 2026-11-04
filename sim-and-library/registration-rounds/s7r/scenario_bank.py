#!/usr/bin/env python3
"""qsim/s7r/scenario_bank.py (S7R protocol §2.2): demand-continuation scenarios from the fit groups only.

Anchor = (loc, date, raw_minute) of a library window; a window starting at raw minute s covers raw minutes [s, s+240) compressed 4:1, so
compressed minute k is raw minute s+4k. Overlapping windows share raw times: each raw time keeps ONE window (the earliest start that has
the anchor at k >= 1 and the full continuation k + FUT_MIN <= 60); duplicates are dropped.
Keys of an anchor: D bucket = int(src(k) // 10) (UE, 0-40 domain), sign of the past change src(k) - src(k-1) in {-1, 0, +1}, minute phase
(0 or 30 s). Library data are per minute, so every anchor serves both phases: the phase key does not discriminate (recorded, not hidden).
Cell support: >= 32 anchors and >= 8 (loc, date) groups; fallback (bucket, phase) -> (phase); still short -> UNSUPPORTED (caller falls
back to S4b; no sample is invented).
Selection (deterministic, no future, no trace id): key = canonical JSON [t, observed tick history of D]; groups of the cell ordered by
sha256(key|group); the first 16 (cycled in that order if fewer than 16 groups) each give one anchor = min sha256(key|group|anchor).
Never ranks by future burst size. Weights 1/16.
Continuation (rollout targets per minute boundary after now): target(m+j) = clip(D_now + src(k+j) - src(k), 0, 40), j >= 1; the rest of
the current minute keeps D_now (pending arrivals unknown to the controller are not used). Clips are counted. D_now outside [0, 40] ->
OUT_OF_DOMAIN (caller falls back).
"""
import json, hashlib
FUT_MIN = 26            # 900 + 600 s horizon = 25 min + boundary extension
NSCEN = 16; MIN_ANCH = 32; MIN_GROUPS = 8; DOMAIN = (0, 40)

def h(x): return hashlib.sha256(json.dumps(x, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")).hexdigest()
def sgn(x): return (x > 0) - (x < 0)

class Bank:
    def __init__(s, lib, fit_groups):
        fg = {(int(a), b) for a, b in fit_groups}; best = {}; ncand = 0
        for wi, tr in enumerate(lib):
            g = (int(tr["loc"]), tr["date"])
            if g not in fg: continue
            for k in range(1, 60 - FUT_MIN):
                ncand += 1
                raw = tr["start"] + 4 * k; key = (g[0], g[1], raw)
                if key not in best or tr["start"] < lib[best[key][0]]["start"]: best[key] = (wi, k)
        s.anchors = []
        for (loc, date, raw), (wi, k) in sorted(best.items()):
            u = lib[wi]["ue"][:60]
            s.anchors.append(dict(id=f"{loc}|{date}|{raw}", g=f"{loc}|{date}", D=u[k], sign=sgn(u[k] - u[k - 1]), inc=[u[k + j] - u[k] for j in range(1, FUT_MIN + 1)]))
        s.cells = {}
        for a in s.anchors:
            b = min(int(a["D"] // 10), 3)
            for ph in (0, 30):
                s.cells.setdefault(("bsp", b, a["sign"], ph), []).append(a)
                s.cells.setdefault(("bp", b, ph), []).append(a)
                s.cells.setdefault(("p", ph), []).append(a)
        s.n_candidates = ncand; s.n_dropped_overlap = ncand - len(s.anchors)
    @staticmethod
    def ok(cell): return cell is not None and len(cell) >= MIN_ANCH and len({a["g"] for a in cell}) >= MIN_GROUPS
    def select(s, t, dhist, d_now, d_prev60, phase):
        """returns dict(status, level, scenarios=[dict(anchor, targets, clips)], hash)"""
        if not (DOMAIN[0] <= d_now <= DOMAIN[1]): return dict(status="OUT_OF_DOMAIN", scenarios=[])
        b = min(int(d_now // 10), 3); sg = sgn(d_now - d_prev60)
        cell = None; level = None
        for lv, key in (("bucket+sign+phase", ("bsp", b, sg, phase)), ("bucket+phase", ("bp", b, phase)), ("phase", ("p", phase))):
            c = s.cells.get(key)
            if s.ok(c): cell = c; level = lv; break
        if cell is None: return dict(status="UNSUPPORTED", scenarios=[])
        key = [int(t), [float(x) for x in dhist]]; kh = h(key)
        groups = sorted({a["g"] for a in cell}, key=lambda g: h([kh, g]))
        bygrp = {}
        for a in cell: bygrp.setdefault(a["g"], []).append(a)
        out = []
        for j in range(NSCEN):
            g = groups[j % len(groups)]; cands = bygrp[g]
            if j >= len(groups):     # fixed re-draw within a repeated group: next anchor in hash order
                order = sorted(cands, key=lambda a: h([kh, g, a["id"]])); a = order[(j // len(groups)) % len(order)]
            else:
                a = min(cands, key=lambda a: h([kh, g, a["id"]]))
            tg = []; clips = 0
            for inc in a["inc"]:
                v = d_now + inc
                if v < DOMAIN[0] or v > DOMAIN[1]: clips += 1
                tg.append(int(min(DOMAIN[1], max(DOMAIN[0], v))))
            out.append(dict(anchor=a["id"], targets=tg, clips=clips))
        return dict(status="OK", level=level, scenarios=out, hash=h([kh, [x["anchor"] for x in out]]), key_hash=kh)
