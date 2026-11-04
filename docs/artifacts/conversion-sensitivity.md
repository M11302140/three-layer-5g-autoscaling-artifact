<!-- artifact file of the paper "Predictable-Cost Autoscaling of a Three-Layer 5G User Plane with Library-Calibrated Risk" (docs/paper), written 2026-10-21 for the round-62 analyses (spec §4.104 H item 4, results §4.105). Content copied from qsim/r62de/REPORT.md, sections "Task D" to "D3", with dashes replaced by a colon or n/a; simulation only, no hardware run. -->

# Workload-conversion sensitivity

## Task D: workload-conversion sensitivity

### Raw source and pipeline
The raw per-minute counts are on disk: `/home/user/Downloads/3b4c9b89-c976-49e7-8358-075fe3699297.csv` (Melbourne Pedestrian Counting System,
resource 3b4c9b89). They are read by the frozen `make_prior.py`. `D_build.py` generalises that script without touching it.

Steps kept identical:
* sum over directions per (loc, date, minute)
* reindex 0..1439 plus linear interpolation (`limit_direction='both'`)
* keep a loc-day only if it has ≥ 1200 rows
* the same 15 window starts, 06:00–20:00 hourly
* centred rolling mean inside the window (`min_periods=1`)
* rejection if the smoothed window peak is < 20 /min, applied to that variant's own smoothed series
* UE = clip(round(40·C/Cmax), 1, 40)
* EXCLUDE = the three evaluation loc-days plus the heldout.json t4/t5 loc-days, as in `make_prior.py --with-heldout`

Varied: smoothing window ∈ {1, 5, 10} min; compression k:1 with **window length 60·k real minutes** (1:1 → 60, 2:1 → 120, 4:1 → 240 real minutes per
60-minute trace; each experiment minute is the mean of k consecutive real minutes); deadband ∈ {0 (none), 2}.
**Reproduction:** variant (5 min, 4:1, 2) equals `prior_traces.json` exactly (1615 traces, list equality), but only with the heldout exclusion. Without
it the build gives 1645 traces. That variant therefore reuses `E_base_p90`.
rise1 = max{u[t+1]−u[t]}; rise10 = max{u[j]−u[i]: 0<j−i≤10} (the `lib_percentiles.py` definition, unclamped), over the 60 experiment minutes; numpy linear
percentiles. Each variant gets its **own Prior** σ̂ and its **own** grouped splits, since the group sets differ: 128/125/120 groups for 1/5/10-min smoothing.
"need-floor" = Σ_min Σ_layer cores·need_l(D) at zero margin and zero lead. It is a demand-only scale, used to compare costs across libraries whose
demand differs.

## D1 library variants

