# §4.107 Task A (round 63): σ̂ leakage correction and nested uncertainty — 2026-10-21

Simulation only, idle host (no hardware run; deployed λ, daemon and harness untouched). All python ran as `nice -n 19 taskset -c 13,14 python3`
with at most 2 worker processes. Frozen files unmodified: md5 of v8sim10.py, v8sim2.py, v8sim3.py, v8sim7.py, v8sim11.py, v8sim10_cal.py and
prior_traces.json recorded before (`frozen_md5_before.txt`) and `md5sum -c` all OK after. Results go to §4.108.

## 0. Method and verification

* **Engine.** `r62de/eng.sim2` (imported, not copied): bit-identical to frozen `v8sim10.sim_nest2` (default flags), dispatch and vmexist in one pass.
  Re-checked here with a *non-full* Prior (split-0 calibration groups): 12/12 (3 λ sets × 4 traces) identical to frozen sim_nest2 on slo, alloc dispatch, alloc vmexist.
* **No lookup matrix.** σ̂ now differs per context, so the r62ab matrix (full-library σ̂) cannot be reused. Each *context* (`core.run_context`) =
  one `v8sim2.Prior(traces, cfg_measured())` + calibration of both targets + held-out evaluation, all with that Prior; simulations are cached per (trace, λ) inside the context.
* **Calibration** = frozen `v8sim10_cal.py` / r62ab `look.py`: coarse GRID_VM {1.0..3.5 step 0.5} × GRID_UP {1.5..4.5 step 0.5} in itertools.product order;
  feasible = mean cal risk ≤ target; cheapest mean cal **dispatch** alloc (python `min`, first in insertion order on ties); ±0.25 refinement (new points only,
  appended in product order), re-select over the whole table. Coarse grid infeasible → min-risk coarse point (look.py rule; never happened here).
  Held-out: mean risk, vmexist alloc (dispatch in brackets) over all held-out traces.
* **Control.** Context with the *full-library* Prior on grouped_split seed 0 reproduces r62ab split 0 exactly (2 %: λ 1.75/2.0, ho 0.0190, vmexist 1288.5;
  0.5 %: 3.0/3.0, 0.0050, 1346.9) → `out/verify.json`, MATCH.
* **Prior inputs (leakage-free).**
  - Task 1: Prior from **all** traces of the 75 calibration groups of `grouped_split(seed)` (970–986 traces); cal = first 300 of those; held-out = the other 50 groups (629–645 traces).
  - Task 2: draws `numpy.random.default_rng(20261021).integers(0,125,size=125)` per resample, generated in the same order as r62ab (so draw b here = draw b there);
    Prior from all resampled traces with duplicates (mean 1616 traces, 79.4 distinct groups); cal = first 300 resampled traces in draw order (mean 273 unique);
    held-out = groups never drawn (mean 590 traces). Means count duplicates, as r62ab.
  - Task 3: rise1 buckets exactly as r62ab (thresholds [7,7,8,9,9,10,11,12,14], D2→D3 and D5→D6 merged, 8 buckets); per bucket, seed s: sorted bucket group keys,
    `random.Random(s).shuffle`, first int(0.6·G) groups = calibration; Prior from the **bucket's** traces of those groups only (bucket-internal σ̂); cal = same traces capped at 300 (cap never binds, max 203);
    held-out = the bucket's remaining groups, evaluated with that Prior.
* **σ̂ fallback check** (`core.prior_diag`): for every Prior, every (kind ∈ {win, run}, layer, 10-UE D-bucket) below the Prior's top bucket was checked for < 30 samples.
  **No Prior in any task had such a bucket** (6/6 split Priors, 0/200 bootstrap Priors, 0/48 bucket Priors fall back); the smallest bucket Prior is D10 with 73–75 traces.

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

## Commands and runtimes

| step | command (cwd /home/user/experiment/qsim/r63a) | wall time |
|---|---|---|
| control + equivalence | `nice -n 19 taskset -c 13,14 python3 run.py verify` (1 process) | 81 s + ~1 s |
| task 1 | `run.py split` (6 contexts, 2 workers) | 245 s |
| task 2 probe | `run.py boot 5` | 175 s → projection 7000 s for 200 |
| task 2 | `run.py boot 200` (resumes, 195 new) | 6874 s (1.9 h) |
| task 3 | `run.py bucket` (48 contexts) | 700 s |
| tables | `analyze.py` (no simulation) | < 5 s |

Whole chain: `nohup ./chain.sh > chain.log` (split → boot 5 → projection rule → boot N → bucket → analyze), 16:22:08 → 18:35:23 (2 h 13 min).
Per-context: split ≈ 18 670 sims, 62–97 s; bootstrap mean 17 032 sims, 70 s; bucket 17–47 s.

## Files (/home/user/experiment/qsim/r63a/)
* `core.py` (context = Prior + calibration + held-out), `run.py` (driver, modes verify/split/boot/bucket), `chain.sh`, `analyze.py`
* `out/verify.json`, `out/split.jsonl`, `out/boot.jsonl` (200 rows), `out/bucket.jsonl` (48 rows): per-context λ, cal risk/alloc, held-out risk/alloc (dispatch, vmexist), σ̂ at D = 20, fallback diagnostics, timings
* `results.json`, `report_tables.md`, `progress.log`, `chain.log`, `frozen_md5_before.txt`
