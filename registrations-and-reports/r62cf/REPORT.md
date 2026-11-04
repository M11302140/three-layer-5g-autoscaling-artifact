# r62cf — spec §4.104 Tasks C (equal-risk baselines) and F (operations cost, emergency-rule parity)

Generated 2026-10-21 by the r62cf scripts in `/home/user/experiment/qsim/r62cf/`. Simulation and arithmetic only; no testbed run, no change to λ/daemon/harness.
All python ran as `nice -n 19 taskset -c 13,14 python3 …`, one worker process at a time. Frozen files untouched (md5 before/after: `frozen_md5_before.txt` / `frozen_md5_after.txt`).
The stdlib `timeit` is imported before any qsim module (the local `qsim/timeit.py` shadows it).

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
| B6 | u ∈ {0.40, 0.45, …, 0.95}; 0.025; [0.375, 0.975] | — | W 10, dwell 300/600 |
| (reference) S single-λ in v8sim11 | λ_vy = λ_wk = λ_up ∈ {1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0}; 0.25; [1.0, 7.0] | — | k = 0 (ablation (a) single_lambda ≈ full within 0.4 %) |

Conservative → aggressive: small T / small u / long lead / long down = conservative (more capacity); large T / large u = aggressive. Deployed points (3.5/600, 4.0/(2,5,5), u 0.70) are coarse-grid points, so their whole-library values come out of the same cache.

Splits: `v8sim3.grouped_split(seed)` seeds 0–5 (60/40 by (loc, date) group), calibration = first 300 traces of the calibration part, held-out = the whole held-out part (629–645 traces). Each grid point is simulated once on all 1615 traces and cached (`cache/<fam>_<phys>_<knob>.json`, per-trace risk and cost vectors); calibration and held-out evaluation are lookups (deterministic simulators, so identical to re-simulating per split). Risk = mean over traces of violating-minute fraction (60 − slo)/60; cost = mean alloc per 60-min trace.

v8sim11 physics: "R38 on" = frozen default PHYS (placement-overflow rule: burst ≥ 7 arrivals with slot churn → .38 knee 4); "R38 off" = counterfactual `knee38 = 5` (§4.66 Table D; appendix-only). Reason to run both: S's nest2 risk is reproduced by v8sim11 only with R38 off (frozen library runs: S4a 0.45 % / 1337, S4b 2.18 % / 1282 vs nest2 0.467 % / 1338, 1.886 % / 1281); with R38 on, the same deployed λ gives 5.11 % / 7.53 % (`v8sim11_lib_S4a_r38on.json`, `…S4b_r38on.json`). Comparing nest2-S with R38-on baselines would therefore compare different physics.

Runner check: `eqcheck.py` — my explicit-controller runner `run_ctl` equals `v8sim11.run` for B4c2, B5c1, B6 u 0.70 and S λ 2.0 on 16 library traces each (0 mismatches of 64).

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
| S4b deployed λ 1.83/2.00, whole library | nest2 / vmexist | 0.0189 | 1281.3 | — | — |
| S4 recalibrated (ablation (e)), six-split held-out | nest2 / vmexist (dispatch) | 0.0194 (0.0007) | 1282.5 (1290.1) | — | — |
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
| S4a deployed λ 2.83/3.08, whole library | nest2 / vmexist | 0.0047 | 1338.2 | — | — |
| S4 recalibrated (ablation (e)), six-split held-out | nest2 / vmexist (dispatch) | 0.0051 (0.0003) | 1338.6 (1344.0) | — | — |
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

## F1 Operations sensitivity (t6, t7; actual-actuation counts)

Inputs: `paper_out_new/ops/ops_per_run.csv` (N_act = vy_create + vy_delete + wk_create + wk_delete + slot_start + slot_stop; N_flap = `flaps`, actual-actuation definition) and `paper_out_new/rq/rq_metrics.csv` (`alloc_vm`, groups "MAIN tX arm"). Three runs per arm and trace (B1: 1). J = C_alloc + α·N_act + β·N_flap (core-min per run).

### F1 per-arm means

