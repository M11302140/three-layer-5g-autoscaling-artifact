<!-- artifact file of the paper "Predictable-Cost Autoscaling of a Three-Layer 5G User Plane with Library-Calibrated Risk" (docs/paper), written 2026-10-21 for the round-62 analyses (spec §4.104 H item 4, results §4.105). Content copied verbatim from qsim/r62cf/REPORT.md, section F1; simulation only, no hardware run. -->

# Operations price J

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
