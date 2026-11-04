#!/usr/bin/env python3
"""r62cf Task F2: emergency-rule parity. Every arm on t3, t4, t6, t7 (trace_ue_60min_v3_tX.json "ue"[:60]), default start fleet
(v8sim11.initial_fleet), frozen PHYS (R38 rule on), with (emerg=True) and without (emerg=False) the daemon EmergencyV6 rule.
emerg=False is checked to be bit-identical to the frozen v8sim11.run."""
import timeit  # stdlib first
import sys, os, json, time
os.chdir("/home/user/experiment/qsim")   # v8sim3 opens prior_traces.json relative to cwd
sys.path.insert(0, '/home/user/experiment/qsim/r62cf'); sys.path.insert(0, '/home/user/experiment/qsim')
import v8sim11_emerg as VE
sys.path.remove('/home/user/experiment/qsim/r62cf')
import v8sim11 as V
E = '/home/user/experiment'
TR = {t: json.load(open(f'{E}/trace_ue_60min_v3_{t}.json'))["ue"][:60] for t in ("t3", "t4", "t6", "t7")}
ARMS = [("S4a", {}), ("S4b", {}), ("v6", {}), ("B4c2", {}), ("B5c1", {}), ("B6", {"u": 0.70})]
PH = None if len(sys.argv) < 2 or sys.argv[1] == "on" else {"knee38": 5}
t0 = time.time(); rows = []
for arm, kw in ARMS:
    for tn, ue in TR.items():
        ref = V.run(ue, arm, phys=PH, **kw); off = VE.run(ue, arm, phys=PH, emerg=False, **kw); on = VE.run(ue, arm, phys=PH, emerg=True, **kw)
        same = ref["slo"] == off["slo"] and abs(ref["alloc_vm"] - off["alloc_vm"]) < 1e-9 and ref["viol"] == off["viol"]
        rows.append(dict(arm=arm, trace=tn, equiv=same, slo_off=off["slo"], alloc_off=off["alloc_vm"], viol_off=[int(x) for x in off["viol"]],
                         slo_on=on["slo"], alloc_on=on["alloc_vm"], viol_on=[int(x) for x in on["viol"]], fires=on["emerg_fires"], latched=on["emerg_latched_ticks"], skips=on["emerg_skips"],
                         acts_off=sum(1 for e in off["events"] if e[1] in ("out", "in")), acts_on=sum(1 for e in on["events"] if e[1] in ("out", "in"))))
        r = rows[-1]
        print(f"{arm:5s} {tn}: equiv {same} | off SLO {r['slo_off']}/60 alloc {r['alloc_off']:.0f} viol {r['viol_off']} | on SLO {r['slo_on']}/60 alloc {r['alloc_on']:.0f} viol {r['viol_on']} | latched ticks {r['latched']} skips {r['skips']} fires {r['fires']}", flush=True)
json.dump(rows, open(f'/home/user/experiment/qsim/r62cf/f2_results{"" if PH is None else "_r38off"}.json', 'w'), indent=0, default=float)
print(f"total {time.time()-t0:.1f}s")