| trace | arm | n | alloc_vm | N_act | N_flap |
|---|---|---|---|---|---|
| t6 | S4a | 3 | 1435.0 | 11.33 | 5.67 |
| t6 | S4b | 3 | 1390.3 | 15.00 | 6.00 |
| t6 | v6 | 3 | 1349.3 | 9.33 | 1.33 |
| t6 | B4c2 | 3 | 1455.7 | 1.33 | 0.00 |
| t6 | B5c1 | 3 | 1433.0 | 2.00 | 0.00 |
| t6 | B6 | 3 | 1447.3 | 2.00 | 0.00 |
| t6 | B1 | 1 | 1464.0 | 0.00 | 0.00 |
| t7 | S4a | 3 | 1427.0 | 10.00 | 3.00 |
| t7 | S4b | 3 | 1387.3 | 12.33 | 4.33 |
| t7 | v6 | 3 | 1353.0 | 9.00 | 2.67 |
| t7 | B4c2 | 3 | 1440.7 | 3.67 | 2.00 |
| t7 | B5c1 | 3 | 1413.0 | 3.67 | 0.00 |
| t7 | B6 | 3 | 1451.0 | 3.00 | 0.67 |
| t7 | B1 | 1 | 1464.0 | 0.00 | 0.00 |

### F1 mean-J saving of S4b = J(baseline) - J(S4b), core-min/run (percent of baseline J); **bold ≤ 0 = saving gone or reversed**


### t6

| alpha | beta | J(S4b) | vs B4c2 | vs B5c1 | vs B6 |
|---|---|---|---|---|---|
| 0 | 0 | 1390.3 | +65.3 (+4.49%) | +42.7 (+2.98%) | +57.0 (+3.94%) |
| 0 | 5 | 1420.3 | +35.3 (+2.43%) | +12.7 (+0.88%) | +27.0 (+1.87%) |
| 0 | 15 | 1480.3 | **-24.7 (-1.69%)** | **-47.3 (-3.30%)** | **-33.0 (-2.28%)** |
| 1 | 0 | 1405.3 | +51.7 (+3.55%) | +29.7 (+2.07%) | +44.0 (+3.04%) |
| 1 | 5 | 1435.3 | +21.7 (+1.49%) | **-0.3 (-0.02%)** | +14.0 (+0.97%) |
| 1 | 15 | 1495.3 | **-38.3 (-2.63%)** | **-60.3 (-4.20%)** | **-46.0 (-3.17%)** |
| 3 | 0 | 1435.3 | +24.3 (+1.67%) | +3.7 (+0.25%) | +18.0 (+1.24%) |
| 3 | 5 | 1465.3 | **-5.7 (-0.39%)** | **-26.3 (-1.83%)** | **-12.0 (-0.83%)** |
| 3 | 15 | 1525.3 | **-65.7 (-4.50%)** | **-86.3 (-6.00%)** | **-72.0 (-4.95%)** |
| 10 | 0 | 1540.3 | **-71.3 (-4.86%)** | **-87.3 (-6.01%)** | **-73.0 (-4.98%)** |
| 10 | 5 | 1570.3 | **-101.3 (-6.90%)** | **-117.3 (-8.08%)** | **-103.0 (-7.02%)** |
| 10 | 15 | 1630.3 | **-161.3 (-10.98%)** | **-177.3 (-12.20%)** | **-163.0 (-11.11%)** |

### t7

| alpha | beta | J(S4b) | vs B4c2 | vs B5c1 | vs B6 |
|---|---|---|---|---|---|
| 0 | 0 | 1387.3 | +53.3 (+3.70%) | +25.7 (+1.82%) | +63.7 (+4.39%) |
| 0 | 5 | 1409.0 | +41.7 (+2.87%) | +4.0 (+0.28%) | +45.3 (+3.12%) |
| 0 | 15 | 1452.3 | +18.3 (+1.25%) | **-39.3 (-2.78%)** | +8.7 (+0.59%) |
| 1 | 0 | 1399.7 | +44.7 (+3.09%) | +17.0 (+1.20%) | +54.3 (+3.74%) |
| 1 | 5 | 1421.3 | +33.0 (+2.27%) | **-4.7 (-0.33%)** | +36.0 (+2.47%) |
| 1 | 15 | 1464.7 | +9.7 (+0.66%) | **-48.0 (-3.39%)** | **-0.7 (-0.05%)** |
| 3 | 0 | 1424.3 | +27.3 (+1.88%) | **-0.3 (-0.02%)** | +35.7 (+2.44%) |
| 3 | 5 | 1446.0 | +15.7 (+1.07%) | **-22.0 (-1.54%)** | +17.3 (+1.18%) |
| 3 | 15 | 1489.3 | **-7.7 (-0.52%)** | **-65.3 (-4.59%)** | **-19.3 (-1.32%)** |
| 10 | 0 | 1510.7 | **-33.3 (-2.26%)** | **-61.0 (-4.21%)** | **-29.7 (-2.00%)** |
| 10 | 5 | 1532.3 | **-45.0 (-3.03%)** | **-82.7 (-5.70%)** | **-48.0 (-3.23%)** |
| 10 | 15 | 1575.7 | **-68.3 (-4.53%)** | **-126.0 (-8.69%)** | **-84.7 (-5.68%)** |

