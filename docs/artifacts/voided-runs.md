<!-- artifact file of the paper "Predictable-Cost Autoscaling of a Three-Layer 5G User Plane with Library-Calibrated Risk" (docs/paper), written 2026-10-21 when the table was moved out of the experimental-setup chapter for the page budget (spec §4.104 H); numbers unchanged, source comments kept. -->

# Voided runs of the main experiment

<!-- main_exp_ledger.tsv; §4.74 A, §4.51, §4.52 A -->

| run | trace | arm | SLO/60 | reason | replacement |
|---|---|---|---|---|---|
| r368 | t3 | B4c2 | n/a | TRex crash during warm-in, no formal segment | r373 / r382 |
| r370 | t3 | B5c1 | 30 | gNB NG death from minute 33 (harness) | r380 |
| r376 | t3 | B6 | 53 | NG events inside the formal segment | r383 |
| r379 | t3 | B4c2 | 56 | network outage during the surge segment | r382 |
| r302 | t4 | B4c2 | 57 | start transient after warm-in | r320 |
| r304 | t4 | B5c1 | 21 | daemon panic on image q6 | r310/r315/r319 on q11 |
| r307 | t4 | v6 | 59 | operator computation on the traffic host during the formal segment | r321 |
| r309 | t4 | S4b | 55 | harness gNB NG death at minute 25 | r322 |

Table. Voided runs of the main experiment, with the reason recorded at the time and the replacement run.
