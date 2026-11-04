<!-- artifact file of the paper "Predictable-Cost Autoscaling of a Three-Layer 5G User Plane with Library-Calibrated Risk" (docs/paper), written 2026-10-21 (spec §4.107 B, §4.108). Content copied verbatim from qsim/r63bf/REPORT.md "B1" and "B2"; log and CSV analysis only. The results chapter (section "H2b: risk fidelity") carries the condensed three-level table and the three class totals -->

# Risk fidelity and the classes of the 117 violating minutes

## B1. Risk fidelity: t3, t4, t6, t7 × {S4a, S4b, v6} (violating minutes per 60-min run)

Sources:
- **registered**: the nest2 exact-trace value, 60 − SLO.
  - S4a/S4b t3/t4 from `qsim/v8_predict_t345_2026-10-07.txt` (vmexist header line; the SLO column is the same for both accountings).
  - v6 t3/t4 from `qsim/v8_predict_v6_t345_2026-10-07.txt` (v8sim2.sim_v6).
  - All arms on t6/t7 from `qsim/v8_predict_t67_2026-10-15.txt`.
- **v8sim11**: the per-slot simulator, computed after the campaign and not registered. Taken from `qsim/m1/REPORT.md` "Supplement R58-2", table (5), with R38 at its defaults.
- **measured**: Σ(60 − slo)/n over the rows of `paper_out_new/rq/rq_metrics.csv` in group `MAIN tX <arm>`, n = 3 each. Void rows and the r381 confirm row are separate groups and are excluded.
- Ratio notation: "∞" means a positive numerator over 0; "n/a" means 0/0.

| trace | arm | registered | v8sim11 | measured (runs; total) | **registered / measured** | **v8sim11 / measured** | measured / registered | measured / v8sim11 |
|---|---|---|---|---|---|---|---|---|
| t3 | S4a | 3 | 3 | 2.33 (r360,r372,r377; 7) | 1.29 | 1.29 | 0.78 | 0.78 |
| t3 | S4b | 3 | 5 | 4.67 (r363,r369,r374; 14) | 0.64 | 1.07 | 1.56 | 0.93 |
| t3 | v6 | 3 | 5 | 5.67 (r361,r367,r378; 17) | 0.53 | 0.88 | 1.89 | 1.13 |
| t4 | S4a | 0 | 2 | 1.00 (r300,r312,r317; 3) | 0.00 | 2.00 | ∞ | 0.50 |
| t4 | S4b | 1 | 4 | 3.33 (r303,r314,r322; 10) | 0.30 | 1.20 | 3.33 | 0.83 |
| t4 | v6 | 3 | 2 | 1.67 (r301,r318,r321; 5) | 1.80 | 1.20 | 0.56 | 0.83 |
| t6 | S4a | 0 | 3 | 0.00 (r402,r414,r419; 0) | n/a | ∞ | n/a | 0.00 |
| t6 | S4b | 0 | 5 | 0.00 (r405,r411,r416; 0) | n/a | ∞ | n/a | 0.00 |
| t6 | v6 | 2 | 2 | 1.67 (r403,r409,r420; 5) | 1.20 | 1.20 | 0.83 | 0.83 |
| t7 | S4a | 0 | 0 | 0.33 (r430,r442,r447; 1) | 0.00 | 0.00 | ∞ | ∞ |
| t7 | S4b | 0 | 0 | 0.00 (r433,r439,r444; 0) | n/a | n/a | n/a | n/a |
| t7 | v6 | 0 | 1 | 0.00 (r431,r437,r448; 0) | n/a | ∞ | n/a | 0.00 |

Reading in the reviewer's direction (prediction / measured), counting finite non-zero cells only:
- **Registered**: 0.30–1.80, over 6 cells.
  - Under-prediction: t4 S4b 0.30, t3 v6 0.53, t3 S4b 0.64.
  - Predicted 0 against measured > 0: t4 S4a and t7 S4a.
- **v8sim11**: 0.88–2.00, over 7 cells.
  - Over-prediction: t6 S4a and t6 S4b (predicted 3 and 5, measured 0) and t7 v6 (1 against 0). These show as ∞.
  - Under-prediction: t7 S4a only (0 against 0.33).

The measured / prediction columns match the existing §4.100 A table exactly.

Sensitivity: if r381 (group `MAIN t4 v6 confirm post-IRQ`, slo 56) is added, t4 v6 measured becomes 9/4 = 2.25. Registered / measured is then 1.33 and v8sim11 / measured 0.89.

## B2. Reclassification of the 117 violating minutes (84 valid runs)

Per-minute fields come from `/home/user/experiment/p2/trace_v7_rNNN.csv`. The old class comes from cross_residual.py (unchanged). The new class uses the following rule.

**Fleet shortage.** A minute is a fleet shortage if any one of these holds:
- **Slot:** ready_slots × 5 UE < target_ue. ready_slots is the numerator of `eupf_cov`.
- **VyOS:** vyos_n × 16 UE < target_ue. CapVY = 4.45 Mpps × 0.93 / 0.25 Mpps per UE = 16.55, floored to 16.
- **Worker:** worker_n × 2 < ceil(target_ue / 5).

