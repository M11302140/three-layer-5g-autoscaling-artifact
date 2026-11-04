<!-- artifact file of the paper "Risk-Calibrated Autoscaling of a Three-Layer 5G User Plane" (docs/paper), written 2026-10-20 when the main paper and the supplementary material were merged into one PDF (spec §4.103). Content moved from S-supplement.md S.10; numbers unchanged. -->
<!-- 2026-10-21 (spec §4.107 B): the paper now carries a condensed three-level table in the results section "H2b: risk fidelity", with ratios in the direction prediction / measured (qsim/r63bf/REPORT.md B1); the table below keeps the direction measured / prediction and agrees with it cell by cell. The 117-minute classification is in risk-fidelity-and-violation-classes.md. -->

# Conditional risk: load features, rise1 bucketing and three levels of prediction


This file holds the material behind the conditional-risk analysis in the results chapter of the paper (its risk-versus-burstiness figure, rise10 deciles): the load features of the prior library with the evaluation traces marked (`../figs/fig_m1_features.pdf`), the decile curves bucketed by rise1 instead of rise10 (`../figs/fig_m1_risk_vs_burst_rise1.pdf`), and the violating minutes per run at three levels of prediction against the measurement (table below).

Figure `../figs/fig_m1_features.pdf`: Load features of the 1615-window prior library (histograms) with the seven evaluation traces marked: mean-to-peak ratio, fraction of minutes at or above 36 UE, largest rise over any 10-minute span (rise10), largest one-minute rise (rise1), lag-1 autocorrelation and stationarity (mean of minutes 30 to 59 minus mean of minutes 0 to 29). Dashed grey marks are the development traces t1 and t2; solid black marks are the test traces t3 to t7.

Figure `../figs/fig_m1_risk_vs_burst_rise1.pdf`: The same curves and hardware points as the rise10 risk-versus-burstiness figure of the paper, bucketed by rise1 (largest one-minute rise) instead of rise10. rise1 is integer-valued with heavy ties, so decile D4 is empty and is omitted; t4 (rise1 = 9, library percentile 45) moves from D2 to D5, t3 to D8, t6 and t7 to D2.

| trace | arm | rise10 decile | decile mean (min/run) | registered (min/run) | v8sim11 (min/run) | measured (min/run) | measured / registered | measured / v8sim11 | measured / decile mean |
|---|---|---|---|---|---|---|---|---|---|
| t3 | S4a | D9 | 0.48 | 3 | 3 | 2.33 | 0.78 | 0.78 | 4.89 |
| t3 | S4b | D9 | 1.76 | 3 | 5 | 4.67 | 1.56 | 0.93 | 2.64 |
| t3 | v6 | D9 | 2.35 | 3 | 5 | 5.67 | 1.89 | 1.13 | 2.41 |
| t4 | S4a | D2 | 0.03 | 0 | 2 | 1.00 | n/a (0 predicted) | 0.50 | 37.0 |
| t4 | S4b | D2 | 0.41 | 1 | 4 | 3.33 | 3.33 | 0.83 | 8.22 |
| t4 | v6 | D2 | 0.43 | 3 | 2 | 1.67 | 0.56 | 0.83 | 3.90 |
| t6 | S4a | D4 | 0.13 | 0 | 3 | 0.00 | n/a (0 predicted) | 0.00 | 0.00 |
| t6 | S4b | D4 | 0.92 | 0 | 5 | 0.00 | n/a (0 predicted) | 0.00 | 0.00 |
| t6 | v6 | D4 | 1.07 | 2 | 2 | 1.67 | 0.83 | 0.83 | 1.55 |
| t7 | S4a | D4 | 0.13 | 0 | 0 | 0.33 | n/a (0 predicted) | n/a (0 predicted) | 2.49 |
| t7 | S4b | D4 | 0.92 | 0 | 0 | 0.00 | n/a (0 predicted) | n/a (0 predicted) | 0.00 |
| t7 | v6 | D4 | 1.07 | 0 | 1 | 0.00 | n/a (0 predicted) | 0.00 | 0.00 |

Table. Violating minutes per 60-minute run at three levels of prediction against the measurement: the rise10-decile mean of the library (decile mean risk × 60), the per-trace prediction registered before the run (fleet-level simulator on the exact trace; v6 by its own simulator), and the per-slot simulator v8sim11 on the exact trace; measured = sum over the three valid runs / 3. The v8sim11 values for S4a, S4b and v6 were computed after the campaign and are not registered values; at registration time v8sim11 had been run only for B4c2, B5c1 and B1. <!-- m1/REPORT.md Supplement (5), all columns verbatim; "S4a/S4b/v6 的 v8sim11 值為本次新算、非登記值" §4.100 A -->
