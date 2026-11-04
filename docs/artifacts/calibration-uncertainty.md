<!-- artifact file of the paper "Predictable-Cost Autoscaling of a Three-Layer 5G User Plane with Library-Calibrated Risk" (docs/paper), written 2026-10-21 for the round-62 analyses (spec §4.104 H item 4, results §4.105). Content copied verbatim from qsim/r62ab/REPORT.md, sections "Task B: uncertainty" and "Limitations"; simulation only, no hardware run. -->
<!-- 2026-10-21 (spec §4.107 A, §4.108, round 63): sections "Round 63" added at the top, copied verbatim from qsim/r63a/REPORT.md "Task 1" and "Task 2" (dash in headings replaced). The round-62 B1 intervals below (σ̂ fixed on the whole library) are superseded by the nested intervals; the B2 library-size subsets and B3 events below still use the whole-library σ̂. -->

# Round 63 (current): leakage-free σ̂ and nested bootstrap

## Task 1: six-split calibration, σ̂ from the calibration groups only

Old = full-library σ̂ (r62ab lookup = frozen v8sim10_FULL, split by split). New = Prior(calibration groups' traces, cfg_measured), used for both calibration and held-out evaluation of that split. ho alloc = held-out vmexist core-min (dispatch in brackets).

| target | split | Prior traces | λ new | λ old | cal risk new | ho risk new | ho risk old | ho alloc new | ho alloc old | σ̂ fallback D-buckets (new Prior) |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.02 | 0 | 977 | 1.75/2.0 | 1.75/2.0 | 0.0186 | 0.0190 | 0.0190 | 1287.6 (1295.1) | 1288.5 (1295.9) | none |
| 0.02 | 1 | 985 | 2.0/2.0 | 2.0/2.0 | 0.0186 | 0.0188 | 0.0175 | 1284.6 (1292.2) | 1288.8 (1296.3) | none |
| 0.02 | 2 | 970 | 1.75/2.0 | 1.75/2.0 | 0.0193 | 0.0205 | 0.0205 | 1274.8 (1282.7) | 1274.8 (1282.7) | none |
| 0.02 | 3 | 981 | 2.0/2.0 | 1.75/2.0 | 0.0173 | 0.0203 | 0.0214 | 1285.1 (1292.8) | 1280.8 (1288.3) | none |
| 0.02 | 4 | 986 | 1.75/2.0 | 1.75/2.0 | 0.0199 | 0.0222 | 0.0211 | 1272.8 (1280.8) | 1275.4 (1283.4) | none |
| 0.02 | 5 | 976 | 2.0/2.0 | 2.0/2.0 | 0.0184 | 0.0168 | 0.0169 | 1287.6 (1295.1) | 1286.7 (1294.2) | none |
| 0.005 | 0 | 977 | 3.0/3.0 | 3.0/3.0 | 0.0048 | 0.0050 | 0.0050 | 1346.8 (1351.8) | 1346.9 (1351.9) | none |
| 0.005 | 1 | 985 | 2.75/3.25 | 2.75/3.25 | 0.0041 | 0.0037 | 0.0037 | 1344.3 (1349.3) | 1345.9 (1350.9) | none |
| 0.005 | 2 | 970 | 2.5/3.0 | 2.75/3.0 | 0.0050 | 0.0056 | 0.0053 | 1328.8 (1334.5) | 1331.6 (1337.4) | none |
| 0.005 | 3 | 981 | 2.5/3.25 | 2.25/3.25 | 0.0048 | 0.0048 | 0.0062 | 1338.3 (1343.5) | 1337.0 (1342.6) | none |
| 0.005 | 4 | 986 | 2.75/3.25 | 3.0/3.0 | 0.0046 | 0.0042 | 0.0054 | 1335.0 (1340.1) | 1333.4 (1338.9) | none |
| 0.005 | 5 | 976 | 3.0/3.0 | 2.25/3.25 | 0.0047 | 0.0036 | 0.0053 | 1342.0 (1347.0) | 1336.6 (1342.1) | none |

Summary (mean ± std over 6 splits, std ddof=0; SE = std/√6):

| target | σ̂ | λ_VM | λ_UP | ho risk | SE | ho alloc vmexist (dispatch) |
|---|---|---|---|---|---|---|
| 0.02 | full library (old) | 1.83 ± 0.12 | 2.00 ± 0.00 | 0.0194 ± 0.0017 | 0.0007 | 1282.5 ± 5.9 (1290.1) |
| 0.02 | calibration groups (new) | 1.88 ± 0.12 | 2.00 ± 0.00 | 0.0196 ± 0.0017 | 0.0007 | 1282.1 ± 6.0 (1289.8) |
| 0.005 | full library (old) | 2.67 ± 0.31 | 3.12 ± 0.12 | 0.0051 ± 0.0007 | 0.0003 | 1338.6 ± 5.8 (1344.0) |
| 0.005 | calibration groups (new) | 2.75 ± 0.20 | 3.12 ± 0.12 | 0.0045 ± 0.0007 | 0.0003 | 1339.2 ± 6.0 (1344.4) |

Rule (§4.107 A): |Δλ_VM mean| ≤ 0.25 and |Δλ_UP mean| ≤ 0.25 and |Δ ho risk mean| ≤ SE_new, both targets.

| target | Δλ_VM | Δλ_UP | Δ ho risk | SE_new | pass |
|---|---|---|---|---|---|
| 0.02 | +0.042 | +0.000 | +0.0002 | 0.0007 | yes |
| 0.005 | +0.083 | +0.000 | -0.0007 | 0.0003 | NO |

**Rule verdict: FAIL**


**Verdict (rule written in §4.107 A): FAIL.** At 2 % the rule passes (Δλ_VM +0.04, Δλ_UP 0, Δ ho risk +0.0002 against SE 0.0007). At 0.5 % the λ part passes
(Δλ_VM +0.08, Δλ_UP 0.00, both ≤ 0.25) but the held-out risk part does not: new 0.00449 ± 0.00070 vs old 0.00514 ± 0.00074, Δ = −0.00065, which is 2.3 × SE_new (0.00029).

Differences, stated:
* The change is toward **lower** held-out risk at 0.5 % (new is 0.0005 below ε = 0.005, i.e. 1.8 SE conservative), not toward optimism; held-out cost moves by +0.6 core-min (1339.2 vs 1338.6 vmexist, +0.05 %). At 2 % cost −0.4 core-min.
* The calibration-group σ̂ is almost the full-library σ̂ (σ̂_win at D = 20, mean over splits: VY 3.703 / UP 2.648 vs full library 3.704 / 2.644). The risk difference comes from
  **different grid selections in 4 of 6 splits at 0.5 %** (splits 2–5: 2.5/3.0, 2.5/3.25, 2.75/3.25, 3.0/3.0 vs old 2.75/3.0, 2.25/3.25, 3.0/3.0, 2.25/3.25) and 1 of 6 at 2 % (split 3: 2.0/2.0 vs 1.75/2.0);
  where the selected λ is the same, held-out values still differ slightly because σ̂ differs (e.g. 2 % split 1: λ 2.0/2.0 both, ho 0.0188 vs 0.0175; at 0.5 % splits 0 and 1 give the same held-out risk).
* Interpretation (not part of the rule): in the 200-resample paired comparison (Task 2) the same leakage change shifts 0.5 % held-out risk by +0.0001 [−0.0010, +0.0014], centred on zero.
  The six-split failure is therefore consistent with grid-selection noise amplified by a small SE, rather than a systematic leakage effect. The rule is applied as written regardless.

**Consequence per §4.107 A:** conditional calibration, the equal-risk ablation and Madrid T1 must be recomputed with the new calibration.
* Conditional calibration: **recomputed here** (Task 3, bucket-internal σ̂).
* **Pending (not recomputed, per instruction):** the equal-risk ablation (`v8sim10_ablation` / `abl/ablation_table.md`), Madrid T1 (`qsim/madrid/t12_table.md`), and the downstream uses of the
  conditional λ in r62ab (test-trace decile-λ table and `fig_r62_decile_lambda.pdf`, which used full-library σ̂).

## Task 2: nested cluster bootstrap (200 resamples, σ̂ re-estimated per resample)

Old = r62ab B1 primary (σ̂ fixed on the full library, cal = first 300), same draws.

| target | σ̂ | resamples | λ_VM mean [2.5, 97.5] | λ_UP mean [2.5, 97.5] | ho risk mean [2.5, 97.5] | P(ho risk > ε) | ho alloc vmexist mean [2.5, 97.5] | ho n (mean) | infeasible |
|---|---|---|---|---|---|---|---|---|---|
| 0.02 | re-estimated per resample (new) | 200 | 1.78 [1.50, 2.00] | 2.07 [2.00, 2.50] | 0.0192 [0.0136, 0.0251] | 0.40 | 1281.1 [1264.6, 1299.1] | 590 | 0 |
| 0.02 | fixed full-library (r62ab, all 200) | 200 | 1.81 [1.50, 2.00] | 2.04 [2.00, 2.25] | 0.0190 [0.0134, 0.0240] | 0.33 | 1281.6 [1265.7, 1298.9] | 590 | 0 |
| 0.005 | re-estimated per resample (new) | 200 | 2.56 [2.00, 3.00] | 3.14 [2.99, 3.50] | 0.0052 [0.0029, 0.0082] | 0.50 | 1335.8 [1317.2, 1351.7] | 590 | 0 |
| 0.005 | fixed full-library (r62ab, all 200) | 200 | 2.59 [2.00, 3.00] | 3.12 [2.99, 3.50] | 0.0051 [0.0026, 0.0082] | 0.49 | 1335.8 [1316.9, 1352.7] | 590 | 0 |

Paired (same draw) differences new − fixed-σ̂, mean [2.5, 97.5]:

| target | Δλ_VM | Δλ_UP | Δ ho risk | Δ ho alloc vmexist | resamples with a different λ |
|---|---|---|---|---|---|
| 0.02 | -0.03 [-0.50, +0.25] | +0.03 [-0.25, +0.50] | +0.0002 [-0.0019, +0.0024] | -0.5 [-6.3, +4.9] | 57/200 |
| 0.005 | -0.03 [-0.75, +0.51] | +0.01 [-0.25, +0.26] | +0.0001 [-0.0010, +0.0014] | -0.1 [-4.5, +4.7] | 73/200 |

Per-resample context time: mean 70 s, sims 17032; unique cal traces 273/300; Prior traces 1616; groups drawn 79.4/125.
Resample Priors with any (kind, layer, 10-UE D-bucket) below 30 samples → global σ̂ fallback: 0/200.

**Reading.**
* **Bands barely move.** 2 %: λ_VM [1.50, 2.00] unchanged; λ_UP upper bound 2.25 → 2.50; held-out risk [0.0134, 0.0240] → [0.0136, 0.0251]; P(ho > ε) 0.33 → 0.40.
  0.5 %: λ_VM [2.00, 3.00] and λ_UP [2.99, 3.50] unchanged; held-out risk [0.0026, 0.0082] → [0.0029, 0.0082]; P(ho > ε) 0.49 → 0.50.
  Cost bands are unchanged within ±1 core-min.
* σ̂ itself varies little across resamples (σ̂_win at D = 20: VY 3.56–3.83, UP 2.54–2.75, 2.5–97.5 %). Re-estimating it changes the selected λ in 57/200 (2 %) and 73/200 (0.5 %)
  resamples, but the paired held-out risk shift is centred on zero at both targets.
* Per §4.107 A the **new (σ̂ re-estimated) intervals replace the old ones**: 2 % λ_VM 1.78 [1.50, 2.00], λ_UP 2.07 [2.00, 2.50], ho risk 0.0192 [0.0136, 0.0251];
  0.5 % λ_VM 2.56 [2.00, 3.00], λ_UP 3.14 [2.99, 3.50], ho risk 0.0052 [0.0029, 0.0082].
* Runtime: 5-resample probe 175 s on 2 workers → projection 7000 s (1.9 h) < 5 h, so **all 200 resamples were run** at the full grid; actual 175 + 6874 s.

# Round 62 (superseded for B1; σ̂ fixed on the whole library)

# Uncertainty of the calibration: bootstrap, library size, events

## Task B: uncertainty

(loc,date) groups in library: 125

### B1 cluster bootstrap (200 resamples of the 125 groups with replacement, numpy default_rng(20261021).integers; calibration = first 300 resampled traces in draw order (primary, = the cal[:300] convention) or all resampled traces (secondary); held-out = groups never drawn)

| target | calibration | λ_VM mean [2.5, 97.5] | λ_UP mean [2.5, 97.5] | ho risk mean [2.5, 97.5] | P(ho risk > ε) | ho alloc vmexist mean [2.5, 97.5] | ho n (mean) | infeasible |
|---|---|---|---|---|---|---|---|---|
| 0.02 | 300 (primary) | 1.81 [1.50, 2.00] | 2.04 [2.00, 2.25] | 0.0190 [0.0134, 0.0240] | 0.33 | 1281.6 [1265.7, 1298.9] | 590 | 0 |
| 0.02 | all resampled | 1.87 [1.75, 2.00] | 2.00 [2.00, 2.00] | 0.0188 [0.0151, 0.0224] | 0.38 | 1281.6 [1265.0, 1298.2] | 590 | 0 |
| 0.005 | 300 (primary) | 2.59 [2.00, 3.00] | 3.12 [2.99, 3.50] | 0.0051 [0.0026, 0.0082] | 0.49 | 1335.8 [1316.9, 1352.7] | 590 | 0 |
| 0.005 | all resampled | 2.75 [2.50, 3.00] | 3.09 [3.00, 3.25] | 0.0048 [0.0029, 0.0069] | 0.45 | 1337.3 [1322.7, 1350.6] | 590 | 0 |

### B2 library size (calibration group budget)

125 = the standard six splits (grouped_split seeds 0-5: 75 calibration groups, 50 held-out groups). 60 / 30 = six random group subsets (seed s: sorted keys, random.Random(s).shuffle, first 60 / 30 groups), held-out = all groups not in the subset. 'cap 300' = calibration traces truncated to the first 300 (the frozen convention; with ≈13 traces per group this binds for 125 and 60 and nearly for 30), 'uncapped' = all traces of the calibration groups.

| target | groups | cap | cal n (mean) | λ_VM mean ± std | λ_UP mean ± std | ho risk mean ± std | ho alloc vmexist mean ± std |
|---|---|---|---|---|---|---|---|
| 0.02 | 125 | 300 | 300 | 1.83 ± 0.12 | 2.00 ± 0.00 | 0.0194 ± 0.0017 | 1282.5 ± 5.9 |
| 0.02 | 125 | uncapped | 979 | 1.83 ± 0.12 | 2.00 ± 0.00 | 0.0195 ± 0.0018 | 1282.5 ± 7.1 |
| 0.02 | 60 | 300 | 300 | 1.83 ± 0.12 | 2.00 ± 0.00 | 0.0193 ± 0.0016 | 1283.3 ± 5.3 |
| 0.02 | 60 | uncapped | 782 | 1.83 ± 0.12 | 2.00 ± 0.00 | 0.0194 ± 0.0018 | 1283.3 ± 6.2 |
| 0.02 | 30 | 300 | 300 | 1.83 ± 0.12 | 2.00 ± 0.00 | 0.0193 ± 0.0013 | 1280.4 ± 3.4 |
| 0.02 | 30 | uncapped | 390 | 1.79 ± 0.09 | 2.00 ± 0.00 | 0.0197 ± 0.0012 | 1279.2 ± 4.1 |
| 0.005 | 125 | 300 | 300 | 2.67 ± 0.31 | 3.12 ± 0.12 | 0.0051 ± 0.0007 | 1338.6 ± 5.8 |
| 0.005 | 125 | uncapped | 979 | 2.88 ± 0.19 | 3.04 ± 0.09 | 0.0050 ± 0.0005 | 1338.6 ± 4.7 |
| 0.005 | 60 | 300 | 300 | 2.67 ± 0.31 | 3.12 ± 0.12 | 0.0049 ± 0.0007 | 1339.2 ± 5.0 |
| 0.005 | 60 | uncapped | 782 | 2.71 ± 0.22 | 3.12 ± 0.12 | 0.0046 ± 0.0007 | 1340.2 ± 3.3 |
| 0.005 | 30 | 300 | 300 | 2.67 ± 0.31 | 3.12 ± 0.12 | 0.0050 ± 0.0006 | 1337.3 ± 2.6 |
| 0.005 | 30 | uncapped | 390 | 2.75 ± 0.29 | 3.08 ± 0.12 | 0.0050 ± 0.0004 | 1336.9 ± 3.2 |

### B3 event rate (consecutive violating minutes collapsed into one event)

Deployed points simulated fresh on all 1615 traces (dual-accounting copy of frozen nest2; 1.83 and 2.83 are off the 0.25 grid). v6 = frozen `v8sim2.sim_v6` does **not** expose per-minute violations (returns slo, alloc, acts, flaps only), so it was run through `dual.sim_v6_pm`, a copy generated from the frozen source whose only change is to also return the per-minute loss vector pct; slo/alloc/acts/flaps verified identical on 60 random traces (verify_dual.py) and violating minutes = 60 − slo checked on all 1615 traces. Grid points 1.75/2.00 and 2.75/3.00 from the matrix shown for reference.

| controller | λ | minute rate | events / 60-min trace | events / minute | mean event length (min) | max length | traces with ≥ 1 event | mean alloc vmexist |
|---|---|---|---|---|---|---|---|---|
| S4b (deployed) | 1.83/2.00 | 1.886 % | 0.949 | 0.01582 | 1.19 | 5 | 61.9 % | 1281.3 |
| S4a (deployed) | 2.83/3.08 | 0.467 % | 0.246 | 0.00410 | 1.14 | 4 | 20.4 % | 1338.2 |
| v6 | fixed constants | 2.388 % | 0.975 | 0.01624 | 1.47 | 6 | 65.6 % | - |
| grid ref (≈S4b) | 1.75/2.0 | 1.992 % | 0.980 | 0.01633 | 1.22 | 5 | 63.3 % | 1278.3 |
| grid ref (≈S4a) | 2.75/3.0 | 0.531 % | 0.275 | 0.00458 | 1.16 | 4 | 22.8 % | 1333.3 |


**Verdict B1, bootstrap.**
- At 2 %, λ_VM [1.50, 2.00], λ_UP [2.00, 2.25] and held-out risk [1.34 %, 2.40 %]. The deployed λ 1.83/2.00 is inside the λ band, and in 33 % of resamples held-out risk exceeds 2 %.
- At 0.5 %, λ_VM [2.00, 3.00], λ_UP [2.99, 3.50] and held-out risk [0.26 %, 0.82 %]. In 49 % of resamples held-out risk exceeds ε. The calibration targets the mean, not a bound, so about half above ε is the expected behaviour.
- Calibrating on all resampled traces instead of 300 narrows the λ bands (2 %: λ_VM [1.75, 2.00]; 0.5 %: [2.50, 3.00]) and the risk band (2 %: [1.51 %, 2.24 %]; 0.5 %: [0.29 %, 0.69 %]).
- Cost bands are ±1.3 % (2 %) and ±1.4 % (0.5 %).

**Verdict B2, library size.**
- **The capped rows are degenerate, and this is a design artefact.** The 60/30 subsets use the same seeded shuffle of the sorted group keys as grouped_split, so the first 300 traces are identical for 125, 60 and 30 groups (about 23 groups). Hence the identical λ in the cap-300 rows; only the held-out set differs.
- **The uncapped rows are the real size test.** 979 traces from 75 groups, 782 from 60, 390 from 30.
  - 2 %: λ moves by at most 0.04 (1.83 → 1.79 for λ_VM; λ_UP fixed at 2.00), and held-out risk stays 1.94–1.97 % with std 0.12–0.18 pp.
  - 0.5 %: λ_VM is 2.88 → 2.71 → 2.75 and λ_UP 3.04 → 3.12 → 3.08, with held-out risk 0.46–0.50 %.
- **Within 30–125 groups, library size has no detectable effect** on λ or held-out risk. The cost spread across splits is ≤ 7 core-min.

**Verdict B3, events.**
- Violations are short. The mean event length is 1.19 min for S4b, 1.14 for S4a and 1.47 for v6, and no event exceeds 5, 4 and 6 min respectively.
- The event rate per minute is therefore about 0.84× the minute rate for S4b (1.58 % against 1.89 %), 0.88× for S4a (0.41 % against 0.47 %) and 0.68× for v6 (1.62 % against 2.39 %).
- Per 60-minute trace that is 0.95 events (S4b), 0.25 (S4a) and 0.98 (v6). The share of traces with at least one event is 61.9 %, 20.4 % and 65.6 %.
- **v6 has 27 % more violating minutes than S4b but only 3 % more events.** Its excess is longer events, not more frequent ones.
- **How v6 was measured.** Frozen `v8sim2.sim_v6` returns only slo, alloc, acts and flaps, so per-minute violations cannot be derived from its outputs. `dual.sim_v6_pm` is generated from the frozen source with one change, which also returns pct. It was verified identical to frozen sim_v6 on 60 traces, and 60 − slo equals its violating-minute count on all 1615 traces.

## Limitations

- **σ̂ is fixed.** `v8sim2.Prior` (σ̂) is fitted once on the full 1615-trace library, held-out traces included. It is not re-estimated inside the bootstrap resamples, the library-size subsets or the rise1 buckets. B1/B2 therefore capture calibration-set sampling of λ only, not the uncertainty of σ̂ itself. The bands are lower bounds on the true uncertainty, and held-out risk benefits from σ̂ having seen the held-out traces.
- The bucket calibration uses 74–203 calibration traces per bucket, against 300 for the full library. With six splits, SE is 0.03–0.23 pp, so ε ± SE is a narrow test: conservative buckets count as "not valid".
- B1 uses 300 calibration traces from about 23 groups, the frozen convention. The "all resampled" variant is reported alongside.
- Test-trace decile-λ predictions are simulation only. Hardware has never run decile λ.


## Text of Results §8 before R65 (moved from the Results chapter, 2026-10-21)

<!-- 2026-10-21 R65 (spec §4.110): Results §8 (sensitivity of the calibration) was cut by half for the page budget; the paragraph below is the r64a text of the paper, verbatim with its source comments; the paper keeps one conclusion sentence with its key number. -->

Uncertainty. Resampling the 125 (location, date) groups 200 times, re-estimating $\hat{\sigma}$ from the drawn groups, calibrating on each resample and evaluating on the groups not drawn gives at 2 % a held-out risk of 0.0192 [0.0136, 0.0251] (mean and 95 % interval), $\lambda_{\mathrm{VM}}$ 1.78 [1.50, 2.00], $\lambda_{\mathrm{UP}}$ 2.07 [2.00, 2.50] and cost 1281.1 [1264.6, 1299.1] core-min; held-out risk exceeds ε in 40 % of resamples. At 0.5 % the held-out risk is 0.0052 [0.0029, 0.0082], $\lambda_{\mathrm{VM}}$ 2.56 [2.00, 3.00], $\lambda_{\mathrm{UP}}$ 3.14 [2.99, 3.50] and cost 1335.8 [1317.2, 1351.7], with 50 % of resamples above ε. <!-- r62ab/REPORT.md B1 table (primary rows) and verdict; §4.105 B1 --> <!-- 2026-10-21 (spec §4.107 A, §4.108): replaced by the nested bootstrap of qsim/r63a/REPORT.md Task 2 (σ̂ re-estimated per resample, same draws as r62ab, seed 20261021). Previous (σ̂ fixed on the whole library): 2 % λ_VM [1.50, 2.00], λ_UP [2.00, 2.25], risk [1.34 %, 2.40 %], cost [1265.7, 1298.9], 33 %; 0.5 % [2.00, 3.00], [2.99, 3.50], [0.26 %, 0.82 %], [1316.9, 1352.7], 49 % --> The deployed λ lies inside the bands; the calibration targets the mean, not a bound. <!-- r62ab/REPORT.md Verdict B1 --> Paired with the same draws under a $\hat{\sigma}$ fixed on the whole library, the held-out risk shifts by +0.0002 [−0.0019, +0.0024] at 2 % and +0.0001 [−0.0010, +0.0014] at 0.5 %: re-estimating $\hat{\sigma}$ changes the selected λ in 57 and 73 of 200 resamples but shows no systematic shift. <!-- r63a/REPORT.md Task 2 paired differences table and reading --> <!-- 2026-10-21: sentence 'Calibrating on all resampled traces instead of the first 300 narrows the risk bands to [1.51 %, 2.24 %] and [0.29 %, 0.69 %]' removed: computed with σ̂ fixed (r62ab B1 'all resampled' rows), not recomputed in round 63; kept in artifacts/calibration-uncertainty.md --> <!-- r62ab/REPORT.md B1 "all resampled" rows --> With uncapped calibration sets, a group budget of 125 (the standard splits, 979 calibration traces), 60 (782) and 30 groups (390) gives $\lambda_{\mathrm{VM}}$ 1.83, 1.83, 1.79 and held-out risk 1.95, 1.94, 1.97 % at 2 %, and $\lambda_{\mathrm{VM}}$ 2.88, 2.71, 2.75 and 0.50, 0.46, 0.50 % at 0.5 %: library size from 125 to 30 groups has no detectable effect; below 30 groups it was not tested. <!-- r62ab/REPORT.md B2 uncapped rows and Verdict B2; the capped rows are degenerate by design (same seeded shuffle) and not used; §4.105 A+B 補充; §4.106 item 6 --> The library-size subsets use the whole-library $\hat{\sigma}$. <!-- r62ab/REPORT.md Limitations; §4.104 共用計算 限制 --> <!-- 2026-10-21 (spec §4.107 A item 1 of the task): deleted the sentence 'σ̂ is fitted once on the whole library, held-out traces included, and is not re-estimated inside the resamples, the size subsets or the rise1 buckets; the bootstrap intervals capture the sampling of λ only and are lower bounds on the true uncertainty because σ̂ is not refitted': σ̂ is now refitted in the resamples and the buckets (r63a Tasks 2 and 3); the B2 size subsets were not recomputed --> Collapsing consecutive violating minutes into one event, S4b has 0.95 events per 60-minute trace, of mean length 1.19 minutes (longest 5), so its event rate of 1.58 % per minute is close to its minute rate; S4a has 0.25 events of 1.14 minutes (0.41 % against its minute rate) and v6 0.98 events of 1.47 minutes (1.62 %). Violations are mostly isolated minutes; v6 has 27 % more violating minutes than S4b but only 3 % more events. <!-- r62ab/REPORT.md B3 table and Verdict B3; §4.105 B3; minute rates 1.886 %, 0.467 %, 2.388 % stated once, in Section 7 -->