| variant (smooth min, compression, deadband) | traces | (loc,date) groups | rise1 P10/P50/P90 | rise10 P10/P50/P90 | σ̂_win at D=20 VY/UP/WK | need-floor core-min/run |
|---|---|---|---|---|---|---|
| 1 / 1:1 / 0 | 1575 | 128 | 17/23/31 | 23/30/36 | 5.67/5.23/5.67 | 861.4 |
| 1 / 1:1 / 2 | 1575 | 128 | 17/23/31 | 23/30/36 | 5.67/5.26/5.67 | 861.3 |
| 1 / 2:1 / 0 | 1696 | 128 | 13/19/26 | 18/24/31 | 5.31/4.84/5.31 | 929.8 |
| 1 / 2:1 / 2 | 1696 | 128 | 13/19/26 | 18/24/31 | 5.31/4.88/5.31 | 929.7 |
| 1 / 4:1 / 0 | 1850 | 128 | 10/14/21 | 14/20/27 | 4.47/4.03/4.47 | 935.2 |
| 1 / 4:1 / 2 | 1850 | 128 | 10/14/21 | 14/20/27 | 4.48/4.07/4.48 | 935.2 |
| 5 / 1:1 / 0 | 1260 | 125 | 4/6/9 | 10/15/20 | 3.47/1.80/3.47 | 1160.0 |
| 5 / 1:1 / 2 | 1260 | 125 | 4/6/9 | 10/14/20 | 3.50/1.89/3.50 | 1160.1 |
| 5 / 2:1 / 0 | 1409 | 125 | 5/7/11 | 11/15/22 | 4.03/2.07/4.03 | 1088.2 |
| 5 / 2:1 / 2 | 1409 | 125 | 5/7/11 | 11/15/22 | 4.04/2.17/4.04 | 1088.5 |
| 5 / 4:1 / 0 | 1615 | 125 | 7/9/14 | 11/16/23 | 3.69/2.58/3.69 | 995.1 |
| 5 / 4:1 / 2 (= frozen library) | 1615 | 125 | 7/9/14 | 11/16/23 | 3.70/2.64/3.70 | 995.1 |
| 10 / 1:1 / 0 | 1166 | 120 | 2/3/5 | 5/9/14 | 1.80/0.95/1.80 | 1264.7 |
| 10 / 1:1 / 2 | 1166 | 120 | 3/4/5 | 5/9/14 | 1.87/1.05/1.87 | 1264.9 |
| 10 / 2:1 / 0 | 1311 | 120 | 3/4/6 | 7/11/17 | 2.30/1.05/2.30 | 1170.5 |
| 10 / 2:1 / 2 | 1311 | 120 | 3/4/6 | 6/11/16 | 2.36/1.19/2.36 | 1170.1 |
| 10 / 4:1 / 0 | 1502 | 120 | 4/5/8 | 8/13/20 | 2.90/1.36/2.90 | 1049.8 |
| 10 / 4:1 / 2 | 1502 | 120 | 4/5/8 | 8/13/19 | 2.91/1.47/2.91 | 1049.6 |


## D2 six-split recalibration per library variant (own Prior σ̂, own grouped splits)

