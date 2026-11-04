<!-- artifact file of the paper "Predictable-Cost Autoscaling of a Three-Layer 5G User Plane with Library-Calibrated Risk" (docs/paper), written 2026-10-21 for the round-62 analyses (spec §4.104 H item 4, results §4.105). Content copied from qsim/r62cf/REPORT.md, sections C.1 to C.7, with dashes replaced by a colon or n/a; simulation only, no hardware run. -->

# Equal-risk baselines in simulation

The paper uses only the same-physics comparisons (per-slot simulator with R38 off, and sim_b6 for B6); the nest2-S against R38-on rows in C.6 are a cross-physics artefact (C.7) and are not used.

## C.1 Baseline models and their knobs (as found in the frozen code)

| baseline | simulator used | controller | knobs in code | deployed value |
|---|---|---|---|---|
| B4c2 (reactive: DASA VyOS + HPA slots + reactive worker) | `v8sim11` per-UE physics (`CtlB4(predictive=False)`) | `HPA(tol, target, 2, 8, down)` on sessions/slot; DASA `desired = ceil(D/μ)` (n0 1, kmax 2), delete if `D ≤ (cur−1)·μ·margin`; maxbatch 3 | `target` (HPA_TARGET), `mu` (DASA_MU), `tol`, `down`, `margin`, `maxbatch` | 3.5 / 12 / 0.05 / 600 s / 0.8 / 3 |
| B5c1 (point forecast) | `v8sim11` (`CtlB4(predictive=True)`) | same law fed with Holt(0.3, 0.05) forecast `max(x, L + lead·T)`; predictive worker pre-build; q11 position cap | as B4 + `holt`, `lead=(up, vy, wk)` ticks | 4.0 / 14 / 0.05 / 600 / 0.8, Holt (0.3, 0.05), lead (2, 5, 5) |
| B6 (Toka-type multi-forecaster) | `v8sim_b6.sim_b6(ue, cfg_measured, u, load_models())` aggregate physics (same `v8sim2.loss_step` as nest2 / sim_v6), **and** `v8sim11.CtlB6` per-UE physics | AR(3)/Holt/MLP, backtest selector W = 10; `need_k(forecast/u)`; dwell UP 300 / VM 600 | `u` (capacity-utilisation target) | 0.70 |

Neither `v8sim_b6.sim_b6` nor `v8sim2.sim_v6` supports vmexist accounting: their `alloc` burns a unit from dispatch to teardown completion (= nest2 `acct='dispatch'`). `v8sim11` reports `alloc_vm` (worker/VyOS VM existence: appear dispatch+15 s, gone delete+20 s; slot pod existence ×0.8) = the vmexist analogue. S is compared in the matching accounting (nest2 vmexist for v8sim11 rows, nest2 dispatch for sim_b6 rows).

## C.2 Parameter grids (fixed before running)

Coarse grid → cal-feasible cheapest → refine the continuous knob by ± one fine step (same discrete value) → cal-feasible cheapest among all evaluated points (planner procedure of v8sim10_cal.py / §4.99, applied per split).

| family | continuous knob (coarse; fine step; bounds) | second knob | fixed |
|---|---|---|---|
| B4c2 | HPA target T ∈ {2.0, 2.5, …, 5.0}; 0.25; [1.75, 5.25]. DASA μ tied to T at the deployed ratio μ = 12·T/3.5 (T 3.5 → μ 12) | down ∈ {300, 600, 900} s | tol 0.05, margin 0.8, maxbatch 3 |
| B5c1 | "threshold" = HPA target T ∈ {2.0, …, 5.0}; 0.25; [1.75, 5.25]. μ = 14·T/4.0 (T 4.0 → μ 14) | Holt lead ticks (up, vy, wk) ∈ {(1, 3, 3), (2, 5, 5), (4, 10, 10)} | tol 0.05, down 600, margin 0.8, Holt (0.3, 0.05) |
| B6 | u ∈ {0.40, 0.45, …, 0.95}; 0.025; [0.375, 0.975] |: | W 10, dwell 300/600 |
| (reference) S single-λ in v8sim11 | λ_vy = λ_wk = λ_up ∈ {1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0}; 0.25; [1.0, 7.0] |: | k = 0 (ablation (a) single_lambda ≈ full within 0.4 %) |

Conservative → aggressive: small T / small u / long lead / long down = conservative (more capacity); large T / large u = aggressive. Deployed points (3.5/600, 4.0/(2,5,5), u 0.70) are coarse-grid points, so their whole-library values come out of the same cache.

Splits: `v8sim3.grouped_split(seed)` seeds 0–5 (60/40 by (loc, date) group), calibration = first 300 traces of the calibration part, held-out = the whole held-out part (629–645 traces). Each grid point is simulated once on all 1615 traces and cached (`cache/<fam>_<phys>_<knob>.json`, per-trace risk and cost vectors); calibration and held-out evaluation are lookups (deterministic simulators, so identical to re-simulating per split). Risk = mean over traces of violating-minute fraction (60 − slo)/60; cost = mean alloc per 60-min trace.

v8sim11 physics: "R38 on" = frozen default PHYS (placement-overflow rule: burst ≥ 7 arrivals with slot churn → .38 knee 4); "R38 off" = counterfactual `knee38 = 5` (§4.66 Table D; appendix-only). Reason to run both: S's nest2 risk is reproduced by v8sim11 only with R38 off (frozen library runs: S4a 0.45 % / 1337, S4b 2.18 % / 1282 vs nest2 0.467 % / 1338, 1.886 % / 1281); with R38 on, the same deployed λ gives 5.11 % / 7.53 % (`v8sim11_lib_S4a_r38on.json`, `…S4b_r38on.json`). Comparing nest2-S with R38-on baselines would therefore compare different physics.

