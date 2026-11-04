#!/usr/bin/env python3
"""r62cf Task F1: J = C_alloc + alpha*N_act + beta*N_flap per run (t6, t7); S4b saving vs B4c2/B5c1/B6.
N_act = vy_create+vy_delete+wk_create+wk_delete+slot_start+slot_stop (ops_per_run.csv, actual-actuation definition);
N_flap = flaps (ops_per_run.csv); C_alloc = alloc_vm (rq_metrics.csv, by run id)."""
import csv, json, statistics as st
E = '/home/user/experiment/paper_out_new'
ops = {r["run"]: r for r in csv.DictReader(open(f'{E}/ops/ops_per_run.csv'))}
alloc = {r["run"]: float(r["alloc_vm"]) for r in csv.DictReader(open(f'{E}/rq/rq_metrics.csv')) if r["group"].startswith("MAIN ")}
ACT = ["vy_create", "vy_delete", "wk_create", "wk_delete", "slot_start", "slot_stop"]
rows = []
for run, r in ops.items():
    if r["trace"] not in ("t6", "t7") or r["role"] != "valid": continue
    rows.append(dict(run=run, trace=r["trace"], arm=r["arm"], C=alloc[run], N_act=sum(int(r[k]) for k in ACT), N_flap=int(r["flaps"])))
A = [0, 1, 3, 10]; Bt = [0, 5, 15]; arms = ["S4a", "S4b", "v6", "B4c2", "B5c1", "B6", "B1"]
out = []
P = lambda s: (print(s), out.append(s))
P("## F1 per-run inputs (t6, t7)\n\n| run | trace | arm | alloc_vm | N_act | N_flap |\n|---|---|---|---|---|---|")
for r in sorted(rows, key=lambda r: (r["trace"], r["arm"], r["run"])): P(f"| {r['run']} | {r['trace']} | {r['arm']} | {r['C']:.0f} | {r['N_act']} | {r['N_flap']} |")
P("\n## F1 per-arm means\n\n| trace | arm | n | alloc_vm | N_act | N_flap |\n|---|---|---|---|---|---|")
M = {}
for tr in ("t6", "t7"):
    for a in arms:
        s = [r for r in rows if r["trace"] == tr and r["arm"] == a]
        if not s: continue
        M[(tr, a)] = (st.mean(r["C"] for r in s), st.mean(r["N_act"] for r in s), st.mean(r["N_flap"] for r in s), len(s))
        P(f"| {tr} | {a} | {len(s)} | {M[(tr,a)][0]:.1f} | {M[(tr,a)][1]:.2f} | {M[(tr,a)][2]:.2f} |")
def J(tr, a, al, be): c, n, f, _ = M[(tr, a)]; return c + al * n + be * f
P("\n## F1 mean-J saving of S4b = J(baseline) - J(S4b), core-min/run (percent of baseline J); **bold ≤ 0 = saving gone or reversed**\n")
for tr in ("t6", "t7"):
    P(f"\n### {tr}\n\n| alpha | beta | J(S4b) | vs B4c2 | vs B5c1 | vs B6 |\n|---|---|---|---|---|---|")
    for al in A:
        for be in Bt:
            js = J(tr, "S4b", al, be); cells = []
            for b in ("B4c2", "B5c1", "B6"):
                jb = J(tr, b, al, be); d = jb - js; c = f"{d:+.1f} ({100*d/jb:+.2f}%)"
                cells.append(f"**{c}**" if d <= 0 else c)
            P(f"| {al} | {be} | {js:.1f} | " + " | ".join(cells) + " |")
P("\n## F1 break-even alpha (saving = 0) for each beta: alpha* = (dC - beta*dFlap)/dAct, dX = X(S4b) - X(baseline) sign-adjusted\n\n| trace | baseline | ΔC (base−S4b) | ΔN_act (S4b−base) | ΔN_flap (S4b−base) | alpha* @beta 0 | @beta 5 | @beta 15 |\n|---|---|---|---|---|---|---|---|")
for tr in ("t6", "t7"):
    for b in ("B4c2", "B5c1", "B6"):
        dC = M[(tr, b)][0] - M[(tr, "S4b")][0]; dA = M[(tr, "S4b")][1] - M[(tr, b)][1]; dF = M[(tr, "S4b")][2] - M[(tr, b)][2]
        al = [((dC - be * dF) / dA if dA > 0 else float("inf")) for be in Bt]
        P(f"| {tr} | {b} | {dC:.1f} | {dA:.2f} | {dF:.2f} | " + " | ".join(f"{x:.2f}" for x in al) + " |")
open('/home/user/experiment/qsim/r62cf/f1_tables.md', 'w').write("\n".join(out) + "\n")
json.dump(rows, open('/home/user/experiment/qsim/r62cf/f1_rows.json', 'w'), indent=0)
