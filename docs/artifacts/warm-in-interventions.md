<!-- artifact file of the paper "Risk-Calibrated Autoscaling of a Three-Layer 5G User Plane" (docs/paper), written 2026-10-20 when the main paper and the supplementary material were merged into one PDF (spec §4.103). Content moved from S-supplement.md S.1; numbers unchanged. -->

# Warm-in interventions per block (manual three-step procedure, harness r33b)


Counts are PLATFORM lines in the campaign log (one line = one action; UE-times = UEs touched). Only valid runs are listed; voided runs are given in parentheses. <!-- §4.93 item 5, §4.82 F, §4.86 -->

| trace block | runs | interventions | UE-times | runs with ≥1 intervention |
|---|---|---|---|---|
| t3 | 19 | 2 (+1 in voided r376) | 2 (+1) | r378 (v6, UE-5), r380 (B5c1, UE-3) |
| t4 | 19 (+1 confirmation) | 0 | 0 | none |
| t5 | 7 | 0 | 0 | none |
| t6 | 19 | 6 | 26 | r407 (B6) 2/10, r413 (B6) 2/11, r417 (B5c1) 1/4, r418 (B6) 1/1 |
| t7 | 19 | 18 | 35 | r431 (v6) 1/1, r434 (B5c1) 4/12, r435 (B6) 3/7, r438 (B4c2) 2/3, r440 (B5c1) 2/2, r441 (B6) 1/2, r443 (B4c2) 3/6, r445 (B5c1) 2/2 |

Table. Warm-in interventions per block (manual three-step procedure, harness r33b).

No intervention occurred inside a scored (formal) segment in any block. <!-- §4.82, §4.86 --> In t7, 14 UE-times were respawned by the operator and 21 were handed back to the harness after the first two steps (R49 rule). <!-- §4.86 -->
