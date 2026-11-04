<!-- artifact file of the paper "Predictable-Cost Autoscaling of a Three-Layer 5G User Plane with Library-Calibrated Risk" (docs/paper), written 2026-10-21 for the round-62 analyses (spec §4.104 H item 4, results §4.105). Content copied verbatim from qsim/r62ab/REPORT.md, section "Task A: conditional λ by rise1 decile" up to "Knob monotonicity"; simulation only, no hardware run. -->
<!-- 2026-10-21 (spec §4.107 A, §4.108): section "Round 63" added at the top, copied verbatim from qsim/r63a/REPORT.md "Task 3" and qsim/r63r/REPORT.md "Task 3"; the figure now reads the round-63 data. The round-62 tables below used the full-library σ̂ inside every bucket and are superseded; their reading "λ_UP rises monotonically with rise1" and "the decile λ moves the t4 S4b prediction to 3" do not hold with the bucket-internal σ̂. -->

# Round 63 (current): conditional calibration with bucket-internal σ̂

**Figure note (round 63).** In `../figs/fig_r62_decile_lambda.pdf` the dotted deployed-λ lines in the λ panels are only a reference level: the bucket λ multiplies the bucket's own σ̂, not the full-library σ̂, so the two are not on the same scale. The statement of round 62 that λ_UP rises monotonically with rise1 is a property of the full-library σ̂ and is withdrawn. <!-- r63r/REPORT.md Figures; §4.108 -->

## Task 3: conditional (rise1-bucket) calibration with bucket-internal σ̂

Old = r62ab Task A (full-library σ̂). valid = |mean ho − ε| ≤ SE, SE = std/√6 (ddof 0).

### target 0.02

| bucket | n | groups | Prior traces (mean) | cal n (mean) | ho n (mean) | λ_VM new | λ_UP new | λ old | ho risk new (mean ± std) | SE new | ho risk old (± std) | ho alloc vm new | old | valid new | valid old | infeasible / off-grid | σ̂ fallback (splits with < 30 in a D-bucket) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| D1 | 344 | 78 | 203 | 203 | 141 | 1.92 ± 0.19 | 2.00 ± 0.00 | 1.46/1.54 | 0.0179 ± 0.0024 | 0.0010 | 0.0182 ± 0.0015 | 1253.2 | 1253.7 | no | no | 0 / 0 | none |
| D2+3 | 268 | 87 | 163 | 163 | 105 | 1.79 ± 0.17 | 2.04 ± 0.09 | 1.58/1.83 | 0.0201 ± 0.0023 | 0.0009 | 0.0200 ± 0.0038 | 1256.7 | 1259.4 | yes | yes | 0 / 0 | none |
| D4 | 230 | 91 | 140 | 140 | 90 | 1.75 ± 0.00 | 2.00 ± 0.00 | 1.54/2.00 | 0.0197 ± 0.0011 | 0.0005 | 0.0180 ± 0.0018 | 1259.4 | 1267.3 | yes | no | 0 / 0 | none |
| D5+6 | 201 | 88 | 121 | 121 | 80 | 1.54 ± 0.17 | 2.25 ± 0.00 | 1.58/2.25 | 0.0222 ± 0.0062 | 0.0025 | 0.0211 ± 0.0056 | 1288.0 | 1294.1 | yes | yes | 0 / 0 | none |
| D7 | 174 | 72 | 108 | 108 | 66 | 1.92 ± 0.19 | 2.04 ± 0.09 | 1.79/2.25 | 0.0211 ± 0.0009 | 0.0004 | 0.0192 ± 0.0037 | 1308.0 | 1310.2 | no | yes | 0 / 0 | none |
| D8 | 143 | 72 | 87 | 87 | 56 | 1.83 ± 0.12 | 2.33 ± 0.19 | 1.92/2.83 | 0.0195 ± 0.0043 | 0.0018 | 0.0200 ± 0.0048 | 1327.3 | 1328.0 | yes | yes | 0 / 0 | none |
| D9 | 134 | 60 | 80 | 80 | 54 | 1.75 ± 0.14 | 2.25 ± 0.14 | 2.04/2.75 | 0.0189 ± 0.0040 | 0.0017 | 0.0209 ± 0.0034 | 1336.2 | 1340.4 | yes | yes | 0 / 0 | none |
| D10 | 121 | 45 | 74 | 74 | 47 | 2.00 ± 0.25 | 2.50 ± 0.14 | 2.42/3.29 | 0.0157 ± 0.0019 | 0.0008 | 0.0163 ± 0.0033 | 1314.7 | 1306.5 | no | no | 0 / 0 | none |

