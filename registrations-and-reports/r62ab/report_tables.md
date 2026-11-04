## Step 0 verification

Lookup vs fresh frozen `v8sim10.sim_nest2` (acct dispatch and vmexist), traces [523, 734, 1275, 1414, 1519] x all 221 points = 1105 pairs: **0 mismatches** (slo, minute vector, alloc dispatch, alloc vmexist, flaps compared exactly) [63s]

Six-split calibration on the matrix vs frozen v8sim10_FULL_2026-10-06.txt (grouped_split seeds 0-5, cal[:300], coarse 6x7 + ±0.25):

| target | split | λ lookup | λ frozen | cal risk lookup / frozen | ho risk lookup / frozen | ho alloc dispatch lookup / frozen | ho alloc vmexist |
|---|---|---|---|---|---|---|---|
| 0.02 | 0 | 1.75/2.0 | 1.75/2.0 | 0.0186 / 0.0186 | 0.0190 / 0.0190 | 1295.9 / 1295.9 | 1288.5 |
| 0.02 | 1 | 2.0/2.0 | 2.0/2.0 | 0.0182 / 0.0182 | 0.0175 / 0.0175 | 1296.3 / 1296.3 | 1288.8 |
| 0.02 | 2 | 1.75/2.0 | 1.75/2.0 | 0.0193 / 0.0193 | 0.0205 / 0.0205 | 1282.7 / 1282.7 | 1274.8 |
| 0.02 | 3 | 1.75/2.0 | 1.75/2.0 | 0.0199 / 0.0199 | 0.0214 / 0.0214 | 1288.3 / 1288.3 | 1280.8 |
| 0.02 | 4 | 1.75/2.0 | 1.75/2.0 | 0.0191 / 0.0191 | 0.0211 / 0.0211 | 1283.4 / 1283.4 | 1275.4 |
| 0.02 | 5 | 2.0/2.0 | 2.0/2.0 | 0.0187 / 0.0187 | 0.0169 / 0.0169 | 1294.2 / 1294.2 | 1286.7 |
| 0.02 | mean | 1.83±0.12 / 2.00±0.00 | | | 0.0194±0.0017 | 1290.1 | 1282.5 |
| 0.005 | 0 | 3.0/3.0 | 3.0/3.0 | 0.0048 / 0.0048 | 0.0050 / 0.0050 | 1351.9 / 1351.9 | 1346.9 |
| 0.005 | 1 | 2.75/3.25 | 2.75/3.25 | 0.0041 / 0.0041 | 0.0037 / 0.0037 | 1350.9 / 1350.9 | 1345.9 |
| 0.005 | 2 | 2.75/3.0 | 2.75/3.0 | 0.0048 / 0.0048 | 0.0053 / 0.0053 | 1337.4 / 1337.4 | 1331.6 |
| 0.005 | 3 | 2.25/3.25 | 2.25/3.25 | 0.0047 / 0.0047 | 0.0062 / 0.0062 | 1342.6 / 1342.6 | 1337.0 |
| 0.005 | 4 | 3.0/3.0 | 3.0/3.0 | 0.0048 / 0.0048 | 0.0054 / 0.0054 | 1338.9 / 1338.9 | 1333.4 |
| 0.005 | 5 | 2.25/3.25 | 2.25/3.25 | 0.0049 / 0.0049 | 0.0053 / 0.0053 | 1342.1 / 1342.1 | 1336.6 |
| 0.005 | mean | 2.67±0.31 / 3.12±0.12 | | | 0.0051±0.0007 | 1344.0 | 1338.6 |

## Task A: conditional λ by rise1 decile

rise1 thresholds P10..P90 (numpy linear): [7.0, 7.0, 8.0, 9.0, 9.0, 10.0, 11.0, 12.0, 14.0]

| decile | rise1 range | n |
|---|---|---|
| D1 | 4-7 | 344 |
| D2 | - | 0 |
| D3 | 8-8 | 268 |
| D4 | 9-9 | 230 |
| D5 | - | 0 |
| D6 | 10-10 | 201 |
| D7 | 11-11 | 174 |
| D8 | 12-12 | 143 |
| D9 | 13-14 | 134 |
| D10 | 15-22 | 121 |

