<!-- artifact file of the paper "Risk-Calibrated Autoscaling of a Three-Layer 5G User Plane" (docs/paper), written 2026-10-20 when the main paper and the supplementary material were merged into one PDF (spec §4.103). Content moved from 03-experimental-setup.md (old Table 5); numbers unchanged. -->

# Sensitivity of the arm means to the voiding rule

Including the voided runs changes the S-arm and v6 means by at most 0.04 % in cost and lowers the baseline means where the void was a missing fleet or a crashed controller, with many more violation minutes (table below). <!-- §4.102 (10); rq_metrics.csv --> r368 has no formal segment and cannot be included.

| trace | arm | alloc_vm excl. → incl. | violation minutes excl. → incl. | added run |
|---|---|---|---|---|
| t3 | B4c2 | 1233.0 → 1189.0 (−3.6 %) | 11 → 15 | r379 |
| t3 | B5c1 | 1153.0 → 1158.0 (+0.4 %) | 12 → 42 | r370 |
| t3 | B6 | 1227.7 → 1225.2 (−0.2 %) | 10 → 17 | r376 |
| t4 | B4c2 | 1446.7 → 1442.8 (−0.3 %) | 2 → 5 | r302 |
| t4 | B5c1 | 1409.7 → 1367.5 (−3.0 %) | 7 → 46 | r304 |
| t4 | S4b | 1420.0 → 1419.5 (−0.04 %) | 10 → 15 | r309 |
| t4 | v6 | 1378.0 → 1377.8 (−0.02 %) | 5 → 6 | r307 |

Table. Sensitivity of the arm means to the voiding rule: valid runs only (excl.) against valid plus voided runs (incl.).