**Valid (ε ± SE), target 0.02: new 5/8 (old 5/8); not exceeding ε + SE: new 7/8 (old 8/8).**

### target 0.005

| bucket | n | groups | Prior traces (mean) | cal n (mean) | ho n (mean) | λ_VM new | λ_UP new | λ old | ho risk new (mean ± std) | SE new | ho risk old (± std) | ho alloc vm new | old | valid new | valid old | infeasible / off-grid | σ̂ fallback (splits with < 30 in a D-bucket) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| D1 | 344 | 78 | 203 | 203 | 141 | 2.67 ± 0.12 | 3.00 ± 0.00 | 2.08/2.25 | 0.0039 ± 0.0009 | 0.0004 | 0.0036 ± 0.0009 | 1299.3 | 1297.8 | no | no | 0 / 0 | none |
| D2+3 | 268 | 87 | 163 | 163 | 105 | 2.46 ± 0.27 | 3.00 ± 0.00 | 2.29/2.58 | 0.0051 ± 0.0010 | 0.0004 | 0.0051 ± 0.0007 | 1301.7 | 1304.4 | yes | yes | 0 / 0 | none |
| D4 | 230 | 91 | 140 | 140 | 90 | 2.71 ± 0.09 | 2.88 ± 0.12 | 2.29/2.79 | 0.0049 ± 0.0012 | 0.0005 | 0.0045 ± 0.0011 | 1311.1 | 1313.0 | yes | no | 0 / 0 | none |
| D5+6 | 201 | 88 | 121 | 121 | 80 | 2.54 ± 0.37 | 3.12 ± 0.24 | 2.67/2.88 | 0.0069 ± 0.0029 | 0.0012 | 0.0063 ± 0.0029 | 1338.7 | 1339.4 | no | no | 0 / 0 | none |
| D7 | 174 | 72 | 108 | 108 | 66 | 2.17 ± 0.19 | 3.04 ± 0.09 | 2.25/3.21 | 0.0041 ± 0.0014 | 0.0006 | 0.0044 ± 0.0017 | 1348.2 | 1350.5 | no | yes | 0 / 0 | none |
| D8 | 143 | 72 | 87 | 87 | 56 | 2.75 ± 0.35 | 3.00 ± 0.00 | 2.96/3.50 | 0.0051 ± 0.0037 | 0.0015 | 0.0055 ± 0.0035 | 1369.7 | 1365.3 | yes | yes | 0 / 0 | none |
| D9 | 134 | 60 | 80 | 80 | 54 | 2.38 ± 0.12 | 3.00 ± 0.00 | 2.71/3.62 | 0.0038 ± 0.0011 | 0.0005 | 0.0042 ± 0.0022 | 1375.8 | 1376.9 | no | yes | 0 / 0 | none |
| D10 | 121 | 45 | 74 | 74 | 47 | 2.50 ± 0.00 | 3.83 ± 0.28 | 3.46/4.50 | 0.0049 ± 0.0026 | 0.0011 | 0.0065 ± 0.0019 | 1369.3 | 1356.9 | yes | no | 0 / 0 | none |

**Valid (ε ± SE), target 0.005: new 4/8 (old 4/8); not exceeding ε + SE: new 7/8 (old 6/8).**


**Reading.**
* **Valid counts are unchanged in total:** 2 % 5/8 (old 5/8), 0.5 % 4/8 (old 4/8). Which buckets pass changes:
  - 2 %: D4 becomes valid (0.0197 vs old 0.0180); D7 becomes invalid on the high side (0.0211 ± 0.0009, SE 0.0004, 2.8 SE above ε; the only bucket over ε + SE). D1 and D10 stay conservative-invalid.
  - 0.5 %: D4 and D10 become valid; D7 and D9 become conservative-invalid (0.0041, 0.0038). D5+6 still fails high (0.0069 ± 0.0029 > ε + SE 0.0062). D1 stays conservative.
  - Not exceeding ε + SE: 2 % 7/8 (old 8/8), 0.5 % 7/8 (old 6/8).