### F1 break-even alpha (saving = 0) for each beta: alpha* = (dC - beta*dFlap)/dAct, dX = X(S4b) - X(baseline) sign-adjusted

| trace | baseline | ΔC (base−S4b) | ΔN_act (S4b−base) | ΔN_flap (S4b−base) | alpha* @beta 0 | @beta 5 | @beta 15 |
|---|---|---|---|---|---|---|---|
| t6 | B4c2 | 65.3 | 13.67 | 6.00 | 4.78 | 2.59 | -1.80 |
| t6 | B5c1 | 42.7 | 13.00 | 6.00 | 3.28 | 0.97 | -3.64 |
| t6 | B6 | 57.0 | 13.00 | 6.00 | 4.38 | 2.08 | -2.54 |
| t7 | B4c2 | 53.3 | 8.67 | 2.33 | 6.15 | 4.81 | 2.12 |
| t7 | B5c1 | 25.7 | 8.67 | 4.33 | 2.96 | 0.46 | -4.54 |
| t7 | B6 | 63.7 | 9.33 | 3.67 | 6.82 | 4.86 | 0.93 |

Reading: at α = β = 0, S4b saves 43–65 core-min/run on t6 (3.0–4.5 %) and 26–64 on t7 (1.8–4.4 %). The saving is erased by very modest operation prices, because S4b makes 12–15 actuations and 4–6 flaps per run against 1.3–3.7 and 0–2 for the baselines:
- **vs B5c1** (smallest cost gap): the saving reaches 0 at (α 1, β 5) on t6 and t7, at (α 3, β 0) on t7, and at β 15 with any α. Break-even α* at β 0 is 3.3 (t6) / 3.0 (t7).
- **vs B4c2**: it reaches 0 at (α 0, β 15) and (α 3, β 5) on t6; on t7 it holds up to (α 3, β 5) and reverses at (α 3, β 15) and α 10. α* at β 0 is 4.8 / 6.2.
- **vs B6**: it reaches 0 at (α 0, β 15) and (α 3, β 5) on t6; on t7 at (α 1, β 15) and (α 3, β 15). α* at β 0 is 4.4 / 6.8.
- At α = 10 every comparison reverses on both traces. With β = 15 every t6 comparison reverses even at α = 0.

## F2 Emergency-rule parity (v8sim11 copy `v8sim11_emerg.py`)

**What v8sim11 models.** The frozen v8sim11 has **no emergency rule for any arm** (no S, v6 or baseline code path; `grep -i emerg` empty). The S arms are therefore reported unchanged: "S without the rule" = frozen v8sim11. To make the parity question answerable, the copy adds the daemon rule as an optional wrapper (`run(..., emerg=True)`) that can be applied to **every** arm. "S/v6 with the rule" is the deployed-like configuration; "B4c2/B5c1/B6 with the rule" is the parity variant. With `emerg=False` the copy is bit-identical to frozen `v8sim11.run` (SLO, violating minutes and alloc on all 24 arm×trace cells: `equiv True`).

