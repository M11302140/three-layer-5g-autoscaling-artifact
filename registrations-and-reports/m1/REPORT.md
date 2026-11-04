# M1 (spec §4.99 Task A): conditional risk of ε — library features, simulated vs measured tail risk, effective n

Generated 2026-10-20 02:43:10 by /home/user/experiment/qsim/m1/m1_analysis.py. Pure simulation; no testbed run, no change to λ/daemon/harness.
Library: /home/user/experiment/qsim/prior_traces.json (1615 windows). Traces: t1 = trace_ue_60min_v3_40.json, t2 = trace_ue_60min_v3_pm.json, t3..t7 = trace_ue_60min_v3_t3..t7.json (key "ue", first 60 minutes).
Simulators (frozen): S4a/S4b = v8sim10.sim_nest2(ue, M.cfg_measured(), S.Prior(lib, cfg), λ, acct='vmexist') with λ S4a {vy 2.83, wk 2.83, up 3.08}, S4b {1.83, 1.83, 2.00}; v6 = v8sim2.sim_v6(ue, v8sim7.cfg_measured()). risk = (60 - slo)/60.

## Commands (run from /home/user/experiment/qsim; v8sim3 opens prior_traces.json relative to the cwd)
```
cd /home/user/experiment/qsim/m1 && nice -n 19 taskset -c 8-15 python3 m1_features.py | tee features_run.log
cd /home/user/experiment/qsim && nice -n 19 taskset -c 8-15 python3 m1/m1_risk.py | tee m1/risk_run.log
cd /home/user/experiment/qsim && nice -n 19 taskset -c 8-15 python3 m1/m1_fig_features.py | tee m1/fig_features_run.log
cd /home/user/experiment/qsim && nice -n 19 taskset -c 8-15 python3 m1/m1_analysis.py | tee m1/analysis_run.log
```
`taskset -c 8-15` resolves to the cgroup-allowed CPUs [8, 13, 14] on this host (16 logical CPUs, user slice cpuset); the pool used 3 workers.

## Runtimes
- m1_features.py: 0.2 s
- m1_risk.py: 25.1 s total (simulation of 1623 traces x 3 arms: 22.8 s; Prior build 2.2 s)
- m1_fig_features.py: 0.5 s
- m1_analysis.py: 0.3 s (up to writing this report)

## Checks
- t1..t5 mp/f36/minUE/rise10 computed here equal the frozen values in t6t7_thresholds.json (assert in m1_features.py).
- The simulated slo/alloc of t1..t7 for S4a/S4b/v6 equal the registered predictions (v8_predict_t345_2026-10-07.txt, v8_predict_v6_t345_2026-10-07.txt, v8_predict_t67_2026-10-15.txt): see table below (ALL MATCH).
- Determinism: t6 simulated twice in the pool, identical results.

## A.1 Features (m1/features.csv; figs/fig_m1_features.pdf)

library n=1615; percentile = numpy linear; (pct) = library percentile rank, mid-rank for ties

| feature | P10 | P25 | P50 | P75 | P90 | mean |
|---|---|---|---|---|---|---|
| mp | 0.420 | 0.509 | 0.610 | 0.705 | 0.767 | 0.603 |
| f36 | 0.017 | 0.033 | 0.067 | 0.117 | 0.167 | 0.083 |
| minUE | 4.000 | 8.000 | 12.000 | 17.000 | 22.000 | 12.731 |
| rise10 | 11.000 | 13.000 | 16.000 | 20.000 | 23.000 | 16.679 |
| rise1 | 7.000 | 8.000 | 9.000 | 11.000 | 14.000 | 9.868 |
| lag1 | 0.449 | 0.613 | 0.785 | 0.875 | 0.919 | 0.728 |
| stat | -11.520 | -7.317 | 0.800 | 8.000 | 14.387 | 0.788 |