* **D10 at 0.5 % is no longer infeasible** (old: 5/6 splits infeasible on the coarse grid). With bucket-internal σ̂ every bucket reaches both targets on every split.
* **λ is much flatter across buckets.** With the full-library σ̂, λ_UP rose 1.54 → 3.29 (2 %) and 2.25 → 4.50 (0.5 %) from D1 to D10. With bucket-internal σ̂ it is 2.00 → 2.50 (2 %)
  and 3.00 → 3.83 (0.5 %, only D10 above 3.12). The reason is that the bucket σ̂ already scales with rise1: σ̂_win,UP at D = 20 runs 1.84 (D1), 2.14, 2.31, 2.50, 2.83, 3.07, 3.32, 3.72 (D10),
  against 2.64 for the full library. The margin λ·σ̂ is roughly preserved (2 % UP at D = 20: D1 old 1.54 × 2.64 = 4.1 vs new 2.00 × 1.84 = 3.7; D10 old 3.29 × 2.64 = 8.7 vs new 2.50 × 3.72 = 9.3).
  So "λ_UP rises monotonically with rise1" (r62ab verdict) is a property of the full-library σ̂, not of the conditional calibration itself.
* Held-out cost per bucket moves by −8 to +12 core-min (largest: D10 +8.2 at 2 %, +12.4 at 0.5 %; D4 −7.9 at 2 %).
* σ̂ fallback: no bucket/split Prior had a 10-UE D-bucket with < 30 rises, so the "global σ̂ of the bucket's calibration groups" fallback was never used.


## Test traces under the leakage-free bucket λ


**Bucket λ** = the mean of the bucket's six split λ in r63a `out/bucket.jsonl` (bucket-internal σ̂), rounded to 0.01. Test-trace buckets by rise1 are the same as in r62ab: t3 12 → D8, t4 9 → D4, t6/t7 7 → D1.

**Priors.**
- **Primary: `v8sim2.Prior(all library traces of the bucket, cfg_measured)`.** The bucket sizes are D8 143, D4 230 and D1 344 traces. The test traces are not in the library, so for deployment every group of the bucket is a calibration group; this is the bucket analogue of the full-library Prior the deployed system carries.
- **Sensitivity: each of the bucket's six split calibration-group Priors**, the Priors the six λ were calibrated with, reported as mean [min–max].
- **Simulators.** nest2 = frozen `v8sim10.sim_nest2(ue,cfg,pr,L,acct='vmexist')`. v8sim11 = `import v8sim11 as V; V.cfg_prior(); V.run(ue,'S',L=L)`, with stdlib `timeit` pre-imported.
  - Primary v8sim11 column: `V._PRIOR` is replaced by the same bucket Prior. v8sim11 reads the Prior only through `cfg_prior()`, for CtlSigma and initial_fleet.
  - An extra column shows the literal call, which keeps V's own full-library Prior. That pairs a bucket-σ̂ λ with the full-library σ̂, so it is not like-for-like.
- **Unchanged columns.** "Full λ" columns and hardware are unchanged from r62ab.
- **Recheck.** The old bucket-λ nest2 column was re-simulated with the old λ and the full-library Prior and reproduces r62ab in 8/8 rows.

Units: violating minutes per run, with alloc vmexist core-min in parentheses. Old = r62ab/REPORT.md "Test traces under decile λ" (full-library σ̂ λ, full-library Prior).