Merged buckets (empty decile joined to the next non-empty one): D1, D2+3, D4, D5+6, D7, D8, D9, D10

Test-trace rise1 and bucket: t3 12 → D8, t4 9 → D4, t5 6 → D1, t6 7 → D1, t7 7 → D1

Per bucket, six grouped 60/40 splits over the bucket's (loc,date) groups (seed s: sorted keys, random.Random(s).shuffle, first int(0.6·G) groups = calibration, capped at 300 traces), calibrated by lookup; held-out = the bucket's remaining groups. ε ± SE rule: valid if |mean ho risk − ε| ≤ SE, SE = std/√6 (std ddof=0, as in the frozen reports). 'Not exceeding' = mean ho ≤ ε + SE. Full-λ risk = bucket mean risk under the deployed full-library λ (fresh sim, whole bucket).

### target 2 % (S4b)

| bucket | n | groups | cal n (mean) | ho n (mean) | λ_VM | λ_UP | cal risk | ho risk (mean ± std) | SE | ho alloc vmexist | full-λ risk (bucket) | valid (ε±SE) | not exceeding | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| D1 | 344 | 78 | 203 | 141 | 1.46 ± 0.09 | 1.54 ± 0.09 | 0.0190 | 0.0182 ± 0.0015 | 0.0006 | 1253.7 | 0.0076 | no | yes |  |
| D2+3 | 268 | 87 | 163 | 105 | 1.58 ± 0.19 | 1.83 ± 0.12 | 0.0189 | 0.0200 ± 0.0038 | 0.0016 | 1259.4 | 0.0118 | yes | yes |  |
| D4 | 230 | 91 | 140 | 90 | 1.54 ± 0.09 | 2.00 ± 0.00 | 0.0186 | 0.0180 ± 0.0018 | 0.0008 | 1267.3 | 0.0150 | no | yes |  |
| D5+6 | 201 | 88 | 121 | 80 | 1.58 ± 0.28 | 2.25 ± 0.14 | 0.0189 | 0.0211 ± 0.0056 | 0.0023 | 1294.1 | 0.0216 | yes | yes |  |
| D7 | 174 | 72 | 108 | 66 | 1.79 ± 0.17 | 2.25 ± 0.25 | 0.0185 | 0.0192 ± 0.0037 | 0.0015 | 1310.2 | 0.0216 | yes | yes |  |
| D8 | 143 | 72 | 87 | 56 | 1.92 ± 0.34 | 2.83 ± 0.34 | 0.0186 | 0.0200 ± 0.0048 | 0.0020 | 1328.0 | 0.0286 | yes | yes |  |
| D9 | 134 | 60 | 80 | 54 | 2.04 ± 0.34 | 2.75 ± 0.29 | 0.0191 | 0.0209 ± 0.0034 | 0.0014 | 1340.4 | 0.0313 | yes | yes |  |
| D10 | 121 | 45 | 74 | 47 | 2.42 ± 0.24 | 3.29 ± 0.09 | 0.0191 | 0.0163 ± 0.0033 | 0.0014 | 1306.5 | 0.0401 | no | yes |  |

**Valid buckets (ε ± SE), target 0.02: 5/8**; not exceeding ε+SE: 8/8. (2 empty decile(s) merged; count is out of 8 non-empty buckets.)

### target 0.5 % (S4a)