Runner check: `eqcheck.py`: my explicit-controller runner `run_ctl` equals `v8sim11.run` for B4c2, B5c1, B6 u 0.70 and S λ 2.0 on 16 library traces each (0 mismatches of 64).

## C.3 Per-split picks

| baseline | target | seed | pick | cal risk | cal cost | held-out risk | held-out cost | feasible |
|---|---|---|---|---|---|---|---|---|
| B4c2-family (v8sim11, R38 on) | 0.02 | 0 | [3.25, 300] | 0.0136 | 1313.5 | 0.0152 | 1337.0 | yes |
| B4c2-family (v8sim11, R38 on) | 0.02 | 1 | [3.5, 600] | 0.0197 | 1326.0 | 0.0219 | 1312.3 | yes |
| B4c2-family (v8sim11, R38 on) | 0.02 | 2 | [3.25, 300] | 0.0150 | 1321.3 | 0.0151 | 1326.7 | yes |
| B4c2-family (v8sim11, R38 on) | 0.02 | 3 | [3.25, 300] | 0.0141 | 1330.6 | 0.0160 | 1328.1 | yes |
| B4c2-family (v8sim11, R38 on) | 0.02 | 4 | [3.25, 300] | 0.0126 | 1345.7 | 0.0163 | 1322.7 | yes |
| B4c2-family (v8sim11, R38 on) | 0.02 | 5 | [3.25, 300] | 0.0157 | 1322.3 | 0.0133 | 1329.1 | yes |
| B4c2-family (v8sim11, R38 on) | 0.005 | 0 | [2.75, 300] | 0.0034 | 1353.3 | 0.0048 | 1374.4 | yes |
| B4c2-family (v8sim11, R38 on) | 0.005 | 1 | [2.75, 300] | 0.0033 | 1379.9 | 0.0051 | 1367.5 | yes |
| B4c2-family (v8sim11, R38 on) | 0.005 | 2 | [2.5, 300] | 0.0024 | 1378.8 | 0.0016 | 1385.4 | yes |
| B4c2-family (v8sim11, R38 on) | 0.005 | 3 | [2.75, 300] | 0.0038 | 1371.0 | 0.0048 | 1366.8 | yes |
| B4c2-family (v8sim11, R38 on) | 0.005 | 4 | [2.75, 300] | 0.0040 | 1380.5 | 0.0051 | 1363.7 | yes |
| B4c2-family (v8sim11, R38 on) | 0.005 | 5 | [2.5, 300] | 0.0029 | 1383.3 | 0.0015 | 1385.2 | yes |
| B5c1-family (v8sim11, R38 on) | 0.02 | 0 | [3.5, 'L1'] | 0.0156 | 1305.7 | 0.0179 | 1329.1 | yes |
| B5c1-family (v8sim11, R38 on) | 0.02 | 1 | [3.5, 'L1'] | 0.0161 | 1336.3 | 0.0165 | 1321.7 | yes |
| B5c1-family (v8sim11, R38 on) | 0.02 | 2 | [3.5, 'L1'] | 0.0161 | 1312.0 | 0.0170 | 1318.9 | yes |
| B5c1-family (v8sim11, R38 on) | 0.02 | 3 | [3.5, 'L1'] | 0.0179 | 1321.2 | 0.0179 | 1320.6 | yes |
| B5c1-family (v8sim11, R38 on) | 0.02 | 4 | [3.5, 'L1'] | 0.0163 | 1338.0 | 0.0184 | 1314.2 | yes |
| B5c1-family (v8sim11, R38 on) | 0.02 | 5 | [3.5, 'L1'] | 0.0184 | 1315.0 | 0.0157 | 1321.1 | yes |
| B5c1-family (v8sim11, R38 on) | 0.005 | 0 | [3.0, 'L4'] | 0.0045 | 1348.7 | 0.0053 | 1369.7 | yes |
| B5c1-family (v8sim11, R38 on) | 0.005 | 1 | [3.0, 'L1'] | 0.0050 | 1372.3 | 0.0065 | 1360.2 | yes |
| B5c1-family (v8sim11, R38 on) | 0.005 | 2 | [2.75, 'L1'] | 0.0035 | 1372.3 | 0.0025 | 1379.8 | yes |
| B5c1-family (v8sim11, R38 on) | 0.005 | 3 | [2.75, 'L1'] | 0.0027 | 1382.3 | 0.0033 | 1378.1 | yes |
| B5c1-family (v8sim11, R38 on) | 0.005 | 4 | [3.0, 'L2'] | 0.0047 | 1374.0 | 0.0062 | 1356.3 | yes |
| B5c1-family (v8sim11, R38 on) | 0.005 | 5 | [2.75, 'L1'] | 0.0034 | 1377.5 | 0.0020 | 1379.8 | yes |
| B6 (v8sim_b6.sim_b6, aggregate physics) | 0.02 | 0 | [0.775] | 0.0157 | 1286.2 | 0.0158 | 1308.0 | yes |
| B6 (v8sim_b6.sim_b6, aggregate physics) | 0.02 | 1 | [0.775] | 0.0151 | 1318.3 | 0.0152 | 1300.9 | yes |
| B6 (v8sim_b6.sim_b6, aggregate physics) | 0.02 | 2 | [0.775] | 0.0162 | 1292.8 | 0.0159 | 1295.3 | yes |
| B6 (v8sim_b6.sim_b6, aggregate physics) | 0.02 | 3 | [0.775] | 0.0159 | 1297.4 | 0.0178 | 1300.6 | yes |
| B6 (v8sim_b6.sim_b6, aggregate physics) | 0.02 | 4 | [0.775] | 0.0148 | 1318.3 | 0.0171 | 1294.0 | yes |
| B6 (v8sim_b6.sim_b6, aggregate physics) | 0.02 | 5 | [0.775] | 0.0155 | 1295.3 | 0.0163 | 1300.4 | yes |
| B6 (v8sim_b6.sim_b6, aggregate physics) | 0.005 | 0 | [0.4] | 0.0066 | 1409.3 | 0.0072 | 1424.6 | no (lowest achievable) |
| B6 (v8sim_b6.sim_b6, aggregate physics) | 0.005 | 1 | [0.4] | 0.0078 | 1425.1 | 0.0068 | 1420.2 | no (lowest achievable) |
| B6 (v8sim_b6.sim_b6, aggregate physics) | 0.005 | 2 | [0.45] | 0.0072 | 1409.4 | 0.0075 | 1413.8 | no (lowest achievable) |
| B6 (v8sim_b6.sim_b6, aggregate physics) | 0.005 | 3 | [0.45] | 0.0078 | 1417.6 | 0.0078 | 1412.0 | no (lowest achievable) |
| B6 (v8sim_b6.sim_b6, aggregate physics) | 0.005 | 4 | [0.4] | 0.0067 | 1425.0 | 0.0077 | 1421.4 | no (lowest achievable) |
| B6 (v8sim_b6.sim_b6, aggregate physics) | 0.005 | 5 | [0.45] | 0.0065 | 1414.8 | 0.0077 | 1413.4 | no (lowest achievable) |
| B6 (v8sim11 CtlB6, R38 on) | 0.02 | 0 | [0.7] | 0.0185 | 1305.4 | 0.0199 | 1328.3 | yes |
| B6 (v8sim11 CtlB6, R38 on) | 0.02 | 1 | [0.7] | 0.0193 | 1336.2 | 0.0182 | 1321.9 | yes |
| B6 (v8sim11 CtlB6, R38 on) | 0.02 | 2 | [0.7] | 0.0198 | 1312.4 | 0.0192 | 1318.0 | yes |
| B6 (v8sim11 CtlB6, R38 on) | 0.02 | 3 | [0.7] | 0.0191 | 1318.5 | 0.0208 | 1321.0 | yes |
| B6 (v8sim11 CtlB6, R38 on) | 0.02 | 4 | [0.7] | 0.0198 | 1337.6 | 0.0213 | 1315.4 | yes |
| B6 (v8sim11 CtlB6, R38 on) | 0.02 | 5 | [0.675] | 0.0152 | 1326.8 | 0.0138 | 1331.5 | yes |
| B6 (v8sim11 CtlB6, R38 on) | 0.005 | 0 | [0.575] | 0.0039 | 1356.0 | 0.0047 | 1378.0 | yes |
| B6 (v8sim11 CtlB6, R38 on) | 0.005 | 1 | [0.575] | 0.0048 | 1382.6 | 0.0051 | 1370.5 | yes |
| B6 (v8sim11 CtlB6, R38 on) | 0.005 | 2 | [0.55] | 0.0037 | 1373.2 | 0.0027 | 1380.5 | yes |
| B6 (v8sim11 CtlB6, R38 on) | 0.005 | 3 | [0.575] | 0.0046 | 1372.4 | 0.0054 | 1370.3 | yes |
| B6 (v8sim11 CtlB6, R38 on) | 0.005 | 4 | [0.575] | 0.0041 | 1383.9 | 0.0054 | 1368.0 | yes |
| B6 (v8sim11 CtlB6, R38 on) | 0.005 | 5 | [0.55] | 0.0042 | 1379.2 | 0.0026 | 1380.3 | yes |
| S single-λ (v8sim11, R38 on) | 0.02 | 0 | [5.0] | 0.0173 | 1395.1 | 0.0153 | 1411.1 | yes |
| S single-λ (v8sim11, R38 on) | 0.02 | 1 | [5.75] | 0.0148 | 1425.1 | 0.0096 | 1418.8 | yes |
| S single-λ (v8sim11, R38 on) | 0.02 | 2 | [4.75] | 0.0191 | 1396.1 | 0.0194 | 1400.4 | yes |
| S single-λ (v8sim11, R38 on) | 0.02 | 3 | [4.75] | 0.0196 | 1403.4 | 0.0187 | 1399.9 | yes |
| S single-λ (v8sim11, R38 on) | 0.02 | 4 | [5.0] | 0.0151 | 1411.9 | 0.0160 | 1404.4 | yes |
| S single-λ (v8sim11, R38 on) | 0.02 | 5 | [5.0] | 0.0168 | 1404.4 | 0.0138 | 1406.3 | yes |
| S single-λ (v8sim11, R38 on) | 0.005 | 0 | [6.25] | 0.0059 | 1418.4 | 0.0041 | 1430.4 | no (lowest achievable) |
| S single-λ (v8sim11, R38 on) | 0.005 | 1 | [6.25] | 0.0058 | 1431.9 | 0.0042 | 1426.8 | no (lowest achievable) |
| S single-λ (v8sim11, R38 on) | 0.005 | 2 | [6.25] | 0.0049 | 1424.9 | 0.0042 | 1427.2 | yes |
| S single-λ (v8sim11, R38 on) | 0.005 | 3 | [6.25] | 0.0039 | 1429.2 | 0.0044 | 1426.6 | yes |
| S single-λ (v8sim11, R38 on) | 0.005 | 4 | [6.25] | 0.0052 | 1430.9 | 0.0048 | 1426.3 | no (lowest achievable) |
| S single-λ (v8sim11, R38 on) | 0.005 | 5 | [6.25] | 0.0046 | 1427.6 | 0.0044 | 1427.2 | yes |
| B4c2-family (v8sim11, R38 off) | 0.02 | 0 | [3.75, 300] | 0.0166 | 1267.3 | 0.0176 | 1289.6 | yes |
| B4c2-family (v8sim11, R38 off) | 0.02 | 1 | [3.75, 300] | 0.0146 | 1299.2 | 0.0180 | 1282.3 | yes |
| B4c2-family (v8sim11, R38 off) | 0.02 | 2 | [3.75, 300] | 0.0142 | 1273.6 | 0.0180 | 1276.8 | yes |
| B4c2-family (v8sim11, R38 off) | 0.02 | 3 | [3.75, 300] | 0.0156 | 1278.6 | 0.0200 | 1280.7 | yes |
| B4c2-family (v8sim11, R38 off) | 0.02 | 4 | [3.75, 300] | 0.0159 | 1300.1 | 0.0188 | 1272.8 | yes |
| B4c2-family (v8sim11, R38 off) | 0.02 | 5 | [3.75, 300] | 0.0191 | 1271.2 | 0.0148 | 1281.4 | yes |
| B4c2-family (v8sim11, R38 off) | 0.005 | 0 | [3.25, 300] | 0.0043 | 1313.4 | 0.0060 | 1336.9 | yes |
| B4c2-family (v8sim11, R38 off) | 0.005 | 1 | [3.0, 300] | 0.0022 | 1361.4 | 0.0032 | 1348.2 | yes |
| B4c2-family (v8sim11, R38 off) | 0.005 | 2 | [3.0, 300] | 0.0030 | 1339.2 | 0.0027 | 1346.9 | yes |
| B4c2-family (v8sim11, R38 off) | 0.005 | 3 | [3.0, 300] | 0.0017 | 1349.0 | 0.0034 | 1347.1 | yes |
| B4c2-family (v8sim11, R38 off) | 0.005 | 4 | [3.25, 300] | 0.0047 | 1345.6 | 0.0053 | 1322.5 | yes |
| B4c2-family (v8sim11, R38 off) | 0.005 | 5 | [2.75, 300] | 0.0026 | 1363.7 | 0.0005 | 1368.2 | yes |
| B5c1-family (v8sim11, R38 off) | 0.02 | 0 | [4.0, 'L4'] | 0.0164 | 1263.4 | 0.0192 | 1283.8 | yes |
| B5c1-family (v8sim11, R38 off) | 0.02 | 1 | [4.0, 'L2'] | 0.0196 | 1290.2 | 0.0198 | 1272.9 | yes |
| B5c1-family (v8sim11, R38 off) | 0.02 | 2 | [4.0, 'L4'] | 0.0191 | 1271.3 | 0.0185 | 1273.0 | yes |
| B5c1-family (v8sim11, R38 off) | 0.02 | 3 | [4.0, 'L2'] | 0.0197 | 1269.7 | 0.0237 | 1273.1 | yes |
| B5c1-family (v8sim11, R38 off) | 0.02 | 4 | [4.0, 'L1'] | 0.0177 | 1291.2 | 0.0255 | 1265.4 | yes |
| B5c1-family (v8sim11, R38 off) | 0.02 | 5 | [3.75, 'L1'] | 0.0106 | 1293.3 | 0.0087 | 1300.9 | yes |
| B5c1-family (v8sim11, R38 off) | 0.005 | 0 | [3.5, 'L1'] | 0.0049 | 1305.6 | 0.0065 | 1329.0 | yes |
| B5c1-family (v8sim11, R38 off) | 0.005 | 1 | [3.25, 'L1'] | 0.0025 | 1357.8 | 0.0027 | 1344.6 | yes |
| B5c1-family (v8sim11, R38 off) | 0.005 | 2 | [3.25, 'L1'] | 0.0027 | 1336.0 | 0.0023 | 1343.4 | yes |
| B5c1-family (v8sim11, R38 off) | 0.005 | 3 | [3.5, 'L4'] | 0.0048 | 1325.2 | 0.0057 | 1324.8 | yes |
| B5c1-family (v8sim11, R38 off) | 0.005 | 4 | [3.5, 'L2'] | 0.0047 | 1338.3 | 0.0062 | 1315.0 | yes |
| B5c1-family (v8sim11, R38 off) | 0.005 | 5 | [3.25, 'L1'] | 0.0045 | 1340.2 | 0.0016 | 1344.2 | yes |
| B6 (v8sim11 CtlB6, R38 off) | 0.02 | 0 | [0.775] | 0.0127 | 1273.9 | 0.0137 | 1295.7 | yes |
| B6 (v8sim11 CtlB6, R38 off) | 0.02 | 1 | [0.775] | 0.0113 | 1304.7 | 0.0120 | 1288.2 | yes |
| B6 (v8sim11 CtlB6, R38 off) | 0.02 | 2 | [0.775] | 0.0128 | 1281.0 | 0.0122 | 1283.3 | yes |
| B6 (v8sim11 CtlB6, R38 off) | 0.02 | 3 | [0.775] | 0.0112 | 1285.1 | 0.0145 | 1288.0 | yes |
| B6 (v8sim11 CtlB6, R38 off) | 0.02 | 4 | [0.775] | 0.0132 | 1306.0 | 0.0135 | 1281.5 | yes |
| B6 (v8sim11 CtlB6, R38 off) | 0.02 | 5 | [0.775] | 0.0138 | 1281.5 | 0.0105 | 1288.2 | yes |
| B6 (v8sim11 CtlB6, R38 off) | 0.005 | 0 | [0.675] | 0.0029 | 1316.5 | 0.0041 | 1338.7 | yes |
| B6 (v8sim11 CtlB6, R38 off) | 0.005 | 1 | [0.675] | 0.0043 | 1345.8 | 0.0028 | 1331.8 | yes |
| B6 (v8sim11 CtlB6, R38 off) | 0.005 | 2 | [0.675] | 0.0044 | 1324.2 | 0.0028 | 1329.1 | yes |
| B6 (v8sim11 CtlB6, R38 off) | 0.005 | 3 | [0.7] | 0.0049 | 1318.4 | 0.0060 | 1320.9 | yes |
| B6 (v8sim11 CtlB6, R38 off) | 0.005 | 4 | [0.675] | 0.0031 | 1347.6 | 0.0039 | 1326.5 | yes |
| B6 (v8sim11 CtlB6, R38 off) | 0.005 | 5 | [0.65] | 0.0042 | 1339.1 | 0.0020 | 1342.8 | yes |
| S single-λ (v8sim11, R38 off) | 0.02 | 0 | [2.25] | 0.0155 | 1285.8 | 0.0158 | 1309.0 | yes |
| S single-λ (v8sim11, R38 off) | 0.02 | 1 | [2.25] | 0.0158 | 1316.8 | 0.0164 | 1303.0 | yes |
| S single-λ (v8sim11, R38 off) | 0.02 | 2 | [2.25] | 0.0168 | 1296.6 | 0.0152 | 1296.8 | yes |
| S single-λ (v8sim11, R38 off) | 0.02 | 3 | [2.25] | 0.0136 | 1296.9 | 0.0172 | 1302.1 | yes |
| S single-λ (v8sim11, R38 off) | 0.02 | 4 | [2.25] | 0.0147 | 1315.6 | 0.0190 | 1296.1 | yes |
| S single-λ (v8sim11, R38 off) | 0.02 | 5 | [2.5] | 0.0176 | 1309.9 | 0.0094 | 1315.0 | yes |
| S single-λ (v8sim11, R38 off) | 0.005 | 0 | [3.25] | 0.0042 | 1336.2 | 0.0026 | 1356.0 | yes |
| S single-λ (v8sim11, R38 off) | 0.005 | 1 | [3.25] | 0.0027 | 1362.5 | 0.0034 | 1350.1 | yes |
| S single-λ (v8sim11, R38 off) | 0.005 | 2 | [3.0] | 0.0048 | 1331.7 | 0.0052 | 1334.9 | yes |
| S single-λ (v8sim11, R38 off) | 0.005 | 3 | [3.25] | 0.0036 | 1348.1 | 0.0037 | 1348.8 | yes |
| S single-λ (v8sim11, R38 off) | 0.005 | 4 | [3.25] | 0.0028 | 1361.3 | 0.0032 | 1343.9 | yes |
| S single-λ (v8sim11, R38 off) | 0.005 | 5 | [3.25] | 0.0032 | 1343.9 | 0.0025 | 1348.0 | yes |

