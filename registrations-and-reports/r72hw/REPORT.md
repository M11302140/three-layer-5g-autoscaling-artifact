# r72hw — S4′ on hardware: E judgement (spec §4.140; 2026-10-31)

Runs: C = 18 (r530–r547, S4′ 2 % / 0.5 % × t4 / t6 / t8 × 3), D = 20 (r560–r565, r568–r581; t11 / t12 × {S4′ 2 %, S4b, A:B4 3.75/300, A:B5 4.0/L2, A:B6 0.775} × 2). r566 / r567 (B6 t11 / t12) were harness faults (TRex server died during warm-in; chain abort) and were replaced by r580 / r581 under the pre-registered rule. All 38 valid runs have flags ok; probes p35 / p36 / p36b / p37 all p99 397–398 µs, e2e 0.010 %.
Hardware metrics: paper_out_new/rq_metrics (alloc_vm = VM-exists accounting; flaps = same layer reversed within 10 min; violation minutes = 0-based minutes with loss > 0.1 % or p99 > 1 ms). Predictions: (a) per-slot R38 off, (b) fleet, (c) per-slot R38 on (r71fin/out/predict.json), (d) daemon-faithful CtlGen (r72hw/out/dver.json). Frozen simulator md5 unchanged after the computation (3daf1387 7a2b02ec ecdfff61 4697713c b24eae16 edb8e00c).

## 1. Endpoints (registered §4.139 / §4.140 B)

