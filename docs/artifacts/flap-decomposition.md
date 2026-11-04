<!-- artifact file of the paper "Risk-Calibrated Autoscaling of a Three-Layer 5G User Plane" (docs/paper), written 2026-10-20 when the main paper and the supplementary material were merged into one PDF (spec §4.103). Content moved from S-supplement.md S.11 (second table) and A-appendix.md A.4 (flap definitions); numbers unchanged. -->

# Flap decomposition and the two flap definitions

| arm | trace | n | flaps total (mean, Σ) | slot-layer flaps (Σ) | slot scale-ins 300–360 s after prior slot scale-out (Σ) | …of which re-scale-out ≤10 min = lock-expiry type (Σ) | same-slot variant (Σ) | flaps attributable to lock-expiry episodes (Σ) | of which in→out half (Σ) | flaps involving any 300–360 s release (refilled or not) (Σ) | flaps as published in rq_metrics.csv (mean, Σ) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| S4a | t3 | 3 | 5.7, 17 | 17 | 6 | 1 | 1 | 2 | 1 | 10 | 7.7, 23 |
| S4a | t4 | 3 | 2.0, 6 | 6 | 0 | 0 | 0 | 0 | 0 | 0 | 2.0, 6 |
| S4a | t5 | 1 | 3.0, 3 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 3.0, 3 |
| S4a | t6 | 3 | 5.7, 17 | 14 | 0 | 0 | 0 | 0 | 0 | 0 | 9.3, 28 |
| S4a | t7 | 3 | 3.0, 9 | 6 | 3 | 0 | 0 | 0 | 0 | 3 | 7.0, 21 |
| **S4a** | **all** | 13 | 4.0, 52 | 46 | 9 | 1 | 1 | 2 | 1 | 13 | 6.2, 81 |
| S4b | t3 | 3 | 7.0, 21 | 20 | 5 | 3 | 2 | 5 | 3 | 9 | 7.0, 21 |
| S4b | t4 | 3 | 0.0, 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1.0, 3 |
| S4b | t5 | 1 | 3.0, 3 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 5.0, 5 |
| S4b | t6 | 3 | 6.0, 18 | 12 | 0 | 0 | 0 | 0 | 0 | 0 | 6.0, 18 |
| S4b | t7 | 3 | 4.3, 13 | 9 | 4 | 1 | 1 | 2 | 1 | 5 | 6.7, 20 |
| **S4b** | **all** | 13 | 4.2, 55 | 44 | 9 | 4 | 3 | 7 | 4 | 14 | 5.2, 67 |
| v6 | t3 | 3 | 7.3, 22 | 18 | 1 | 1 | 1 | 3 | 1 | 3 | 7.3, 22 |
| v6 | t4 | 3 | 0.0, 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.0, 0 |
| v6 | t5 | 1 | 3.0, 3 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 3.0, 3 |
| v6 | t6 | 3 | 1.3, 4 | 4 | 1 | 0 | 0 | 0 | 0 | 1 | 1.3, 4 |
| v6 | t7 | 3 | 2.7, 8 | 8 | 0 | 0 | 0 | 0 | 0 | 0 | 2.7, 8 |
| **v6** | **all** | 13 | 2.8, 37 | 32 | 2 | 1 | 1 | 3 | 1 | 4 | 2.8, 37 |

Table. Flap decomposition per arm and trace for S4a, S4b and v6 (valid runs; Σ = sum over runs): flaps under the corrected definition (mean, Σ), slot-layer flaps, slot scale-ins 300 to 360 s after the previous slot scale-out, of which re-scaled-out within 10 minutes (the lock-expiry type), the same-slot variant, flaps attributable to lock-expiry episodes, of which the in-to-out half, flaps involving any 300 to 360 s release whether refilled or not, and the flaps of rq_metrics.csv under the original definition (mean, Σ). <!-- paper_out_new/ops/flap_decomp.md (ops_analysis.py, 2026-10-20), all values verbatim; spec §4.100 D -->

## Flap counts under the original and the corrected definition (formerly Appendix Table A.4)

Flaps per scored hour, mean over valid runs. "Original" is the rq_metrics.py count used in earlier drafts, which keyed daemon messages on their first token and therefore counted a retracted reversible scale-in (the slot was never deleted) and its paired retraction as two actuations; "corrected" (2026-10-20) counts actual actuations only (create/delete VyOS, create/delete worker, slot start/stop). The two definitions differ only for the S arms, which are the only arms that use reversible scale-in. <!-- paper_out_new/ops/flap_decomp.md, ops/xcheck.md; §4.100 D -->

| arm | t3 orig / corr | t4 | t5 | t6 | t7 | all runs |
|---|---|---|---|---|---|---|
| S4a | 7.7 / 5.7 | 2.0 / 2.0 | 3.0 / 3.0 | 9.3 / 5.7 | 7.0 / 3.0 | 6.2 / 4.0 |
| S4b | 7.0 / 7.0 | 1.0 / 0.0 | 5.0 / 3.0 | 6.0 / 6.0 | 6.7 / 4.3 | 5.2 / 4.2 |
| v6 | 7.3 / 7.3 | 0.0 / 0.0 | 3.0 / 3.0 | 1.3 / 1.3 | 2.7 / 2.7 | 2.8 / 2.8 |
| B4c2 | 0.7 / 0.7 | 0.0 / 0.0 | 0.0 / 0.0 | 0.0 / 0.0 | 2.0 / 2.0 | 0.6 / 0.6 |
| B5c1 | 3.0 / 3.0 | 0.0 / 0.0 | 0.0 / 0.0 | 0.0 / 0.0 | 0.0 / 0.0 | 0.7 / 0.7 |
| B6 | 2.3 / 2.3 | 0.0 / 0.0 | 0.0 / 0.0 | 0.0 / 0.0 | 0.7 / 0.7 | 0.7 / 0.7 |
| B1 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |

Table. Flaps per scored hour under the original (rq_metrics) and the corrected (actual actuation) definition; the S arms remain the highest under both. Of the S-arm flaps under the corrected definition, only 2 of 52 (S4a) and 7 of 55 (S4b) are slot releases at the 300 s lock expiry followed by a refill within 10 minutes; the remainder are demand-following reversals 400 to 600 s apart, concentrated on t3 and t6. <!-- §4.100 D -->


## Moved from the Results chapter, 2026-10-21 R66

Relief moves are rare in every arm (at most 0.7 UE moves per scored hour). Most flaps are demand-following reversals 400 to 600 s apart on t3 and t6; the lock-expiry type explains 2 of 52, 7 of 55 and 3 of 37 flaps for S4a, S4b and v6.
