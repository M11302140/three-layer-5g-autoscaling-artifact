<!-- artifact file of the paper "Risk-Calibrated Autoscaling of a Three-Layer 5G User Plane" (docs/paper), written 2026-10-20 when the main paper and the supplementary material were merged into one PDF (spec §4.103). Content moved from S-supplement.md S.5; numbers unchanged. -->

# Per-run results, trace t5


| arm | run | SLO/60 | viol. | alloc_vm | prediction | Δ | note |
|---|---|---|---|---|---|---|---|
| S4a | r330 | 60 | 0 | 1462.0 | 1464 | −0.1 % | |
| S4b | r333 | 60 | 0 | 1453.0 | 1454 | −0.1 % | |
| v6 | r331 | 60 | 0 | 1453.0 | 1451 | +0.1 % | |
| B4c2 | r332 | 60 | 0 | 1464.0 | n/r | -- |  |
| B5c1 | r334 | 60 | 0 | 1464.0 | n/r | -- |  |
| B6 | r335 | 60 | 0 | 1464.0 | 1464 | +0.0 % | |
| B1 | r336 | 60 | 0 | 1464.0 | n/r | -- |  |

Table. Per-run results on t5 (all runs, including voided, replaced and confirmation runs; alloc_vm in core-min; Δ against the registered or supplementary prediction).