| trace | mp (pct) | f36 (pct) | minUE (pct) | rise10 (pct) | rise1 (pct) | lag1 (pct) | stat (pct) |
|---|---|---|---|---|---|---|---|
| t1 | 0.497 (22) | 0.133 (82) | 6.000 (17) | 17.000 (56) | 12.000 (80) | 0.926 (93) | 5.733 (68) |
| t2 | 0.662 (64) | 0.100 (71) | 13.000 (54) | 13.000 (23) | 5.000 (2) | 0.913 (88) | -4.133 (34) |
| t3 | 0.483 (19) | 0.033 (23) | 12.000 (49) | 22.000 (87) | 12.000 (80) | 0.863 (71) | -4.200 (34) |
| t4 | 0.781 (92) | 0.250 (97) | 19.000 (80) | 12.000 (17) | 9.000 (45) | 0.710 (37) | 5.233 (67) |
| t5 | 0.774 (91) | 0.100 (71) | 22.000 (91) | 13.000 (23) | 6.000 (5) | 0.686 (34) | -4.267 (34) |
| t6 | 0.694 (72) | 0.033 (23) | 20.000 (84) | 14.000 (31) | 7.000 (14) | 0.758 (44) | -1.167 (43) |
| t7 | 0.695 (73) | 0.117 (77) | 14.000 (59) | 15.000 (39) | 7.000 (14) | 0.846 (65) | -10.400 (14) |

## A.2 Simulated risk of t1..t7 (m1/risk_per_trace.csv; registered values in parentheses)

| trace | S4a slo / risk / alloc (registered slo/alloc) | S4b slo / risk / alloc (registered slo/alloc) | v6 slo / risk / alloc (registered slo/alloc) |
|---|---|---|---|
| t1 | 60/60 / 0.0% / 1149 (60/1149) | 59/60 / 1.7% / 1080 (59/1080) | 58/60 / 3.3% / 1081 (58/1081) |
| t2 | 60/60 / 0.0% / 1413 (60/1413) | 60/60 / 0.0% / 1338 (60/1338) | 59/60 / 1.7% / 1296 (59/1296) |
| t3 | 57/60 / 5.0% / 1257 (57/1257) | 57/60 / 5.0% / 1129 (57/1129) | 57/60 / 5.0% / 1104 (57/1104) |
| t4 | 60/60 / 0.0% / 1454 (60/1454) | 59/60 / 1.7% / 1427 (59/1427) | 57/60 / 5.0% / 1387 (57/1387) |
| t5 | 60/60 / 0.0% / 1464 (60/1464) | 60/60 / 0.0% / 1454 (60/1454) | 60/60 / 0.0% / 1451 (60/1451) |
| t6 | 60/60 / 0.0% / 1449 (60/1449) | 60/60 / 0.0% / 1393 (60/1393) | 58/60 / 3.3% / 1363 (58/1363) |
| t7 | 60/60 / 0.0% / 1430 (60/1430) | 60/60 / 0.0% / 1395 (60/1395) | 60/60 / 0.0% / 1380 (60/1380) |

registered-prediction cross-check: ALL MATCH

Library-wide (1615 windows): S4a: mean risk 0.467%  frac traces with >=1 violating min 20.4%  mean alloc 1338.2; S4b: mean risk 1.886%  frac traces with >=1 violating min 61.9%  mean alloc 1281.3; v6: mean risk 2.388%  frac traces with >=1 violating min 65.6%  mean alloc 1262.3

## A.2 Library deciles by rise10 percentile rank (mid-rank for ties; ties share a decile)

| decile | rise10 range | n windows | S4a mean risk (%) | S4b mean risk (%) | v6 mean risk (%) | S4a frac. windows with >=1 viol. min (%) | S4b frac. windows with >=1 viol. min (%) | v6 frac. windows with >=1 viol. min (%) | S4a mean alloc | S4b mean alloc | v6 mean alloc | traces |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| D1 (P0-P10) | 4-10 | 137 | 0.01 | 0.18 | 0.26 | 0.7 | 9.5 | 12.4 | 1348 | 1295 | 1288 |  |
| D2 (P10-P20) | 11-12 | 185 | 0.05 | 0.68 | 0.71 | 2.7 | 34.6 | 29.7 | 1392 | 1347 | 1329 | t4 |
| D3 (P20-P30) | 13-13 | 106 | 0.06 | 1.08 | 1.27 | 3.8 | 51.9 | 44.3 | 1389 | 1347 | 1326 | t2,t5 |
| D4 (P30-P40) | 14-15 | 261 | 0.22 | 1.53 | 1.79 | 12.6 | 57.1 | 63.2 | 1395 | 1349 | 1332 | t6,t7 |
| D5 (P40-P50) | 16-16 | 156 | 0.30 | 1.66 | 2.08 | 13.5 | 67.3 | 67.9 | 1360 | 1305 | 1283 |  |
| D6 (P50-P60) | 17-17 | 108 | 0.31 | 1.64 | 2.48 | 15.7 | 60.2 | 69.4 | 1357 | 1303 | 1284 | t1 |
| D7 (P60-P70) | 18-19 | 218 | 0.53 | 2.14 | 2.87 | 23.9 | 70.2 | 84.9 | 1314 | 1254 | 1234 |  |
| D8 (P70-P80) | 20-20 | 94 | 0.69 | 3.00 | 3.48 | 37.2 | 88.3 | 90.4 | 1300 | 1237 | 1211 |  |
| D9 (P80-P90) | 21-22 | 174 | 0.80 | 2.94 | 3.92 | 37.9 | 86.2 | 90.8 | 1281 | 1209 | 1192 | t3 |
| D10 (P90-P100) | 23-34 | 176 | 1.60 | 3.90 | 4.90 | 54.5 | 92.6 | 94.3 | 1235 | 1156 | 1131 |  |