| variant | target | λ_VM | λ_UP | cal risk | held-out risk | held-out alloc vmexist (dispatch) | Δalloc vs e | splits | alloc / need-floor |
|---|---|---|---|---|---|---|---|---|---|
| 1 / 1:1 / 0 | 0.02 | 1.58 ± 0.12 | 3.21 ± 0.39 | 0.0193 | 0.0192 ± 0.0016 | 1415.3 ± 3.6 (1420.8) | +10.35% | 6 | 1.643 |
| 1 / 1:1 / 0 | 0.005 | 2.38 ± 0.12 | 3.46 ± 0.17 | 0.0043 | 0.0044 ± 0.0014 | 1449.5 ± 4.0 (1451.9) | +8.29% | 6 | 1.683 |
| 1 / 1:1 / 2 | 0.02 | 1.58 ± 0.12 | 3.12 ± 0.12 | 0.0192 | 0.0190 ± 0.0021 | 1416.2 ± 4.0 (1421.7) | +10.43% | 6 | 1.644 |
| 1 / 1:1 / 2 | 0.005 | 2.42 ± 0.12 | 3.38 ± 0.12 | 0.0040 | 0.0042 ± 0.0014 | 1450.5 ± 4.0 (1452.7) | +8.36% | 6 | 1.684 |
| 1 / 2:1 / 0 | 0.02 | 1.54 ± 0.17 | 2.62 ± 0.28 | 0.0188 | 0.0197 ± 0.0026 | 1392.0 ± 6.8 (1396.9) | +8.53% | 6 | 1.497 |
| 1 / 2:1 / 0 | 0.005 | 2.29 ± 0.09 | 3.33 ± 0.19 | 0.0047 | 0.0050 ± 0.0016 | 1434.7 ± 4.9 (1437.4) | +7.18% | 6 | 1.543 |
| 1 / 2:1 / 2 | 0.02 | 1.54 ± 0.09 | 2.62 ± 0.19 | 0.0183 | 0.0189 ± 0.0020 | 1392.4 ± 5.5 (1397.3) | +8.57% | 6 | 1.498 |
| 1 / 2:1 / 2 | 0.005 | 2.33 ± 0.12 | 3.21 ± 0.17 | 0.0045 | 0.0049 ± 0.0021 | 1434.4 ± 6.3 (1436.8) | +7.16% | 6 | 1.543 |
| 1 / 4:1 / 0 | 0.02 | 1.75 ± 0.14 | 2.00 ± 0.00 | 0.0190 | 0.0196 ± 0.0015 | 1297.5 ± 6.7 (1304.7) | +1.17% | 6 | 1.387 |
| 1 / 4:1 / 0 | 0.005 | 2.38 ± 0.24 | 2.88 ± 0.12 | 0.0047 | 0.0052 ± 0.0011 | 1359.9 ± 9.8 (1364.5) | +1.59% | 6 | 1.454 |
| 1 / 4:1 / 2 | 0.02 | 1.71 ± 0.17 | 2.04 ± 0.09 | 0.0191 | 0.0195 ± 0.0020 | 1298.0 ± 8.5 (1305.3) | +1.21% | 6 | 1.388 |
| 1 / 4:1 / 2 | 0.005 | 2.50 ± 0.20 | 2.83 ± 0.12 | 0.0048 | 0.0050 ± 0.0011 | 1360.8 ± 9.7 (1365.2) | +1.66% | 6 | 1.455 |
| 5 / 1:1 / 0 | 0.02 | 1.92 ± 0.31 | 2.33 ± 0.12 | 0.0185 | 0.0189 ± 0.0037 | 1389.0 ± 4.8 (1394.9) | +8.30% | 6 | 1.197 |
| 5 / 1:1 / 0 | 0.005 | 2.83 ± 0.24 | 3.42 ± 0.31 | 0.0046 | 0.0047 ± 0.0012 | 1418.9 ± 5.2 (1422.0) | +6.00% | 6 | 1.223 |
| 5 / 1:1 / 2 | 0.02 | 2.08 ± 0.12 | 2.33 ± 0.12 | 0.0187 | 0.0189 ± 0.0025 | 1387.7 ± 5.2 (1393.5) | +8.20% | 6 | 1.196 |
| 5 / 1:1 / 2 | 0.005 | 3.12 ± 0.12 | 3.17 ± 0.12 | 0.0045 | 0.0045 ± 0.0012 | 1419.1 ± 5.2 (1422.0) | +6.01% | 6 | 1.223 |
| 5 / 2:1 / 0 | 0.02 | 1.83 ± 0.12 | 2.42 ± 0.12 | 0.0187 | 0.0188 ± 0.0011 | 1362.4 ± 4.8 (1367.9) | +6.23% | 6 | 1.252 |
| 5 / 2:1 / 0 | 0.005 | 2.79 ± 0.22 | 3.33 ± 0.24 | 0.0046 | 0.0047 ± 0.0011 | 1402.4 ± 5.8 (1405.3) | +4.76% | 6 | 1.289 |
| 5 / 2:1 / 2 | 0.02 | 2.00 ± 0.14 | 2.17 ± 0.19 | 0.0196 | 0.0193 ± 0.0017 | 1358.2 ± 8.1 (1364.0) | +5.90% | 6 | 1.248 |
| 5 / 2:1 / 2 | 0.005 | 2.79 ± 0.17 | 3.33 ± 0.12 | 0.0045 | 0.0047 ± 0.0009 | 1401.7 ± 5.9 (1404.6) | +4.71% | 6 | 1.288 |
| 5 / 4:1 / 0 | 0.02 | 1.79 ± 0.09 | 2.04 ± 0.09 | 0.0187 | 0.0192 ± 0.0020 | 1284.1 ± 6.5 (1291.6) | +0.12% | 6 | 1.290 |
| 5 / 4:1 / 0 | 0.005 | 2.54 ± 0.27 | 3.17 ± 0.19 | 0.0047 | 0.0050 ± 0.0007 | 1338.9 ± 4.7 (1344.1) | +0.02% | 6 | 1.345 |
| 5 / 4:1 / 2 | 0.02 | 1.83 ± 0.12 | 2.00 ± 0.00 | 0.0190 | 0.0194 ± 0.0017 | 1282.5 ± 5.9 (1290.1) | -0.00% | 6 | 1.289 |
| 5 / 4:1 / 2 | 0.005 | 2.67 ± 0.31 | 3.12 ± 0.12 | 0.0047 | 0.0051 ± 0.0007 | 1338.6 ± 5.8 (1344.0) | -0.00% | 6 | 1.345 |
| 10 / 1:1 / 0 | 0.02 | 1.50 ± 0.00 | 1.58 ± 0.12 | 0.0176 | 0.0189 ± 0.0010 | 1368.2 ± 4.9 (1373.7) | +6.68% | 6 | 1.082 |
| 10 / 1:1 / 0 | 0.005 | 2.42 ± 0.19 | 2.58 ± 0.19 | 0.0042 | 0.0049 ± 0.0008 | 1394.9 ± 3.8 (1398.8) | +4.21% | 6 | 1.103 |
| 10 / 1:1 / 2 | 0.02 | 1.92 ± 0.19 | 1.58 ± 0.19 | 0.0168 | 0.0184 ± 0.0022 | 1375.0 ± 6.8 (1379.7) | +7.21% | 6 | 1.087 |
| 10 / 1:1 / 2 | 0.005 | 2.67 ± 0.19 | 2.88 ± 0.24 | 0.0048 | 0.0054 ± 0.0009 | 1397.5 ± 4.8 (1400.8) | +4.40% | 6 | 1.105 |
| 10 / 2:1 / 0 | 0.02 | 1.83 ± 0.24 | 1.79 ± 0.39 | 0.0185 | 0.0205 ± 0.0023 | 1327.5 ± 5.3 (1333.9) | +3.51% | 6 | 1.134 |
| 10 / 2:1 / 0 | 0.005 | 2.79 ± 0.17 | 3.00 ± 0.00 | 0.0046 | 0.0056 ± 0.0006 | 1355.4 ± 6.2 (1360.6) | +1.25% | 6 | 1.158 |
| 10 / 2:1 / 2 | 0.02 | 1.71 ± 0.22 | 2.00 ± 0.00 | 0.0181 | 0.0197 ± 0.0032 | 1322.2 ± 7.8 (1328.7) | +3.09% | 6 | 1.130 |
| 10 / 2:1 / 2 | 0.005 | 2.71 ± 0.09 | 3.04 ± 0.09 | 0.0043 | 0.0053 ± 0.0006 | 1358.2 ± 6.1 (1362.8) | +1.46% | 6 | 1.161 |
| 10 / 4:1 / 0 | 0.02 | 2.00 ± 0.14 | 1.88 ± 0.19 | 0.0191 | 0.0216 ± 0.0026 | 1254.5 ± 10.0 (1262.2) | -2.18% | 6 | 1.195 |
| 10 / 4:1 / 0 | 0.005 | 2.75 ± 0.20 | 3.04 ± 0.09 | 0.0045 | 0.0060 ± 0.0006 | 1298.3 ± 8.7 (1304.4) | -3.01% | 6 | 1.237 |
| 10 / 4:1 / 2 | 0.02 | 1.67 ± 0.19 | 2.25 ± 0.00 | 0.0187 | 0.0218 ± 0.0034 | 1252.9 ± 10.2 (1260.7) | -2.30% | 6 | 1.194 |
| 10 / 4:1 / 2 | 0.005 | 2.88 ± 0.28 | 3.04 ± 0.09 | 0.0048 | 0.0062 ± 0.0006 | 1296.4 ± 7.4 (1302.6) | -3.15% | 6 | 1.235 |