## C.4 Summary per baseline (mean ± population std over 6 splits; SE = std/√6)

| baseline | accounting | target | picks (6 splits) | cal risk | held-out risk (SE) | held-out cost | infeasible splits |
|---|---|---|---|---|---|---|---|
| B4c2-family (v8sim11, R38 on) | alloc_vm (VM existence) | 0.02 | 3.25/300, 3.5/600, 3.25/300, 3.25/300, 3.25/300, 3.25/300 | 0.0151 ± 0.0023 | 0.0163 ± 0.0027 (0.0011) | 1326.0 ± 7.5 | 0/6 |
| B4c2-family (v8sim11, R38 on) | alloc_vm (VM existence) | 0.005 | 2.75/300, 2.75/300, 2.5/300, 2.75/300, 2.75/300, 2.5/300 | 0.0033 ± 0.0005 | 0.0038 ± 0.0016 (0.0007) | 1373.8 ± 8.7 | 0/6 |
| B5c1-family (v8sim11, R38 on) | alloc_vm (VM existence) | 0.02 | 3.5/L1, 3.5/L1, 3.5/L1, 3.5/L1, 3.5/L1, 3.5/L1 | 0.0167 ± 0.0010 | 0.0172 ± 0.0009 (0.0004) | 1320.9 ± 4.4 | 0/6 |
| B5c1-family (v8sim11, R38 on) | alloc_vm (VM existence) | 0.005 | 3.0/L4, 3.0/L1, 2.75/L1, 2.75/L1, 3.0/L2, 2.75/L1 | 0.0040 ± 0.0008 | 0.0043 ± 0.0018 (0.0007) | 1370.6 ± 9.5 | 0/6 |
| B6 (v8sim_b6.sim_b6, aggregate physics) | dispatch | 0.02 | 0.775, 0.775, 0.775, 0.775, 0.775, 0.775 | 0.0155 ± 0.0005 | 0.0164 ± 0.0009 (0.0004) | 1299.9 ± 4.5 | 0/6 |
| B6 (v8sim_b6.sim_b6, aggregate physics) | dispatch | 0.005 | 0.4, 0.4, 0.45, 0.45, 0.4, 0.45 | 0.0071 ± 0.0005 | 0.0075 ± 0.0004 (0.0001) | 1417.6 ± 4.7 | 6/6 |
| B6 (v8sim11 CtlB6, R38 on) | alloc_vm (VM existence) | 0.02 | 0.7, 0.7, 0.7, 0.7, 0.7, 0.675 | 0.0186 ± 0.0016 | 0.0189 ± 0.0025 (0.0010) | 1322.7 ± 5.6 | 0/6 |
| B6 (v8sim11 CtlB6, R38 on) | alloc_vm (VM existence) | 0.005 | 0.575, 0.575, 0.55, 0.575, 0.575, 0.55 | 0.0042 ± 0.0004 | 0.0043 ± 0.0012 (0.0005) | 1374.6 ± 5.1 | 0/6 |
| S single-λ (v8sim11, R38 on) | alloc_vm (VM existence) | 0.02 | 5.0, 5.75, 4.75, 4.75, 5.0, 5.0 | 0.0171 ± 0.0018 | 0.0155 ± 0.0033 (0.0013) | 1406.8 ± 6.6 | 0/6 |
| S single-λ (v8sim11, R38 on) | alloc_vm (VM existence) | 0.005 | 6.25, 6.25, 6.25, 6.25, 6.25, 6.25 | 0.0050 ± 0.0007 | 0.0043 ± 0.0002 (0.0001) | 1427.4 ± 1.4 | 3/6 |
| B4c2-family (v8sim11, R38 off) | alloc_vm (VM existence) | 0.02 | 3.75/300, 3.75/300, 3.75/300, 3.75/300, 3.75/300, 3.75/300 | 0.0160 ± 0.0016 | 0.0179 ± 0.0016 (0.0007) | 1280.6 ± 5.2 | 0/6 |
| B4c2-family (v8sim11, R38 off) | alloc_vm (VM existence) | 0.005 | 3.25/300, 3.0/300, 3.0/300, 3.0/300, 3.25/300, 2.75/300 | 0.0031 ± 0.0011 | 0.0035 ± 0.0018 (0.0007) | 1345.0 ± 13.7 | 0/6 |
| B5c1-family (v8sim11, R38 off) | alloc_vm (VM existence) | 0.02 | 4.0/L4, 4.0/L2, 4.0/L4, 4.0/L2, 4.0/L1, 3.75/L1 | 0.0172 ± 0.0032 | 0.0192 ± 0.0053 (0.0022) | 1278.2 ± 11.5 | 0/6 |
| B5c1-family (v8sim11, R38 off) | alloc_vm (VM existence) | 0.005 | 3.5/L1, 3.25/L1, 3.25/L1, 3.5/L4, 3.5/L2, 3.25/L1 | 0.0040 ± 0.0010 | 0.0042 ± 0.0020 (0.0008) | 1333.5 ± 11.4 | 0/6 |
| B6 (v8sim11 CtlB6, R38 off) | alloc_vm (VM existence) | 0.02 | 0.775, 0.775, 0.775, 0.775, 0.775, 0.775 | 0.0125 ± 0.0010 | 0.0127 ± 0.0013 (0.0005) | 1287.5 ± 4.5 | 0/6 |
| B6 (v8sim11 CtlB6, R38 off) | alloc_vm (VM existence) | 0.005 | 0.675, 0.675, 0.675, 0.7, 0.675, 0.65 | 0.0040 ± 0.0007 | 0.0036 ± 0.0013 (0.0005) | 1331.6 ± 7.3 | 0/6 |
| S single-λ (v8sim11, R38 off) | alloc_vm (VM existence) | 0.02 | 2.25, 2.25, 2.25, 2.25, 2.25, 2.5 | 0.0156 ± 0.0013 | 0.0155 ± 0.0030 (0.0012) | 1303.7 ± 6.6 | 0/6 |
| S single-λ (v8sim11, R38 off) | alloc_vm (VM existence) | 0.005 | 3.25, 3.25, 3.0, 3.25, 3.25, 3.25 | 0.0035 ± 0.0007 | 0.0034 ± 0.0009 (0.0004) | 1347.0 ± 6.5 | 0/6 |

