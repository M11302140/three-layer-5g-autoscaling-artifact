#!/usr/bin/env python3
"""fig_t4_burst.pdf (double column, 7.0 x 3.0 in) -- 2026-10-24 R68 (spec §4.116, section 2): the t4 burst mechanism, minutes 18-22,
for one S4b run and one B6 run (new Fig. 6 of the paper, replacing the t6 time series).

Run selection (applied here): S4b = the t4 run whose alloc_vm is closest to the median of r303/r314/r322 (rq_metrics.csv, group
"MAIN t4 S4b"; ties -> lower run number); B6 = same rule over r305/r311 (group "MAIN t4 B6 u=0.70" WITHOUT r316, which the
§4.117 session-count audit found polluted); with two runs the median is their mean and the tie goes to the lower run number.

Rows (per column = run):
 1 active UEs per second (trace_v7_<run>_1s.csv column `ue`);
 2 ready eUPF slots per minute (trace_v7_<run>.csv `eupf_cov` numerator, step) with the daemon's slot order ("hbo scale_out_up (eupf)")
   and slot ready ("eupf rehome (scale-out) done") events (v7<run>_daemon.log);
 3 UEs on the victim slot .38 (DNN "internet"): the daemon's per-slot distribution samples ("v6 pool relief" / "v6 hot slot relief",
   field dist, first digit of each 3-digit entry = UE count) as dots, re-anchoring a reconstruction that applies the harness log's
   "UE-N arrives on internetK" / "UE-N departs" events (DNN -> slot map: internet=.38, internet2=.31 ... internet8=.37, as in
   experiment/p2/classify_minutes.py); the 5-UE knee as a dashed line;
 4 overflow packets dropped by slot .38 per minute (`slot_oob_38`, bars, left axis) and end-to-end loss per second (`e2e_pct`, line,
   right axis); minutes violating the SLO (per-minute e2e_pct > 0.1 or lat_p99_us > 1000, the rq_metrics.py rule) shaded.
Time axis: minutes since the formal start, from the "[hh:mm:ss] start:" line of trace_v7_<run>.log (local time, UTC+8), which is the
clock of the 1-s CSV (epoch ts) and of the daemon log (UTC).
Run: cd figs/scripts && nice -n 19 taskset -c 13 python3 fig_t4_burst.py [preview.png]
"""
import os, sys, re, json, csv, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import common as C

C.set_style()
P2 = C.P2
TZ = dt.timezone(dt.timedelta(hours=8))
DNN_SLOT = {'internet': 38, 'internet2': 31, 'internet3': 32, 'internet4': 33, 'internet5': 34, 'internet6': 35, 'internet7': 36, 'internet8': 37}
VICTIM = 38
W0, W1 = 18.0, 22.0          # window in minutes since formal start

rows = C.load_rq()
def pick(group, runs):
    rr = [r for r in C.rows_of(rows, group) if r["run"] in runs]
    vals = sorted((C.alloc(r), int(r["run"][1:]), r["run"]) for r in rr)
    med = float(np.median([v[0] for v in vals]))
    best = min(vals, key=lambda v: (abs(v[0] - med), v[1]))
    print(f"{group}: {[(v[2], v[0]) for v in vals]} median {med:.1f} -> {best[2]}")
    return best[2]
RUN_S4B = pick("MAIN t4 S4b", {"r303", "r314", "r322"})
RUN_B6 = pick("MAIN t4 B6 u=0.70", {"r305", "r311"})        # r316 excluded (§4.117 audit)
RUN_S4P = pick("R72 t4 S4p2", {"r532", "r533", "r536"})     # rev. 4: planner, ε = 2 % (all three at 1394 -> r532)
RUNS = [("S4b", RUN_S4B), ("B6", RUN_B6), ("S4p2", RUN_S4P)]

def start_of(run):
    for line in open(f"{P2}/trace_v7_{run}.log"):
        m = re.match(r"\[(\d\d):(\d\d):(\d\d)\] start:", line)
        if m: return (int(m[1]), int(m[2]), int(m[3]))
    raise SystemExit("no start line " + run)