**Rule as ported** (planner.go `EmergencyV6` 647–672, v6shadow.go 882–900 latch and EWMA, controller.go 236–290 force block):
- offered = D × 250 kpps (sigma-mode daemon uses UECount × PerUEBidir); offeredEWMA = 0.7·prev + 0.3·offered per 30 s tick, used in every branch (as the daemon passes `v.offeredEWMA`).
- **Measured loss mapping:** meas_UP = P90 over the last 60 s (12 × 5 s physics steps) of the slot-overflow loss / D, and meas_VY = the same for VyOS-overflow loss (daemon: `DropUP.P90_60`, `VyosLossRatio.P90_60`). This is valid when D ≥ 1 (≥ 200 kpps). e2e = 1 − (1 − meas_VY)(1 − meas_UP).
- NUP = RepUP (booting + ready + draining pods); NVY = admitted VyOS. uVY = EWMA / (NVY · 4.45 M); uUP = EWMA / (NUP · 1.35 M).
- raw = (e2e ≥ 0.001 ∧ (uVY ≥ 0.5 ∨ uUP ≥ 0.5)) ∨ uVY ≥ 1.001 ∨ uUP ≥ 1.020. Here 1.001 = ThetaCritVY with the empty pre-cliff table (1 − 1/u = 0.001), and 1.020 = ThetaCritUP = 1 + ln(1.001)/0.05. The rule latches after 2 consecutive raw ticks.
- Force: if latched, the controller dispatched no scale-out (or drain cancel) in this tick, and more than 90 s have passed since the last force, then:
  - if meas_VY ≥ meas_UP and VyOS VMs < 3, deploy a VyOS;
  - else, if RepUP < 8 and no slot is booting, scale out one slot (cancel a drain if one is in flight). If there is no ready worker position, create the slot's worker first when none is booting (executor behaviour).
  - The force is suppressed if the reverse action was dispatched within T_ready(rev) + T_ready(act) + 30 s (VyOS 145 s, slot 165 s), as in the daemon.

| arm | trace | SLO without rule | SLO with rule | Δ SLO min | alloc without | alloc with | Δ alloc | latched ticks | why the force did not act (ticks) | forces attempted (t s, action, dispatched) |
|---|---|---|---|---|---|---|---|---|---|---|
| S4a | t3 | 57/60 | 57/60 | +0 | 1254 | 1254 | +0 | 6 | controller_scaled_out 1, no_action:slots_at_max_8 5 | — |
| S4a | t4 | 58/60 | 58/60 | +0 | 1452 | 1452 | +0 | 3 | no_action:slots_at_max_8 3 | — |
| S4a | t6 | 57/60 | 57/60 | +0 | 1448 | 1448 | +0 | 5 | no_action:slots_at_max_8 5 | — |
| S4a | t7 | 60/60 | 60/60 | +0 | 1432 | 1432 | +0 | 0 | — | — |
| S4b | t3 | 55/60 | 55/60 | +0 | 1138 | 1138 | +0 | 9 | refractory 1, controller_scaled_out 2, no_action:slots_at_max_8 5 | 240 up(noworker,worker booting) False |
| S4b | t4 | 56/60 | 56/60 | +0 | 1425 | 1425 | +0 | 6 | no_action:slots_at_max_8 6 | — |
| S4b | t6 | 55/60 | 55/60 | +0 | 1397 | 1397 | +0 | 8 | no_action:slots_at_max_8 8 | — |
| S4b | t7 | 60/60 | 60/60 | +0 | 1396 | 1396 | +0 | 0 | — | — |
| v6 | t3 | 55/60 | 55/60 | +0 | 1119 | 1119 | +0 | 9 | refractory 1, controller_scaled_out 2, no_action:slots_at_max_8 5 | 240 up(noworker,worker booting) False |
| v6 | t4 | 58/60 | 58/60 | +0 | 1382 | 1382 | +0 | 3 | no_action:slots_at_max_8 3 | — |
| v6 | t6 | 58/60 | 58/60 | +0 | 1365 | 1365 | +0 | 3 | no_action:slots_at_max_8 3 | — |
| v6 | t7 | 59/60 | 59/60 | +0 | 1368 | 1368 | +0 | 1 | controller_scaled_out 1 | — |
| B4c2 | t3 | 57/60 | 57/60 | +0 | 1234 | 1234 | +0 | 6 | refractory 2, controller_scaled_out 1, no_action:slots_at_max_8 2 | 240 up(noworker,worker booting) False |
| B4c2 | t4 | 60/60 | 60/60 | +0 | 1447 | 1447 | +0 | 0 | — | — |
| B4c2 | t6 | 60/60 | 60/60 | +0 | 1448 | 1448 | +0 | 0 | — | — |
| B4c2 | t7 | 60/60 | 60/60 | +0 | 1442 | 1442 | +0 | 0 | — | — |
| B5c1 | t3 | 55/60 | 55/60 | +0 | 1163 | 1163 | +0 | 10 | refractory 2, controller_scaled_out 1, no_action:slots_at_max_8 6 | 240 up(noworker,worker booting) False |
| B5c1 | t4 | 58/60 | 58/60 | +0 | 1410 | 1410 | +0 | 3 | no_action:slots_at_max_8 3 | — |
| B5c1 | t6 | 58/60 | 58/60 | +0 | 1375 | 1375 | +0 | 3 | no_action:slots_at_max_8 3 | — |
| B5c1 | t7 | 60/60 | 60/60 | +0 | 1410 | 1410 | +0 | 0 | — | — |
| B6 | t3 | 55/60 | 55/60 | +0 | 1218 | 1218 | +0 | 6 | refractory 2, controller_scaled_out 1, no_action:slots_at_max_8 2 | 240 up(noworker,worker booting) False |
| B6 | t4 | 60/60 | 60/60 | +0 | 1447 | 1447 | +0 | 0 | — | — |
| B6 | t6 | 60/60 | 60/60 | +0 | 1437 | 1437 | +0 | 0 | — | — |
| B6 | t7 | 60/60 | 60/60 | +0 | 1448 | 1448 | +0 | 0 | — | — |