## C.5 Deployed knobs, whole library (from the cached grid points)

| baseline | knob | library risk | library cost |
|---|---|---|---|
| B4c2 T3.5/μ12/down600 | 3.5_600 | 0.0221 | 1310.4 |
| B5c1 T4.0/μ14/lead(2,5,5) | 4.0_L2 | 0.0395 | 1271.4 |
| B6 u0.70 (sim_b6) | 0.7 | 0.0120 | 1327.5 |
| B6 u0.70 (v8sim11) | 0.7 | 0.0198 | 1319.6 |
| B4c2 (R38 off) | 3.5_600 | 0.0104 | 1310.4 |
| B5c1 (R38 off) | 4.0_L2 | 0.0210 | 1271.3 |
| B6 u0.70 (v8sim11, R38 off) | 0.7 | 0.0055 | 1319.5 |

## C.6 Equal-risk cost table and verdicts
Rule: S 'cheaper' iff its equal-risk cost is lower by > 2 % of the baseline's; 'more expensive' iff higher by > 2 %; otherwise 'same level'. Risk-difference flag: |Δrisk| > combined SE √(SE_S² + SE_B²) (6-split SE = std/√6).


### target ε = 0.02

| row | simulator / accounting | risk (SE) | cost | S4-recal vs row: verdict | risk differs > 1 SE? |
|---|---|---|---|---|---|
| S4b deployed λ 1.83/2.00, whole library | nest2 / vmexist | 0.0189 | 1281.3 |: |: |
| S4 recalibrated (ablation (e)), six-split held-out | nest2 / vmexist (dispatch) | 0.0194 (0.0007) | 1282.5 (1290.1) |: |: |
| v6 fixed constants, whole library | v8sim2.sim_v6 / dispatch | 0.0239 | 1262.3 | S more expensive (-2.20 %) (dispatch vs dispatch) | v6 is not at ε (realised 0.0239) |
| B4c2-family (v8sim11, R38 on) | alloc_vm | 0.0163 (0.0011) | 1326.0 | S cheaper (+3.28 %) | YES (Δ = +0.0031) |
| B5c1-family (v8sim11, R38 on) | alloc_vm | 0.0172 (0.0004) | 1320.9 | S cheaper (+2.91 %) | YES (Δ = +0.0022) |
| B6 (v8sim_b6.sim_b6, aggregate physics) | dispatch | 0.0164 (0.0004) | 1299.9 | same level (+0.75 %) | YES (Δ = +0.0030) |
| B6 (v8sim11 CtlB6, R38 on) | alloc_vm | 0.0189 (0.0010) | 1322.7 | S cheaper (+3.04 %) | no (Δ = +0.0005) |
| B4c2-family (v8sim11, R38 off) | alloc_vm | 0.0179 (0.0007) | 1280.6 | same level (-0.15 %) | YES (Δ = +0.0015) |
| B5c1-family (v8sim11, R38 off) | alloc_vm | 0.0192 (0.0022) | 1278.2 | same level (-0.34 %) | no (Δ = +0.0002) |
| B6 (v8sim11 CtlB6, R38 off) | alloc_vm | 0.0127 (0.0005) | 1287.5 | same level (+0.39 %) | YES (Δ = +0.0067) |

