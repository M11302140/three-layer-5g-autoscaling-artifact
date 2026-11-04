#!/usr/bin/env python3
"""qsim/s7r/objective.py (S7R protocol §2.3): rollout objective = alloc_vm existence integral over the horizon + terminal committed cost.

C_j(a) = integral_{t0}^{H} [3 N_worker_exists + 2 N_vyos_exists + 0.8 N_slot_exists] dt/60  +  terminal_committed_cost_j
terminal_committed_cost (core-min) = remaining existence that must still be paid after H:
  * units already deleting: until their 'gone' time;
  * a slot draining: until its expected deletion = max(H, now) + remaining moves x move_s + release delay + tail (empty: its drain_empty time);
  * units dispatched but not yet appeared/ready: they will exist at least until the reverse lock of their layer expires;
  * every unit of a layer whose reverse lock (last scale-out + 300 s slot / 600 s VM) is still running at H: until the lock expires
    (it cannot be removed earlier by the base policy);
  never counted twice: only time after H; never charged for orders not yet issued.
Risk: bad_minute = loss fraction > 0.1 % OR any single unit overflowing >= 10 s in the minute (event_phys.minute_bad); the horizon is
extended to the next full minute boundary; minutes already in progress carry the observed accumulated traffic/loss.
"""
from event_phys import SLOT_ORDER, CORES

def terminal_committed_cost(ph, H, last_out, lock_up=300, lock_vm=600):
    p = ph.p; extra = 0.0
    # deleting units
    for w in ph.workers.values():
        if w["state"] == "deleting" and w["gone"] is not None and w["gone"] > H: extra += CORES["wk"] * (w["gone"] - H) / 60
    for v in ph.vyos.values():
        if v["state"] == "deleting" and v["gone"] is not None and v["gone"] > H: extra += CORES["vy"] * (v["gone"] - H) / 60
    # draining slots
    for o in SLOT_ORDER:
        sl = ph.slots[o]
        if sl["state"] != "drain": continue
        if sl["drain_empty"] is not None: end = sl["drain_empty"]
        else:
            nmv = sum(1 for m in ph.moves if m["src"] == o) + (1 if ph.cur_move is not None and ph.cur_move["src"] == o else 0)
            end = max(H, ph.t) + nmv * p["move_s"] + p["release_delay_s"] + p["release_tail_s"]
        if end > H: extra += CORES["up"] * (end - H) / 60
    # reverse locks still running at H: every live unit of that layer must exist until the lock expires
    locks = {"up": lock_up, "vy": lock_vm, "wk": lock_vm}
    for k in ("up", "vy", "wk"):
        until = last_out.get(k, -1e9) + locks[k]
        if until <= H: continue
        if k == "up": n = sum(1 for o in SLOT_ORDER if ph.slots[o]["state"] in ("boot", "ready"))
        elif k == "vy": n = sum(1 for v in ph.vyos.values() if v["state"] in ("boot", "adm"))
        else: n = sum(1 for w in ph.workers.values() if w["state"] in ("boot", "ready"))
        extra += CORES[k] * n * (until - H) / 60
    return extra
# the existence integral itself is ph.alloc(after) - ph.alloc(before): event_phys.measure accumulates it second by second
