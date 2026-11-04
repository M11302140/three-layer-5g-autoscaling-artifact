<!-- artifact file of the paper (docs/paper), written 2026-10-21 (R4rev, spec §4.112 D7) when the main table of the results chapter was split: Table 1a (SLO, violation minutes, alloc_vm, paired differences) stays in the paper, Table 1b (prediction deviation Δ and risk-fidelity ratios ρ) moved here for the page limit. Every value is copied verbatim from the r66 / rev. 0 main table (snapshots/rev. 0/04-results.md, Table 1); sources: rq_metrics.csv (alloc_vm), registered predictions §4.37 / §4.77 B, ρ from qsim/r63bf/REPORT.md B1 (artifacts/risk-fidelity-and-violation-classes.md). -->

# Main table, part b: prediction deviation and risk-fidelity ratios (Table 1b)

| arm | quantity | t3 (surge) | t4 (burst) | t5 (1 run) | t6 | t7 |
|---|---|---|---|---|---|---|
| S4a | Δ | −1.9 % | −0.3 % | −0.1 % | −1.0 % | −0.2 % |
| S4a | $\rho$ registered / per-slot | 1.29 / 1.29 | 0.00 / 2.00 | – | – / ∞ | 0.00 / 0.00 |
| S4b | Δ | +0.7 % | −0.5 % | −0.1 % | −0.2 % | −0.5 % |
| S4b | $\rho$ registered / per-slot | 0.64 / 1.07 | 0.30 / 1.20 | – | – / ∞ | – / – |
| v6 | Δ | +2.9 % | −0.6 % | +0.1 % | −1.0 % | −2.0 % |
| v6 | $\rho$ registered / per-slot | 0.53 / 0.88 | 1.80 / 1.20 | – | 1.20 / 1.20 | – / ∞ |
| B4c2 | Δ | – | – | – | +0.5 % | −0.1 % |
| B5c1 | Δ | – | – | – | +4.2 % | +0.2 % |
| B6 | Δ | −0.2 % | +0.0 % | +0.0 % | −0.1 % | +0.4 % |
| B1 | Δ | – | – | – | – | – |

Table 1b. Per arm and trace: Δ = (measured − prediction) / prediction of the three-run mean `alloc_vm` (one run for B1 and t5) against the prediction registered before the block; –: no registered prediction (B1 everywhere, B4c2 and B5c1 on t3 to t5); B4c2 and B5c1 on t6 and t7 are compared with additional, non-registered per-slot predictions. Risk-fidelity ratio $\rho$ = predicted / measured violating minutes per run, for the fleet-level prediction registered before the runs / the per-slot simulator computed after the campaign (not registered); ∞: positive prediction, none measured; –: no value (0 / 0, or t5). Baseline rows: no registered risk prediction. The SLO / violation-minute / alloc_vm values of every cell are in Table 1a of the paper.

## Table 1 of the paper before the split (rev. 0), verbatim

| arm | t3 (surge) | t4 (burst) | t5 (1 run) | t6 | t7 |
|---|---|---|---|---|---|
| S4a | 57.7 / 7 / 1233 (−1.9 %) \newline $\rho$ 1.29 / 1.29 | 59.0 / 3 / 1450 (−0.3 %) † ‡ \newline $\rho$ 0.00 / 2.00 | 60.0 / 0 / 1462 (−0.1 %) \newline $\rho$ – | 60.0 / 0 / 1435 (−1.0 %) † \newline $\rho$ – / ∞ | 59.7 / 1 / 1427 (−0.2 %) \newline $\rho$ 0.00 / 0.00 |
| S4b | 55.3 / 14 / 1137 (+0.7 %) \newline $\rho$ 0.64 / 1.07 | 56.7 / 10 / 1420 (−0.5 %) \newline $\rho$ 0.30 / 1.20 | 60.0 / 0 / 1453 (−0.1 %) \newline $\rho$ – | 60.0 / 0 / 1390 (−0.2 %) † ‡ \newline $\rho$ – / ∞ | 60.0 / 0 / 1387 (−0.5 %) \newline $\rho$ – / – |
| v6 | 54.3 / 17 / 1136 (+2.9 %) \newline $\rho$ 0.53 / 0.88 | 58.3 / 5 / 1378 (−0.6 %) \newline $\rho$ 1.80 / 1.20 | 60.0 / 0 / 1453 (+0.1 %) \newline $\rho$ – | 58.3 / 5 / 1349 (−1.0 %) \newline $\rho$ 1.20 / 1.20 | 60.0 / 0 / 1353 (−2.0 %) \newline $\rho$ – / ∞ |
| B4c2 | 56.3 / 11 / 1233 | 59.3 / 2 / 1447 | 60.0 / 0 / 1464 | 58.3 / 5 / 1456 (+0.5 %) | 60.0 / 0 / 1441 (−0.1 %) |
| B5c1 | 56.0 / 12 / 1153 | 57.7 / 7 / 1410 | 60.0 / 0 / 1464 | 59.3 / 2 / 1433 (+4.2 %) | 60.0 / 0 / 1413 (+0.2 %) |
| B6 | 56.7 / 10 / 1228 (−0.2 %) | 59.7 / 1 / 1452 (+0.0 %) | 60.0 / 0 / 1464 (+0.0 %) | 60.0 / 0 / 1447 (−0.1 %) | 60.0 / 0 / 1451 (+0.4 %) |
| B1 | 60.0 / 0 / 1464 | 60.0 / 0 / 1464 | 60.0 / 0 / 1464 | 60.0 / 0 / 1464 | 59.0 / 1 / 1464 |
| S4b − B4c2 | −96.0 (−7.8 %) [−103, −88] | −26.7 (−1.8 %) [−27, −26] | −11 (−0.8 %) | −65.3 (−4.5 %) [−72, −54] | −53.3 (−3.7 %) [−55, −50] |
| S4b − B5c1 | −16.0 (−1.4 %) [−21, −8] | +10.3 (+0.7 %) [+10, +11] | −11 (−0.8 %) | −42.7 (−3.0 %) [−45, −39] | −25.7 (−1.8 %) [−28, −22] |
| S4b − B6 | −90.7 (−7.4 %) [−105, −73] | −32.3 (−2.2 %) [−44, −26] | −11 (−0.8 %) | −57.0 (−3.9 %) [−76, −45] | −63.7 (−4.4 %) [−68, −58] |

Table 1. Main results: per arm and trace, "SLO/60 / violation minutes / alloc_vm (Δ against the registered prediction)", three-run means except B1 and t5 (one run). Second line of the S4a, S4b and v6 cells: risk-fidelity ratio $\rho$ = predicted / measured violating minutes per run, for the fleet-level prediction registered before the runs / the per-slot simulator computed after the campaign (not registered); ∞: positive prediction, none measured; –: no value (0 / 0, or t5). Baseline rows: no registered risk prediction. Lower block: paired cost differences, S4b minus each tuned baseline, mean over runs in core-min (relative), and in brackets the range over all run pairs. <!-- paired block: §4.102 (6), old Table 5; per-run values in artifacts/per-run-t3.md to per-run-t7.md -->
