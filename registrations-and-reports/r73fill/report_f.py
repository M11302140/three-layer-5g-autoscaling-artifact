#!/usr/bin/env python3
"""spec §4.141: render REPORT.md from out/f.json (+ out/b2.json) and compute the Table X verdicts of the planner on t3/t5/t7 against the
deployed-knob baselines (rq groups MAIN *), the same-target B6 0.775 on t3 (spec §4.121 H, r493/r505) and CR. No new hardware computation."""
import json, csv, numpy as np
R='/home/user/experiment/qsim/r73fill'; o=json.load(open(f'{R}/out/f.json')); b2=json.load(open(f'{R}/out/b2.json'))
rq=[r for r in csv.DictReader(open('/home/user/experiment/paper_out_new/rq/rq_metrics.csv'))]
def grp(g):
    rs=[r for r in rq if r['group']==g]; c=[float(r['alloc_vm']) for r in rs]; v=[60-int(r['slo']) for r in rs]
    return dict(n=len(rs),cost=float(np.mean(c)),lo=min(c),hi=max(c),viol=float(np.mean(v)),vlo=min(v),vhi=max(v),flaps=float(np.mean([int(r['flaps']) for r in rs])))
def verdict(a,b):
    cc=(a['hi']<b['lo']) or (b['hi']<a['lo']); cs=0 if not cc else (-1 if a['cost']<b['cost'] else 1)
    dv=a['viol']-b['viol']; vs=0 if abs(dv)<1-1e-9 else (-1 if dv<0 else 1)
    if cs==0 and vs==0: return 'equal'
    if cs<=0 and vs<=0: return 'dominates'
    if cs>=0 and vs>=0: return 'dominated'
    return 'trade-off'
C=o['cells']; A=o['A']; A3=o['A3']; B=o['B']; CS=o['C_summary']; F=o['fidelity']; HW=o['hw']
BASE={'B4c2':lambda t: grp(f'MAIN {t} B4c2'),'B5c1':lambda t: grp(f'MAIN {t} B5c1 (q11)'),'B6':lambda t: grp(f'MAIN {t} B6 u=0.70')}
B6ST_T3=dict(n=2,cost=1179.0,lo=1174,hi=1184,viol=3.5,vlo=3,vhi=4,flaps=3.0)   # same-target B6 0.775 on t3 (numbers.md §7; r493/r505)
T4={}   # Table X rows for t3/t5/t7
for tn in ('t3','t5','t7'):
    for arm in ('S4p2','S4p05'):
        a=C[f'{tn}|{arm}']; row={k:verdict(a,fn(tn)) for k,fn in BASE.items()}
        if tn=='t3': row['B6*']=verdict(a,B6ST_T3)
        row['CR']=A[f'{tn}|{arm}']['verdict']; T4[f'{tn}|{arm}']=row
# same-target rows on t4/t8 from f.json A3 (planner side)
for tn in ('t4','t8'):
    for arm in ('S4p2','S4p05'):
        T4[f'{tn}|{arm}']={'B4*':A3[f'{tn}|B4A_375_300|vs {arm}']['verdict'],'B6*':A3[f'{tn}|B6c5_h|vs {arm}']['verdict']}
