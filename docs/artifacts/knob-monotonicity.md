<!-- artifact file of the paper "Predictable-Cost Autoscaling of a Three-Layer 5G User Plane with Library-Calibrated Risk" (docs/paper), written 2026-10-21 for the round-62 analyses (spec §4.104 H item 4, results §4.105). Content copied verbatim from qsim/r62ab/REPORT.md, section "Knob monotonicity"; simulation only, no hardware run. -->

# Knob monotonicity

### Knob monotonicity (realised risk ordering S4a ≤ S4b ≤ v6)

Hardware: groups exactly 'MAIN tX S4a' / 'MAIN tX S4b' / 'MAIN tX v6' in rq_metrics.csv (VOID runs and 'v6 confirm post-IRQ' r381 excluded; r381 noted). Violating minutes per run = 60 − slo. Simulation rows: nest2 (S4a/S4b at deployed λ) and v8sim2.sim_v6 on the same trace; Madrid from qsim/madrid/t12_table.md; Melbourne library = fresh deployed-λ sims over all 1615 traces.

| setting | S4a | S4b | v6 | order | reversal? |
|---|---|---|---|---|---|
| hardware t3 | 7/3 (2.33) | 14/3 (4.67) | 17/3 (5.67) | S4a < S4b < v6 | **none** |
| hardware t4 | 3/3 (1.00) | 10/3 (3.33) | 5/3 (1.67) | S4a < v6 < S4b | **S4b > v6** |
| hardware t5 | 0/1 (0.00) | 0/1 (0.00) | 0/1 (0.00) | S4a ≤ S4b ≤ v6 | **none** |
| hardware t6 | 0/3 (0.00) | 0/3 (0.00) | 5/3 (1.67) | S4a ≤ S4b ≤ v6 | **none** |
| hardware t7 | 1/3 (0.33) | 0/3 (0.00) | 0/3 (0.00) | S4b ≤ v6 ≤ S4a | **S4a > S4b** |
| sim nest2/sim_v6 t3 | 3 | 3 | 3 | | none |
| sim nest2/sim_v6 t4 | 0 | 1 | 3 | | none |
| sim nest2/sim_v6 t5 | 0 | 0 | 0 | | none |
| sim nest2/sim_v6 t6 | 0 | 0 | 2 | | none |
| sim nest2/sim_v6 t7 | 0 | 0 | 0 | | none |
| madrid_1to1 (sim, mean risk %) | 0.048 | 0.213 | 0.396 | | none |
| madrid_compressed (sim, mean risk %) | 0.062 | 0.111 | 0.272 | | none |
| Melbourne library 1615 (sim, mean risk %) | 0.467 | 1.886 | 2.388 | | none |

(r381 'MAIN t4 v6 confirm post-IRQ': 4 violating minutes; including it, hardware t4 v6 = 9/4.)

**Verdict, monotonicity.** Simulation is monotone everywhere: nest2 and sim_v6 on t3–t7, Madrid 1:1, Madrid compressed, and the Melbourne library. Hardware has **two reversals**:
- **t4, S4b > v6:** 10/3 against 5/3 per run. Including r381 (v6 at 9/4 = 2.25 per run), S4b is still riskier.
- **t7, S4a > S4b:** 1/3 against 0/3. This is a single violating minute.

The S4a < S4b ordering holds on t3 and t4 and ties on t5 and t6. The S4b < v6 ordering holds on t3 and t6. With 3 runs per arm the t7 reversal is within noise (one minute); the t4 reversal is the substantive one (+5 minutes over 3 runs).
