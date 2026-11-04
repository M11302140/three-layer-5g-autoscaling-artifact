<!-- artifact file of the paper "Predictable-Cost Autoscaling of a Three-Layer 5G User Plane with Library-Calibrated Risk" (docs/paper), written 2026-10-21 (spec §4.107 C, §4.108). Content copied verbatim from qsim/r63bf/REPORT.md "C"; log and CSV analysis only -->

# Host CPU burned, allocation, UE moves and violations on t6 and t7


Sources:
- burned, burned_wk, burned_vy, alloc_vm and slo (core-min per run): `rq_metrics.csv` groups `MAIN tX <arm>`. Group names used: B5c1 = "B5c1 (q11)", B6 = "B6 u=0.70".
- Moves: `paper_out_new/ops/ops_per_run.csv`, means per run over the same runs.
  - drain moves = Σ `{` in `drain: plan` moves.
  - relief = Σ `moves` of `v6 pool relief`.
  - hot-slot relief = Σ `moves` of `v6 hot slot relief`.

| trace | arm | n | burned (runs) | burned_wk / burned_vy | alloc_vm | viol. min (total) | drain UE moves/run | relief UE moves/run | hot-slot UE moves/run |
|---|---|---|---|---|---|---|---|---|---|
| t6 | S4a | 3 | 687.0 (689,683,689) | 483.3 / 203.7 | 1435.0 | 0 | 4.33 | 0 | 0 |
| t6 | **S4b** | 3 | **654.0** (648,652,662) | 457.7 / 196.3 | 1390.3 | **0** | 0.00 | 0 | 0 |
| t6 | v6 | 3 | 647.3 (638,647,657) | 470.3 / 177.0 | 1349.3 | 5 | 4.00 | 0 | 0.67 |
| t6 | B4c2 | 3 | 712.7 (713,732,693) | 504.0 / 209.0 | 1455.7 | 5 | 1.00 | 0 | 0.33 |
| t6 | B5c1 | 3 | 683.0 (692,673,684) | 485.3 / 197.7 | 1433.0 | 2 | 1.33 | 0 | 0 |
| t6 | B6 | 3 | 714.7 (733,706,705) | 513.3 / 201.3 | 1447.3 | 0 | 0.00 | 0 | 0 |
| t6 | B1 | 1 | 730.0 | 521.0 / 209.0 | 1464.0 | 0 | 0 | 0 | 0 |
| t7 | S4a | 3 | 667.7 (663,660,680) | 470.7 / 197.0 | 1427.0 | 1 | 5.00 | 0 | 0 |
| t7 | **S4b** | 3 | **644.3** (645,640,648) | 447.3 / 197.0 | 1387.3 | **0** | 3.00 | 0 | 0 |
| t7 | v6 | 3 | 641.7 (638,648,639) | 463.0 / 179.3 | 1353.0 | 0 | 6.00 | 0 | 0 |
| t7 | B4c2 | 3 | 715.7 (705,722,720) | 521.0 / 194.7 | 1440.7 | 0 | 1.67 | 0 | 0 |
| t7 | B5c1 | 3 | 679.7 (684,684,671) | 496.0 / 183.7 | 1413.0 | 0 | 4.67 | 0 | 0 |
| t7 | B6 | 3 | 711.7 (710,719,706) | 510.0 / 201.7 | 1451.0 | 0 | 1.33 | 0 | 0 |
| t7 | B1 | 1 | 733.0 | 526.0 / 207.0 | 1464.0 | 1 | 0 | 0 | 0 |

**S4b's burned is below all three tuned baselines on both traces.**
- t6: 654.0 against B4c2 712.7 (−58.7, −8.2%), B5c1 683.0 (−29.0, −4.2%) and B6 714.7 (−60.7, −8.5%).
- t7: 644.3 against 715.7 (−71.4, −10.0%), 679.7 (−35.4, −5.2%) and 711.7 (−67.4, −9.5%).
- Each single S4b run is below every single run of each baseline on the same trace. S4b max is 662 on t6 and 648 on t7; the baseline mins are 673 on t6 (B5c1 r412) and 671 on t7 (B5c1 r445).
- v6 is lower than S4b on both traces: −6.7 on t6 and −2.6 on t7.

Moves and violations:
- S4b made 0 drain UE moves per run on t6 and 3.0 on t7.
- No arm made any pool-relief UE moves on t6/t7.
- Hot-slot relief appears only in v6 t6 (2 moves in r420) and B4c2 t6 (1).
- S4b scored 0 violating minutes in all 6 formal t6/t7 runs, so its UE moves caused no scored violation.

