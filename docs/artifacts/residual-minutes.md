<!-- artifact file of the paper "Predictable-Cost Autoscaling of a Three-Layer 5G User Plane with Library-Calibrated Risk" (docs/paper), written 2026-10-21 when the table was moved out of Appendix C for the page budget (spec §4.104 H); numbers unchanged. Source: spec §4.93 item 2. -->

# Residual violation minutes with unexplained mechanism

| trace | arm | run | minute | victim slot | UEs | slot oob (M pkts) | loss % | note |
|---|---|---|---|---|---|---|---|---|
| t3 | v6 | r361 | 3 | .38 | 4 | 0.41 | 0.24 | first surge minute; same slot at 7 UEs in minute 4 (sample lag, conjecture) |
| t3 | B5c1 | r380 | 3 | .38 | 4 | 0.58 | 0.35 | same as above; 6 UEs in minute 4 |
| t4 | B5c1 | r319 | 20 | .38 | 4 | 1.76 | 0.73 | burst minute |
| t4 | B4c2 | r320 | 2 | .32 | 4 | 0.57 | 0.33 | start segment |
| t6 | B4c2 | r410 | 10 | .32 | 4 | 1.15 | 0.58 | no VM/pod operation in window |
| t6 | B4c2 | r410 | 14 | .32 | 4 | 0.46 | 0.25 | same |
| t6 | v6 | r420 | 9 | .34 | 4 | 0.29 | 0.14 | slot/worker scale-out in window |
| t6 | v6 | r420 | 10 | .34 | 4 | 0.45 | 0.24 | same |
| t6 | v6 | r420 | 13 | .34 | 2 | 0.75 | 0.43 | same |
| t7 | none | n/a | n/a | n/a | n/a | n/a | n/a | none |

Table. Residual violation minutes with unexplained mechanism (all traces).

<!-- 2026-10-21 R64 (§4.109): the text of former Appendix C appended below, verbatim -->

## Former Appendix C (text)

Definition: the victim slot (largest out-of-buffer counter in that minute) holds fewer than 5 UEs, and the same slot had no violation in the previous minute (continuations are folded into the preceding event). Classification uses the controller's distribution samples within ±150 s. <!-- §4.93 item 2 -->

The nine minutes are, by trace, arm, run and minute (victim slot, UEs on it): t3 v6 r361 minute 3 (.38, 4 UEs) and t3 B5c1 r380 minute 3 (.38, 4), both first surge minutes with the same slot at 7 and 6 UEs in minute 4 (sample lag, conjecture); t4 B5c1 r319 minute 20 (.38, 4; burst minute); t4 B4c2 r320 minute 2 (.32, 4; start segment); t6 B4c2 r410 minutes 10 and 14 (.32, 4; no VM or pod operation in the window); t6 v6 r420 minutes 9, 10 and 13 (.34, 4, 4 and 2; slot and worker scale-out in the window); none on t7. Out-of-buffer counts and loss per minute are in the artifact repository (residual-minutes.md). <!-- old Table A.2 (§4.93 item 2), moved 2026-10-21 to artifacts/residual-minutes.md for the page budget; values verbatim -->

With the literal rule, which counts a continuation following a non-capacity minute as independent, the count is 11 instead of 9; the two t3 entries stay in the list, since their sample-lag explanation is a conjecture. <!-- §4.93 item 2, R54 rulings 1 and 2 -->