Library-wide mean risk: S4a 0.467%, S4b 1.886%, v6 2.388% (n = 1615).

Trace placement: t1: rise10 = 17, percentile rank 55.7 -> D6; t2: rise10 = 13, percentile rank 23.2 -> D3; t3: rise10 = 22, percentile rank 86.5 -> D9; t4: rise10 = 12, percentile rank 16.8 -> D2; t5: rise10 = 13, percentile rank 23.2 -> D3; t6: rise10 = 14, percentile rank 30.9 -> D4; t7: rise10 = 15, percentile rank 38.9 -> D4

## A.3 Pre-registered rule: decile mean simulated risk vs measured hardware risk (3 runs x 60 min)

| trace | decile | arm | sim. risk of the exact trace (%) | decile mean sim. risk (%) | measured risk (%) | ratio = decile mean / measured | verdict |
|---|---|---|---|---|---|---|---|
| t3 | D9 (21-22) | S4b | 5.00 | 2.94 | 7.78 (14/180) | 0.38 | simulator under-estimates tail risk by factor 2.64 |
| t3 | D9 (21-22) | S4a | 5.00 | 0.80 | 3.89 (7/180) | 0.20 | simulator under-estimates tail risk by factor 4.89 |
| t3 | D9 (21-22) | v6 | 5.00 | 3.92 | 9.44 (17/180) | 0.41 | simulator under-estimates tail risk by factor 2.41 |
| t4 | D2 (11-12) | S4b | 1.67 | 0.68 | 5.56 (10/180) | 0.12 | simulator under-estimates tail risk by factor 8.22 |
| t4 | D2 (11-12) | S4a | 0.00 | 0.05 | 1.67 (3/180) | 0.03 | simulator under-estimates tail risk by factor 37.00 |
| t4 | D2 (11-12) | v6 | 5.00 | 0.71 | 2.78 (5/180) | 0.26 | simulator under-estimates tail risk by factor 3.90 |
| t6 | D4 (14-15) | S4b | 0.00 | 1.53 | 0.00 (0/180) | n/a (measured 0) | (rule pre-registered for t3/t4 only; shown for reference) |
| t6 | D4 (14-15) | S4a | 0.00 | 0.22 | 0.00 (0/180) | n/a (measured 0) | (rule pre-registered for t3/t4 only; shown for reference) |
| t6 | D4 (14-15) | v6 | 3.33 | 1.79 | 2.78 (5/180) | 0.64 | (rule pre-registered for t3/t4 only; shown for reference) |
| t7 | D4 (14-15) | S4b | 0.00 | 1.53 | 0.00 (0/180) | n/a (measured 0) | (rule pre-registered for t3/t4 only; shown for reference) |
| t7 | D4 (14-15) | S4a | 0.00 | 0.22 | 0.56 (1/180) | 0.40 | (rule pre-registered for t3/t4 only; shown for reference) |
| t7 | D4 (14-15) | v6 | 0.00 | 1.79 | 0.00 (0/180) | n/a (measured 0) | (rule pre-registered for t3/t4 only; shown for reference) |

## A.4 Effective sample size