| bucket | n | groups | cal n (mean) | ho n (mean) | λ_VM | λ_UP | cal risk | ho risk (mean ± std) | SE | ho alloc vmexist | full-λ risk (bucket) | valid (ε±SE) | not exceeding | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| D1 | 344 | 78 | 203 | 141 | 2.08 ± 0.12 | 2.25 ± 0.00 | 0.0046 | 0.0036 ± 0.0009 | 0.0003 | 1297.8 | 0.0006 | no | yes |  |
| D2+3 | 268 | 87 | 163 | 105 | 2.29 ± 0.22 | 2.58 ± 0.12 | 0.0046 | 0.0051 ± 0.0007 | 0.0003 | 1304.4 | 0.0016 | yes | yes |  |
| D4 | 230 | 91 | 140 | 90 | 2.29 ± 0.17 | 2.79 ± 0.09 | 0.0044 | 0.0045 ± 0.0011 | 0.0004 | 1313.0 | 0.0015 | no | yes |  |
| D5+6 | 201 | 88 | 121 | 80 | 2.67 ± 0.40 | 2.88 ± 0.19 | 0.0043 | 0.0063 ± 0.0029 | 0.0012 | 1339.4 | 0.0039 | no | no |  |
| D7 | 174 | 72 | 108 | 66 | 2.25 ± 0.20 | 3.21 ± 0.09 | 0.0047 | 0.0044 ± 0.0017 | 0.0007 | 1350.5 | 0.0042 | yes | yes |  |
| D8 | 143 | 72 | 87 | 56 | 2.96 ± 0.55 | 3.50 ± 0.14 | 0.0045 | 0.0055 ± 0.0035 | 0.0014 | 1365.3 | 0.0075 | yes | yes | 3 split(s) refined off-matrix (fresh sim) |
| D9 | 134 | 60 | 80 | 54 | 2.71 ± 0.22 | 3.62 ± 0.12 | 0.0046 | 0.0042 ± 0.0022 | 0.0009 | 1376.9 | 0.0117 | yes | yes |  |
| D10 | 121 | 45 | 74 | 47 | 3.46 ± 0.09 | 4.50 ± 0.00 | 0.0070 | 0.0065 ± 0.0019 | 0.0008 | 1356.9 | 0.0198 | no | no | 5 split(s) infeasible on coarse grid → min-risk point; 1 split(s) refined off-matrix (fresh sim) |

**Valid buckets (ε ± SE), target 0.005: 4/8**; not exceeding ε+SE: 6/8. (2 empty decile(s) merged; count is out of 8 non-empty buckets.)

### Test traces under decile λ

Decile λ = mean of the bucket's six split λ (rounded to 0.01), target 0.5 % for S4a and 2 % for S4b. nest2 = frozen `v8sim10.sim_nest2(ue,cfg,pr,L,acct='vmexist')`; v8sim11 = `V.run(ue,'S',L=L)` (CtlSigma with the given λ, start=None → initial_fleet with the same λ, PHYS defaults, R38 on). Full-library λ columns: registered nest2 and v8sim11 values from m1/REPORT.md Supplement R58-2, re-simulated here (fresh value in brackets when it differs). Units: violating minutes per run (alloc vmexist in parentheses).

| trace | rise1 | bucket | arm | decile λ | full λ: nest2 | full λ: v8sim11 | decile λ: nest2 | decile λ: v8sim11 | hardware (total/runs) |
|---|---|---|---|---|---|---|---|---|---|
| t3 | 12 | D8 | S4a | 2.96/3.5 | 3 (1257) | 3 (1254) | 2 (1273) | 2 (1273) | 7/3 |
| t3 | 12 | D8 | S4b | 1.92/2.83 | 3 (1129) | 5 (1138) | 3 (1220) | 3 (1218) | 14/3 |
| t4 | 9 | D4 | S4a | 2.29/2.79 | 0 (1454) | 2 (1452) | 1 (1438) | 2 (1435) | 3/3 |
| t4 | 9 | D4 | S4b | 1.54/2.0 | 1 (1427) | 4 (1425) | 3 (1397) | 4 (1395) | 10/3 |
| t6 | 7 | D1 | S4a | 2.08/2.25 | 0 (1449) | 3 (1448) | 0 (1406) | 5 (1405) | 0/3 |
| t6 | 7 | D1 | S4b | 1.46/1.54 | 0 (1393) | 5 (1397) | 1 (1347) | 5 (1361) | 0/3 |
| t7 | 7 | D1 | S4a | 2.08/2.25 | 0 (1430) | 0 (1432) | 0 (1399) | 0 (1402) | 1/3 |
| t7 | 7 | D1 | S4b | 1.46/1.54 | 0 (1395) | 0 (1396) | 0 (1368) | 2 (1372) | 0/3 |

### Knob monotonicity (realised risk ordering S4a ≤ S4b ≤ v6)