| trace | rise1 | bucket | arm | bucket λ old → new | full λ: nest2 | full λ: v8sim11 | bucket λ: nest2 old → new | bucket λ: v8sim11 old → new | v8sim11 new λ, full-library Prior | six split Priors: nest2 / v8sim11 (mean [min–max]) | hardware |
|---|---|---|---|---|---|---|---|---|---|---|---|
| t3 | 12 | D8 | S4a | 2.96/3.5 → **2.75/3.0** | 3 (1257) | 3 (1254) | 2 (1273) → **3 (1269)** | 2 (1273) → **3 (1267)** | 3 (1234) | 2.17 [2–3] / 2.17 [2–3] | 7/3 |
| t3 | 12 | D8 | S4b | 1.92/2.83 → **1.83/2.33** | 3 (1129) | 5 (1138) | 3 (1220) → **3 (1212)** | 3 (1218) → **3 (1210)** | 5 (1163) | 3.00 [3–3] / 3.00 [3–3] | 14/3 |
| t4 | 9 | D4 | S4a | 2.29/2.79 → **2.71/2.88** | 0 (1454) | 2 (1452) | 1 (1438) → **1 (1438)** | 2 (1435) → **2 (1436)** | 2 (1446) | 1.00 [1–1] / 2.00 [2–2] | 3/3 |
| t4 | 9 | D4 | S4b | 1.54/2.0 → **1.75/2.0** | 1 (1427) | 4 (1425) | 3 (1397) → **1 (1423)** | 4 (1395) → **4 (1420)** | 4 (1420) | 1.00 [1–1] / 4.00 [4–4] | 10/3 |
| t6 | 7 | D1 | S4a | 2.08/2.25 → **2.67/3.0** | 0 (1449) | 3 (1448) | 0 (1406) → **0 (1406)** | 5 (1405) → **5 (1405)** | 3 (1435) | 0.00 [0–0] / 5.00 [5–5] | 0/3 |
| t6 | 7 | D1 | S4b | 1.46/1.54 → **1.92/2.0** | 0 (1393) | 5 (1397) | 1 (1347) → **0 (1369)** | 5 (1361) → **5 (1383)** | 5 (1397) | 0.00 [0–0] / 5.00 [5–5] | 0/3 |
| t7 | 7 | D1 | S4a | 2.08/2.25 → **2.67/3.0** | 0 (1430) | 0 (1432) | 0 (1399) → **0 (1399)** | 0 (1402) → **0 (1402)** | 0 (1430) | 0.00 [0–0] / 0.00 [0–0] | 1/3 |
| t7 | 7 | D1 | S4b | 1.46/1.54 → **1.92/2.0** | 0 (1395) | 0 (1396) | 0 (1368) → **0 (1388)** | 2 (1372) → **2 (1392)** | 0 (1396) | 0.00 [0–0] / 2.00 [2–2] | 0/3 |

**Reading.**
- **The bucket λ changed a lot, but in the opposite direction for low- and high-rise buckets.** The new λ is calibrated against the bucket's own σ̂.
  - D1 (t6/t7): S4a rises 2.08/2.25 → 2.67/3.00 and S4b 1.46/1.54 → 1.92/2.00. The D1 σ̂ is smaller (σ̂_win,UP at D = 20 is 1.84 vs 2.64 for the full library), so a larger λ is needed for the same risk.
  - D8 (t3): λ falls (S4a 2.96/3.50 → 2.75/3.00; S4b 1.92/2.83 → 1.83/2.33).
  - D4 (t4): λ rises (S4a 2.29/2.79 → 2.71/2.88; S4b 1.54/2.00 → 1.75/2.00).
- **Violating minutes barely move. 4 rows are unchanged in both simulators, and 4 change by 1–2 minutes in nest2 only.**
  - t3 S4a: nest2 2 → 3 and v8sim11 2 → 3. With the six split Priors it is 2 in five of six, mean 2.17.
  - t4 S4b: nest2 3 → 1; v8sim11 stays at 4. Hardware is 10/3.
  - t6 S4b: nest2 1 → 0.
  - t6/t7: v8sim11 is unchanged at 5/5/0/2.
- **Cost (alloc vmexist).** The old finding was that the low-rise saving on t6/t7 was 27–46 core-min/run against the full-λ nest2. That saving is unchanged for S4a (43 / 31 on t6 / t7) and shrinks to 24 / 7 for S4b (old 46 / 27).
  - t6 S4a: 1406 vs 1449 full λ (unchanged from old, because the margins happen to round to the same need).
  - t6 S4b: 1369 vs 1393 (old 1347).
  - t7 S4b: 1388 vs 1395 (old 1368).
  - t3: cost falls 4–8 (S4a 1273 → 1269, S4b 1220 → 1212). t4 S4b cost rises 26 (1397 → 1423).
- **Unchanged conclusion.** The decile λ does not close the hardware gap on t3 (14/3, 7/3) or t4 (10/3). On t6/t7, nest2 predicts 0 minutes and v8sim11 still predicts 5 (t6) and 2 (t7 S4b).
- **Sensitivity to the Prior.** The split Priors agree with the all-bucket Prior in every row except t3 S4a.
- **Literal v8sim11 call (full-library Prior).** It differs from the primary column in t3 S4b (5 vs 3) and t7 S4b (0 vs 2), and in cost. The literal call under-provisions D8 (1163 vs 1210) and over-provisions D1 (1435 vs 1405), because the λ is applied to the wrong σ̂.


# Round 62 (superseded; σ̂ from the whole library)

# Conditional calibration by rise1 bucket