- library windows: 1615; distinct sensors (loc): 18; distinct dates: 14
- (loc, date) groups = **effective n = 125**
- windows per group: mean 12.92, min 1, max 15; distribution {windows: groups} = 1: 1, 4: 2, 6: 2, 7: 1, 8: 5, 9: 4, 10: 4, 11: 4, 12: 8, 13: 24, 14: 31, 15: 39
- start field is in real minutes of day (values 360..1200); each window covers 240 real minutes (4 real min = 1 trace min)
- consecutive-window start gaps within a group: delta=60 min: 1488 pairs, delta=120 min: 1 pairs, delta=300 min: 1 pairs (1490 consecutive pairs)
- overlap = max(0, 240 - delta_start)/240: mean 0.749, median 0.750, min 0.000, max 0.750; fraction of pairs with overlap 0.75: 99.9%
- for reference, non-overlapping 240-min windows per group would be at most 4 -> about 500 independent windows if every group were fully covered (actual coverage is lower, see distribution above)

## Figures
- /home/user/docs/paper-v2/figs/fig_m1_features.pdf (double column, 7.0 in): library histograms of mp, f36, rise10, rise1, lag-1, stationarity; dashed grey marks = t1/t2 (development), solid black = t3-t7 (test), labelled.
- /home/user/docs/paper-v2/figs/fig_m1_risk_vs_burst.pdf (single column, 3.4 in): decile mean simulated risk per arm (filled markers, lines; S4a blue circle, S4b orange square, v6 green triangle, as in common.py) vs rise10 decile; hollow markers = measured hardware risk of t3/t4/t6/t7 (3 runs x 60 min) placed at the trace's decile (x offset -0.2/0/+0.2 for S4a/S4b/v6); dotted verticals mark the deciles of t3, t4, t6/t7.

## Verdict (rule A.3, pre-registered)
- t3 / S4b: ratio 0.38 -> simulator under-estimates tail risk by factor 2.64
- t3 / S4a: ratio 0.20 -> simulator under-estimates tail risk by factor 4.89
- t3 / v6: ratio 0.41 -> simulator under-estimates tail risk by factor 2.41
- t4 / S4b: ratio 0.12 -> simulator under-estimates tail risk by factor 8.22
- t4 / S4a: ratio 0.03 -> simulator under-estimates tail risk by factor 37.00
- t4 / v6: ratio 0.26 -> simulator under-estimates tail risk by factor 3.90

## Supplement R58-2 (spec §4.99 A (5) and (6), added 10-20)

Generated 2026-10-20 15:45:11 by /home/user/experiment/qsim/m1/m1_supplement.py (`cd /home/user/experiment/qsim && nice -n 19 taskset -c 13,14 python3 m1/m1_supplement.py | tee m1/supplement_run.log`).

### (5) Three-level prediction table: rise10-decile mean vs registered per-trace vs per-slot (v8sim11) per-trace vs measured

Units: violating minutes per 60-minute run. Registered = nest2 exact trace at deployed λ, acct = vmexist (S4a/S4b), v8sim2.sim_v6 (v6); values are those in m1/risk_per_trace.csv, which were verified equal to the registered prediction files. v8sim11 = `import v8sim11 as V; V.cfg_prior(); r = V.run(tr, arm)` with arm names exactly "S4a", "S4b", "v6" (v8sim11.make_ctl: S4a/S4b -> CtlSigma with its own LAM table = deployed λ, v6 -> CtlV6), start = None (initial_fleet), phys = None, no kwargs; R38 (slot .38 overflow rule) is on by default via v8sim11.PHYS and was left at its defaults: {'knee': 5, 'knee38': 4, 'a38': 7, 'churn38_s': 300, 'hold38_s': 60, 'PHYS_OVERRIDE env': None}; violating minutes = 60 - slo = len(viol). Decile mean = rise10 decile mean risk x 60 (from §A.2 table). Measured = 3-run total / 3. Ratios are measured / prediction; n/a when the prediction is 0.