**Placement overflow.** The fleet check passes and the old class is capacity, tail or type2.

**Other.** The fleet check passes and the old class is non-slot or nodist.

Fleet shortage takes precedence over every old class.

Notes on the fleet fields. All of them bias the shortage count low:
- `eupf_cov` = `n_valid/8` from `mlib.eupf_decap_drop` (`experiment/mlib.py:114-128`, via `p2/loss_ledger.py:228`). It counts slots whose eUPF counters were readable at both ends of the minute window. A slot pod that exists but has not finished its rehome is therefore counted, so ready_slots is an upper bound on carrying slots.
- `vyos_n` = `len(m.vyos_pool)`, the harness traffic pool (dataplane-admitted). It is sampled when the row is written at the end of the minute (`experiment/trace_run.py:2043-2052`), so a VyOS admitted during the minute counts for the whole minute.
- `worker_n` = workers present in the host CPU snapshot.

**Worker shortage never occurs alone.** It occurred in 6 minutes, always together with slot shortage. ready_slots ≤ 2 × worker_n held in every violating minute, so worker shortage logically implies slot shortage.

| trace | runs | violating min | fleet shortage | placement overflow | other |
|---|---|---|---|---|---|
| t3 | 19 | 71 | **47 (66.2%)** | 16 (22.5%) | 8 (11.3%) |
| t4 | 20 | 32 | **14 (43.8%)** | 16 (50.0%) | 2 (6.3%) |
| t5 | 7 | 0 | 0 | 0 | 0 |
| t6 | 19 | 12 | 0 | **11 (91.7%)** | 1 (8.3%) |
| t7 | 19 | 2 | 0 | 1 (50%) | 1 (50%) |
| **all** | **84** | **117** | **61 (52.1%)** | **44 (37.6%)** | **12 (10.3%)** |

- Old to new: capacity 83 → 53 fleet + 30 placement; tail 10 → 4 + 6; type2 11 → 3 + 8; nodist 1 → 1 fleet; non-slot 12 → 12 other.
- Layers short in the 61 fleet minutes:
  - slot + VyOS: 26
  - slot only: 26
  - slot + VyOS + worker: 6
  - VyOS only: 3 (r301, r321 and r381, each at t4 min 21: vyos_n 2, target 34)
- The fleet minutes are the t3 min 3–5 step (target 33 → 40 → 36 UE with 6/8 slots and 2 VyOS) in all 6 arms, and the t4 min 20–21 burst (37 UE on 7/8 slots, or 2 VyOS). The full list is in `r63bf_out.txt`.

Sensitivities (`r63bf_extra_out.txt`):

| rule variant | fleet | placement | other | t4 fleet |
|---|---|---|---|---|
| main rule (VY cap 16) | 61 | 44 | 12 | 14 |
| VY cap 16.55 (unrounded) | 61 | 44 | 12 | 14 |
| VY cap 18 (= v8sim11 `PHYS['vy_knee']`) | 58 | 47 | 12 | 11 |
| slot check only | 58 | 47 | 12 | 11 |
| active_ue instead of target_ue | 61 | 44 | 12 | 14 |

The cap-16 and cap-16.55 rules differ on 17 minutes (t3 min 3, vyos_n 2, target 33). All 17 are slot-short anyway, so the counts do not move.

Per arm (fleet / placement / other):

| trace | S4a | S4b | v6 | B4c2 | B5c1 | B6 | B1 |
|---|---|---|---|---|---|---|---|
| t3 | 6/1/0 | 9/1/4 | 9/6/2 | 9/2/0 | 8/3/1 | 6/3/1 | – |
| t4 | 0/3/0 | 3/7/0 | 8/1/0 (of which r381 3/1/0) | 0/1/1 | 3/3/1 | 0/1/0 | – |
| t6 | – | – | 0/4/1 | 0/5/0 | 0/2/0 | – | – |
| t7 | 0/0/1 | – | – | – | – | – | 0/1/0 |

<!-- 2026-10-21 R64 (§4.109): the H2b section of the results chapter was reduced to three sentences and its table merged into the main table; the r63 text and table of that section follow, verbatim (in the paper, "Table 3" was this table and "Section 6"/"Section 7" referred to the old numbering) -->

## Text of the H2b section before R64

<!-- Section added 2026-10-21 (spec §4.107 B, round 63). Source: experiment/qsim/r63bf/REPORT.md B1 (three-level table; registered = nest2 exact-trace 60 − SLO from qsim/v8_predict_t345_2026-10-07.txt, v8_predict_v6_t345_2026-10-07.txt and v8_predict_t67_2026-10-15.txt; per-slot = v8sim11 from qsim/m1/REPORT.md Supplement R58-2 (5), computed after the campaign, not registered; measured = Σ(60 − slo)/3 over rq_metrics.csv groups "MAIN tX <arm>", voided runs and r381 excluded) and B2 (117 violating minutes of the 84 valid runs, three classes); full tables in artifacts/risk-fidelity-and-violation-classes.md; the earlier three-level table (measured / prediction) is in artifacts/conditional-risk-three-levels.md. -->