def load(run):
    h, m, s = start_of(run)
    sec = list(csv.DictReader(open(f"{P2}/trace_v7_{run}_1s.csv")))
    t_first = dt.datetime.fromtimestamp(float(sec[0]["ts"]), TZ)
    t0 = t_first.replace(hour=h, minute=m, second=s, microsecond=0)
    if abs((t0 - t_first).total_seconds()) > 120: raise SystemExit(f"{run}: start line {h}:{m}:{s} does not match 1-s CSV first ts {t_first}")
    T0 = t0.timestamp()
    def rel(ts): return (ts - T0) / 60.0
    one = [(rel(float(r["ts"])), int(r["ue"]) if r["ue"] else None, float(r["e2e_pct"]) if r["e2e_pct"] else None,
            float(r["lat_p99_us"]) if r["lat_p99_us"] else None) for r in sec]
    permin = list(csv.DictReader(open(f"{P2}/trace_v7_{run}.csv")))
    pm = {}
    for r in permin:
        mi = int(r["min"]); cov = r["eupf_cov"]
        loss = float(r["e2e_pct"]) if r["e2e_pct"] not in ("", "?") else 1e9
        p99 = float(r["lat_p99_us"]) if r["lat_p99_us"] not in ("", "?") else 1e9
        pm[mi] = dict(ready=int(cov.split("/")[0]), oob38=float(r[f"slot_oob_{VICTIM}"] or 0), viol=not (loss <= 0.1 and p99 <= 1000),
                      active=int(float(r["active_ue"])), loss=loss, p99=p99)
    # daemon events (UTC timestamps)
    orders, readys, dists = [], [], []
    for line in open(f"{P2}/v7{run}_daemon.log"):
        if '"time"' not in line: continue
        try: d = json.loads(line)
        except Exception: continue
        ts = dt.datetime.strptime(d["time"][:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=dt.timezone.utc).timestamp()
        t = rel(ts); msg = d.get("msg", "")
        if msg == "hbo scale_out_up (eupf)": orders.append(t)
        elif msg == "eupf rehome (scale-out) done": readys.append(t)
        elif msg in ("v6 pool relief", "v6 hot slot relief") and "dist" in d:
            cnt = {}
            for k, v in re.findall(r"(internet\d?):(\d+)", d["dist"]):
                cnt[DNN_SLOT[k]] = int(v[0]) if len(v) == 3 else int(v)
            if msg == "v6 hot slot relief" and sum(cnt.values()) == 0: continue     # all-zero map = relief bookkeeping, not a count
            dists.append((t, cnt))
    # harness arrival / departure events
    ue_slot = {}; ev = []
    for line in open(f"{P2}/trace_v7_{run}.log"):
        m = re.match(r"\[(\d\d):(\d\d):(\d\d)\] min(\d+): UE-(\d+) (arrives on (internet\d?)|departs)", line)
        if not m: continue
        hh, mm, ss = int(m[1]), int(m[2]), int(m[3]); t = (t0.replace(hour=hh, minute=mm, second=ss) - t0).total_seconds() / 60.0
        if t < -1: t += 24 * 60
        ue = int(m[5])
        if m[7]: ue_slot[ue] = DNN_SLOT[m[7]]; ev.append((t, +1, DNN_SLOT[m[7]], ue))
        else: ev.append((t, -1, ue_slot.get(ue), ue))
    # reconstruct victim-slot count: anchor at each dist sample, apply events in between
    pts = []  # (t, count)
    anchors = sorted([(t, c.get(VICTIM, 0)) for t, c in dists])
    def anchor_before(t):
        prev = [a for a in anchors if a[0] <= t]
        return prev[-1] if prev else None
    a = anchor_before(W0 - 1)
    if a is None: a = anchors[0]
    t, n = a; pts.append((t, n))
    stream = sorted([e for e in ev if e[0] > t] + [(x[0], 0, None, None) for x in anchors if x[0] > t])
    for e in stream:
        if e[1] == 0:
            n = dict(anchors)[e[0]]; pts.append((e[0], n)); continue
        if e[2] == VICTIM: n += e[1]
        elif e[2] is None and e[1] < 0: print(f"  note {run}: departure of UE-{e[3]} at {e[0]:.2f} min has no known slot (warm-in UE); ignored")
        pts.append((e[0], n))
    return dict(one=one, pm=pm, orders=orders, readys=readys, dists=anchors, victim=pts, ue_slot=ue_slot, ev=ev)

data = {arm: load(run) for arm, run in RUNS}
for arm, run in RUNS:
    d = data[arm]
    print(f"{arm} {run}: minutes 18-22 ready", [d['pm'][m]['ready'] for m in range(18, 23)], "oob38", [d['pm'][m]['oob38'] for m in range(18, 23)],
          "viol", [m for m in range(18, 23) if d['pm'][m]['viol']], "orders", [round(x, 2) for x in d['orders'] if W0 <= x <= W1],
          "ready events", [round(x, 2) for x in d['readys'] if W0 <= x <= W1], "dist samples", [(round(t, 2), n) for t, n in d['dists'] if W0 - 1 <= t <= W1 + 1])
    arr = [e for e in d['ev'] if e[1] > 0 and 20 <= e[0] < 21]; print(f"  arrivals in minute 20: {len(arr)} ->", sorted(e[2] for e in arr))

fig, axes = plt.subplots(4, 3, figsize=(7.0, 3.3), sharex=True, gridspec_kw={"height_ratios": [1.0, 0.9, 1.0, 1.0], "hspace": 0.1, "wspace": 0.26})
for j, (arm, run) in enumerate(RUNS):
    d = data[arm]; col = C.ARMS[arm][1]
    for i in range(4):
        ax = axes[i, j]
        for m in range(int(W0), int(W1)):
            if d["pm"][m]["viol"]: ax.axvspan(m, m + 1, color="#F2D4D4", lw=0, zorder=0)
        ax.set_xlim(W0, W1); ax.grid(axis="y", lw=0.4, alpha=0.3)
        for sp in ("top", "right"): ax.spines[sp].set_visible(False)
    # 1 active UEs
    ax = axes[0, j]; xs = [t for t, ue, _, _ in d["one"] if W0 <= t <= W1 and ue is not None]; ys = [ue for t, ue, _, _ in d["one"] if W0 <= t <= W1 and ue is not None]
    ax.step(xs, ys, where="post", color="#222222", lw=1.0); ax.set_ylim(25, 40)
    ax.set_title(f"{C.ARMS[arm][0].split(' (')[0]}, run {run}", pad=2, fontsize=8)
    # 2 ready slots + events
    ax = axes[1, j]; mins = list(range(int(W0), int(W1) + 1)); rd = [d["pm"][min(m, 59)]["ready"] for m in mins]
    ax.step(mins, rd, where="post", color=col, lw=1.4); ax.set_ylim(5.5, 8.6); ax.set_yticks([6, 7, 8])
    for t in d["orders"]:
        if W0 <= t <= W1: ax.plot([t], [rd[int(t) - int(W0)] + 0.35], marker="v", ms=4, color="#444444", zorder=5)
    for t in d["readys"]:
        if W0 <= t <= W1: ax.plot([t], [8.35], marker="^", ms=4, color=col, zorder=5)
    # 3 victim slot count
    ax = axes[2, j]; pts = [(t, n) for t, n in d["victim"] if t <= W1 + 0.01]
    if pts and pts[0][0] > W0: pts = [(W0, pts[0][1])] + pts
    pts = [(max(W0, t), n) for t, n in pts]
    ax.step([t for t, _ in pts] + [W1], [n for _, n in pts] + [pts[-1][1]], where="post", color=col, lw=1.4)
    ax.axhline(5, ls="--", lw=0.7, color="#888888")
    for t, c in d["dists"]:
        if W0 <= t <= W1: ax.plot([t], [c], marker="o", ms=3.5, color="#222222", zorder=5)
    ax.set_ylim(2.5, 6.8); ax.set_yticks([3, 4, 5, 6])
    # 4 overflow bars + loss line
    ax = axes[3, j]
    ax.bar([m + 0.5 for m in range(int(W0), int(W1))], [d["pm"][m]["oob38"] / 1e3 for m in range(int(W0), int(W1))], width=0.9, color=col, alpha=0.55, lw=0)
    ax.set_ylim(0, max(1.0, max(d["pm"][m]["oob38"] / 1e3 for m in range(18, 22)) * 1.15))
    ax2 = ax.twinx(); xs = [t for t, _, l, _ in d["one"] if W0 <= t <= W1 and l is not None]; ys = [l for t, _, l, _ in d["one"] if W0 <= t <= W1 and l is not None]
    ax2.plot(xs, ys, color="#B22222", lw=0.8); ax2.set_ylim(0, max(0.5, max(ys) * 1.1 if ys else 0.5))
    ax2.axhline(0.1, ls=":", lw=0.6, color="#B22222")
    for sp in ("top",): ax2.spines[sp].set_visible(False)
    ax2.tick_params(axis="y", labelsize=6.5, colors="#B22222")
    if j == 2: ax2.set_ylabel("e2e loss per s (%)", color="#B22222", fontsize=7)
    ax.set_xlabel("minute since formal start")
axes[0, 0].set_ylabel("active UEs"); axes[1, 0].set_ylabel("ready slots\n(of 8)"); axes[2, 0].set_ylabel("UEs on\nslot .38"); axes[3, 0].set_ylabel("overflow on .38\n(kpkt / min)")
h = [Line2D([], [], marker="v", color="#444444", ls="", ms=4, label="slot order (daemon)"), Line2D([], [], marker="^", color="#777777", ls="", ms=4, label="slot ready"),
     Line2D([], [], marker="o", color="#222222", ls="", ms=3.5, label="daemon per-slot sample"), Line2D([], [], color="#888888", ls="--", lw=0.7, label="5-UE knee"),
     Line2D([], [], color="#B22222", lw=0.8, label="e2e loss per s"), plt.Rectangle((0, 0), 1, 1, color="#F2D4D4", label="SLO-violating minute")]
fig.legend(handles=h, loc="upper center", ncol=6, fontsize=6, frameon=False, bbox_to_anchor=(0.5, 1.02), handlelength=1.4, columnspacing=1.0)
fig.subplots_adjust(top=0.88, bottom=0.12, left=0.085, right=0.945)
C.save(fig, "fig_t4_burst.pdf")
if len(sys.argv) > 1: fig.savefig(sys.argv[1], dpi=160)