| trace | arm | rise10 decile | decile mean (min/run, %) | registered (min/run) | v8sim11 (min/run; minutes; alloc_vm) | measured (min/run) | measured / registered | measured / v8sim11 | measured / decile mean |
|---|---|---|---|---|---|---|---|---|---|
| t3 | S4a | D9 | 0.48 (0.80%) | 3 | 3; [3, 4, 5]; 1254 | 2.33 (7/3) | 0.78 | 0.78 | 4.89 |
| t3 | S4b | D9 | 1.76 (2.94%) | 3 | 5; [3, 4, 5, 7, 8]; 1138 | 4.67 (14/3) | 1.56 | 0.93 | 2.64 |
| t3 | v6 | D9 | 2.35 (3.92%) | 3 | 5; [3, 4, 5, 7, 8]; 1119 | 5.67 (17/3) | 1.89 | 1.13 | 2.41 |
| t4 | S4a | D2 | 0.03 (0.05%) | 0 | 2; [20, 21]; 1452 | 1.00 (3/3) | ∞ (pred 0) | 0.50 | 37.00 |
| t4 | S4b | D2 | 0.41 (0.68%) | 1 | 4; [20, 21, 49, 50]; 1425 | 3.33 (10/3) | 3.33 | 0.83 | 8.22 |
| t4 | v6 | D2 | 0.43 (0.71%) | 3 | 2; [20, 21]; 1382 | 1.67 (5/3) | 0.56 | 0.83 | 3.90 |
| t6 | S4a | D4 | 0.13 (0.22%) | 0 | 3; [17, 43, 44]; 1448 | 0.00 (0/3) | n/a (pred 0) | 0.00 | 0.00 |
| t6 | S4b | D4 | 0.92 (1.53%) | 0 | 5; [17, 18, 32, 33, 43]; 1397 | 0.00 (0/3) | n/a (pred 0) | 0.00 | 0.00 |
| t6 | v6 | D4 | 1.07 (1.79%) | 2 | 2; [17, 18]; 1365 | 1.67 (5/3) | 0.83 | 0.83 | 1.55 |
| t7 | S4a | D4 | 0.13 (0.22%) | 0 | 0; -; 1432 | 0.33 (1/3) | ∞ (pred 0) | ∞ (pred 0) | 2.49 |
| t7 | S4b | D4 | 0.92 (1.53%) | 0 | 0; -; 1396 | 0.00 (0/3) | n/a (pred 0) | n/a (pred 0) | 0.00 |
| t7 | v6 | D4 | 1.07 (1.79%) | 0 | 1; [43]; 1368 | 0.00 (0/3) | n/a (pred 0) | 0.00 | 0.00 |

v8sim11 violation sources (viol_src per violating minute): t3/S4a: {3: ['R38', 'capacity', 'slot'], 4: ['R38', 'capacity', 'slot', 'vy'], 5: ['slot']}; t3/S4b: {3: ['R38', 'capacity', 'slot'], 4: ['capacity', 'slot', 'vy'], 5: ['R38', 'capacity', 'slot'], 7: ['slot'], 8: ['slot']}; t3/v6: {3: ['R38', 'capacity', 'slot'], 4: ['capacity', 'slot', 'vy'], 5: ['R38', 'capacity', 'slot'], 7: ['slot'], 8: ['slot']}; t4/S4a: {20: ['R38'], 21: ['R38']}; t4/S4b: {20: ['R38', 'capacity', 'slot'], 21: ['R38'], 49: ['R38'], 50: ['R38']}; t4/v6: {20: ['R38', 'capacity', 'slot', 'vy'], 21: ['R38']}; t6/S4a: {17: ['R38'], 43: ['R38'], 44: ['R38']}; t6/S4b: {17: ['R38'], 18: ['R38'], 32: ['R38'], 33: ['R38', 'slot'], 43: ['R38']}; t6/v6: {17: ['R38'], 18: ['R38']}; t7/v6: {43: ['R38']}

### (6) Re-bucketing by rise1 (max one-minute rise), same decile method (percentile rank, mid-rank ties)

rise1 is integer-valued with heavy ties (library P10/P50/P90 = 7/9/14), so some deciles are empty and others wide; empty deciles are shown as '-' and omitted from the figure.

| decile | rise1 range | n windows | S4a mean risk (%) | S4b mean risk (%) | v6 mean risk (%) | traces |
|---|---|---|---|---|---|---|
| D1 (P0-P10) | 4-6 | 122 | 0.05 | 0.29 | 0.64 | t2,t5 |
| D2 (P10-P20) | 7-7 | 222 | 0.07 | 1.02 | 1.65 | t6,t7 |
| D3 (P20-P30) | 8-8 | 268 | 0.16 | 1.18 | 1.85 |  |
| D4 (P30-P40) | - | 0 | - | - | - |  |
| D5 (P40-P50) | 9-9 | 230 | 0.15 | 1.50 | 1.95 | t4 |
| D6 (P50-P60) | 10-10 | 201 | 0.39 | 2.16 | 2.55 |  |
| D7 (P60-P70) | 11-11 | 174 | 0.42 | 2.16 | 2.51 |  |
| D8 (P70-P80) | 12-12 | 143 | 0.75 | 2.86 | 3.65 | t1,t3 |
| D9 (P80-P90) | 13-13 | 69 | 1.01 | 3.33 | 3.02 |  |
| D10 (P90-P100) | 14-22 | 186 | 1.76 | 3.63 | 4.24 |  |

