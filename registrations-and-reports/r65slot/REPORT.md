# r65slot (spec §4.112 A): per-slot (v8sim11, R38 on) calibration of S — 2026-10-21/22

Simulation only (nice 19, taskset 13,14, 2 workers; 22:58–23:59 + analysis). Frozen files md5 before/after: 7/7 OK. Runner verified equal to v8sim11.run S4b on 17 library traces (0 mismatches). Grid VM 1.0–5.0 × UP 1.5–7.0 step 0.5 (108), ±0.25 refinement, selection on cal alloc_vm, Prior from calibration groups (as r63a). No split infeasible; 3/6 splits at 0.5 % at the UP edge (7.0 / 7.25).

| target | split | λ_slot VM/UP | flags | cal risk | ho risk (v8sim11) | ho alloc_vm | v8sim11 @ nest2 λ: ho risk / alloc_vm |
|---|---|---|---|---|---|---|---|
| 0.02 | 0 | 0.75/5.5 | - | 0.0184 | 0.0173 | 1354.6 | 0.0773 / 1288.2 |
| 0.02 | 1 | 0.75/5.75 | - | 0.0176 | 0.0143 | 1352.0 | 0.0761 / 1285.4 |
| 0.02 | 2 | 0.75/5.25 | - | 0.0196 | 0.0199 | 1344.0 | 0.0744 / 1275.8 |
| 0.02 | 3 | 0.75/5.0 | - | 0.0199 | 0.0206 | 1341.4 | 0.0757 / 1285.9 |
| 0.02 | 4 | 1.0/5.0 | - | 0.0192 | 0.0220 | 1340.7 | 0.0805 / 1273.9 |
| 0.02 | 5 | 0.75/5.25 | - | 0.0199 | 0.0170 | 1349.8 | 0.0705 / 1288.5 |
| 0.005 | 0 | 2.25/6.75 | - | 0.0048 | 0.0030 | 1398.1 | 0.0524 / 1346.0 |
| 0.005 | 1 | 2.25/7.25 | EDGE | 0.0040 | 0.0016 | 1398.2 | 0.0442 / 1343.6 |
| 0.005 | 2 | 1.5/7.0 | EDGE | 0.0044 | 0.0052 | 1378.8 | 0.0534 / 1327.9 |
| 0.005 | 3 | 2.0/6.5 | - | 0.0047 | 0.0054 | 1384.7 | 0.0432 / 1337.5 |
| 0.005 | 4 | 1.75/7.0 | EDGE | 0.0049 | 0.0057 | 1381.7 | 0.0464 / 1333.8 |
| 0.005 | 5 | 2.0/6.5 | - | 0.0034 | 0.0041 | 1391.0 | 0.0470 / 1341.1 |

| target | calibration | λ_VM | λ_UP | held-out risk (SE) | held-out alloc_vm | infeasible / edge splits |
|---|---|---|---|---|---|---|
| 0.02 | nest2, leakage-free (r63a; nest2 risk) | 1.88 | 2.00 | 0.0196 (0.0007) | 1282.1 | - |
| 0.02 | per-slot v8sim11 (this run; per-slot risk) | 0.79 ± 0.09 | 5.29 ± 0.27 | 0.0185 (0.0011) | 1347.1 ± 5.3 | 0 / 0 |
| 0.02 | nest2 λ evaluated in v8sim11 (per-slot risk) | per split | per split | 0.0757 | 1282.9 | - |
| 0.005 | nest2, leakage-free (r63a; nest2 risk) | 2.75 | 3.12 | 0.0045 (0.0003) | 1339.2 | - |
| 0.005 | per-slot v8sim11 (this run; per-slot risk) | 1.96 ± 0.27 | 6.83 ± 0.28 | 0.0042 (0.0006) | 1388.8 ± 7.6 | 0 / 3 |
| 0.005 | nest2 λ evaluated in v8sim11 (per-slot risk) | per split | per split | 0.0478 | 1338.3 | - |

R3 cost increase:
* 0.02: λ_slot vs nest2 λ: VM 0.79 vs 1.88, UP 5.29 vs 2.00. Cross-physics (each calibrated in its own simulator): 1347.1 / 1282.1 − 1 = +5.07 %. Same physics (v8sim11): 1347.1 / 1282.9 − 1 = +5.00 % (nest2 λ in v8sim11 has per-slot risk 0.0757).
* 0.005: λ_slot vs nest2 λ: VM 1.96 vs 2.75, UP 6.83 vs 3.12. Cross-physics (each calibrated in its own simulator): 1388.8 / 1339.2 − 1 = +3.70 %. Same physics (v8sim11): 1388.8 / 1338.3 − 1 = +3.77 % (nest2 λ in v8sim11 has per-slot risk 0.0478).

Whole library (full-library Prior, λ = split mean rounded to 0.25):
* 0.02: λ 0.75/5.25: per-slot risk 0.0207, alloc_vm 1345.9
* 0.005: λ 2.0/6.75: per-slot risk 0.0040, alloc_vm 1389.8

Per trace (violating minutes per run / alloc_vm). Ratios pred/measured only at deployed λ (hardware never ran λ_slot).
| trace | arm | nest2 registered | v8sim11 @ deployed λ | measured | reg / meas | v8sim11 / meas | v8sim11 @ λ_slot (min / alloc_vm) |
|---|---|---|---|---|---|---|---|
| t3 | S4a | 3 | 3 (1254) | 2.33 | 1.29 | 1.29 | 1 / 1350 |
| t3 | S4b | 3 | 5 (1138) | 4.67 | 0.64 | 1.07 | 2 / 1316 |
| t4 | S4a | 0 | 2 (1452) | 1.00 | 0.00 | 2.00 | 0 / 1452 |
| t4 | S4b | 1 | 4 (1425) | 3.33 | 0.30 | 1.20 | 1 / 1421 |
| t6 | S4a | 0 | 3 (1448) | 0.00 | n/a | ∞ | 0 / 1438 |
| t6 | S4b | 0 | 5 (1397) | 0.00 | n/a | ∞ | 0 / 1412 |
| t7 | S4a | 0 | 0 (1432) | 0.33 | 0.00 | 0.00 | 0 / 1447 |
| t7 | S4b | 0 | 0 (1396) | 0.00 | n/a | n/a | 0 / 1402 |

R1 (t3/t4 S4a,S4b v8sim11/measured in [0.5,2]): ['1.29', '1.07', '2.00', '1.20'] -> PASS
R2 (t6/t7 sum |pred-meas|, v8sim11 <= nest2): 8.33 vs 0.33 -> FAIL
Verdict sentence 'placement-aware calibration brings the mismatch within a factor of two': NOT WRITTEN