*Within v8sim11 (R38 on): S single-λ calibrated in the same physics = held-out risk 0.0155 (0.0013), cost 1406.8.*

| baseline (same physics) | risk (SE) | cost | S-v8sim11 vs baseline | risk differs > 1 SE? |
|---|---|---|---|---|
| B4c2-family (v8sim11, R38 on) | 0.0163 (0.0011) | 1326.0 | S more expensive (-6.10 %) | no (Δ = -0.0008) |
| B5c1-family (v8sim11, R38 on) | 0.0172 (0.0004) | 1320.9 | S more expensive (-6.50 %) | YES (Δ = -0.0017) |
| B6 (v8sim11 CtlB6, R38 on) | 0.0189 (0.0010) | 1322.7 | S more expensive (-6.36 %) | YES (Δ = -0.0034) |

*Within v8sim11 (R38 off): S single-λ calibrated in the same physics = held-out risk 0.0155 (0.0012), cost 1303.7.*

| baseline (same physics) | risk (SE) | cost | S-v8sim11 vs baseline | risk differs > 1 SE? |
|---|---|---|---|---|
| B4c2-family (v8sim11, R38 off) | 0.0179 (0.0007) | 1280.6 | same level (-1.80 %) | YES (Δ = -0.0023) |
| B5c1-family (v8sim11, R38 off) | 0.0192 (0.0022) | 1278.2 | same level (-1.99 %) | YES (Δ = -0.0037) |
| B6 (v8sim11 CtlB6, R38 off) | 0.0127 (0.0005) | 1287.5 | same level (-1.26 %) | YES (Δ = +0.0028) |