Figure `../figs/fig_r62_decile_lambda.pdf` (script `fig_r62_decile_lambda.py`, not included: not a paper figure) plots the per-bucket held-out risk and λ of the tables below.

## Task A: conditional λ by rise1 decile

rise1 is the maximum one-minute rise of ue[:60]. The decile thresholds use numpy.percentile (linear) at 10..90 % over the library, and each trace goes to the first decile whose threshold is ≥ its rise1. The data has heavy integer ties: P10 = P20 = 7 and P40 = P50 = 9, so D2 and D5 are empty. **D2 is merged into D3 and D5 into D6**, which leaves 8 buckets, and the valid counts below are out of 8, not 10.

rise1 thresholds P10..P90 (numpy linear): [7.0, 7.0, 8.0, 9.0, 9.0, 10.0, 11.0, 12.0, 14.0]

| decile | rise1 range | n |
|---|---|---|
| D1 | 4-7 | 344 |
| D2 | - | 0 |
| D3 | 8-8 | 268 |
| D4 | 9-9 | 230 |
| D5 | - | 0 |
| D6 | 10-10 | 201 |
| D7 | 11-11 | 174 |
| D8 | 12-12 | 143 |
| D9 | 13-14 | 134 |
| D10 | 15-22 | 121 |

Merged buckets (empty decile joined to the next non-empty one): D1, D2+3, D4, D5+6, D7, D8, D9, D10

Test-trace rise1 and bucket: t3 12 → D8, t4 9 → D4, t5 6 → D1, t6 7 → D1, t7 7 → D1

Per bucket, six grouped 60/40 splits over the bucket's (loc,date) groups (seed s: sorted keys, random.Random(s).shuffle, first int(0.6·G) groups = calibration, capped at 300 traces), calibrated by lookup; held-out = the bucket's remaining groups. ε ± SE rule: valid if |mean ho risk − ε| ≤ SE, SE = std/√6 (std ddof=0, as in the frozen reports). 'Not exceeding' = mean ho ≤ ε + SE. Full-λ risk = bucket mean risk under the deployed full-library λ (fresh sim, whole bucket).

### target 2 % (S4b)

| bucket | n | groups | cal n (mean) | ho n (mean) | λ_VM | λ_UP | cal risk | ho risk (mean ± std) | SE | ho alloc vmexist | full-λ risk (bucket) | valid (ε±SE) | not exceeding | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| D1 | 344 | 78 | 203 | 141 | 1.46 ± 0.09 | 1.54 ± 0.09 | 0.0190 | 0.0182 ± 0.0015 | 0.0006 | 1253.7 | 0.0076 | no | yes |  |
| D2+3 | 268 | 87 | 163 | 105 | 1.58 ± 0.19 | 1.83 ± 0.12 | 0.0189 | 0.0200 ± 0.0038 | 0.0016 | 1259.4 | 0.0118 | yes | yes |  |
| D4 | 230 | 91 | 140 | 90 | 1.54 ± 0.09 | 2.00 ± 0.00 | 0.0186 | 0.0180 ± 0.0018 | 0.0008 | 1267.3 | 0.0150 | no | yes |  |
| D5+6 | 201 | 88 | 121 | 80 | 1.58 ± 0.28 | 2.25 ± 0.14 | 0.0189 | 0.0211 ± 0.0056 | 0.0023 | 1294.1 | 0.0216 | yes | yes |  |
| D7 | 174 | 72 | 108 | 66 | 1.79 ± 0.17 | 2.25 ± 0.25 | 0.0185 | 0.0192 ± 0.0037 | 0.0015 | 1310.2 | 0.0216 | yes | yes |  |
| D8 | 143 | 72 | 87 | 56 | 1.92 ± 0.34 | 2.83 ± 0.34 | 0.0186 | 0.0200 ± 0.0048 | 0.0020 | 1328.0 | 0.0286 | yes | yes |  |
| D9 | 134 | 60 | 80 | 54 | 2.04 ± 0.34 | 2.75 ± 0.29 | 0.0191 | 0.0209 ± 0.0034 | 0.0014 | 1340.4 | 0.0313 | yes | yes |  |
| D10 | 121 | 45 | 74 | 47 | 2.42 ± 0.24 | 3.29 ± 0.09 | 0.0191 | 0.0163 ± 0.0033 | 0.0014 | 1306.5 | 0.0401 | no | yes |  |