**(i) flaps, primary pooled**: six-cell S4′ hardware flap sum = **13.33** vs threshold 19.4 (S4 38.8 × 0.5) → **PASS**. Registered predictions of the pooled sum: (a) 13, (b) 9, (c) 13, (d) 13.
**(i) secondary per cell** (S4′ mean ≤ 0.5 × S4 hw mean): **5 / 6**. Failing cell: t4 0.5 % (S4′ 2.0 vs threshold 1.0; equal to S4a's 2.0).

| cell | runs | S4′ hw flaps (each) | mean | threshold 0.5×S4 | pass | S4 hw flaps | pred flaps a / b / c / d |
|---|---|---|---|---|---|---|---|
| t4 2 % | r532/r533/r536 | [0, 0, 0] | 0.00 | 0.50 | yes | 1.0 | 0 / 0 / 0 / 0 |
| t4 0.5 % | r541/r544/r546 | [2, 2, 2] | 2.00 | 1.00 | no | 2.0 | 1 / 1 / 1 / 1 |
| t6 2 % | r531/r538/r539 | [2, 2, 2] | 2.00 | 3.00 | yes | 6.0 | 2 / 2 / 2 / 2 |
| t6 0.5 % | r530/r537/r540 | [2, 2, 2] | 2.00 | 4.67 | yes | 9.33 | 2 / 1 / 2 / 2 |
| t8 2 % | r534/r535/r547 | [1, 4, 2] | 2.33 | 4.50 | yes | 9.0 | 4 / 2 / 4 / 4 |
| t8 0.5 % | r542/r543/r545 | [6, 5, 4] | 5.00 | 5.75 | yes | 11.5 | 4 / 3 / 4 / 4 |

**(ii) t4 2 % minutes 49 / 50**: violation minutes of r532 / r533 / r536 = [[20, 21], [20, 21], [20, 21]]; contains 49 or 50: [False, False, False] → **no**. Hardware majority set = [20, 21]. Version match: (a) symdiff 1, (b) symdiff 1, (c) match, (d) symdiff 1. → **t4 valid physics = (c) per-slot R38 on** (registered rule: majority = [20, 21] → (c)). For reference, S4b's hardware majority on the same cell is [20, 21, 49, 50], which (c) also reproduced; S4′ removes minutes 49 / 50 on hardware as (c) predicted.

**(iii) cost**: cells within ± 2 %: (a) 6 / 6, (b) 5 / 6, (c) 6 / 6, (d) 6 / 6.

| cell | S4′ hw alloc_vm (each) | mean | pred a | err % | pred b | err % | pred c | err % | pred d | err % | S4 hw |
|---|---|---|---|---|---|---|---|---|---|---|---|
| t4 2 % | [1394.0, 1394.0, 1394.0] | 1394.0 | 1393.7 | -0.02 | 1397.5 | +0.25 | 1393.7 | -0.02 | 1393.7 | -0.02 | 1420.0 |
| t4 0.5 % | [1447.0, 1448.0, 1448.0] | 1447.7 | 1447.0 | -0.04 | 1450.0 | +0.16 | 1447.0 | -0.04 | 1447.0 | -0.04 | 1449.3 |
| t6 2 % | [1367.0, 1367.0, 1352.0] | 1362.0 | 1367.3 | +0.39 | 1368.5 | +0.47 | 1369.4 | +0.55 | 1365.9 | +0.29 | 1390.3 |
| t6 0.5 % | [1420.0, 1433.0, 1419.0] | 1424.0 | 1426.6 | +0.18 | 1428.3 | +0.30 | 1426.6 | +0.18 | 1425.2 | +0.08 | 1435.0 |
| t8 2 % | [1007.0, 1078.0, 1052.0] | 1045.7 | 1050.0 | +0.42 | 1039.3 | -0.61 | 1050.0 | +0.42 | 1050.0 | +0.42 | 1054.5 |
| t8 0.5 % | [1102.0, 1110.0, 1088.0] | 1100.0 | 1096.0 | -0.37 | 1077.8 | -2.01 | 1096.0 | -0.37 | 1096.0 | -0.37 | 1107.5 |

**Secondary, t8 cost ratio S4′ / S4 (hardware)**: 2 % 0.9916 (-0.84 %), 0.5 % 0.9932 (-0.68 %). Predicted: (a)(c) +0.84 % / +1.02 %, (b) +2.21 % / +1.68 %. Hardware has S4′ slightly cheaper, predictions slightly costlier; the S4 reference has only two runs per point and the S4′ t8 2 % runs spread 1007–1078, so the sign of a ≤ 1 % ratio is not resolved by n = 3 vs 2 [已驗證 numbers; 推測 on resolution].

### Violation minutes, all C cells (hardware each run vs predictions)

| cell | hw violation minutes | majority | a | b | c | d |
|---|---|---|---|---|---|---|
| t4 2 % | [[20, 21], [20, 21], [20, 21]] | [20, 21] | [20] | [20, 21, 22] | [20, 21] | [20] |
| t4 0.5 % | [[], [], []] | [] | [] | [] | [20, 21] | [] |
| t6 2 % | [[], [], []] | [] | [] | [17] | [17, 18, 43] | [] |
| t6 0.5 % | [[], [], []] | [] | [] | [] | [17] | [] |
| t8 2 % | [[20, 21, 22], [20, 21], [20, 21]] | [20, 21] | [20, 21] | [20] | [20, 21] | [20, 21] |
| t8 0.5 % | [[], [], []] | [] | [20, 21] | [20] | [20, 21] | [20, 21] |

Notes: t4 0.5 % hardware has no violations in all three runs ((a)(b)(d) predicted none; (c) predicted [20, 21]); t6 both points clean ((c) predicted [17, 18, 43] / [17]); t8 2 % has [20, 21] twice and [20, 21, 22] once (r534, minute 22 = 0.25 % loss during the post-burst scale-in); t8 0.5 % clean on hardware while all four versions predicted [20, 21] (S4a's hardware on the same cell had [20] / [20, 21]).

## 2. Generalisation set t11 / t12 (A-group baselines)

### t11

| arm | runs | SLO / 60 | violation minutes | hw alloc_vm (each) | mean | hw flaps (each) | acts | S4′ − arm cost % (hw) | pred (a) | S4′ − arm % (pred a) | pred a err % | pred d | pred d err % |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S4p2 | r562/r564 | [60, 60] | [[], []] | [1296.0, 1299.0] | 1297.5 | [2, 2] | 7.0 | +0.00 | 1297.8 | +0.00 | +0.02 | 1296.8 | -0.05 |
| S4b | r569/r577 | [60, 60] | [[], []] | [1270.0, 1268.0] | 1269.0 | [9, 9] | 14.0 | +2.25 | 1292.7 | +0.40 | +1.86 | 1273.2 | +0.33 |
| B4A_375_300 | r561/r568 | [60, 60] | [[], []] | [1314.0, 1305.0] | 1309.5 | [2, 2] | 7.0 | -0.92 | 1316.8 | -1.45 | +0.56 | 1316.8 | +0.56 |
| B5c1_slo | r563/r573 | [60, 60] | [[], []] | [1323.0, 1324.0] | 1323.5 | [0, 0] | 5.0 | -1.96 | 1324.5 | -2.02 | +0.08 | 1324.5 | +0.08 |
| B6c5_h | r574/r580 | [60, 60] | [[], []] | [1355.0, 1331.0] | 1343.0 | [1, 1] | 7.0 | -3.39 | 1312.7 | -1.13 | -2.26 | 1312.7 | -2.26 |

### t12

| arm | runs | SLO / 60 | violation minutes | hw alloc_vm (each) | mean | hw flaps (each) | acts | S4′ − arm cost % (hw) | pred (a) | S4′ − arm % (pred a) | pred a err % | pred d | pred d err % |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S4p2 | r570/r575 | [60, 59] | [[], [51]] | [1436.0, 1439.0] | 1437.5 | [5, 5] | 8.0 | +0.00 | 1433.0 | +0.00 | -0.31 | 1432.0 | -0.38 |
| S4b | r572/r579 | [60, 60] | [[], []] | [1440.0, 1440.0] | 1440.0 | [8, 8] | 14.0 | -0.17 | 1443.4 | -0.72 | +0.24 | 1440.6 | +0.04 |
| B4A_375_300 | r571/r576 | [55, 60] | [[3, 18, 20, 21, 22], []] | [1458.0, 1459.0] | 1458.5 | [1, 0] | 2.0 | -1.44 | 1459.7 | -1.82 | +0.08 | 1459.7 | +0.08 |
| B5c1_slo | r560/r565 | [60, 60] | [[], []] | [1455.0, 1454.0] | 1454.5 | [1, 1] | 3.0 | -1.17 | 1455.8 | -1.57 | +0.09 | 1455.8 | +0.09 |
| B6c5_h | r578/r581 | [60, 60] | [[], []] | [1453.0, 1451.0] | 1452.0 | [1, 1] | 3.0 | -1.00 | 1451.2 | -1.25 | -0.06 | 1451.2 | -0.06 |

Reading: on t11 S4′ is 2.25 % costlier than S4b on hardware (registered expectation +0.4 % under (a); (d) predicted +1.85 %; hardware sides with (d): S4b t11 was the registered version-sensitive cell, hw 1269.0 vs (a) 1292.7 / (d) 1273.2). Against the A-group baselines S4′ is cheaper on both traces (t11 −0.92 / −1.96 / −3.39 % vs B4 / B5 / B6; t12 −1.44 / −1.17 / −1.00 %) and on t12 is −0.17 % vs S4b. Flaps: S4′ 2 / 5 vs S4b 9 / 8; baselines 0–2 (B4 t12 0.5). Violations: only r575 (S4′ t12, minute 51, 0.12 % loss, p99 299 µs) and r571 (B4 t12, minutes 3 / 18 / 20 / 21 / 22, loss 0.24–0.76 % at full fleet 4 / 3, p99 ≤ 388 µs; the other B4 run r576 is clean). Both are hardware-only events (all versions predicted zero violations for every D cell); no rerun under the registered rule.

A-group per-slot fidelity (pred (a) vs hw mean): B4 +0.56 % / +0.08 %, B5 +0.08 % / +0.09 %, B6 −2.26 % / −0.06 % (t11 / t12). B6 t11 is outside ± 2 % (hw 1355 / 1331, spread 24 core-min between the two runs). S4′ +0.02 % / −0.31 %; S4b (a) +1.86 % / +0.24 %, (d) +0.33 % / +0.04 %.

## 3. Start audit I1 (38 runs added) and B5 A-group recomputation

Hardware minute-0 fleet (slots / VyOS / workers) equal to the simulator initial_fleet in **25 / 38** runs. Mismatches:

| run | trace | arm | hw | sim |
|---|---|---|---|---|
| r530 | t6 | S4p05 | 6/2/3 | 7/2/4 |
| r537 | t6 | S4p05 | 6/2/4 | 7/2/4 |
| r540 | t6 | S4p05 | 6/2/3 | 7/2/4 |
| r541 | t4 | S4p05 | 5/2/3 | 6/2/3 |
| r542 | t8 | S4p05 | 4/2/3 | 5/2/3 |
| r543 | t8 | S4p05 | 4/2/2 | 5/2/3 |
| r544 | t4 | S4p05 | 5/2/3 | 6/2/3 |
| r545 | t8 | S4p05 | 4/2/2 | 5/2/3 |
| r546 | t4 | S4p05 | 5/2/3 | 6/2/3 |
| r562 | t11 | S4p2 | 8/3/4 | 7/3/4 |
| r564 | t11 | S4p2 | 8/3/4 | 7/3/4 |
| r570 | t12 | S4p2 | 8/3/4 | 7/3/4 |
| r575 | t12 | S4p2 | 8/3/4 | 7/3/4 |

Pattern: all nine S4′ 0.5 % C runs start one slot below the simulator (and t6 / t8 sometimes one worker below); all four S4′ 2 % D runs start at 8 / 3 / 4 (warm-in convergence at UE0 30 / 29, the t11 / t12 general-band rule) where the simulator's own initial_fleet is 7 / 3 / 4. S4b D runs start 7 / 3 / 4 = simulator. All A-group baseline D runs start 8 / 3 / 4 = their simulator initial_fleet. Cost errors of the mismatched S4′ cells stay within 0.42 % (table in §1), so the start offset does not move the fidelity claim here.

B5 A-group (4.0/L2) cells with hardware start + HPA prefill (audit.CtlB4P semantics on RB.make's B5 controller): hardware start = simulator start (8 / 3 / 4) on both traces, so the recomputation is identical to the registered (a): t11 1324.5 (hw 1323.5, +0.08 %), t12 1455.8 (hw 1454.5, +0.09 %), violations none, flaps 0 / 1. Same for B4 (1316.8 / 1459.7) and B6 (1312.7 / 1451.2) with hardware start.

## 4. Per-run table (38 runs)

| run | phase | trace | arm | SLO/60 | worst loss % | p99 max µs | alloc_vm | burned | flaps | acts vy/wk/up | violation minutes | start s/v/w | wk/vy/slot-min |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| r530 | C | t6 | S4p05 | 60 | 0.01 | 398 | 1420 | 682 | 2 | 2/1/5 | [] | 6/2/3 | 239/167/460 |
| r531 | C | t6 | S4p2 | 60 | 0.08 | 832 | 1367 | 624 | 2 | 2/1/5 | [] | 6/2/3 | 235/154/442 |
| r532 | C | t4 | S4p2 | 58 | 0.47 | 3913 | 1394 | 679 | 0 | 1/1/3 | [20, 21] | 5/2/3 | 239/159/452 |
| r533 | C | t4 | S4p2 | 58 | 0.52 | 3909 | 1394 | 671 | 0 | 1/1/3 | [20, 21] | 5/2/3 | 238/159/452 |
| r534 | C | t8 | S4p2 | 57 | 0.29 | 2946 | 1007 | 425 | 1 | 2/2/3 | [20, 21, 22] | 4/2/2 | 171/129/294 |
| r535 | C | t8 | S4p2 | 58 | 0.51 | 2983 | 1078 | 489 | 4 | 4/7/7 | [20, 21] | 4/2/2 | 184/138/314 |
| r536 | C | t4 | S4p2 | 58 | 0.56 | 3906 | 1394 | 692 | 0 | 1/1/3 | [20, 21] | 5/2/3 | 239/159/451 |
| r537 | C | t6 | S4p05 | 60 | 0.0 | 399 | 1433 | 685 | 2 | 2/0/5 | [] | 6/2/4 | 240/171/461 |
| r538 | C | t6 | S4p2 | 60 | 0.09 | 861 | 1367 | 631 | 2 | 2/1/5 | [] | 6/2/3 | 235/154/442 |
| r539 | C | t6 | S4p2 | 60 | 0.05 | 733 | 1352 | 635 | 2 | 2/2/5 | [] | 6/2/3 | 232/154/438 |
| r540 | C | t6 | S4p05 | 60 | 0.04 | 400 | 1419 | 686 | 2 | 2/1/5 | [] | 6/2/3 | 239/167/460 |
| r541 | C | t4 | S4p05 | 60 | 0.01 | 412 | 1447 | 707 | 2 | 1/1/5 | [] | 5/2/3 | 239/178/469 |
| r542 | C | t8 | S4p05 | 60 | 0.01 | 400 | 1102 | 459 | 6 | 2/6/9 | [] | 4/2/3 | 192/129/331 |
| r543 | C | t8 | S4p05 | 60 | 0.01 | 399 | 1110 | 476 | 5 | 4/6/7 | [] | 4/2/2 | 191/139/319 |
| r544 | C | t4 | S4p05 | 60 | 0.01 | 501 | 1448 | 718 | 2 | 1/1/5 | [] | 5/2/3 | 239/178/470 |
| r545 | C | t8 | S4p05 | 60 | 0.01 | 423 | 1088 | 462 | 4 | 2/6/7 | [] | 4/2/2 | 192/129/318 |
| r546 | C | t4 | S4p05 | 60 | 0.01 | 398 | 1448 | 706 | 2 | 1/1/5 | [] | 5/2/3 | 239/178/469 |
| r547 | C | t8 | S4p2 | 58 | 0.16 | 2918 | 1052 | 434 | 2 | 2/6/5 | [20, 21] | 4/2/2 | 182/129/307 |
| r560 | D | t12 | B5c1_slo | 60 | 0.01 | 400 | 1455 | 707 | 1 | 3/0/0 | [] | 8/3/4 | 240/174/480 |
| r561 | D | t11 | B4A_375_300 | 60 | 0.01 | 471 | 1314 | 628 | 2 | 3/1/3 | [] | 8/3/4 | 226/147/424 |
| r562 | D | t11 | S4p2 | 60 | 0.01 | 400 | 1296 | 594 | 2 | 1/1/5 | [] | 8/3/4 | 225/144/415 |
| r563 | D | t11 | B5c1_slo | 60 | 0.0 | 398 | 1323 | 626 | 0 | 1/1/3 | [] | 8/3/4 | 227/147/434 |
| r564 | D | t11 | S4p2 | 60 | 0.01 | 399 | 1299 | 581 | 2 | 1/1/5 | [] | 8/3/4 | 225/144/417 |
| r565 | D | t12 | B5c1_slo | 60 | 0.01 | 398 | 1454 | 695 | 1 | 3/0/0 | [] | 8/3/4 | 240/173/480 |
| r568 | D | t11 | B4A_375_300 | 60 | 0.01 | 398 | 1305 | 608 | 2 | 3/1/3 | [] | 8/3/4 | 224/147/421 |
| r569 | D | t11 | S4b | 60 | 0.0 | 397 | 1270 | 563 | 9 | 1/1/12 | [] | 7/3/4 | 219/145/402 |
| r570 | D | t12 | S4p2 | 60 | 0.0 | 399 | 1436 | 690 | 5 | 3/0/5 | [] | 8/3/4 | 240/171/465 |
| r571 | D | t12 | B4A_375_300 | 55 | 0.76 | 399 | 1458 | 710 | 1 | 1/0/2 | [3, 18, 20, 21, 22] | 8/3/4 | 240/177/479 |
| r572 | D | t12 | S4b | 60 | 0.01 | 398 | 1440 | 671 | 8 | 3/0/11 | [] | 7/3/4 | 240/176/457 |
| r573 | D | t11 | B5c1_slo | 60 | 0.0 | 396 | 1324 | 636 | 0 | 1/1/3 | [] | 8/3/4 | 227/147/435 |
| r574 | D | t11 | B6c5_h | 60 | 0.01 | 399 | 1355 | 626 | 1 | 3/1/3 | [] | 8/3/4 | 233/156/428 |
| r575 | D | t12 | S4p2 | 59 | 0.12 | 397 | 1439 | 691 | 5 | 3/0/5 | [51] | 8/3/4 | 240/172/466 |
| r576 | D | t12 | B4A_375_300 | 60 | 0.0 | 424 | 1459 | 720 | 0 | 1/0/0 | [] | 8/3/4 | 240/177/480 |
| r577 | D | t11 | S4b | 60 | 0.06 | 395 | 1268 | 560 | 9 | 1/1/12 | [] | 7/3/4 | 219/144/401 |
| r578 | D | t12 | B6c5_h | 60 | 0.01 | 474 | 1453 | 718 | 1 | 3/0/0 | [] | 8/3/4 | 240/173/480 |
| r579 | D | t12 | S4b | 60 | 0.03 | 450 | 1440 | 676 | 8 | 3/0/11 | [] | 7/3/4 | 240/176/457 |
| r580 | D-retry | t11 | B6c5_h | 60 | 0.0 | 397 | 1331 | 646 | 1 | 3/1/3 | [] | 8/3/4 | 225/156/429 |
| r581 | D-retry | t12 | B6c5_h | 60 | 0.0 | 397 | 1451 | 712 | 1 | 3/0/0 | [] | 8/3/4 | 240/173/480 |

## 5. Summary

- (i) pooled flaps 13.33 ≤ 19.4: **yes**; per cell 5 / 6 (t4 0.5 % fails at 2.0 vs 1.0).
- (ii) t4 2 % minutes 49 / 50: **absent** in 3 / 3; hardware majority [20, 21] = version **(c)** (per-slot R38 on); (a)(b)(d) each differ by one minute.
- (iii) cost within ± 2 %: (a) 6 / 6, (c) 6 / 6, (d) 6 / 6, (b) 5 / 6; max |error| of (a) 0.42 %.
- Secondary t8 ratio: hardware −0.8 % / −0.7 % (S4′ cheaper) vs predicted +0.8 % / +1.0 %; within the resolution of n = 3 vs 2.
- Generalisation: S4′ cheaper than all three A-group baselines on both traces (−0.9 … −3.4 %), ≈ S4b on t12 (−0.17 %), 2.25 % costlier than S4b on t11 (registered as expected in direction; magnitude matches version (d), not (a)); S4′ flaps 2 / 5 vs S4b 9 / 8.
- Fidelity over the 16 cells (6 C + 10 D), version (a): 15 / 16 within ± 2 %; the exception is B6 t11 (−2.26 %). S4b t11 is within ± 2 % only marginally under (a) (+1.86 %) and clearly under (d) (+0.33 %).
- Files: out/e.json (all numbers), eval_e.py (computation), report_e.py (this file).