json.dump(T4,open(f'{R}/out/table4.json','w'),indent=1)
out=[]; P=out.append
P("# r73fill — the 22 fill-in runs: judgement (spec §4.141; 2026-11-02)\n")
P("Runs: 22 valid of 24 started (r582–r605). r585 (B4 3.75/300, t8; ng-dead) and r591 (planner 2 %, t7; warm-in gate failed three times → chain-abort, driver STOP under §4.81 condition 3, resumed after a SCP→AMF restart on worker-0 by the author's ruling) were harness faults, replaced by r604 / r605 under the registered rule. Probes p38 / p39: p99 397 µs, e2e 0.010 %. All 22 valid runs have flags ok.")
P("Hardware metrics: paper_out_new/rq_metrics (groups \"R73 *\"; alloc_vm = VM-exists accounting; flaps = same-layer reversal within 10 min; violation minutes = 0-based minutes with loss > 0.1 % or p99 > 1 ms). Predictions (a)(b)(c)(d): r73fill/out/predict.json (registered 10-31, spec §4.141 item 2). CR references: rq groups MAIN t3/t5/t7 S4b (2 %) / S4a (0.5 %). Frozen simulator md5 unchanged (3daf1387 7a2b02ec ecdfff61 4697713c b24eae16 edb8e00c).\n")
P("## 1. Cells\n\n| cell | runs | viol/run (range) / alloc_vm (range) | violation minutes | flaps | start hw (slot/VY/WK) | registered start | own initial_fleet | pred a | err % | pred b | err % | pred c | err % | pred d | err % |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
def fmt(st):
    v=f"{st['viol']:.2f}" if st['viol']%1 else f"{int(st['viol'])}"
    if st['n']>1 and st['vhi']>st['vlo']: v+=f" ({st['vlo']}–{st['vhi']})"
    c=f"{st['cost']:.0f}"
    if st['n']>1: c+=f" ({st['lo']:.0f}–{st['hi']:.0f})"
    return f"{v} / {c}"
def pe(p): return "n/a | n/a" if p is None else f"{p['alloc_vm']:.1f} | {p['err_pct']:+.2f}"
for k,c in C.items():
    P(f"| {k} | {'/'.join(c['runs'])} | {fmt(c)} | {c['viol_lists']} | {c['flaps_each']} | {c['start']} | {c['reg_start']} | {c['own_start']} | " + " | ".join(pe(c['pred'][v]) for v in 'abcd') + " |")
P("\nCR references (hardware): " + "; ".join(f"{k}: {fmt(v)}, flaps {v['flaps_each']}, viol {v['viol_lists']}" for k,v in o['cr'].items()) + ".\n")
P("## 2. Endpoints (registered §4.141 item 4)\n")
P("**(A) Table X verdicts of the planner against CR on t3 / t5 / t7 (rule: a cost difference counts only when the run ranges do not overlap, a violation difference only when ≥ 1 minute per run), against the registered expectation (item 3):**\n\n| cell | planner cost (range) / viol / flaps | CR cost (range) / viol / flaps | Δcost % | Δviol | verdict | expected | consistent |\n|---|---|---|---|---|---|---|---|")
for k,a in A.items():
    p=a['planner']; c=a['cr']; P(f"| {k} | {p['cost']:.1f} ({p['range'][0]:.0f}–{p['range'][1]:.0f}) / {p['viol']:.2f} / {p['flaps']:.2f} | {c['cost']:.1f} ({c['range'][0]:.0f}–{c['range'][1]:.0f}) / {c['viol']:.2f} / {c['flaps']:.2f} | {a['dcost_pct']:+.2f} | {a['dviol']:+.2f} | **{a['verdict']}** | {a['expected']} | {'yes' if a['consistent'] else 'no'} |")
P(f"\nConsistent: **{sum(1 for a in A.values() if a['consistent'])} / 6** (t3 both points). t5 has one run per arm, so every cost difference 'counts' under the rule: the planner is 4 and 2 core-min (0.28 % and 0.14 %) dearer than CR at zero violations on both sides → 'dominated' by the letter of the rule where 'equal' was expected. t7 2 %: r586 paid five placement-overflow minutes (35–39, loss 0.18–0.60 % at the full fleet 8/3/4 during departures; r599 and r605 none), so the mean violation difference is +1.67 and the cost is 0.55 % above CR outside both ranges → dominated. t7 0.5 %: cost ranges identical (1426–1429), violations 0 vs 0.33 → equal. Flaps are lower than CR's in all six cells.\n")
P("**(iii) same-target B4 / B6 on t4 / t8 against the planner (verdict from the planner's side):**\n\n| cell | planner cost (range) / viol / flaps | baseline cost (range) / viol / flaps | planner − baseline % | Δviol | verdict | expected | consistent |\n|---|---|---|---|---|---|---|---|")
for k,a in A3.items():
    p=a['planner']; c=a['baseline']; P(f"| {k} | {p['cost']:.1f} ({p['range'][0]:.0f}–{p['range'][1]:.0f}) / {p['viol']:.2f} / {p['flaps']:.2f} | {c['cost']:.1f} ({c['range'][0]:.0f}–{c['range'][1]:.0f}) / {c['viol']:.2f} / {c['flaps']:.2f} | {a['planner_minus_pct']:+.2f} | {a['dviol']:+.2f} | **{a['verdict']}** | {a['expected'] or '—'} | {'—' if a['consistent'] is None else ('yes' if a['consistent'] else 'no')} |")
P("\nt4 at 2 %: trade-off as registered (planner 3.0 / 2.8 % cheaper, 1.5 / 2.0 more violation minutes). t4 at 0.5 %: both same-target baselines are 0.7 / 1.0 % cheaper outside the run ranges at 0.5 / 0 violation minutes (the planner's 0), so the planner is dominated by the rule, where 'equal or planner dominates' was expected (the registered model note already predicted B4 / B6 cheaper by 0.7 / 1.1 %). t8 B6 at 2 %: the planner's runs spread 1007–1078 and contain B6's 1009–1016, so its +3.3 % cost does not count while its 1.17 fewer violation minutes do → 'dominates' by the rule where trade-off was expected; at 0.5 % trade-off as expected. t8 B4 (no expectation registered): 8.4 % cheaper than the planner at 2 % with 0.67 more violation minutes (< 1 → does not count) → the planner is dominated; at 0.5 % trade-off (B4 14 % cheaper, 3.0 more violation minutes).\n")
P("**(B) ±2 % hits of the four versions** (cell means; per run in brackets; B4 has no fleet model → (b) over 8 cells / 18 runs):\n")
for v,b in B.items(): P(f"- ({v}) {b['cell_within2']} / {b['cell_n']} cells [{b['run_within2']} / {b['run_n']} runs]; max |cell error| {b['max_abs_cell_err']:.2f} %; cell errors " + ", ".join(f"{k} {e:+.2f}" for k,e in b['cell_err'].items()))
P("\nThe one cell outside ±2 % is the same-target B4 3.75/300 on t8 (predicted 913.0, measured 965 / 964–966, −5.39 % for (a) = (c) = (d); the baseline predictions share one per-slot model). All six planner cells are within 0.66 % (max t3 0.5 %: +0.66 %).\n")
P(f"**(C) weak dominance over CR (Table 1 rule: cost not higher, violation minutes not more, at least one strictly better):** **{CS['n_two']} of {CS['cells']} paired cells** (the six t4 / t6 / t8 cells of the C block; none of the six new cells). Counting flaps as a third criterion changes nothing ({CS['n_three']} / {CS['cells']}). Excluding the single-run t5 cells: {CS['n_two_no_t5']} / 10. Per new cell: t3 2 % cost higher (+1.9 %); t3 0.5 % violations more (+3.3); t5 2 % / 0.5 % cost higher by 4 / 2 core-min; t7 2 % cost higher (+0.6 %) and violations more (+1.7); t7 0.5 % cost higher by 0.67 core-min (1427.7 vs 1427.0; under a 1 core-min tolerance, the rounding unit of alloc_vm, it would count → 7 / 12).\n")
P("## 3. Table X rows for the planner on t3 / t5 / t7 (same rule; deployed-knob baselines from rq groups MAIN *, B6* = same-target 0.775 on t3 from spec §4.121 H) and same-target columns on t4 / t8\n\n| cell | B4c2 | B5c1 | B6 (u 0.70) | B6* 0.775 | B4* 3.75/300 | CR |\n|---|---|---|---|---|---|---|")
for k,row in T4.items(): P(f"| {k} | {row.get('B4c2','—')} | {row.get('B5c1','—')} | {row.get('B6','—')} | {row.get('B6*','—')} | {row.get('B4*','—')} | {row.get('CR','—')} |")
P("\nBaseline references used (mean viol / cost (range)): " + "; ".join(f"{t} {b}: {fmt(fn(t))}" for t in ('t3','t5','t7') for b,fn in BASE.items()) + f"; t3 B6 0.775: {fmt(B6ST_T3)}.\n")
P("## 4. Start audit I1 (22 runs added)\n")
I=o['I1']; S=o['I1_summary']
P(f"Hardware minute-0 fleet (slots / VyOS / workers) equal to the registered start in {S['same_reg']} / 22 runs and to the simulator's own initial_fleet in {S['same_own']} / 22. Mismatches:\n\n| run | trace | arm | hw | registered | own initial_fleet |\n|---|---|---|---|---|---|")
for x in I:
    if not (x['same_reg'] and x['same_own']): P(f"| {x['run']} | {x['trace']} | {x['arm']} | {'/'.join(map(str,x['hw']))} | {'/'.join(map(str,x['reg']))} | {'/'.join(map(str,x['own']))} |")
P("\nt7 2 %: align_fleet reached 7 slots / 4 workers but did not add the third VyOS (t7_v7r586.log: 'start fleet rep 7 vy 2 wk 4'); the daemon added it in minute 2 in all three runs; the hardware start equals the planner's own initial_fleet (7/2/4), the registered prediction used the alignment target 7/3/4 (error +0.30 %). t7 0.5 %: hardware = registered alignment 7/3/4, the planner's own initial_fleet is 8/3/4. t4 B6: both runs start at 6 slots where the simulator starts at 5 (warm-in convergence); t4 B4 r602 at 5 where the simulator starts at 6.\n")
P("## 5. Violation classes (B2 rule, classify_b2.classify) and fleet-level hits\n")
for r,cls in b2.items(): P(f"- {r} ({HW[r]['trace']} {HW[r]['arm']}): {cls}")
P("\nFleet-shortage minutes vs the fleet-level prediction (b): planner t3 2 % and 0.5 % (b) [3, 4, 5] → hardware fleet-shortage minutes 3, 4, 5 in 6 / 6 runs (hit 18, miss 0, false alarm 0); minutes 6–7 (and 10, 12 in r590) are placement overflow / other. t7 2 %: (b) none; r586's minutes 35–39 are placement overflow at the full fleet. t5, t7 0.5 %: none / none. Same-target B6 t8 (b) has no violation list; hardware minute 20 is fleet shortage in all four B4 / B6 t8 runs, 21–23 placement / other. t4 B4 r602 minute 1: placement.\n")
P("## 6. Fidelity totals\n")
P(f"Version (a): {F['new_within2']} / {F['new_cells']} new cells within ±2 % (outside: {F['outside']}); with the 35 earlier cells: **{F['total_within2']} / {F['total_cells']}**. Planner cells: 8 + 6 = 14, max |error| {max(0.42,F['planner_max_abs']):.2f} % (new cells " + ", ".join(f"{k} {e:+.2f}" for k,e in F['errs'].items() if 'S4p' in k) + ").\n")
P("## 7. Per-run table (22 runs)\n\n| run | phase | trace | arm | SLO/60 | worst loss % | p99 max µs | alloc_vm | burned | flaps | acts vy/wk/up | violation minutes | start s/v/w | wk/vy/slot-min |\n|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
for k in sorted(HW):
    h=HW[k]; P(f"| {k} | {h['phase']} | {h['trace']} | {h['arm']} | {h['slo']} | {h['worst']} | {h['p99max']} | {h['alloc_vm']:.0f} | {h['burned']} | {h['flaps']} | {h['acts_vy']}/{h['acts_wk']}/{h['acts_up']} | {h['viol']} | {'/'.join(map(str,h['start']))} | {h['wk_min']}/{h['vy_min']}/{h['slot_min']} |")
P("\n## 8. Summary\n\n- (A) 2 / 6 cells consistent with the registered expectation (t3 trade-off ×2); t5 dominated ×2 (n = 1, 4 / 2 core-min), t7 2 % dominated (r586's five placement minutes; +0.55 % cost), t7 0.5 % equal.\n- (B) (a)(c)(d) 9 / 10 cells (20 / 22 runs), (b) 8 / 8 (18 / 18); outside: same-target B4 on t8, −5.4 %.\n- (C) weakly dominates CR in 6 of 12 paired cells (the t4 / t6 / t8 cells); none of t3 / t5 / t7 (t7 0.5 % misses by 0.67 core-min).\n- (iii) t4 2 % trade-off ×2 as registered; t4 0.5 % dominated by both same-target baselines (0.7 / 1.0 % cheaper); t8 B6 2 % 'dominates' by the rule (cost inside the planner's range), 0.5 % trade-off; t8 B4 dominated at 2 %, trade-off at 0.5 %.\n- Files: out/f.json, out/b2.json, out/table4.json (numbers), eval_f.py (computation), report_f.py (this file).")
open(f'{R}/REPORT.md','w').write("\n".join(out)+"\n"); print("written"); print(json.dumps(T4,indent=0))
