<!-- artifact file of the paper "Predictable-Cost Autoscaling of a Three-Layer 5G User Plane with Library-Calibrated Risk" (docs/paper), written 2026-10-21 when the table was moved out of the paper (Appendix B) for the page budget (spec §4.104 H); numbers unchanged, source comments kept. -->

# Emergency-rule firings in the main experiment

<!-- §4.95, §4.96 A -->

| group | runs | forced action (s after formal start) | planner's own order would have come at | pre-emption | trajectory effect | cost vs planner-only simulation |
|---|---|---|---|---|---|---|
| t4 S4a | r300, r312, r317 | DEPLOY_VYOS at +36 / +38 / +39 | +66 / +68 / +69 (nest2: minute 1) | 1 tick | none | +4 core-min (+0.3 %) |
| t6 S4b | r405, r411, r416 | DEPLOY_VYOS at +61 / +60 / +64 | +361 / +360 / +364 (nest2: minute 6) | 10 ticks | early VyOS released at minute 11 to 13 (lock expiry), re-ordered at minute 14 | +2 / +6 / +6 core-min (≤ +0.4 %) |
| t6 S4a | r419 (controls r402, r414) | SCALE_OUT_UP at +36 (8th slot) | 8th slot ordered by the planner at minute 7 in the controls | about 5 minutes | 8th slot released at minute 8, re-ordered at minute 10 | +7 slot-min vs controls (+5.6 core-min, +0.4 %) |
| v6 (own rule) | r361 ×2, r367, r378 (t3), r420 (t6) | SCALE_OUT_UP in the surge or ramp segment | n/a (v6 not simulated with nest2) | n/a | n/a | n/a |

Table. Emergency-rule firings in the main experiment (inherited rule, rule 16 of the decision-path table of the Method chapter).

<!-- 2026-10-21 R64 (§4.109): the text of former Appendix B appended below, verbatim -->

## Former Appendix B (text)

Sources: daemon decision logs of the 84 valid runs, the per-tick planner log, and the frozen nest2 simulator rerun with the registered λ. <!-- §4.95, §4.96 A -->

In t4 S4a (r300, r312, r317) the rule ordered a VyOS at +36, +38 and +39 s after the formal start, one tick before the planner's own order at +66 to +69 s (nest2: minute 1), with no change of trajectory and +4 core-min (+0.3 %). In t6 S4b (r405, r411, r416) it ordered a VyOS at +60 to +64 s, ten ticks before the planner's order at +360 to +364 s (nest2: minute 6); the early VyOS was released at minute 11 to 13 when its lock expired and re-ordered at minute 14, at +2, +6 and +6 core-min (≤ +0.4 %). In t6 S4a r419 it ordered the eighth slot at +36 s, about five minutes before the planner did in the controls r402 and r414 (minute 7); the slot was released at minute 8 and re-ordered at minute 10, +7 slot-min against the controls (+5.6 core-min, +0.4 %). v6 fired its own rule (SCALE_OUT_UP in the surge or ramp segment) twice in r361 and once each in r367 and r378 on t3 and in r420 on t6; v6 is not simulated with nest2. The table form is in the artifact repository (emergency-firings.md). <!-- old Table A.1 (§4.95, §4.96 A), moved 2026-10-21 to artifacts/emergency-firings.md for the page budget; values verbatim -->

The S-arm firings followed the start transient described in the Limitations of the Results chapter: the VyOS loss-ratio reading (a VPP-side ratio, p90 over 60 s) of 0.26 to 0.37 occurred in exactly the nine S-arm runs whose pre-formal fleet alignment drained or deleted a unit, and was 0.000 in the other seventeen. <!-- §4.96 D; §4.97 items 1, 2 --> In t6 S4a the reading occurred in all three runs but the rule fired only in r419, because in r402 and r414 the planner had a scale-out order in the same tick and the forced order is skipped in that case. <!-- §4.96 C -->