R38-off repeat (counterfactual knee38 = 5), same table condensed:

| arm | trace | SLO without / with | alloc without / with | latched | forces |
|---|---|---|---|---|---|
| S4a | t3 | 57 / 57 | 1255 / 1255 | 5 | — |
| S4a | t4 | 60 / 60 | 1452 / 1452 | 0 | — |
| S4a | t6 | 60 / 60 | 1448 / 1448 | 0 | — |
| S4a | t7 | 60 / 60 | 1432 / 1432 | 0 | — |
| S4b | t3 | 55 / 55 | 1138 / 1138 | 8 | 270 up(noworker,worker booting) False |
| S4b | t4 | 59 / 59 | 1425 / 1425 | 1 | — |
| S4b | t6 | 60 / 60 | 1390 / 1390 | 0 | — |
| S4b | t7 | 60 / 60 | 1396 / 1396 | 0 | — |
| v6 | t3 | 55 / 55 | 1119 / 1119 | 8 | 270 up(noworker,worker booting) False |
| v6 | t4 | 59 / 59 | 1382 / 1382 | 1 | — |
| v6 | t6 | 60 / 60 | 1360 / 1360 | 0 | — |
| v6 | t7 | 60 / 60 | 1368 / 1368 | 0 | — |
| B4c2 | t3 | 57 / 57 | 1234 / 1234 | 5 | 270 up(noworker,worker booting) False |
| B4c2 | t4 | 60 / 60 | 1447 / 1447 | 0 | — |
| B4c2 | t6 | 60 / 60 | 1448 / 1448 | 0 | — |
| B4c2 | t7 | 60 / 60 | 1442 / 1442 | 0 | — |
| B5c1 | t3 | 55 / 55 | 1163 / 1163 | 9 | 270 up(noworker,worker booting) False |
| B5c1 | t4 | 59 / 59 | 1410 / 1410 | 1 | — |
| B5c1 | t6 | 60 / 60 | 1375 / 1375 | 0 | — |
| B5c1 | t7 | 60 / 60 | 1410 / 1410 | 0 | — |
| B6 | t3 | 55 / 55 | 1218 / 1218 | 5 | 270 up(noworker,worker booting) False |
| B6 | t4 | 60 / 60 | 1447 / 1447 | 0 | — |
| B6 | t6 | 60 / 60 | 1437 / 1437 | 0 | — |
| B6 | t7 | 60 / 60 | 1448 / 1448 | 0 | — |

Whole-library supplement (1615 traces, R38 on; without-rule reference = frozen `v8sim11_lib_<arm>_r38on.json`):

| arm | risk without | risk with | Δ risk (pp) | cost without | cost with | Δ cost | forces attempted / dispatched | traces changed |
|---|---|---|---|---|---|---|---|---|
| S4a | 5.110 % | 5.118 % | +0.007 | 1337.5 | 1337.8 | +0.4 (+0.03 %) | 308 / 184 | 171 |
| S4b | 7.528 % | 7.492 % | -0.036 | 1282.4 | 1284.2 | +1.8 (+0.14 %) | 948 / 577 | 458 |
| v6 | 5.676 % | 5.607 % | -0.069 | 1258.8 | 1261.3 | +2.5 (+0.20 %) | 1152 / 608 | 483 |
| B4c2 | 2.215 % | 2.189 % | -0.026 | 1310.4 | 1311.2 | +0.8 (+0.06 %) | 545 / 216 | 185 |
| B5c1 | 3.948 % | 3.912 % | -0.036 | 1271.4 | 1273.2 | +1.8 (+0.14 %) | 1053 / 537 | 421 |
| B6 | 1.980 % | 1.979 % | -0.001 | 1319.6 | 1320.3 | +0.7 (+0.05 %) | 344 / 91 | 82 |