Trace placement by rise1: t1: rise1 = 12, percentile rank 79.8 -> D8; t2: rise1 = 5, percentile rank 1.7 -> D1; t3: rise1 = 12, percentile rank 79.8 -> D8; t4: rise1 = 9, percentile rank 45.0 -> D5; t5: rise1 = 6, percentile rank 5.2 -> D1; t6: rise1 = 7, percentile rank 14.4 -> D2; t7: rise1 = 7, percentile rank 14.4 -> D2. By rise10 the same traces were: t1 -> D6; t2 -> D3; t3 -> D9; t4 -> D2; t5 -> D3; t6 -> D4; t7 -> D4.

| trace | rise1 decile | arm | decile mean sim. risk (%) | measured (%) | ratio = decile mean / measured | verdict (rule A.3, t3/t4) | rise10 decile mean (%) / ratio |
|---|---|---|---|---|---|---|---|
| t3 | D8 (12-12) | S4b | 2.86 | 7.78 (14/180) | 0.37 | simulator under-estimates tail risk by factor 2.72 | 2.94 / 0.38 |
| t3 | D8 (12-12) | S4a | 0.75 | 3.89 (7/180) | 0.19 | simulator under-estimates tail risk by factor 5.21 | 0.80 / 0.20 |
| t3 | D8 (12-12) | v6 | 3.65 | 9.44 (17/180) | 0.39 | simulator under-estimates tail risk by factor 2.59 | 3.92 / 0.41 |
| t4 | D5 (9-9) | S4b | 1.50 | 5.56 (10/180) | 0.27 | simulator under-estimates tail risk by factor 3.70 | 0.68 / 0.12 |
| t4 | D5 (9-9) | S4a | 0.15 | 1.67 (3/180) | 0.09 | simulator under-estimates tail risk by factor 10.95 | 0.05 / 0.03 |
| t4 | D5 (9-9) | v6 | 1.95 | 2.78 (5/180) | 0.70 | within [0.5, 2] | 0.71 / 0.26 |
| t6 | D2 (7-7) | S4b | 1.02 | 0.00 (0/180) | n/a (measured 0) | (reference only) | 1.53 / nan |
| t6 | D2 (7-7) | S4a | 0.07 | 0.00 (0/180) | n/a (measured 0) | (reference only) | 0.22 / nan |
| t6 | D2 (7-7) | v6 | 1.65 | 2.78 (5/180) | 0.59 | (reference only) | 1.79 / 0.64 |
| t7 | D2 (7-7) | S4b | 1.02 | 0.00 (0/180) | n/a (measured 0) | (reference only) | 1.53 / nan |
| t7 | D2 (7-7) | S4a | 0.07 | 0.56 (1/180) | 0.12 | (reference only) | 0.22 / 0.40 |
| t7 | D2 (7-7) | v6 | 1.65 | 0.00 (0/180) | n/a (measured 0) | (reference only) | 1.79 / nan |

t4 outcome: rise1 = 9 (library percentile rank 45.0) -> D5; by rise10 it was D2: t4 moves to a higher decile. Decile mean risk at t4's rise1 decile: S4a 0.15%, S4b 1.50%, v6 1.95% vs at its rise10 decile: S4a 0.05%, S4b 0.68%, v6 0.71%.

Verdicts (rule A.3 with rise1 deciles): t3/S4b: ratio 0.37 -> simulator under-estimates tail risk by factor 2.72; t3/S4a: ratio 0.19 -> simulator under-estimates tail risk by factor 5.21; t3/v6: ratio 0.39 -> simulator under-estimates tail risk by factor 2.59; t4/S4b: ratio 0.27 -> simulator under-estimates tail risk by factor 3.70; t4/S4a: ratio 0.09 -> simulator under-estimates tail risk by factor 10.95; t4/v6: ratio 0.70 -> within [0.5, 2]

Figure: /home/user/docs/paper-v2/figs/fig_m1_risk_vs_burst_rise1.pdf (single column; same encoding as fig_m1_risk_vs_burst.pdf, x = rise1 decile; empty deciles omitted).

Runtime: v8sim11 12 runs + cfg_prior 0.3 s; whole script 2.5 s.