Hardware: groups exactly 'MAIN tX S4a' / 'MAIN tX S4b' / 'MAIN tX v6' in rq_metrics.csv (VOID runs and 'v6 confirm post-IRQ' r381 excluded; r381 noted). Violating minutes per run = 60 − slo. Simulation rows: nest2 (S4a/S4b at deployed λ) and v8sim2.sim_v6 on the same trace; Madrid from qsim/madrid/t12_table.md; Melbourne library = fresh deployed-λ sims over all 1615 traces.

| setting | S4a | S4b | v6 | order | reversal? |
|---|---|---|---|---|---|
| hardware t3 | 7/3 (2.33) | 14/3 (4.67) | 17/3 (5.67) | S4a < S4b < v6 | **none** |
| hardware t4 | 3/3 (1.00) | 10/3 (3.33) | 5/3 (1.67) | S4a < v6 < S4b | **S4b > v6** |
| hardware t5 | 0/1 (0.00) | 0/1 (0.00) | 0/1 (0.00) | S4a ≤ S4b ≤ v6 | **none** |
| hardware t6 | 0/3 (0.00) | 0/3 (0.00) | 5/3 (1.67) | S4a ≤ S4b ≤ v6 | **none** |
| hardware t7 | 1/3 (0.33) | 0/3 (0.00) | 0/3 (0.00) | S4b ≤ v6 ≤ S4a | **S4a > S4b** |
| sim nest2/sim_v6 t3 | 3 | 3 | 3 | | none |
| sim nest2/sim_v6 t4 | 0 | 1 | 3 | | none |
| sim nest2/sim_v6 t5 | 0 | 0 | 0 | | none |
| sim nest2/sim_v6 t6 | 0 | 0 | 2 | | none |
| sim nest2/sim_v6 t7 | 0 | 0 | 0 | | none |
| madrid_1to1 (sim, mean risk %) | 0.048 | 0.213 | 0.396 | | none |
| madrid_compressed (sim, mean risk %) | 0.062 | 0.111 | 0.272 | | none |
| Melbourne library 1615 (sim, mean risk %) | 0.467 | 1.886 | 2.388 | | none |

(r381 'MAIN t4 v6 confirm post-IRQ': 4 violating minutes; including it, hardware t4 v6 = 9/4.)

## Task B: uncertainty

(loc,date) groups in library: 125

### B1 cluster bootstrap (200 resamples of the 125 groups with replacement, numpy default_rng(20261021).integers; calibration = first 300 resampled traces in draw order (primary, = the cal[:300] convention) or all resampled traces (secondary); held-out = groups never drawn)

| target | calibration | λ_VM mean [2.5, 97.5] | λ_UP mean [2.5, 97.5] | ho risk mean [2.5, 97.5] | P(ho risk > ε) | ho alloc vmexist mean [2.5, 97.5] | ho n (mean) | infeasible |
|---|---|---|---|---|---|---|---|---|
| 0.02 | 300 (primary) | 1.81 [1.50, 2.00] | 2.04 [2.00, 2.25] | 0.0190 [0.0134, 0.0240] | 0.33 | 1281.6 [1265.7, 1298.9] | 590 | 0 |
| 0.02 | all resampled | 1.87 [1.75, 2.00] | 2.00 [2.00, 2.00] | 0.0188 [0.0151, 0.0224] | 0.38 | 1281.6 [1265.0, 1298.2] | 590 | 0 |
| 0.005 | 300 (primary) | 2.59 [2.00, 3.00] | 3.12 [2.99, 3.50] | 0.0051 [0.0026, 0.0082] | 0.49 | 1335.8 [1316.9, 1352.7] | 590 | 0 |
| 0.005 | all resampled | 2.75 [2.50, 3.00] | 3.09 [3.00, 3.25] | 0.0048 [0.0029, 0.0069] | 0.45 | 1337.3 [1322.7, 1350.6] | 590 | 0 |

### B2 library size (calibration group budget)

125 = the standard six splits (grouped_split seeds 0-5: 75 calibration groups, 50 held-out groups). 60 / 30 = six random group subsets (seed s: sorted keys, random.Random(s).shuffle, first 60 / 30 groups), held-out = all groups not in the subset. 'cap 300' = calibration traces truncated to the first 300 (the frozen convention; with ≈13 traces per group this binds for 125 and 60 and nearly for 30), 'uncapped' = all traces of the calibration groups.