**Reading.**
* **Calibration transfers; λ does not.** In all 18 variants the six-split procedure returns a feasible λ, and held-out risk lands near the target.
  * At 2 %: 0.0184–0.0218. At 0.5 %: 0.0042–0.0062.
  * Exceptions: the two 10-min/4:1 libraries (0.0216/0.0218 at 2 %; 0.0060/0.0062 at 0.5 %, SD 0.0006) and the 10-min/2:1 libraries at 0.5 %
    (0.0053/0.0056). Their held-out risk sits above target by more than one standard error (6-split SD/√6). Calibrating on smooth traces under-protects
    slightly on held-out data.
  * The calibrated λ itself moves with the conversion: λ_VM 1.50–2.08 and λ_UP 1.58–3.21 at 2 %; λ_VM 2.29–3.12 and λ_UP 2.58–3.46 at 0.5 %. So a λ is
    only meaningful together with the library it was calibrated on.
* **Smoothing and compression dominate; the deadband does not matter.** Deadband 0 vs 2 changes λ by ≤ 0.42, cost by ≤ 0.5 %, and rise1/rise10 by
  at most one UE.
  * Removing smoothing (1-min) makes traces far more volatile: rise1 P50 14–23 vs 9; σ̂_win,UP at D=20 rises from 2.6 to 4.0–5.3.
  * That raises the cost relative to the need-floor from 1.29 (standard) to 1.39–1.64 at 2 % (1.45–1.68 at 0.5 %).
  * Heavier smoothing (10-min) lowers volatility and the cost/floor ratio (1.08–1.20).
  * Raw core-min (Δalloc vs e) mixes this with each library's demand level (the need-floor ranges 861–1265), so the ratio column is the comparable one.
