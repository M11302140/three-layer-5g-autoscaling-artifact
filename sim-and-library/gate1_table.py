#!/usr/bin/env python3
"""(docstring removed)"""
import sys, csv, json, re, os, statistics as st
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import v8sim11 as V
E = "/home/user/experiment"; P = f"{E}/p2"; RQ = f"{E}/paper_out_new/rq/rq_metrics.csv"
TRF = {"t1": "trace_ue_60min_v3_40.json", "t2": "trace_ue_60min_v3_pm.json", "t4": "trace_ue_60min_v3_t4.json"}

RUNS = {
 ("S4a", "t1"): ["r264", "r265", "r266"], ("S4a", "t2"): ["r250", "r254", "r260"], ("S4a", "t4"): ["r300", "r312", "r317"],
 ("S4b", "t1"): ["r251", "r255", "r261"], ("S4b", "t2"): ["r252", "r256", "r262"], ("S4b", "t4"): ["r303", "r314", "r322"],
 ("v6", "t1"): ["r267", "r268"], ("v6", "t2"): ["r248", "r258"], ("v6", "t4"): ["r301", "r318", "r321"],
 ("B4c2", "t1"): ["r272"], ("B4c2", "t2"): ["r276"], ("B4c2", "t4"): ["r308", "r313", "r320"],
 ("B5c1", "t1"): ["r274"], ("B5c1", "t2"): ["r278", "r287"], ("B5c1", "t4"): ["r310", "r315", "r319"],
 ("B6", "t1"): ["r285"], ("B6", "t2"): ["r286"], ("B6", "t4"): ["r305", "r311", "r316"],
}
def measured():
    m = {}
    for r in csv.DictReader(open(RQ)): m[r["run"]] = r
    return m
def start_fleet(run):
    """(docstring removed)"""
    rows = list(csv.DictReader(open(f"{P}/trace_v7_{run}.csv")))
    r0 = rows[0]; vy = int(float(r0["vyos_n"])); wk = int(float(r0["worker_n"]))
    up = None
    try:
        for line in open(f"{P}/v7{run}_daemon.log"):
            if '"msg":"mid"' in line:
                d = json.loads(line); up = int(d["up_rep"]); break
    except FileNotFoundError: pass
    if up is None:
        mm = re.match(r"(\d+)/", r0.get("eupf_cov", "")); up = int(mm[1]) if mm else 2
    return (up, vy, wk)
def meas_viol(run):
    out = []
    for r in csv.DictReader(open(f"{P}/trace_v7_{run}.csv")):
        try:
            if float(r["e2e_pct"]) > 0.1 or float(r["lat_p99_us"]) > 1000 or r["lat_p99_us"] in ("", "nan"): out.append(int(float(r["min"])))
        except ValueError: pass
    return out
def main():
    phys = {}
    args = sys.argv[1:]
    if args and args[0] == "--phys":
        for kv in args[1:]: k, v = kv.split("="); phys[k] = float(v) if "." in v else int(v)
    meas = measured(); TR = {t: json.load(open(f"{E}/{f}"))["ue"][:60] for t, f in TRF.items()}
    print(f"# gate-1 table (v8sim11; phys overrides {phys})")
    print("| arm | trace | runs | meas alloc_vm (mean) | sim alloc_vm | cost err | meas viol/run | sim viol | Δviol | sim viol minutes | start fleet |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    rows = []
    for (arm, tn), runs in RUNS.items():
        runs = [r for r in runs if r in meas]
        if not runs: continue
        ma = st.mean(float(meas[r]["alloc_vm"]) for r in runs); mv = st.mean(60 - int(meas[r]["slo"]) for r in runs)
        sims = []
        for r in runs:
            stf = start_fleet(r); res = V.run(TR[tn], arm, start=stf, phys=phys); sims.append((res, stf))
        sa = st.mean(x[0]["alloc_vm"] for x in sims); sv = st.mean(60 - x[0]["slo"] for x in sims)
        err = 100 * (sa - ma) / ma
        print(f"| {arm} | {tn} | {' '.join(runs)} | {ma:.0f} | {sa:.0f} | {err:+.1f}% | {mv:.2f} | {sv:.2f} | {sv-mv:+.2f} | sim {[x[0]['viol'] for x in sims]} meas {[meas_viol(r) for r in runs]} | {[x[1] for x in sims]} |")
        rows.append((arm, tn, ma, sa, err, mv, sv))
    print("\n## ranking by violation minutes per trace (measured vs sim)")
    for tn in ("t1", "t2", "t4"):
        rr = [x for x in rows if x[1] == tn]
        print(f"- {tn}: measured {[a for a,*_ in sorted(rr, key=lambda x: x[5])]} | sim {[a for a,*_ in sorted(rr, key=lambda x: x[6])]}")
    bad = [(a, t, e, mv, sv) for a, t, _, _, e, mv, sv in rows if abs(e) > 2 or abs(sv - mv) > 1]
    print(f"\ncost >2% or |Δviol|>1: {bad if bad else 'none'}")
if __name__ == "__main__": main()