| target | groups | cap | cal n (mean) | λ_VM mean ± std | λ_UP mean ± std | ho risk mean ± std | ho alloc vmexist mean ± std |
|---|---|---|---|---|---|---|---|
| 0.02 | 125 | 300 | 300 | 1.83 ± 0.12 | 2.00 ± 0.00 | 0.0194 ± 0.0017 | 1282.5 ± 5.9 |
| 0.02 | 125 | uncapped | 979 | 1.83 ± 0.12 | 2.00 ± 0.00 | 0.0195 ± 0.0018 | 1282.5 ± 7.1 |
| 0.02 | 60 | 300 | 300 | 1.83 ± 0.12 | 2.00 ± 0.00 | 0.0193 ± 0.0016 | 1283.3 ± 5.3 |
| 0.02 | 60 | uncapped | 782 | 1.83 ± 0.12 | 2.00 ± 0.00 | 0.0194 ± 0.0018 | 1283.3 ± 6.2 |
| 0.02 | 30 | 300 | 300 | 1.83 ± 0.12 | 2.00 ± 0.00 | 0.0193 ± 0.0013 | 1280.4 ± 3.4 |
| 0.02 | 30 | uncapped | 390 | 1.79 ± 0.09 | 2.00 ± 0.00 | 0.0197 ± 0.0012 | 1279.2 ± 4.1 |
| 0.005 | 125 | 300 | 300 | 2.67 ± 0.31 | 3.12 ± 0.12 | 0.0051 ± 0.0007 | 1338.6 ± 5.8 |
| 0.005 | 125 | uncapped | 979 | 2.88 ± 0.19 | 3.04 ± 0.09 | 0.0050 ± 0.0005 | 1338.6 ± 4.7 |
| 0.005 | 60 | 300 | 300 | 2.67 ± 0.31 | 3.12 ± 0.12 | 0.0049 ± 0.0007 | 1339.2 ± 5.0 |
| 0.005 | 60 | uncapped | 782 | 2.71 ± 0.22 | 3.12 ± 0.12 | 0.0046 ± 0.0007 | 1340.2 ± 3.3 |
| 0.005 | 30 | 300 | 300 | 2.67 ± 0.31 | 3.12 ± 0.12 | 0.0050 ± 0.0006 | 1337.3 ± 2.6 |
| 0.005 | 30 | uncapped | 390 | 2.75 ± 0.29 | 3.08 ± 0.12 | 0.0050 ± 0.0004 | 1336.9 ± 3.2 |

### B3 event rate (consecutive violating minutes collapsed into one event)

Deployed points simulated fresh on all 1615 traces (dual-accounting copy of frozen nest2; 1.83 and 2.83 are off the 0.25 grid). v6 = frozen `v8sim2.sim_v6` does **not** expose per-minute violations (returns slo, alloc, acts, flaps only), so it was run through `dual.sim_v6_pm`, a copy generated from the frozen source whose only change is to also return the per-minute loss vector pct; slo/alloc/acts/flaps verified identical on 60 random traces (verify_dual.py) and violating minutes = 60 − slo checked on all 1615 traces. Grid points 1.75/2.00 and 2.75/3.00 from the matrix shown for reference.

| controller | λ | minute rate | events / 60-min trace | events / minute | mean event length (min) | max length | traces with ≥ 1 event | mean alloc vmexist |
|---|---|---|---|---|---|---|---|---|
| S4b (deployed) | 1.83/2.00 | 1.886 % | 0.949 | 0.01582 | 1.19 | 5 | 61.9 % | 1281.3 |
| S4a (deployed) | 2.83/3.08 | 0.467 % | 0.246 | 0.00410 | 1.14 | 4 | 20.4 % | 1338.2 |
| v6 | fixed constants | 2.388 % | 0.975 | 0.01624 | 1.47 | 6 | 65.6 % | - |
| grid ref (≈S4b) | 1.75/2.0 | 1.992 % | 0.980 | 0.01633 | 1.22 | 5 | 63.3 % | 1278.3 |
| grid ref (≈S4a) | 2.75/3.0 | 0.531 % | 0.275 | 0.00458 | 1.16 | 4 | 22.8 % | 1333.3 |

(off-matrix fresh sims for refinement: 747; analyze.py runtime 200 s)