* At the standard conversion, the 4:1 rows with 1-min smoothing and 0 deadband stay within +1.7 % of (e). The deadband-0 twin of the standard library
  is within ±0.1 %.

### Per-UE rate model
Simulation only; not validated on hardware.
* **Where UE becomes pps.** v8sim2/v8sim10 never convert to pps explicitly. Demand is `d = S.expand(ue)*cfg.scale` in UE units of 250 kpps, and
  capacities are in the same units: `Cfg.cap_up = 5` UE per slot, `cap_vy = 4.45e6·0.93/250e3` UE per VyOS.
* **The copy.** `eng.sim2(..., load=...)` keeps the controller on the integer UE count n(t). This matches daemon v7.1.3, which plans on the agent's UE
  count; its logged `offered` is exactly n×250 k. The **loss model** instead sees `load(t) = Σ_{i<n(t)} r_i / 250`.
* **Which UEs are active.** UE identity is LIFO by index, as in the harness (`trace_run.py`: departures pop the most recent arrival), so the active set
  is UE 0..n−1.
* **Rate draws.** r_i ∈ {150, 250, 350} kpps uniform, drawn once per UE index per trace: `np.random.default_rng(20261021)`, 40 draws per trace in
  library order.
* **Prior.** The standard one, fitted on UE counts. Command: `run_cal.py --name D_rates --rates`.

## D3 per-UE rate model (rates {150,250,350} kpps, seed 20261021): simulation only; not validated on hardware

| variant | target | λ_VM | λ_UP | cal risk | held-out risk | held-out alloc vmexist (dispatch) | Δalloc vs e | splits |
|---|---|---|---|---|---|---|---|---|
| (e) standard (250 kpps/UE) | 0.02 | 1.83 ± 0.12 | 2.00 ± 0.00 | 0.0190 | 0.0194 ± 0.0017 | 1282.5 ± 5.9 (1290.1) | -0.00% | 6 |
| (e) standard (250 kpps/UE) | 0.005 | 2.67 ± 0.31 | 3.12 ± 0.12 | 0.0047 | 0.0051 ± 0.0007 | 1338.6 ± 5.8 (1344.0) | -0.00% | 6 |
| per-UE random rate | 0.02 | 3.04 ± 0.34 | 3.38 ± 0.24 | 0.0195 | 0.0212 ± 0.0017 | 1351.3 ± 11.8 (1355.9) | +5.36% | 6 |
| per-UE random rate | 0.005 | infeasible in all splits (6) |||||||


* 2 %: the recalibration needs a much larger λ (3.04/3.38 vs 1.83/2.00) and costs **+5.4 %**. Held-out risk is 0.0212 ± 0.0017, slightly above target.
* **0.5 % is infeasible on the grid in all six splits.** Minimum cal risk is 1.56–1.88 %, always at the corner 3.5/4.5. Held-out risk at that corner is
  0.0180 ± 0.0010 at 1382.9 core-min.