H2 concerns cost. Whether the simulator also predicts violation minutes is a separate question: λ is calibrated so that the simulated library risk meets ε, so ε is a simulation-level target, and cost fidelity does not imply risk fidelity. Table 3 compares three levels for the arms that never saw a target trace: the fleet-level prediction registered before the runs, the per-slot simulator computed after the campaign and not registered, and the hardware mean. <!-- §4.107 B; r63bf/REPORT.md B1 sources -->

| cell | registered / per-slot / hardware | registered / hardware | per-slot / hardware |
|---|---|---|---|
| t3 S4a | 3 / 3 / 2.33 | 1.29 | 1.29 |
| t3 S4b | 3 / 5 / 4.67 | 0.64 | 1.07 |
| t3 v6 | 3 / 5 / 5.67 | 0.53 | 0.88 |
| t4 S4a | 0 / 2 / 1.00 | 0.00 | 2.00 |
| t4 S4b | 1 / 4 / 3.33 | 0.30 | 1.20 |
| t4 v6 | 3 / 2 / 1.67 | 1.80 | 1.20 |
| t6 S4a | 0 / 3 / 0.00 | n/a | ∞ |
| t6 S4b | 0 / 5 / 0.00 | n/a | ∞ |
| t6 v6 | 2 / 2 / 1.67 | 1.20 | 1.20 |
| t7 S4a | 0 / 0 / 0.33 | 0.00 | 0.00 |
| t7 S4b | 0 / 0 / 0.00 | n/a | n/a |
| t7 v6 | 0 / 1 / 0.00 | n/a | ∞ |

Table 3. Risk fidelity: violating minutes per 60-minute run at three levels, the fleet-level prediction registered before the runs, the per-slot simulator computed after the campaign (not registered) and the hardware mean over three valid runs, with the ratios prediction / hardware (∞: positive prediction, none measured; n/a: 0 / 0). <!-- r63bf/REPORT.md B1 table, columns registered, v8sim11, measured, registered / measured, v8sim11 / measured, verbatim. In the direction measured / prediction (as in §4.100 A and artifacts/conditional-risk-three-levels.md): measured / registered 0.78, 1.56, 1.89 (t3), ∞, 3.33, 0.56 (t4), n/a, n/a, 0.83 (t6), ∞, n/a, n/a (t7); measured / per-slot 0.78, 0.93, 1.13 (t3), 0.50, 0.83, 0.83 (t4), 0.00, 0.00, 0.83 (t6), ∞, n/a, 0.00 (t7) -->

Over the six cells where prediction and measurement are both non-zero, the registered values lie at 0.30 to 1.80 times the hardware, under-predicting t4 S4b (0.30), t3 v6 (0.53) and t3 S4b (0.64); they predicted 0 on t4 S4a and t7 S4a, where the hardware had violations. <!-- r63bf/REPORT.md B1 reading (registered) --> The per-slot values lie at 0.88 to 2.00 over seven such cells and place the t4 violations in minutes 20 and 21 as slot .38 overflow, but they predict 3 and 5 minutes on t6 for S4a and S4b and 1 on t7 for v6, where the hardware had none. <!-- r63bf/REPORT.md B1 reading (v8sim11); m1/REPORT.md Supplement R58-2 (minutes 20 and 21, slot .38) --> With the v6 confirmation run r381, t4 v6 measures 2.25 per run (registered / hardware 1.33). <!-- r63bf/REPORT.md B1 sensitivity -->

The 117 violating minutes of the 84 valid runs show what the fleet-level simulator can and cannot see. A minute is a fleet shortage when some layer's ready fleet cannot carry the target demand (ready slots × 5 UE, VyOS × 16 UE or workers × 2 slots below the target), a placement overflow when the fleet suffices but a slot overflowed, and other when the violation is not of slot type. Fleet shortage accounts for 61 minutes (52.1 %), placement overflow for 44 (37.6 %) and other for 12 (10.3 %). <!-- r63bf/REPORT.md B2 rule and table (all: 61 / 44 / 12 of 117); §4.108 B2 --> Every fleet-shortage minute lies on t3 (47, the minute-3 to 5 step from 33 to 40 UE, in all six arms) or on t4 (14, the minute-20 to 21 burst); on t6, 11 of the 12 minutes are placement overflow. <!-- r63bf/REPORT.md B2 per-trace table and bullets; §4.108 B2 --> The fleet fields bias the shortage count low, since a slot counts as ready once its counters are readable and the VyOS count is sampled at the end of the minute; with a VyOS capacity of 18 UE or the slot check alone the split is 58 / 47 / 12. <!-- r63bf/REPORT.md B2 notes on the fleet fields and sensitivity table --> The calibrated fleet-level simulator covers only the first class; placement overflow is only partly approximated by the per-slot simulator (Section~\ref{sec:02sim6}). <!-- §4.107 B ("校準模擬器只涵蓋第一類"); §4.108 B2 -->
