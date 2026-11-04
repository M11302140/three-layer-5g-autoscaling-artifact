#!/usr/bin/env python3
"""(docstring removed)"""
import sys, json, glob, os, collections
sys.path.insert(0, '/home/user/experiment/qsim')
import v8sim_b6 as B6, v8sim7 as M
E = '/home/user/experiment'; D = '/home/user/hhro-daemon/cmd/hhro-daemon/testdata/b6equiv'
FILES = {"t1": "40", "t2": "pm", "t3": "t3", "t4": "t4", "t5": "t5", "t6": "t6", "t7": "t7"}
cfg = M.cfg_measured(); mk = B6.load_models()
names = sys.argv[1:] or sorted(os.path.basename(p)[:-5] for p in glob.glob(f'{D}/*.json'))
tot_cells = 0
for tn in names:
    r = json.load(open(f'{D}/{tn}.json')); u = float(r.get("u", 0.70))
    ue = json.load(open(f"{E}/trace_ue_60min_v3_{FILES[tn]}.json"))["ue"][:60]
    ev = []; q = B6.sim_b6(ue, cfg, u, mk, ev=ev)
    qev = collections.Counter((int(t) // 60, f"{a}:{k}") for t, a, k in ev)
    dev = collections.Counter()
    for e in r["events"]:
        tick, a, k = e.split(":"); dev[(tick and int(tick) * 30 // 60, f"{a}:{k}")] += 1
    keys = sorted(set(qev) | set(dev)); nd = [k for k in keys if qev.get(k, 0) != dev.get(k, 0)]
    first = f"min{nd[0][0]} {nd[0][1]}: qsim {qev.get(nd[0],0)} daemon {dev.get(nd[0],0)}" if nd else "none"
    tot_cells += len(nd)
    print(f"=== {tn} u={u:.2f}: qsim SLO {q['slo']}/60 alloc {q['alloc']:.0f} worst {q['worst']:.2f}% acts {sum(qev.values())} | daemon SLO {r['slo']}/60 alloc {r['alloc']:.0f} worst {r['worst']:.2f}% acts {sum(dev.values())} | differing (min,act) cells {len(nd)} | first diff: {first}")
    if nd:
        print("    diff cells:", ", ".join(f"m{m} {a} q{qev.get((m,a),0)}/d{dev.get((m,a),0)}" for m, a in nd[:12]))
print(f"TOTAL differing cells: {tot_cells}")