### target ε = 0.005

| row | simulator / accounting | risk (SE) | cost | S4-recal vs row: verdict | risk differs > 1 SE? |
|---|---|---|---|---|---|
| S4a deployed λ 2.83/3.08, whole library | nest2 / vmexist | 0.0047 | 1338.2 |: |: |
| S4 recalibrated (ablation (e)), six-split held-out | nest2 / vmexist (dispatch) | 0.0051 (0.0003) | 1338.6 (1344.0) |: |: |
| v6 fixed constants, whole library | v8sim2.sim_v6 / dispatch | 0.0239 | 1262.3 | S more expensive (-6.47 %) (dispatch vs dispatch) | v6 is not at ε (realised 0.0239) |
| B4c2-family (v8sim11, R38 on) | alloc_vm | 0.0038 (0.0007) | 1373.8 | S cheaper (+2.56 %) | YES (Δ = +0.0013) |
| B5c1-family (v8sim11, R38 on) | alloc_vm | 0.0043 (0.0007) | 1370.6 | S cheaper (+2.34 %) | YES (Δ = +0.0008) |
| B6 (v8sim_b6.sim_b6, aggregate physics) [6/6 splits infeasible: lowest achievable] | dispatch | 0.0075 (0.0001) | 1417.6 | S cheaper (+5.19 %) | YES (Δ = -0.0024) |
| B6 (v8sim11 CtlB6, R38 on) | alloc_vm | 0.0043 (0.0005) | 1374.6 | S cheaper (+2.62 %) | YES (Δ = +0.0008) |
| B4c2-family (v8sim11, R38 off) | alloc_vm | 0.0035 (0.0007) | 1345.0 | same level (+0.47 %) | YES (Δ = +0.0016) |
| B5c1-family (v8sim11, R38 off) | alloc_vm | 0.0042 (0.0008) | 1333.5 | same level (-0.38 %) | YES (Δ = +0.0009) |
| B6 (v8sim11 CtlB6, R38 off) | alloc_vm | 0.0036 (0.0005) | 1331.6 | same level (-0.52 %) | YES (Δ = +0.0015) |

