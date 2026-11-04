<!-- artifact file of the paper "Risk-Calibrated Autoscaling of a Three-Layer 5G User Plane" (docs/paper), written 2026-10-20 when the main paper and the supplementary material were merged into one PDF (spec §4.103). Content moved from S-supplement.md S.8 (the S4a measured-risk paragraph came from the experimental-setup chapter); numbers unchanged. -->

# Secondary statistics per arm and trace


| trace | arm | worst min. loss % | p99 max µs | flaps | under vy/up | over vy/up |
|---|---|---|---|---|---|---|
| t3 | S4a / S4b / v6 | 4.43 / 6.60 / 6.14 | 2945 / 3985 / 3988 | 5.7 / 7.0 / 7.3 | 0.0/2.0 / 1.0/3.0 / 1.0/3.0 | 16.0/41.3 / 8.0/26.3 / 9.0/29.3 |
| t3 | B4c2 / B5c1 / B6 / B1 | 5.51 / 5.11 / 8.51 / 0.00 | 3820 / 3984 / 2973 / 394 | 0.7 / 3.0 / 2.3 / 0 | 0.3/3.0 / 1.0/2.7 / 0.3/2.3 / 0 | 15.7/39.7 / 4.0/35.0 / 13.7/43.3 / 57/57 |
| t4 | S4a / S4b / v6 | 0.47 / 0.80 / 0.56 | 2096 / 2952 / 3395 | 2.0 / 0.0 / 0.0 | 0/0 / 0.0/1.0 / 2.0/1.0 | 20.0/22.0 / 14.0/11.0 / 2.0/10.0 |
| t4 | B4c2 / B5c1 / B6 / B1 | 0.12 / 0.82 / 0.14 / 0.00 | 1623 / 2964 / 396 / 398 | 0 / 0 / 0 / 0 | 0/0 / 0.0/1.0 / 0/0 / 0 | 19.0/23.7 / 9.0/11.0 / 20.7/24.3 / 22/26 |
| t5 | S4a / S4b / v6 | 0.00 / 0.00 / 0.00 | 395 / 392 / 449 | 3 / 3 / 3 | 0/0 ×3 | 20/25 / 20/19 / 18/21 |
| t5 | B4c2 / B5c1 / B6 / B1 | 0.01 / 0.05 / 0.00 / 0.00 | 397 / 395 / 398 / 393 | 0 ×4 | 0/0 ×4 | 20/26 ×4 |
| t6 | S4a / S4b / v6 | 0.01 / 0.00 / 0.19 | 397 / 398 / 1317 | 5.7 / 6.0 / 1.3 | 0/0 / 0/0 / 1.0/0.0 | 29.7/34.3 / 22.3/21.0 / 10.0/25.0 |
| t6 | B4c2 / B5c1 / B6 / B1 | 0.29 / 0.13 / 0.01 / 0.03 | 396 / 396 / 397 / 395 | 0 ×4 | 0/0 ×4 | 34.0/38.7 / 27.0/31.0 / 28.7/39.0 / 36/39 |
| t7 | S4a / S4b / v6 | 0.15 / 0.01 / 0.00 | 396 / 399 / 415 | 3.0 / 4.3 / 2.7 | 0/0 ×3 | 19.0/32.3 / 16.7/25.0 / 3.0/28.3 |
| t7 | B4c2 / B5c1 / B6 / B1 | 0.01 / 0.00 / 0.00 / 0.39 | 398 / 396 / 396 / 395 | 2.0 / 0 / 0.7 / 0 | 0/0 ×4 | 14.0/35.0 / 6.3/33.7 / 20.3/35.0 / 27/35 |

Table. Secondary statistics, means over valid runs: worst-minute loss (rq_metrics.md "worst%"), maximum p99, flaps under the corrected actuation definition, and under- and over-provisioned minutes per layer (VyOS/slot). <!-- rq_metrics.md MAIN t3 to t7 rows for loss, p99, under, over; flaps column replaced 2026-10-20 by the corrected values of the flap-definition table (old Table A.13, now in flap-decomposition.md) (ops/ops_table.md), which differ from rq_metrics.csv only for the S arms --> The flaps column was corrected on 2026-10-20: the earlier rq_metrics count treated a retracted reversible scale-in and its retraction as two actuations; the corrected count holds actual actuations only, and flap-decomposition.md lists both definitions side by side with the reason. <!-- ops/REPORT.md §5; §4.100 D --> Under the corrected definition the S arms still flap more than every tuned baseline on t3, t6 and t7 (3.0 to 7.0 per run against 0 to 3), have no under-provisioned minutes on t5 to t7, and S4b over-provisions the slot layer less than every tuned baseline on t6 and t7 (21.0 and 25.0 minutes against 31.0 to 39.0 and 33.7 to 35.0). <!-- flap-definition table (old A.13) corrected column (S4a 5.7/5.7/3.0, S4b 7.0/6.0/4.3 on t3/t6/t7 against B arms 0 to 3.0); rq_metrics.md MAIN rows: under vy/up, over vy/up -->

S4a measured risk. S4a violation minutes per trace, valid runs only: t3 7 (runs 2/2/3), t4 3 (0/1/2), t5 0, t6 0 (worst minute loss 0.01%), t7 1 (r442 minute 44, loss 0.15%, a 7-second black UE with a stale NAS session, noted outside the classification rules). <!-- §4.93 item 3, rq_metrics.md MAIN rows -->

## H1 on t6 and t7: crediting S4b (moved from the results chapter, Section 3, on 2026-10-21 for the page budget)

Crediting S4b with the VyOS it started one unit short of on t7 (+2.8 core-min per run) or with the upper bound of the pre-formal trim of one idle worker on t6 (+30 core-min per run) leaves it below the tightest bound (1390.1 against 1441.3, 1420.3 against 1461.7). <!-- §4.89 D items 1 and 2 -->