**Valid buckets (ε ± SE), target 0.02: 5/8**; not exceeding ε+SE: 8/8. (2 empty decile(s) merged; count is out of 8 non-empty buckets.)

### target 0.5 % (S4a)

| bucket | n | groups | cal n (mean) | ho n (mean) | λ_VM | λ_UP | cal risk | ho risk (mean ± std) | SE | ho alloc vmexist | full-λ risk (bucket) | valid (ε±SE) | not exceeding | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| D1 | 344 | 78 | 203 | 141 | 2.08 ± 0.12 | 2.25 ± 0.00 | 0.0046 | 0.0036 ± 0.0009 | 0.0003 | 1297.8 | 0.0006 | no | yes |  |
| D2+3 | 268 | 87 | 163 | 105 | 2.29 ± 0.22 | 2.58 ± 0.12 | 0.0046 | 0.0051 ± 0.0007 | 0.0003 | 1304.4 | 0.0016 | yes | yes |  |
| D4 | 230 | 91 | 140 | 90 | 2.29 ± 0.17 | 2.79 ± 0.09 | 0.0044 | 0.0045 ± 0.0011 | 0.0004 | 1313.0 | 0.0015 | no | yes |  |
| D5+6 | 201 | 88 | 121 | 80 | 2.67 ± 0.40 | 2.88 ± 0.19 | 0.0043 | 0.0063 ± 0.0029 | 0.0012 | 1339.4 | 0.0039 | no | no |  |
| D7 | 174 | 72 | 108 | 66 | 2.25 ± 0.20 | 3.21 ± 0.09 | 0.0047 | 0.0044 ± 0.0017 | 0.0007 | 1350.5 | 0.0042 | yes | yes |  |
| D8 | 143 | 72 | 87 | 56 | 2.96 ± 0.55 | 3.50 ± 0.14 | 0.0045 | 0.0055 ± 0.0035 | 0.0014 | 1365.3 | 0.0075 | yes | yes | 3 split(s) refined off-matrix (fresh sim) |
| D9 | 134 | 60 | 80 | 54 | 2.71 ± 0.22 | 3.62 ± 0.12 | 0.0046 | 0.0042 ± 0.0022 | 0.0009 | 1376.9 | 0.0117 | yes | yes |  |
| D10 | 121 | 45 | 74 | 47 | 3.46 ± 0.09 | 4.50 ± 0.00 | 0.0070 | 0.0065 ± 0.0019 | 0.0008 | 1356.9 | 0.0198 | no | no | 5 split(s) infeasible on coarse grid → min-risk point; 1 split(s) refined off-matrix (fresh sim) |

**Valid buckets (ε ± SE), target 0.005: 4/8**; not exceeding ε+SE: 6/8. (2 empty decile(s) merged; count is out of 8 non-empty buckets.)

**Verdict A, calibration validity.**
- **2 %: 5/8 buckets valid** under ε ± SE. The three that fail (D1, D4, D10) are all *conservative*: held-out risk 0.0182, 0.0180 and 0.0163 against ε = 0.02. All 8/8 are ≤ ε + SE.
- **0.5 %: 4/8 valid.**
  - D1 and D4 fail conservatively.
  - D5+6 fails high: 0.0063 ± 0.0029 against ε + SE = 0.0062, i.e. about 1.1 SE above ε.
  - D10 is infeasible: on 5 of 6 splits no coarse point reaches 0.5 % on the calibration set, so the minimum-risk point (λ_VM ≈ 3.5, λ_UP 4.5) is used, and its held-out risk is 0.0065.
  - Only 6/8 buckets are ≤ ε + SE.
- **The full-library λ is badly mis-calibrated conditionally.** At 2 % its bucket risk runs from 0.0076 (D1) to 0.0401 (D10), and at 0.5 % from 0.0006 to 0.0198. Conditioning on rise1 brings every bucket at 2 %, and every feasible bucket at 0.5 %, to roughly ε.
- **λ_UP rises monotonically with rise1** (2 %: 1.54 → 3.29; 0.5 %: 2.25 → 4.50). λ_VM is flatter and noisier.
- **Held-out cost tracks the risk you need.** Low-rise buckets are cheaper than under the full λ (for example D1 at 2 %: 1253.7 core-min vmexist held-out).
- **Precision is limited by bucket size.** Buckets have 45–91 groups and 74–203 calibration traces, and the six-split std of held-out risk is 2–3× the full-library value.

### Test traces under decile λ

