<!-- artifact file of the paper "Predictable-Cost Autoscaling of a Three-Layer 5G User Plane with Library-Calibrated Risk" (docs/paper), written 2026-10-21 (R64, spec §4.109, fallback cut) when the cost-versus-violation figure of the Results chapter was reduced from four panels (t3, t4, t6, t7) to two (t3, t6); data unchanged. -->

# Cost versus SLO violation on t4 and t7 (panels removed from the paper)

Figure file: `docs/paper/figs/fig_cost_viol_2x2.pdf` (all four panels t3, t4, t6, t7; script `fig_cost_viol_2x2.py`, not included: not a paper figure, data `experiment/paper_out_new/rq/rq_metrics.csv`, column `alloc_vm` and 60 − `slo`). The paper keeps the t3 and t6 panels (`figs/fig_cost_viol_t3t6.pdf`).

Caption of the four-panel figure (r63): Cost versus SLO violation on t3 (surge), t4 (burst), t6 and t7. Per arm, the marker is the three-run mean of the violating minutes (x; loss above 0.1 % or p99 above 1 ms) and of the allocated cost in core-minutes (y), with min-to-max bars and the label mean cost / mean violating minutes; B1 has one run. Hollow black circles are voided or replaced runs (r370 and r304 clamped to the right edge); the hollow diamond on t4 is the v6 confirmation run r381, not in the v6 mean. The y-axis is shared.

What the t4 and t7 panels show (three-run means, alloc_vm core-min / violating minutes per run; the same values as the main table, where violation minutes are summed over runs):

| arm | t4 (burst) | t7 |
|---|---|---|
| S4a | 1450 / 1.0 | 1427 / 0.3 |
| S4b | 1420 / 3.3 | 1387 / 0.0 |
| v6 | 1378 / 1.7 | 1353 / 0.0 |
| B4c2 | 1447 / 0.7 | 1441 / 0.0 |
| B5c1 | 1410 / 2.3 | 1413 / 0.0 |
| B6 | 1452 / 0.3 | 1451 / 0.0 |
| B1 (one run) | 1464 / 0 | 1464 / 1 |

Also on the t4 panel: the voided runs (r304 at 39 violating minutes, clamped to the right edge, and the other t4 voids of voided-runs.md) as hollow circles, and the v6 confirmation run r381 (56/60, alloc_vm 1377) as a hollow diamond. On t4 the S arms and B5c1 pay the minute-20/21 burst (Results, stress traces); on t7 every arm except S4a (one minute in r442) and B1 (one minute) is at 60/60 in every run.