* The cause is structural, not λ. With heterogeneous rates the offered load exceeds the **maximum fleet** (8 slots × 5 = 40 UE-eq on UP;
  3 VyOS = 49.6 UE-eq) in **1.63 %** of all library minutes. With the standard 250 kpps per UE it never does. That is an irreducible risk floor above
  0.5 %, so the 0.5 % target cannot be met by any λ under FMAX = 8/3. Lowest reachable risk ≈ 1.6–1.8 %.


## Text of Results §8 before R65 (moved from the Results chapter, 2026-10-21)

<!-- 2026-10-21 R65 (spec §4.110): Results §8 (sensitivity of the calibration) was cut by half for the page budget; the paragraph below is the r64a text of the paper, verbatim with its source comments; the paper keeps one conclusion sentence with its key number. -->

Workload conversion. The library was rebuilt from the raw per-minute Melbourne counts in 18 variants, smoothing window 1, 5 or 10 minutes × compression 1:1, 2:1 or 4:1 × dead band 0 or 2 UE (1166 to 1850 traces); the standard variant (5 minutes, 4:1, 2) reproduces the prior library exactly. <!-- r62de/REPORT.md Task D "Raw source and pipeline", D1 table --> The conversion changes the load sharply: the median rise1 is 14 to 23 UE per minute at 1-minute smoothing, 6 to 9 at 5 minutes and 3 to 5 at 10 minutes. <!-- r62de/REPORT.md D1 table; §4.105 D --> All 18 variants calibrate, with held-out risk 1.84 to 2.18 % at 2 % and 0.42 to 0.62 % at 0.5 %; the 10-minute, 4:1 libraries at both targets and the 10-minute, 2:1 libraries at 0.5 % lie above target by more than one standard error. <!-- r62de/REPORT.md D2 table and reading --> λ moves with the conversion (2 %: $\lambda_{\mathrm{VM}}$ 1.50 to 2.08, $\lambda_{\mathrm{UP}}$ 1.58 to 3.21; 0.5 %: 2.29 to 3.12 and 2.58 to 3.46), so the procedure transfers and the values do not: a λ is meaningful only with the library it was calibrated on. The dead band changes λ by at most 0.42 and cost by at most 0.5 %. <!-- r62de/REPORT.md D2 reading; §4.105 D --> In a per-UE rate model, run only in simulation and not validated on hardware, each UE draws 150, 250 or 350 kpps while the controller still counts UEs; the 2 % target stays feasible at λ 3.04 / 3.38 and +5.4 % cost (held-out 2.12 %), but 0.5 % is infeasible in all six splits, because the offered load then exceeds the largest fleet (8 slots, 3 VyOS) in 1.63 % of library minutes, a floor that no λ removes. <!-- r62de/REPORT.md D3 table and bullets; §4.105 D per-UE -->


## Text of Results §8 "Workload conversion" before the 2026-10-22 cut (verbatim, spec §4.113 equal-trade cut b)

Workload conversion. The library was rebuilt from the raw per-minute Melbourne counts in 18 variants of smoothing, compression and dead band; all 18 calibrate (held-out modeled risk 1.84 to 2.18 % at 2 %), but λ moves with the conversion ($\lambda_{\mathrm{UP}}$ 1.58 to 3.21 at 2 %), so the procedure transfers and the values do not: a λ is meaningful only with the library it was calibrated on. In a per-UE rate model, run only in simulation, 0.5 % is infeasible in all six splits because the offered load exceeds the largest fleet in 1.63 % of library minutes, a floor that no λ removes (variants, load shift and the 2 % result in the artifact repository, conversion-sensitivity.md). <!-- r62de/REPORT.md Task D "Raw source and pipeline", D1 table --> <!-- r62de/REPORT.md D1 table; §4.105 D --> <!-- r62de/REPORT.md D2 table and reading --> <!-- r62de/REPORT.md D2 reading; §4.105 D --> <!-- r62de/REPORT.md D3 table and bullets; §4.105 D per-UE -->
