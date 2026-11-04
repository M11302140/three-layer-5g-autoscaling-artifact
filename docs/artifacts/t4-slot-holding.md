<!-- artifact file of the paper "Risk-Calibrated Autoscaling of a Three-Layer 5G User Plane" (docs/paper), written 2026-10-20 when the main paper and the supplementary material were merged into one PDF (spec §4.103). Content moved from S-supplement.md S.9; numbers unchanged. -->

# Trace t4: slot holding before the burst, per run


| arm | run | slots/VyOS at min 19 | violating minutes | UEs on .38 at min 20 |
|---|---|---|---|---|
| S4a | r300 | 8/8, 3 | none | 5 |
| S4a | r312 | 8/8, 3 | 20 | 5 |
| S4a | r317 | 8/8, 3 | 20, 21 | 5 |
| v6 | r301 | 7/8, 2 | 20, 21 | 5 |
| v6 | r318 | 7/8, 2 | 20 | 6 |
| v6 | r321 | 7/8, 2 | 20, 21 | 6 |
| B4c2 | r308 | 8/8, 3 | none | 5 |
| B4c2 | r313 | 8/8, 3 | none | 5 |
| B4c2 | r320 | 8/8, 3 | none | 4 |
| S4b | r303 | 7/8, 3 | 20, 21 | 5 |
| S4b | r314 | 7/8, 3 | 20, 21 | 5 |
| S4b | r322 | 7/8, 3 | 20, 21 | 5 |
| B5c1 | r310 | 7/8, 3 | 20, 21 | 5 |
| B5c1 | r315 | 7/8, 3 | 20, 21 | n/a (no dist sample) |
| B5c1 | r319 | 7/8, 3 | 20, 21 | 4 |
| B6 | r305 | 8/8, 3 | none | 5 |
| B6 | r311 | 8/8, 3 | none | 5 |
| B6 | r316 | 8/8, 3 | none | 4 |
| B1 | r306 | 8/8, 3 | none | 5 |
| v6 (confirmation) | r381 | 7/8, 2 | 20, 21 | 5 |

Table. Trace t4: slots and VyOS held at the end of minute 19, violating minutes among 20 and 21, and UEs on the victim slot .38 at minute 20, per run.

## Classification of the t4 violation minutes (moved from the results chapter, Section 4, on 2026-10-21 for the page budget)

Of the 28 t4 violation minutes in valid runs (32 with the confirmation run r381), 21 are capacity type including continuations of a capacity event, 4 are events with fewer than five UEs on the victim slot by the literal rule (2 after folding continuations), 1 has no distribution sample and 2 are not slot overflows. <!-- §4.91 item 1; moved here from Section 7 on 2026-10-20 -->