Reading: on t3, t4, t6 and t7 the rule changes **nothing for any arm** (Δ SLO 0, Δ alloc 0 in all 24 cells, in both physics variants). The latch does fire (0–10 ticks per run), but when it fires:
- in nearly every case all **8 slots are already open**, VyOS loss is 0 (so meas_VY < meas_UP), and the rule has no action left;
- otherwise the controller is itself scaling out in that tick, or the 90 s refractory blocks it;
- the single attempted force (t3 ≈ min 4, all arms) needs a slot on a worker that is still booting, so nothing is dispatched.

The violating minutes in these traces are per-slot placement overflow at full fleet, which +1 capacity cannot fix. Over the whole library the rule does dispatch (91–608 forces per arm over 1615 traces), but the effect is tiny: risk changes by −0.07 to +0.01 pp and cost by +0.03 to +0.20 %. B4c2, B5c1 and B6 gain −0.026, −0.036 and −0.001 pp. **Parity conclusion: giving the baselines the daemon's emergency rule, or removing it from S, would not change any t3–t7 comparison in this simulator.** Caveat: the simulator's "measured loss" is model loss, without the measurement noise and transients that make the real latch fire (the reason the daemon requires 2 ticks and u ≥ 0.5). Real-testbed emergency firings (ops_per_run `emergency` column) are therefore not reproduced one-to-one.

## Commands and runtimes

All commands were run in `/home/user/experiment/qsim/r62cf` as `nice -n 19 taskset -c 13,14 python3 <script>`, one process at a time.

| step | command | wall time |
|---|---|---|
| per-call benchmark | `bench.py` | ~1 min. B4c2 / B5c1 27 ms, v8sim11 B6 55 ms, v8sim11 S 56 ms, sim_b6 18 ms, nest2 30 ms, sim_v6 3 ms per trace (unloaded; 25–70 ms under load from the other agents) |
| runner equivalence | `eqcheck.py` | ~10 s, 0 mismatches of 64 |
| Task C calibration | `calib_c.py B4on B5on B6b6 B4off B5off Son B6on B6off Soff` (logs `calib_run.out` + `calib_run2.out`, `calib_progress.log`; results `calib_results.json`; cache `cache/`) | 00:53–03:32 = 2 h 39 min. Interrupted once at 01:07 to reorder phases: the cache was kept and the run resumed. 185 grid points × 1615 traces = 2.63 h of simulation |
| Task C tables | `analyze_c.py` → `c_tables.md` | < 5 s |
| F1 | `f1_ops.py` → `f1_tables.md`, `f1_rows.json` | < 1 s |
| F2 | `f2_emerg.py on` / `f2_emerg.py off` → `f2_results.json`, `f2_results_r38off.json`, `f2_run*.log`; `f2_lib.py` → `f2_lib.json` | 6 s / 9 s; library 7 min |

Total compute ≈ 2.9 h, under the 4 h cap. No grid resolution was reduced and all six splits were used. The phase order was changed only so that the S-in-v8sim11 reference and the R38-off phases were not cut by the budget guard.

## Limitations

- B4c2 and B5c1 exist only in the per-UE v8sim11. B6 exists in both sim_b6 (aggregate) and v8sim11, and no aggregate (nest2-type) B4/B5 model exists. The equal-risk statements are therefore made per physics; cross-physics rows are flagged above.
- μ (DASA) is tied to the HPA target at the deployed ratio (one knob per family plus down or lead). An independent μ dimension could lower the baselines' cost slightly further, so the "same level" verdicts are conservative for the baselines.
- sim_b6 and sim_v6 cost is dispatch accounting; v8sim11 cost is alloc_vm. Each comparison uses S in the matching accounting.
- The F2 measured-loss mapping is a model proxy (see the caveat above).
