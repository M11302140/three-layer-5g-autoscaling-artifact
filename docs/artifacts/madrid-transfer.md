<!-- artifact file of the paper "Predictable-Cost Autoscaling of a Three-Layer 5G User Plane with Library-Calibrated Risk" (docs/paper), written 2026-10-21 when the table was moved out of the results chapter for the page budget (spec §4.104 H); numbers unchanged, source comments kept. -->

# Transfer tests on the Madrid 1:1 library

| test | arm or target | $\lambda_{\mathrm{VM}}$ / $\lambda_{\mathrm{UP}}$ | risk | alloc (core-min) | outcome |
|---|---|---|---|---|---|
| T1 | S4a (ε = 0.5 %), Melbourne λ | 2.83 / 3.08 | 0.048 % ± 0.016 | 1224.5 | 0.10 ε: conservative, transfers |
| T1 | S4b (ε = 2 %), Melbourne λ | 1.83 / 2.00 | 0.213 % ± 0.034 | 1130.5 | 0.11 ε: conservative, transfers |
| T2 | v6, frozen constants | n/a | 0.396 % ± 0.055 | 1091.5 | 2.388 % on Melbourne: −1.99 pp |
| R = R′ | 2 % target | 0.96 / 1.50 | 0.0188 ± 0.0027 | 1021.4 ± 13.6 | below ε − SE |
| R = R′ | 0.5 % target | 2.25 / 2.50 | 0.0051 ± 0.0010 | 1111.7 ± 11.2 | recovers |
| R | 0.396 % (v6's risk) | 2.04 / 2.79 | 0.0039 ± 0.0010 | 1124.0 ± 9.2 | equal risk to v6: +3.0 % |
| R′ | 0.396 % (v6's risk) | 2.29 / 2.71 | 0.0040 ± 0.0010 | 1124.5 ± 9.8 | equal risk to v6: +3.0 % |

Table. Transfer tests on the Madrid 1:1 library (556 windows): T1 and T2 on the whole library (± = standard error over traces); R (λ grid floor 1.0 / 1.5) and R′ (grid extended to 0.5 on both axes, step 0.25) as held-out means over six grouped splits (± = standard deviation over splits; standard errors 0.0011, 0.0004 and 0.0004). R′ selects the same λ as R in every split at 2 % and 0.5 %, and no R′ split touched the 0.5 floor. <!-- madrid/REPORT.md step 5 table (T1/T2), step 6 / recal_table.md (R mean ± std rows), recal2_table.md (R′ rows: identical to R at 0.02 and 0.005; at 0.00396 λ 2.29 ± 0.43 / 2.71 ± 0.25, risk 0.0040 ± 0.0010, alloc 1124.5 ± 9.8; floor-touch 0/6 at every target) -->

## Sentences shortened in the paper on 2026-10-21 (page budget)

A completeness rule written before the data were examined excluded a station whose segments miss 1 % or more of their seconds: BS1 to BS3 were excluded at 1.68 %, 1.48 % and 8.94 % missing seconds, and BS4 to BS6 were kept at 0.36 %, 0.67 % and 0.045 % with linear interpolation of the missing seconds.

 every cheaper point exceeds 2 % on the calibration set (for example 0.0224 at 0.75 / 1.5 and 0.0248 at 1.0 / 1.25 against 0.0184 at 1.0 / 1.5 in the first split).

## T1 with the leakage-free λ (round 63)

<!-- 2026-10-21 (spec §4.107 A, §4.108): copied verbatim from qsim/r63r/REPORT.md "Task 2". -->


The procedure is the same as `madrid/mad_t12.py` T1: frozen `v8sim10.sim_nest2(ue, cfg_measured(), Prior, L, acct='vmexist')` over the 556 kept 1:1 windows of `madrid/madrid_lib.json`.
- **Prior.** The Melbourne full-library Prior (`prior_traces.json`, 1615 traces), which is the Prior the deployed system carries.
- **Rule (§4.99 B item 7).** Realised risk in [ε, 1.5ε] → "λ transfers directly"; < ε → "conservative, transfers"; > 1.5ε → "needs recalibration".
- **Reproduction check.** The deployed-λ rows reproduce madrid/REPORT.md exactly: 0.048 % / 1224.5 and 0.213 % / 1130.5, both MATCH.

| λ set | ε | realised risk ± SE | traces with ≥1 violation | alloc vmexist ± SE | risk/ε | T1 verdict | old T1 (madrid/REPORT.md, deployed λ) |
|---|---|---|---|---|---|---|---|
| **S4b new 1.88/1.88/2.00** | 0.02 | **0.213 %** ± 0.034 | 8.8 % | **1131.6** ± 9.1 | 0.11 | **conservative, transfers** | 0.213 %, 1130.5, conservative, transfers |
| **S4a new 2.75/2.75/3.12** | 0.005 | **0.048 %** ± 0.017 | 1.6 % | **1226.2** ± 8.1 | 0.10 | **conservative, transfers** | 0.048 %, 1224.5, conservative, transfers |
| S4b deployed 1.83/2.00 (reference, fresh) | 0.02 | 0.213 % ± 0.034 | 8.8 % | 1130.5 ± 9.0 | 0.11 | conservative, transfers | (same) |
| S4a deployed 2.83/3.08 (reference, fresh) | 0.005 | 0.048 % ± 0.016 | 1.8 % | 1224.5 ± 8.3 | 0.10 | conservative, transfers | (same) |
| sensitivity: unrounded 1.875/2.00 and 2.75/3.125 | | identical to the rounded rows (0.213 % / 1131.6; 0.048 % / 1226.2) | | | | | |

**T1 verdict: unchanged.** Both arms are "conservative, transfers" at ≈ 0.1 ε.
- **Risk.** The realised risk is the same to the minute: S4b 71 violating minutes and S4a 16 of 33 360.
- **Alloc.** Alloc moves +1.1 (S4b) and +1.7 (S4a) core-min per trace (+0.1 %).
- **Traces with violations.** The S4a share of traces with any violation drops from 1.8 % to 1.6 % (10 → 9 windows), with the same total minutes.



## Sentence moved from the Results chapter (2026-10-22, rev. 1)

The compressed Madrid library gives the same picture (T1 0.062 % / 0.111 %, T2 0.272 %). Including the two cells excluded by the completeness rule, with segments cut at 10 s gaps (a sensitivity check, not adopted: 781 windows, 65 groups), gives T1 0.073 % / 0.301 % and T2 0.516 % with the same verdicts.
