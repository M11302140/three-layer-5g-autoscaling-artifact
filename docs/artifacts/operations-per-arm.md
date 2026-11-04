<!-- artifact file of the paper "Predictable-Cost Autoscaling of a Three-Layer 5G User Plane with Library-Calibrated Risk" (docs/paper), written 2026-10-21 when the table was moved out of the results chapter for the page budget (spec §4.104 H); numbers unchanged, source comments kept. -->

# Actuations per scored hour, per arm

<!-- Source: experiment/paper_out_new/ops/REPORT.md, ops_table.md (ops_analysis.py, 2026-10-20); spec §4.100 D -->

| arm | n | VyOS create / delete | worker create / delete | slot start / stop | reversible scale-ins cancelled | drains | emergency firings | flaps |
|---|---|---|---|---|---|---|---|---|
| S4a | 13 | 1.4 / 0.9 | 0.8 / 0.5 | 3.8 / 3.2 | 1.1 | 5.2 | 0.3 | 4.0 |
| S4b | 13 | 1.4 / 1.2 | 1.3 / 0.8 | 3.5 / 3.3 | 0.7 | 4.4 | 0.2 | 4.2 |
| v6 | 13 | 1.0 / 0.8 | 1.2 / 0.9 | 3.0 / 2.8 | 0.0 | 3.5 | 0.4 | 2.8 |
| B4c2 | 13 | 0.8 / 0.8 | 0.0 / 0.2 | 1.6 / 0.8 | 0.0 | 1.5 | 0.0 | 0.6 |
| B5c1 | 13 | 0.5 / 0.7 | 0.9 / 0.5 | 2.1 / 1.3 | 0.0 | 2.5 | 0.0 | 0.7 |
| B6 | 13 | 1.0 / 0.8 | 0.5 / 0.3 | 1.5 / 0.9 | 0.0 | 1.3 | 0.0 | 0.7 |
| B1 | 5 | 0.0 / 0.0 | 0.0 / 0.0 | 0.0 / 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

Table. Actuations per scored hour, pooled over the valid runs of each arm (13 per arm, 5 for B1), mean; counters are exact daemon-log messages inside the scored segment; drains are drain plans. <!-- ops/ops_table.md per-trace, pooled and r381 tables, all values verbatim; drain UE moves column of the source omitted here -->


## Actuation paragraph of the Results chapter before R66 (2026-10-21), verbatim

Actuations. Actuations per scored hour were counted in every valid run's daemon log and averaged per arm (13 runs per arm, 5 for B1; full table in the artifact repository, operations-per-arm.md); a flap is an actuation reversed on the same layer within 600 s, and a cancelled reversible scale-in is not an actuation. <!-- ops/REPORT.md §2 definitions; per-trace counts (old supplement Table S11) in artifacts/operations-per-trace.md --> No daemon log contains a PFCP re-association line, so that column is omitted. <!-- ops/REPORT.md §2: "no PFCP re-association log line exists; column omitted" --> <!-- Table 2 (actuations per scored hour per arm) moved 2026-10-21 to artifacts/operations-per-arm.md for the page budget (§4.104 H); its key values are in the sentence above --> Pooled over traces, the S arms actuate most, the tuned baselines less, and B1 performs no action: slot starts / stops per hour are 3.8 / 3.2 (S4a), 3.5 / 3.3 (S4b) and 3.0 / 2.8 (v6) against 1.6 / 0.8, 2.1 / 1.3 and 1.5 / 0.9 for B4c2, B5c1 and B6, and flaps 4.0, 4.2 and 2.8 against 0.6, 0.7 and 0.7. <!-- ops/ops_table.md pooled rows (old Table 2 of this chapter, verbatim values) --> Relief moves are rare in every arm: at most 0.4 UE moves per scored hour by pool relief and 0.7 by hot-slot relief, both in v6 (S4a 0.0 and 0.2, S4b 0.3 and 0.5). <!-- ops/ops_table.md pooled rows: pool / hot-slot S4a 0.0/0.2, S4b 0.3/0.5, v6 0.4/0.7, B4c2 0.3/0.2, B5c1 0.1/0.2, B6 0.2/0.2 --> Emergency firings occur only in S4a, S4b and v6, never in a B arm. <!-- §4.100 D --> Reversible scale-ins that were cancelled before deletion occur only in the S arms, which are the only arms that use reversible scale-in. <!-- ops/REPORT.md §5 --> The lock-expiry flap type, a slot release 300 to 360 s after the previous slot scale-out followed by a refill within 10 minutes, explains 2 of the 52 S4a flaps, 7 of the 55 S4b flaps and 3 of the 37 v6 flaps; the S arms release at the lock boundary (gaps of 323 to 333 s) nine times each, but most of those releases are not refilled. <!-- ops/flap_decomp.md, ops/REPORT.md §4: 2/52, 7/55, 3/37; 9 releases at 323 to 333 s --> The remainder are demand-following reversals 400 to 600 s apart, concentrated on t3 and t6; S4b and v6 have no flap on t4. <!-- ops/REPORT.md §4; §4.100 D --> <!-- flap decomposition per arm and trace and the two flap definitions (old supplement Table S12, old Table A.4) in artifacts/flap-decomposition.md -->

