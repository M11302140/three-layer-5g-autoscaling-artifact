# r73fill — the 22 fill-in runs: judgement (spec §4.141; 2026-11-02)

Runs: 22 valid of 24 started (r582–r605). r585 (B4 3.75/300, t8; ng-dead) and r591 (planner 2 %, t7; warm-in gate failed three times → chain-abort, driver STOP under §4.81 condition 3, resumed after a SCP→AMF restart on worker-0 by the author's ruling) were harness faults, replaced by r604 / r605 under the registered rule. Probes p38 / p39: p99 397 µs, e2e 0.010 %. All 22 valid runs have flags ok.
Hardware metrics: paper_out_new/rq_metrics (groups "R73 *"; alloc_vm = VM-exists accounting; flaps = same-layer reversal within 10 min; violation minutes = 0-based minutes with loss > 0.1 % or p99 > 1 ms). Predictions (a)(b)(c)(d): r73fill/out/predict.json (registered 10-31, spec §4.141 item 2). CR references: rq groups MAIN t3/t5/t7 S4b (2 %) / S4a (0.5 %). Frozen simulator md5 unchanged (3daf1387 7a2b02ec ecdfff61 4697713c b24eae16 edb8e00c).

## 1. Cells

| cell | runs | viol/run (range) / alloc_vm (range) | violation minutes | flaps | start hw (slot/VY/WK) | registered start | own initial_fleet | pred a | err % | pred b | err % | pred c | err % | pred d | err % |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| t3|S4p2 | r584/r589/r596 | 3.67 (3–4) / 1159 (1153–1164) | [[3, 4, 5], [3, 4, 5, 6], [3, 4, 5, 6]] | [2, 2, 2] | [[6, 2, 3], [6, 2, 3], [6, 2, 3]] | [6, 2, 3] | [6, 2, 3] | 1160.9 | +0.16 | 1150.8 | -0.71 | 1160.9 | +0.16 | 1160.9 | +0.16 |
| t3|S4p05 | r590/r598/r600 | 5.67 (5–7) / 1182 (1178–1187) | [[3, 4, 5, 6, 7, 10, 12], [3, 4, 5, 6, 7], [3, 4, 5, 6, 7]] | [4, 2, 2] | [[6, 2, 3], [6, 2, 3], [6, 2, 3]] | [6, 2, 3] | [6, 2, 3] | 1189.8 | +0.66 | 1180.4 | -0.13 | 1189.8 | +0.66 | 1183.4 | +0.12 |
| t5|S4p2 | r582 | 0 / 1457 | [[]] | [2] | [[8, 3, 4]] | [8, 3, 4] | [8, 3, 4] | 1457.2 | +0.02 | 1459.1 | +0.15 | 1457.2 | +0.02 | 1458.2 | +0.08 |
| t5|S4p05 | r593 | 0 / 1464 | [[]] | [0] | [[8, 3, 4]] | [8, 3, 4] | [8, 3, 4] | 1464.0 | -0.00 | 1464.0 | -0.00 | 1464.0 | -0.00 | 1462.8 | -0.08 |
| t7|S4p2 | r586/r599/r605 | 1.67 (0–5) / 1395 (1393–1398) | [[35, 36, 37, 38, 39], [], []] | [0, 2, 2] | [[7, 2, 4], [7, 2, 4], [7, 2, 4]] | [7, 3, 4] | [7, 2, 4] | 1399.2 | +0.30 | 1395.6 | +0.05 | 1399.2 | +0.30 | 1397.8 | +0.20 |
| t7|S4p05 | r583/r594/r601 | 0 / 1428 (1426–1429) | [[], [], []] | [5, 8, 5] | [[7, 3, 4], [7, 3, 4], [7, 3, 4]] | [7, 3, 4] | [8, 3, 4] | 1431.1 | +0.24 | 1429.1 | +0.10 | 1431.1 | +0.24 | 1429.7 | +0.14 |
| t4|B4A_375_300 | r597/r602 | 0.50 (0–1) / 1437 (1437–1437) | [[], [1]] | [0, 0] | [[6, 2, 3], [5, 2, 3]] | [6, 2, 3] | [6, 2, 3] | 1438.0 | +0.07 | n/a | n/a | 1438.0 | +0.07 | 1438.0 | +0.07 |
| t4|B6c5_h | r587/r603 | 0 / 1434 (1433–1434) | [[], []] | [2, 2] | [[6, 2, 3], [6, 2, 3]] | [5, 2, 3] | [5, 2, 3] | 1431.7 | -0.12 | 1443.1 | +0.67 | 1431.7 | -0.12 | 1431.7 | -0.12 |
| t8|B4A_375_300 | r592/r604 | 3 (2–4) / 965 (964–966) | [[20, 21], [20, 21, 22, 23]] | [4, 4] | [[4, 2, 2], [4, 2, 2]] | [4, 2, 2] | [4, 2, 2] | 913.0 | -5.39 | n/a | n/a | 913.0 | -5.39 | 913.0 | -5.39 |
| t8|B6c5_h | r588/r595 | 3.50 (3–4) / 1012 (1009–1016) | [[20, 21, 22], [20, 21, 22, 23]] | [5, 5] | [[4, 1, 2], [4, 1, 2]] | [4, 1, 2] | [4, 1, 2] | 997.9 | -1.44 | 1022.3 | +0.97 | 997.9 | -1.44 | 997.9 | -1.44 |

CR references (hardware): t3|S4b: 4.67 (3–6) / 1137 (1133–1143), flaps [7, 7, 7], viol [[3, 4, 5, 6, 7, 9], [3, 4, 5], [3, 4, 5, 6, 7]]; t3|S4a: 2.33 (2–3) / 1233 (1228–1238), flaps [7, 7, 9], viol [[3, 4], [3, 4], [3, 4, 5]]; t5|S4b: 0 / 1453, flaps [5], viol [[]]; t5|S4a: 0 / 1462, flaps [3], viol [[]]; t7|S4b: 0 / 1387 (1386–1390), flaps [7, 7, 6], viol [[], [], []]; t7|S4a: 0.33 (0–1) / 1427 (1426–1429), flaps [7, 7, 7], viol [[], [44], []].

## 2. Endpoints (registered §4.141 item 4)

**(A) Table X verdicts of the planner against CR on t3 / t5 / t7 (rule: a cost difference counts only when the run ranges do not overlap, a violation difference only when ≥ 1 minute per run), against the registered expectation (item 3):**

| cell | planner cost (range) / viol / flaps | CR cost (range) / viol / flaps | Δcost % | Δviol | verdict | expected | consistent |
|---|---|---|---|---|---|---|---|
| t3|S4p2 | 1159.0 (1153–1164) / 3.67 / 2.00 | 1137.0 (1133–1143) / 4.67 / 7.00 | +1.93 | -1.00 | **trade-off** | trade-off | yes |
| t3|S4p05 | 1182.0 (1178–1187) / 5.67 / 2.67 | 1233.3 (1228–1238) / 2.33 / 7.67 | -4.16 | +3.33 | **trade-off** | trade-off | yes |
| t5|S4p2 | 1457.0 (1457–1457) / 0.00 / 2.00 | 1453.0 (1453–1453) / 0.00 / 5.00 | +0.28 | +0.00 | **dominated** | equal | no |
| t5|S4p05 | 1464.0 (1464–1464) / 0.00 / 0.00 | 1462.0 (1462–1462) / 0.00 / 3.00 | +0.14 | +0.00 | **dominated** | equal | no |
| t7|S4p2 | 1395.0 (1393–1398) / 1.67 / 1.33 | 1387.3 (1386–1390) / 0.00 / 6.67 | +0.55 | +1.67 | **dominated** | dominates | no |
| t7|S4p05 | 1427.7 (1426–1429) / 0.00 / 6.00 | 1427.0 (1426–1429) / 0.33 / 7.00 | +0.05 | -0.33 | **equal** | dominates | no |

Consistent: **2 / 6** (t3 both points). t5 has one run per arm, so every cost difference 'counts' under the rule: the planner is 4 and 2 core-min (0.28 % and 0.14 %) dearer than CR at zero violations on both sides → 'dominated' by the letter of the rule where 'equal' was expected. t7 2 %: r586 paid five placement-overflow minutes (35–39, loss 0.18–0.60 % at the full fleet 8/3/4 during departures; r599 and r605 none), so the mean violation difference is +1.67 and the cost is 0.55 % above CR outside both ranges → dominated. t7 0.5 %: cost ranges identical (1426–1429), violations 0 vs 0.33 → equal. Flaps are lower than CR's in all six cells.

**(iii) same-target B4 / B6 on t4 / t8 against the planner (verdict from the planner's side):**

| cell | planner cost (range) / viol / flaps | baseline cost (range) / viol / flaps | planner − baseline % | Δviol | verdict | expected | consistent |
|---|---|---|---|---|---|---|---|
| t4|B4A_375_300|vs S4p2 | 1394.0 (1394–1394) / 2.00 / 0.00 | 1437.0 (1437–1437) / 0.50 / 0.00 | -2.99 | +1.50 | **trade-off** | trade-off | yes |
| t4|B6c5_h|vs S4p2 | 1394.0 (1394–1394) / 2.00 / 0.00 | 1433.5 (1433–1434) / 0.00 / 2.00 | -2.76 | +2.00 | **trade-off** | trade-off | yes |
| t4|B4A_375_300|vs S4p05 | 1447.7 (1447–1448) / 0.00 / 2.00 | 1437.0 (1437–1437) / 0.50 / 0.00 | +0.74 | -0.50 | **dominated** | equal|dominates | no |
| t4|B6c5_h|vs S4p05 | 1447.7 (1447–1448) / 0.00 / 2.00 | 1433.5 (1433–1434) / 0.00 / 2.00 | +0.99 | +0.00 | **dominated** | equal|dominates | no |
| t8|B6c5_h|vs S4p2 | 1045.7 (1007–1078) / 2.33 / 2.33 | 1012.5 (1009–1016) / 3.50 / 5.00 | +3.28 | -1.17 | **dominates** | trade-off | no |
| t8|B6c5_h|vs S4p05 | 1100.0 (1088–1110) / 0.00 / 5.00 | 1012.5 (1009–1016) / 3.50 / 5.00 | +8.64 | -3.50 | **trade-off** | trade-off | yes |
| t8|B4A_375_300|vs S4p2 | 1045.7 (1007–1078) / 2.33 / 2.33 | 965.0 (964–966) / 3.00 / 4.00 | +8.36 | -0.67 | **dominated** | — | — |
| t8|B4A_375_300|vs S4p05 | 1100.0 (1088–1110) / 0.00 / 5.00 | 965.0 (964–966) / 3.00 / 4.00 | +13.99 | -3.00 | **trade-off** | — | — |

t4 at 2 %: trade-off as registered (planner 3.0 / 2.8 % cheaper, 1.5 / 2.0 more violation minutes). t4 at 0.5 %: both same-target baselines are 0.7 / 1.0 % cheaper outside the run ranges at 0.5 / 0 violation minutes (the planner's 0), so the planner is dominated by the rule, where 'equal or planner dominates' was expected (the registered model note already predicted B4 / B6 cheaper by 0.7 / 1.1 %). t8 B6 at 2 %: the planner's runs spread 1007–1078 and contain B6's 1009–1016, so its +3.3 % cost does not count while its 1.17 fewer violation minutes do → 'dominates' by the rule where trade-off was expected; at 0.5 % trade-off as expected. t8 B4 (no expectation registered): 8.4 % cheaper than the planner at 2 % with 0.67 more violation minutes (< 1 → does not count) → the planner is dominated; at 0.5 % trade-off (B4 14 % cheaper, 3.0 more violation minutes).

**(B) ±2 % hits of the four versions** (cell means; per run in brackets; B4 has no fleet model → (b) over 8 cells / 18 runs):

- (a) 9 / 10 cells [20 / 22 runs]; max |cell error| 5.39 %; cell errors t3|S4p2 +0.16, t3|S4p05 +0.66, t5|S4p2 +0.02, t5|S4p05 -0.00, t7|S4p2 +0.30, t7|S4p05 +0.24, t4|B4A_375_300 +0.07, t4|B6c5_h -0.12, t8|B4A_375_300 -5.39, t8|B6c5_h -1.44
- (b) 8 / 8 cells [18 / 18 runs]; max |cell error| 0.97 %; cell errors t3|S4p2 -0.71, t3|S4p05 -0.13, t5|S4p2 +0.15, t5|S4p05 -0.00, t7|S4p2 +0.05, t7|S4p05 +0.10, t4|B6c5_h +0.67, t8|B6c5_h +0.97
- (c) 9 / 10 cells [20 / 22 runs]; max |cell error| 5.39 %; cell errors t3|S4p2 +0.16, t3|S4p05 +0.66, t5|S4p2 +0.02, t5|S4p05 -0.00, t7|S4p2 +0.30, t7|S4p05 +0.24, t4|B4A_375_300 +0.07, t4|B6c5_h -0.12, t8|B4A_375_300 -5.39, t8|B6c5_h -1.44
- (d) 9 / 10 cells [20 / 22 runs]; max |cell error| 5.39 %; cell errors t3|S4p2 +0.16, t3|S4p05 +0.12, t5|S4p2 +0.08, t5|S4p05 -0.08, t7|S4p2 +0.20, t7|S4p05 +0.14, t4|B4A_375_300 +0.07, t4|B6c5_h -0.12, t8|B4A_375_300 -5.39, t8|B6c5_h -1.44

The one cell outside ±2 % is the same-target B4 3.75/300 on t8 (predicted 913.0, measured 965 / 964–966, −5.39 % for (a) = (c) = (d); the baseline predictions share one per-slot model). All six planner cells are within 0.66 % (max t3 0.5 %: +0.66 %).

**(C) weak dominance over CR (Table 1 rule: cost not higher, violation minutes not more, at least one strictly better):** **6 of 12 paired cells** (the six t4 / t6 / t8 cells of the C block; none of the six new cells). Counting flaps as a third criterion changes nothing (6 / 12). Excluding the single-run t5 cells: 6 / 10. Per new cell: t3 2 % cost higher (+1.9 %); t3 0.5 % violations more (+3.3); t5 2 % / 0.5 % cost higher by 4 / 2 core-min; t7 2 % cost higher (+0.6 %) and violations more (+1.7); t7 0.5 % cost higher by 0.67 core-min (1427.7 vs 1427.0; under a 1 core-min tolerance, the rounding unit of alloc_vm, it would count → 7 / 12).

## 3. Table X rows for the planner on t3 / t5 / t7 (same rule; deployed-knob baselines from rq groups MAIN *, B6* = same-target 0.775 on t3 from spec §4.121 H) and same-target columns on t4 / t8

| cell | B4c2 | B5c1 | B6 (u 0.70) | B6* 0.775 | B4* 3.75/300 | CR |
|---|---|---|---|---|---|---|
| t3|S4p2 | dominates | equal | trade-off | dominates | — | trade-off |
| t3|S4p05 | trade-off | dominated | trade-off | dominated | — | trade-off |
| t5|S4p2 | dominates | dominates | dominates | — | — | dominated |
| t5|S4p05 | equal | equal | equal | — | — | dominated |
| t7|S4p2 | trade-off | trade-off | trade-off | — | — | dominated |
| t7|S4p05 | dominates | dominated | dominates | — | — | equal |
| t4|S4p2 | — | — | — | trade-off | trade-off | — |
| t4|S4p05 | — | — | — | dominated | dominated | — |
| t8|S4p2 | — | — | — | dominates | dominated | — |
| t8|S4p05 | — | — | — | trade-off | trade-off | — |

Baseline references used (mean viol / cost (range)): t3 B4c2: 3.67 (3–5) / 1233 (1231–1236); t3 B5c1: 4 (3–5) / 1153 (1151–1154); t3 B6: 2 (1–3) / 1228 (1216–1238); t5 B4c2: 0 / 1464; t5 B5c1: 0 / 1464; t5 B6: 0 / 1464; t7 B4c2: 0 / 1441 (1440–1441); t7 B5c1: 0 / 1413 (1412–1414); t7 B6: 0 / 1451 (1448–1454); t3 B6 0.775: 3.50 (3–4) / 1179 (1174–1184).

## 4. Start audit I1 (22 runs added)

Hardware minute-0 fleet (slots / VyOS / workers) equal to the registered start in 16 / 22 runs and to the simulator's own initial_fleet in 16 / 22. Mismatches:

| run | trace | arm | hw | registered | own initial_fleet |
|---|---|---|---|---|---|
| r583 | t7 | S4p05 | 7/3/4 | 7/3/4 | 8/3/4 |
| r586 | t7 | S4p2 | 7/2/4 | 7/3/4 | 7/2/4 |
| r587 | t4 | B6c5_h | 6/2/3 | 5/2/3 | 5/2/3 |
| r594 | t7 | S4p05 | 7/3/4 | 7/3/4 | 8/3/4 |
| r599 | t7 | S4p2 | 7/2/4 | 7/3/4 | 7/2/4 |
| r601 | t7 | S4p05 | 7/3/4 | 7/3/4 | 8/3/4 |
| r602 | t4 | B4A_375_300 | 5/2/3 | 6/2/3 | 6/2/3 |
| r603 | t4 | B6c5_h | 6/2/3 | 5/2/3 | 5/2/3 |
| r605 | t7 | S4p2 | 7/2/4 | 7/3/4 | 7/2/4 |

t7 2 %: align_fleet reached 7 slots / 4 workers but did not add the third VyOS (t7_v7r586.log: 'start fleet rep 7 vy 2 wk 4'); the daemon added it in minute 2 in all three runs; the hardware start equals the planner's own initial_fleet (7/2/4), the registered prediction used the alignment target 7/3/4 (error +0.30 %). t7 0.5 %: hardware = registered alignment 7/3/4, the planner's own initial_fleet is 8/3/4. t4 B6: both runs start at 6 slots where the simulator starts at 5 (warm-in convergence); t4 B4 r602 at 5 where the simulator starts at 6.

## 5. Violation classes (B2 rule, classify_b2.classify) and fleet-level hits

- r584 (t3 S4p2): {'3': 'fleet', '4': 'fleet', '5': 'fleet'}
- r589 (t3 S4p2): {'3': 'fleet', '4': 'fleet', '5': 'fleet', '6': 'placement'}
- r596 (t3 S4p2): {'3': 'fleet', '4': 'fleet', '5': 'fleet', '6': 'placement'}
- r590 (t3 S4p05): {'3': 'fleet', '4': 'fleet', '5': 'fleet', '6': 'placement', '7': 'placement', '10': 'placement', '12': 'placement'}
- r598 (t3 S4p05): {'3': 'fleet', '4': 'fleet', '5': 'fleet', '6': 'placement', '7': 'other'}
- r600 (t3 S4p05): {'3': 'fleet', '4': 'fleet', '5': 'fleet', '6': 'placement', '7': 'other'}
- r586 (t7 S4p2): {'35': 'placement', '36': 'placement', '37': 'placement', '38': 'placement', '39': 'placement'}
- r597 (t4 B4A_375_300): {}
- r602 (t4 B4A_375_300): {'1': 'placement'}
- r592 (t8 B4A_375_300): {'20': 'fleet', '21': 'other'}
- r604 (t8 B4A_375_300): {'20': 'fleet', '21': 'placement', '22': 'placement', '23': 'other'}
- r588 (t8 B6c5_h): {'20': 'fleet', '21': 'placement', '22': 'other'}
- r595 (t8 B6c5_h): {'20': 'fleet', '21': 'placement', '22': 'placement', '23': 'other'}

Fleet-shortage minutes vs the fleet-level prediction (b): planner t3 2 % and 0.5 % (b) [3, 4, 5] → hardware fleet-shortage minutes 3, 4, 5 in 6 / 6 runs (hit 18, miss 0, false alarm 0); minutes 6–7 (and 10, 12 in r590) are placement overflow / other. t7 2 %: (b) none; r586's minutes 35–39 are placement overflow at the full fleet. t5, t7 0.5 %: none / none. Same-target B6 t8 (b) has no violation list; hardware minute 20 is fleet shortage in all four B4 / B6 t8 runs, 21–23 placement / other. t4 B4 r602 minute 1: placement.

## 6. Fidelity totals

Version (a): 9 / 10 new cells within ±2 % (outside: ['t8|B4A_375_300']); with the 35 earlier cells: **42 / 45**. Planner cells: 8 + 6 = 14, max |error| 0.66 % (new cells t3|S4p2 +0.16, t3|S4p05 +0.66, t5|S4p2 +0.02, t5|S4p05 -0.00, t7|S4p2 +0.30, t7|S4p05 +0.24).

## 7. Per-run table (22 runs)

| run | phase | trace | arm | SLO/60 | worst loss % | p99 max µs | alloc_vm | burned | flaps | acts vy/wk/up | violation minutes | start s/v/w | wk/vy/slot-min |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| r582 | F | t5 | S4p2 | 60 | 0.01 | 397 | 1457 | 704 | 2 | 0/0/3 | [] | 8/3/4 | 240/180/471 |
| r583 | F | t7 | S4p05 | 60 | 0.01 | 470 | 1428 | 682 | 5 | 3/1/7 | [] | 7/3/4 | 238/172/460 |
| r584 | F | t3 | S4p2 | 57 | 3.44 | 2984 | 1164 | 525 | 2 | 2/2/6 | [3, 4, 5] | 6/2/3 | 205/129/364 |
| r586 | F | t7 | S4p2 | 55 | 0.6 | 399 | 1398 | 675 | 0 | 2/1/3 | [35, 36, 37, 38, 39] | 7/2/4 | 238/159/453 |
| r587 | F | t4 | B6c5_h | 60 | 0.01 | 412 | 1433 | 700 | 2 | 1/1/4 | [] | 6/2/3 | 239/172/468 |
| r588 | F | t8 | B6c5_h | 57 | 0.52 | 2921 | 1016 | 450 | 5 | 5/4/8 | [20, 21, 22] | 4/1/2 | 179/115/312 |
| r589 | F | t3 | S4p2 | 56 | 5.06 | 2977 | 1153 | 525 | 2 | 2/2/6 | [3, 4, 5, 6] | 6/2/3 | 202/129/360 |
| r590 | F | t3 | S4p05 | 53 | 5.0 | 2970 | 1187 | 531 | 4 | 2/3/9 | [3, 4, 5, 6, 7, 10, 12] | 6/2/3 | 208/132/376 |
| r592 | F | t8 | B4A_375_300 | 58 | 0.51 | 2923 | 964 | 425 | 4 | 4/8/4 | [20, 21] | 4/2/2 | 171/117/267 |
| r593 | F | t5 | S4p05 | 60 | 0.0 | 396 | 1464 | 721 | 0 | 0/0/0 | [] | 8/3/4 | 240/180/480 |
| r594 | F | t7 | S4p05 | 60 | 0.01 | 397 | 1426 | 678 | 8 | 3/1/9 | [] | 7/3/4 | 237/171/460 |
| r595 | F | t8 | B6c5_h | 56 | 0.54 | 2973 | 1009 | 453 | 5 | 5/4/8 | [20, 21, 22, 23] | 4/1/2 | 178/112/314 |
| r596 | F | t3 | S4p2 | 56 | 4.62 | 3984 | 1160 | 530 | 2 | 2/2/6 | [3, 4, 5, 6] | 6/2/3 | 203/129/362 |
| r597 | F | t4 | B4A_375_300 | 60 | 0.01 | 396 | 1437 | 707 | 0 | 1/0/2 | [] | 6/2/3 | 239/174/468 |
| r598 | F | t3 | S4p05 | 55 | 5.57 | 3988 | 1178 | 517 | 2 | 2/3/7 | [3, 4, 5, 6, 7] | 6/2/3 | 207/130/371 |
| r599 | F | t7 | S4p2 | 60 | 0.01 | 399 | 1394 | 659 | 2 | 2/1/5 | [] | 7/2/4 | 238/160/448 |
| r600 | F | t3 | S4p05 | 55 | 5.06 | 2984 | 1181 | 516 | 2 | 2/3/7 | [3, 4, 5, 6, 7] | 6/2/3 | 209/130/372 |
| r601 | F | t7 | S4p05 | 60 | 0.0 | 396 | 1429 | 681 | 5 | 3/1/7 | [] | 7/3/4 | 238/172/460 |
| r602 | F | t4 | B4A_375_300 | 59 | 0.15 | 398 | 1437 | 710 | 0 | 1/0/3 | [1] | 5/2/3 | 239/174/466 |
| r603 | F | t4 | B6c5_h | 60 | 0.01 | 400 | 1434 | 701 | 2 | 1/1/4 | [] | 6/2/3 | 239/172/468 |
| r604 | F-retry | t8 | B4A_375_300 | 56 | 1.06 | 2941 | 966 | 428 | 4 | 4/7/4 | [20, 21, 22, 23] | 4/2/2 | 172/118/267 |
| r605 | F-retry | t7 | S4p2 | 60 | 0.01 | 400 | 1393 | 654 | 2 | 2/1/6 | [] | 7/2/4 | 238/159/450 |

## 8. Summary

- (A) 2 / 6 cells consistent with the registered expectation (t3 trade-off ×2); t5 dominated ×2 (n = 1, 4 / 2 core-min), t7 2 % dominated (r586's five placement minutes; +0.55 % cost), t7 0.5 % equal.
- (B) (a)(c)(d) 9 / 10 cells (20 / 22 runs), (b) 8 / 8 (18 / 18); outside: same-target B4 on t8, −5.4 %.
- (C) weakly dominates CR in 6 of 12 paired cells (the t4 / t6 / t8 cells); none of t3 / t5 / t7 (t7 0.5 % misses by 0.67 core-min).
- (iii) t4 2 % trade-off ×2 as registered; t4 0.5 % dominated by both same-target baselines (0.7 / 1.0 % cheaper); t8 B6 2 % 'dominates' by the rule (cost inside the planner's range), 0.5 % trade-off; t8 B4 dominated at 2 %, trade-off at 0.5 %.
- Files: out/f.json, out/b2.json, out/table4.json (numbers), eval_f.py (computation), report_f.py (this file).
