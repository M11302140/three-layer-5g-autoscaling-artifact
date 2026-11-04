<!-- artifact file of the paper "Risk-Calibrated Autoscaling of a Three-Layer 5G User Plane" (docs/paper), written 2026-10-20 when the main paper and the supplementary material were merged into one PDF (spec §4.103). Content moved from S-supplement.md S.6; numbers unchanged. -->

# Per-run results, trace t6


| arm | run | SLO/60 | viol. | alloc_vm | prediction | Δ | note |
|---|---|---|---|---|---|---|---|
| S4a | r402 | 60 | 0 | 1433.0 | 1449 | -1.1 % | start transient (†) |
| S4a | r414 | 60 | 0 | 1435.0 | 1449 | -1.0 % | start transient (†) |
| S4a | r419 | 60 | 0 | 1437.0 | 1449 | -0.8 % | start transient (†); emergency rule fired (‡) |
| S4b | r405 | 60 | 0 | 1388.0 | 1393 | -0.4 % | start transient (†); emergency rule fired (‡) |
| S4b | r411 | 60 | 0 | 1394.0 | 1393 | +0.1 % | start transient (†); emergency rule fired (‡) |
| S4b | r416 | 60 | 0 | 1389.0 | 1393 | -0.3 % | start transient (†); emergency rule fired (‡) |
| v6 | r403 | 60 | 0 | 1350.0 | 1363 | -1.0 % |  |
| v6 | r409 | 60 | 0 | 1339.0 | 1363 | -1.8 % |  |
| v6 | r420 | 55 | 5 | 1359.0 | 1363 | -0.3 % | emergency rule fired (‡) |
| B4c2 | r404 | 60 | 0 | 1448.0 | (1448, suppl.) | +0.0 % |  |
| B4c2 | r410 | 55 | 5 | 1459.0 | (1448, suppl.) | +0.8 % |  |
| B4c2 | r415 | 60 | 0 | 1460.0 | (1448, suppl.) | +0.8 % |  |
| B5c1 | r406 | 60 | 0 | 1433.0 | (1375, suppl.) | +4.2 % |  |
| B5c1 | r412 | 58 | 2 | 1433.0 | (1375, suppl.) | +4.2 % |  |
| B5c1 | r417 | 60 | 0 | 1433.0 | (1375, suppl.) | +4.2 % |  |
| B6 | r407 | 60 | 0 | 1464.0 | 1449 | +1.0 % |  |
| B6 | r413 | 60 | 0 | 1439.0 | 1449 | -0.7 % |  |
| B6 | r418 | 60 | 0 | 1439.0 | 1449 | -0.7 % |  |
| B1 | r408 | 60 | 0 | 1464.0 | – | -- |  |

Table. Per-run results on t6 (all runs, including voided, replaced and confirmation runs; alloc_vm in core-min; Δ against the registered or supplementary prediction).
