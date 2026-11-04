<!-- artifact file of the paper "Risk-Calibrated Autoscaling of a Three-Layer 5G User Plane" (docs/paper), written 2026-10-20 when the main paper and the supplementary material were merged into one PDF (spec §4.103). Content moved from S-supplement.md S.3; numbers unchanged. -->

# Per-run results, trace t3


| arm | run | SLO/60 | viol. | alloc_vm | prediction | Δ | note |
|---|---|---|---|---|---|---|---|
| S4a | r360 | 58 | 2 | 1234.0 | 1257 | -1.8 % |  |
| S4a | r372 | 58 | 2 | 1228.0 | 1257 | -2.3 % |  |
| S4a | r377 | 57 | 3 | 1238.0 | 1257 | -1.5 % |  |
| S4b | r363 | 54 | 6 | 1135.0 | 1129 | +0.5 % |  |
| S4b | r369 | 57 | 3 | 1133.0 | 1129 | +0.4 % |  |
| S4b | r374 | 55 | 5 | 1143.0 | 1129 | +1.2 % |  |
| v6 | r361 | 53 | 7 | 1165.0 | 1104 | +5.5 % | emergency rule fired (‡) |
| v6 | r367 | 53 | 7 | 1121.0 | 1104 | +1.5 % | emergency rule fired (‡) |
| v6 | r378 | 57 | 3 | 1123.0 | 1104 | +1.7 % | emergency rule fired (‡) |
| B4c2 | r362 | 57 | 3 | 1231.0 | n/r | -- |  |
| B4c2 | r373 | 55 | 5 | 1236.0 | n/r | -- |  |
| B4c2 | r379 | 56 | 4 | 1057.0 | n/r | -- | voided: network outage; rerun r382 |
| B4c2 | r382 | 57 | 3 | 1232.0 | n/r | -- | replacement-for-r379 (rerun after PCF restart) |
| B5c1 | r364 | 57 | 3 | 1154.0 | n/r | -- |  |
| B5c1 | r370 | 30 | 30 | 1173.0 | n/r | -- | voided: harness gNB-8 NG; replaced by r380 |
| B5c1 | r375 | 55 | 5 | 1151.0 | n/r | -- |  |
| B5c1 | r380 | 56 | 4 | 1154.0 | n/r | -- | replacement-for-r370 |
| B6 | r365 | 58 | 2 | 1216.0 | 1230 | -1.1 % |  |
| B6 | r371 | 57 | 3 | 1238.0 | 1230 | +0.7 % |  |
| B6 | r376 | 53 | 7 | 1218.0 | 1230 | -1.0 % | voided: formal NG events; replaced by r383 |
| B6 | r383 | 55 | 5 | 1229.0 | 1230 | -0.1 % | replacement-for-r376 |
| B1 | r366 | 60 | 0 | 1464.0 | – | -- |  |

Table. Per-run results on t3 (all runs, including voided, replaced and confirmation runs; alloc_vm in core-min; Δ against the registered or supplementary prediction).
