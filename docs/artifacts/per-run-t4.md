<!-- artifact file of the paper "Risk-Calibrated Autoscaling of a Three-Layer 5G User Plane" (docs/paper), written 2026-10-20 when the main paper and the supplementary material were merged into one PDF (spec §4.103). Content moved from S-supplement.md S.4; numbers unchanged. -->

# Per-run results, trace t4


| arm | run | SLO/60 | viol. | alloc_vm | prediction | Δ | note |
|---|---|---|---|---|---|---|---|
| S4a | r300 | 60 | 0 | 1450.0 | 1454 | -0.3 % | start transient (†); emergency rule fired (‡) |
| S4a | r312 | 59 | 1 | 1450.0 | 1454 | -0.3 % | start transient (†); emergency rule fired (‡) |
| S4a | r317 | 58 | 2 | 1450.0 | 1454 | -0.3 % | start transient (†); emergency rule fired (‡) |
| S4b | r303 | 56 | 4 | 1420.0 | 1427 | -0.5 % |  |
| S4b | r309 | 55 | 5 | 1418.0 | 1427 | -0.6 % | voided: harness gNB-8; rerun r322 |
| S4b | r314 | 58 | 2 | 1420.0 | 1427 | -0.5 % |  |
| S4b | r322 | 56 | 4 | 1420.0 | 1427 | -0.5 % |  |
| v6 | r301 | 58 | 2 | 1378.0 | 1387 | -0.6 % |  |
| v6 | r307 | 59 | 1 | 1377.0 | 1387 | -0.7 % | voided: compute overlap |
| v6 | r318 | 59 | 1 | 1378.0 | 1387 | -0.6 % |  |
| v6 | r321 | 58 | 2 | 1378.0 | 1387 | -0.6 % |  |
| v6 | r381 | 56 | 4 | 1377.0 | 1387 | -0.7 % | confirmation run (not in means) |
| B4c2 | r302 | 57 | 3 | 1431.0 | n/r | -- | replaced: start transient; replaced by r320 |
| B4c2 | r308 | 60 | 0 | 1447.0 | n/r | -- |  |
| B4c2 | r313 | 60 | 0 | 1447.0 | n/r | -- |  |
| B4c2 | r320 | 58 | 2 | 1446.0 | n/r | -- |  |
| B5c1 | r304 | 21 | 39 | 1241.0 | n/r | -- | voided: q6 crash |
| B5c1 | r310 | 58 | 2 | 1409.0 | n/r | -- |  |
| B5c1 | r315 | 57 | 3 | 1410.0 | n/r | -- |  |
| B5c1 | r319 | 58 | 2 | 1410.0 | n/r | -- |  |
| B6 | r305 | 59 | 1 | 1447.0 | 1452 | -0.3 % |  |
| B6 | r311 | 60 | 0 | 1446.0 | 1452 | -0.4 % |  |
| B6 | r316 | 60 | 0 | 1464.0 | 1452 | +0.8 % |  |
| B1 | r306 | 60 | 0 | 1464.0 | – | -- |  |

Table. Per-run results on t4 (all runs, including voided, replaced and confirmation runs; alloc_vm in core-min; Δ against the registered or supplementary prediction).
