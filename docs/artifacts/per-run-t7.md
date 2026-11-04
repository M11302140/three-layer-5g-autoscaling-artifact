<!-- artifact file of the paper "Risk-Calibrated Autoscaling of a Three-Layer 5G User Plane" (docs/paper), written 2026-10-20 when the main paper and the supplementary material were merged into one PDF (spec §4.103). Content moved from S-supplement.md S.7; numbers unchanged. -->

# Per-run results, trace t7


| arm | run | SLO/60 | viol. | alloc_vm | prediction | Δ | note |
|---|---|---|---|---|---|---|---|
| S4a | r430 | 60 | 0 | 1426.0 | 1430 | -0.3 % |  |
| S4a | r442 | 59 | 1 | 1426.0 | 1430 | -0.3 % |  |
| S4a | r447 | 60 | 0 | 1429.0 | 1430 | -0.1 % |  |
| S4b | r433 | 60 | 0 | 1390.0 | 1395 | -0.4 % |  |
| S4b | r439 | 60 | 0 | 1386.0 | 1395 | -0.6 % |  |
| S4b | r444 | 60 | 0 | 1386.0 | 1395 | -0.6 % |  |
| v6 | r431 | 60 | 0 | 1352.0 | 1380 | -2.0 % |  |
| v6 | r437 | 60 | 0 | 1353.0 | 1380 | -2.0 % |  |
| v6 | r448 | 60 | 0 | 1354.0 | 1380 | -1.9 % |  |
| B4c2 | r432 | 60 | 0 | 1441.0 | (1442, suppl.) | -0.1 % |  |
| B4c2 | r438 | 60 | 0 | 1440.0 | (1442, suppl.) | -0.1 % |  |
| B4c2 | r443 | 60 | 0 | 1441.0 | (1442, suppl.) | -0.1 % |  |
| B5c1 | r434 | 60 | 0 | 1412.0 | (1410, suppl.) | +0.1 % |  |
| B5c1 | r440 | 60 | 0 | 1413.0 | (1410, suppl.) | +0.2 % |  |
| B5c1 | r445 | 60 | 0 | 1414.0 | (1410, suppl.) | +0.3 % |  |
| B6 | r435 | 60 | 0 | 1448.0 | 1445 | +0.2 % |  |
| B6 | r441 | 60 | 0 | 1451.0 | 1445 | +0.4 % |  |
| B6 | r446 | 60 | 0 | 1454.0 | 1445 | +0.6 % |  |
| B1 | r436 | 59 | 1 | 1464.0 | – | -- |  |

Table. Per-run results on t7 (all runs, including voided, replaced and confirmation runs; alloc_vm in core-min; Δ against the registered or supplementary prediction).