*Within v8sim11 (R38 on): S single-λ calibrated in the same physics = held-out risk 0.0043 (0.0001), cost 1427.4 [3/6 splits infeasible: lowest achievable].*

| baseline (same physics) | risk (SE) | cost | S-v8sim11 vs baseline | risk differs > 1 SE? |
|---|---|---|---|---|
| B4c2-family (v8sim11, R38 on) | 0.0038 (0.0007) | 1373.8 | S more expensive (-3.90 %) | no (Δ = +0.0005) |
| B5c1-family (v8sim11, R38 on) | 0.0043 (0.0007) | 1370.6 | S more expensive (-4.14 %) | no (Δ = +0.0001) |
| B6 (v8sim11 CtlB6, R38 on) | 0.0043 (0.0005) | 1374.6 | S more expensive (-3.84 %) | no (Δ = +0.0000) |

*Within v8sim11 (R38 off): S single-λ calibrated in the same physics = held-out risk 0.0034 (0.0004), cost 1347.0.*

| baseline (same physics) | risk (SE) | cost | S-v8sim11 vs baseline | risk differs > 1 SE? |
|---|---|---|---|---|
| B4c2-family (v8sim11, R38 off) | 0.0035 (0.0007) | 1345.0 | same level (-0.15 %) | no (Δ = -0.0001) |
| B5c1-family (v8sim11, R38 off) | 0.0042 (0.0008) | 1333.5 | same level (-1.01 %) | no (Δ = -0.0008) |
| B6 (v8sim11 CtlB6, R38 off) | 0.0036 (0.0005) | 1331.6 | same level (-1.15 %) | no (Δ = -0.0002) |