Decile λ = mean of the bucket's six split λ (rounded to 0.01), target 0.5 % for S4a and 2 % for S4b. nest2 = frozen `v8sim10.sim_nest2(ue,cfg,pr,L,acct='vmexist')`; v8sim11 = `V.run(ue,'S',L=L)` (CtlSigma with the given λ, start=None → initial_fleet with the same λ, PHYS defaults, R38 on). Full-library λ columns: registered nest2 and v8sim11 values from m1/REPORT.md Supplement R58-2, re-simulated here (fresh value in brackets when it differs). Units: violating minutes per run (alloc vmexist in parentheses).

| trace | rise1 | bucket | arm | decile λ | full λ: nest2 | full λ: v8sim11 | decile λ: nest2 | decile λ: v8sim11 | hardware (total/runs) |
|---|---|---|---|---|---|---|---|---|---|
| t3 | 12 | D8 | S4a | 2.96/3.5 | 3 (1257) | 3 (1254) | 2 (1273) | 2 (1273) | 7/3 |
| t3 | 12 | D8 | S4b | 1.92/2.83 | 3 (1129) | 5 (1138) | 3 (1220) | 3 (1218) | 14/3 |
| t4 | 9 | D4 | S4a | 2.29/2.79 | 0 (1454) | 2 (1452) | 1 (1438) | 2 (1435) | 3/3 |
| t4 | 9 | D4 | S4b | 1.54/2.0 | 1 (1427) | 4 (1425) | 3 (1397) | 4 (1395) | 10/3 |
| t6 | 7 | D1 | S4a | 2.08/2.25 | 0 (1449) | 3 (1448) | 0 (1406) | 5 (1405) | 0/3 |
| t6 | 7 | D1 | S4b | 1.46/1.54 | 0 (1393) | 5 (1397) | 1 (1347) | 5 (1361) | 0/3 |
| t7 | 7 | D1 | S4a | 2.08/2.25 | 0 (1430) | 0 (1432) | 0 (1399) | 0 (1402) | 1/3 |
| t7 | 7 | D1 | S4b | 1.46/1.54 | 0 (1395) | 0 (1396) | 0 (1368) | 2 (1372) | 0/3 |

Reading the test-trace table:
- **Decile λ does not close the hardware gap on t3 and t4.**
  - On t3 the D8 λ raises the UP margin (S4b 1.92/2.83 against 1.83/2.00). nest2 stays at 3 minutes and v8sim11 falls from 5 to 3, while hardware is 14/3 = 4.7 per run.
  - On t4 (D4) the S4b decile λ is *lower* than the deployed λ (1.54/2.00). nest2 rises to 3 minutes and v8sim11 stays at 4, close to the hardware 3.3 per run.
- **On t6 and t7 (D1) the decile λ is much lower and saves 27–46 core-min per run (vmexist).** nest2 predicts 0–1 violating minutes.
  - v8sim11 predicts 5 on t6 (S4a and S4b) and 2 on t7 S4b, the per-slot model's sensitivity to the low-rise saving. At full λ, Supplement R58-2 attributes the t6 v8sim11 minutes to R38; the decile-λ minutes were not decomposed here.
  - Hardware with the deployed (higher) λ had 0/3, so the low-rise saving is untested on hardware.
- **Consistency check.** The full-library columns re-simulated here equal the registered nest2 and v8sim11 values in m1/REPORT.md Supplement R58-2 in all 8 rows; no bracketed fresh value appears.

### Operator use (described only, not implemented)

At each decision point the operator computes rise1 over the last 10 minutes of observed UE counts. To keep a 60-minute statistic comparable, use the same max one-minute rise; the shorter window biases it low, so either recompute the library thresholds on 10-minute windows or treat the result as a lower bound. The operator then looks up the bucket from the frozen threshold table (P10..P90 = 7, 7, 8, 9, 9, 10, 11, 12, 14 UE/min, with D2 and D5 merged). The bucket row gives two things:
- the **conditional risk of the current λ**: the "full-λ risk (bucket)" column. For example, D10 under S4b is 4.0 %, not the advertised 2 %.
- the **bucket-calibrated λ** that brings held-out risk back to about ε, with its held-out cost.

The operator can either just report the conditional risk or switch λ to the bucket value. A switch should take effect only at a quiet point; this lookup does not model a mid-run change of λ, and the D10 0.5 % row is infeasible on the grid (minimum achievable held-out risk about 0.65 %).