Grid points simulated: 185, total simulation time 2.63 h (single process).

## C.7 Reading and verdicts

**Which comparison is valid.** S's reference numbers come from nest2. v8sim11 reproduces them only with R38 off (S single-λ calibrated in v8sim11 R38 off: 1.55 % / 1303.7 at ε 2 %, 0.34 % / 1347.0 at ε 0.5 %; nest2 S4 recalibrated: 1.94 % / 1282.5 and 0.51 % / 1338.6). With R38 on (the frozen default), S itself costs **1406.8 at 2 %** and cannot reach 0.5 % on 3/6 calibration splits (lowest achievable is λ 6.25, 0.43 % / 1427.4). The verdicts "S cheaper than the R38-on baselines" in the C.6 main table compare nest2-S against R38-on baselines. They are a **cross-physics artefact and should not be published**. Valid comparisons:

| target | baseline | same-physics comparison | verdict (> 2 % rule) |
|---|---|---|---|
| 2 % | B4c2 | v8sim11 R38 off: S 1303.7 vs B4c2 1280.6 (S −1.80 %); nest2-S4 1282.5 vs B4c2 R38-off 1280.6 (−0.15 %) | **same level** (S nominally dearer); risks differ > 1 SE (S 1.55 % vs B4 1.79 % in v8sim11 R38 off) |
| 2 % | B5c1 | v8sim11 R38 off: 1303.7 vs 1278.2 (−1.99 %); nest2-S4 vs B5 R38-off −0.34 % | **same level** (borderline at −1.99 %); risk differs > 1 SE in v8sim11 (1.55 vs 1.92 %) |
| 2 % | B6 | sim_b6 (aggregate physics, dispatch): S4 dispatch 1290.1 vs B6 1299.9 (+0.75 %); v8sim11 R38 off: 1303.7 vs 1287.5 (−1.26 %) | **same level**; B6's held-out risk is lower (1.64 % sim_b6, 1.27 % v8sim11 R38 off), > 1 SE |
| 0.5 % | B4c2 | v8sim11 R38 off: 1347.0 vs 1345.0 (−0.15 %); nest2-S4 1338.6 vs 1345.0 (+0.47 %) | **same level** |
| 0.5 % | B5c1 | v8sim11 R38 off: 1347.0 vs 1333.5 (−1.01 %); nest2 vs B5 R38-off −0.38 % | **same level** |
| 0.5 % | B6 | sim_b6: **B6 cannot reach 0.5 %** (6/6 splits infeasible; lowest achievable u 0.40–0.45 = 0.75 % / 1417.6 dispatch) → S4 1344.0 dispatch at 0.51 % is **cheaper by 5.2 % at lower risk**. v8sim11 R38 off: B6 reaches 0.36 % / 1331.6, S 1347.0 (−1.15 %) | sim_b6: **S cheaper** (B6 cannot reach the target); v8sim11: **same level** |
| both | all three | v8sim11 **R38 on** (frozen default physics), same physics: S dearer by 6.1 / 6.5 / 6.4 % (2 %) and 3.9 / 4.1 / 3.8 % (0.5 %) than B4c2 / B5c1 / B6 | **S more expensive** under the R38 rule |

v6 (fixed constants, sim_v6 dispatch, library 2.39 % / 1262.3) is not at either ε. At its realised 2.39 % it is cheaper than S4-recal at 2 % (1290.1 dispatch) by 2.2 %.

Summary: in the physics that reproduces S's nest2 numbers (aggregate sim_b6 for B6, v8sim11 R38 off for all three), **S is at the same level (within 2 %) as every equal-risk-calibrated baseline at both targets**, except that sim_b6-B6 cannot reach 0.5 %. In the frozen default v8sim11 physics (R38 on), the placement-overflow rule penalises S much more than the baselines, which open slots earlier, and **S is 4–6.5 % more expensive**. Note on the risk side: at equal *target*, the baselines' held-out risks fall mostly below ε. Their knobs are coarse (one grid step moves library risk by about 0.5–3 pp), and they land on the conservative side. S4-recal's held-out risk (1.94 %, 0.51 %) is above most baseline rows by more than 1 SE, so the equal-target comparison slightly favours S on cost.

Deployed baseline knobs are not at ε: B4c2 3.5/600 = 2.21 % (R38 on) / 1.04 % (off); B5c1 4.0/(2,5,5) = 3.95 % / 2.10 %; B6 0.70 = 1.20 % (sim_b6), 1.98 % / 0.55 % (v8sim11 on/off). Recalibration moves B4 to T 3.25–3.75 with **down 300 s** at every split (the shorter down window is always cheaper at equal risk), B5 to T 3.5–4.0 with mostly the short lead (1, 3, 3) at 2 %, and B6 to u 0.70–0.775 (2 %) and 0.55–0.70 (0.5 %).

## Limitations

- B4c2 and B5c1 exist only in the per-UE v8sim11. B6 exists in both sim_b6 (aggregate) and v8sim11, and no aggregate (nest2-type) B4/B5 model exists. The equal-risk statements are therefore made per physics; cross-physics rows are flagged above.
- μ (DASA) is tied to the HPA target at the deployed ratio (one knob per family plus down or lead). An independent μ dimension could lower the baselines' cost slightly further, so the "same level" verdicts are conservative for the baselines.
- sim_b6 and sim_v6 cost is dispatch accounting; v8sim11 cost is alloc_vm. Each comparison uses S in the matching accounting.
- The F2 measured-loss mapping is a model proxy (see the caveat above).
