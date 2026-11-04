# r63r: recomputations required by the §4.107 A rule failure (leakage-free σ̂) — 2026-10-21

The rule in §4.107 A failed at the 0.5 % target (§4.108, "A σ̂ 洩漏修正"). The rule requires every table that depends on the calibrated λ to be recomputed with the leakage-free calibration, where σ̂ comes from each split's calibration groups only. This folder does the three recomputations.
Simulation only, on an idle host (standing VPP/TRex load only; no run chain; deployed λ, daemon and harness untouched). Every python process ran as `nice -n 19 taskset -c 13,14 python3`, with at most 2 simulation workers.
Frozen and reused files were not modified: `md5sum -c frozen_md5_before.txt` reports all 19 OK. The 19 files are v8sim10/2/3/7/11, v8sim10_cal, prior_traces.json, v8sim10_abl, v8sim10_ablation, r62de/eng, r63a core/run/bucket.jsonl/split.jsonl, r62ab/results.json, abl/ablation_raw.json and ablation_table.md, and madrid/madrid_lib.json and t12_summary.json.
Writes went only to r63r/ and to docs/paper-v2/figs/: the two PDFs, plus the data-source lines of the two figure scripts. The previous PDFs and scripts are kept in `r63r/old_figs/`.

## Task 1: equal-risk ablation with split-specific σ̂ (`abl.py`, `analyze_abl.py`)

**Method.** The procedure is identical to `v8sim10_ablation.py`. That module is imported for VARIANTS, the grids, NCAL 300 and `trace_metrics`, and the simulator is `v8sim10_abl.sim_nest2(..., variant=)`. There is one change: for split s, the Prior is `v8sim2.Prior(all traces of the calibration groups of grouped_split(s), cfg_measured)` (970–986 traces, the same as r63a task 1). That Prior is used for both calibration and held-out evaluation, so held-out groups never enter σ̂.
- **Calibration** is the same as in `v8sim10_ablation.calibrate`: the coarse grid (1-D GRID_1D for (a)) on the first 300 calibration traces with acct dispatch, then the cheapest feasible point, then ±0.25 refinement and re-selection. An infeasible grid is recorded with no fallback.
- **Held-out evaluation** runs every held-out trace twice: acct vmexist for risk and metrics, and acct dispatch for the dispatch alloc.
- **Caching.** Simulations are cached per (trace, λ) inside a (variant, split) context, so the two targets share the coarse grid. This is caching only; the arithmetic is unchanged.
- **Scale and runtime.** 36 contexts (6 variants × 6 splits) on 2 workers took 5609 s (1.56 h), about 0.65 M simulations.
- **Verdict rule (unchanged).** A component contributes when, relative to (e), |Δcost| > 1 % (held-out alloc vmexist) or |Δflaps| > 2 per run. No (variant, target, split) was infeasible. No variant triggered the "not equal-risk" note (held-out risk > e + 0.25·target).

**Check, variant (e) against r63a's six-split results:** 12/12 (2 targets × 6 splits) are identical in λ, cal risk, cal alloc, held-out risk, held-out alloc vmexist and dispatch (`out/abl_table.md`, bottom). For example, 2 % gives 1.88/2.00, held-out 0.0196, 1282.1; 0.5 % gives 2.75/3.12, 0.0045, 1339.2.

Old = `abl/ablation_table.md` (full-library σ̂). New = σ̂ from the calibration groups. Values are means over 6 splits; held-out risk ± std (ddof 0).

| variant | target | λ_VM/λ_UP old → new | ho risk old → new | alloc vmexist old → new (dispatch new) | Δcost vs e old → new | flaps/run old → new | Δflaps old → new | under VY/UP new | over VY/UP new | verdict old → new |
|---|---|---|---|---|---|---|---|---|---|---|
| (e) full | 0.02 | 1.83/2.00 → 1.88/2.00 | 0.0194 → 0.0196 ± 0.0017 | 1282.5 → 1282.1 (1289.8) | +0.00% → +0.00% | 6.38 → 6.42 | +0.00 → +0.00 | 0.39/0.96 | 16.84/22.13 | baseline → baseline |
| (a) single_lambda | 0.02 | 2.00/2.00 → 2.00/2.00 | 0.0178 → 0.0188 ± 0.0015 | 1287.2 → 1284.7 (1292.3) | +0.37% → +0.20% | 6.41 → 6.40 | +0.02 → -0.01 | 0.32/0.96 | 17.93/22.13 | no contribution → no contribution |
| (b) independent | 0.02 | 1.50/2.54 → 1.50/2.54 | 0.0197 → 0.0196 ± 0.0018 | 1274.5 → 1274.9 (1281.4) | -0.63% → -0.56% | 5.30 → 5.28 | -1.08 → -1.14 | 0.70/0.71 | 13.37/26.11 | no contribution → no contribution |
| (b') independent_full | 0.02 | 1.46/2.67 → 1.46/2.67 | 0.0203 → 0.0202 ± 0.0020 | 1266.4 → 1266.9 (1275.0) | -1.25% → -1.19% | 5.04 → 5.03 | -1.35 → -1.39 | 0.74/0.71 | 13.06/26.86 | CONTRIBUTES → CONTRIBUTES |
| (c) fixed_dwell | 0.02 | 2.25/2.46 → 2.21/2.50 | 0.0199 → 0.0197 ± 0.0008 | 1300.9 → 1299.8 (1311.0) | +1.44% → +1.38% | 10.29 → 10.20 | +3.91 → +3.78 | 0.54/0.79 | 17.13/23.99 | CONTRIBUTES → CONTRIBUTES |
| (d) lock_only | 0.02 | 2.29/2.46 → 2.33/2.42 | 0.0193 → 0.0190 ± 0.0023 | 1299.2 → 1298.0 (1313.3) | +1.30% → +1.24% | 17.14 → 17.12 | +10.76 → +10.70 | 0.47/0.78 | 17.73/24.99 | CONTRIBUTES → CONTRIBUTES |
| (e) full | 0.005 | 2.67/3.12 → 2.75/3.12 | 0.0051 → 0.0045 ± 0.0007 | 1338.6 → 1339.2 (1344.4) | +0.00% → +0.00% | 5.04 → 4.94 | +0.00 → +0.00 | 0.10/0.21 | 24.01/33.48 | baseline → baseline |
| (a) single_lambda | 0.005 | 3.12/3.12 → 3.12/3.12 | 0.0041 → 0.0040 ± 0.0007 | 1344.5 → 1344.2 (1349.0) | +0.44% → +0.37% | 4.83 → 4.81 | -0.21 → -0.13 | 0.06/0.21 | 26.50/33.48 | no contribution → no contribution |
| (b) independent | 0.005 | 2.29/3.54 → 2.29/3.54 | 0.0056 → 0.0054 ± 0.0010 | 1329.3 → 1329.2 (1334.1) | -0.69% → -0.75% | 4.11 → 4.05 | -0.93 → -0.89 | 0.20/0.18 | 20.66/36.37 | no contribution → no contribution |
| (b') independent_full | 0.005 | 2.29/3.62 → 2.29/3.62 | 0.0052 → 0.0053 ± 0.0009 | 1322.5 → 1321.8 (1328.1) | -1.20% → -1.30% | 3.95 → 3.95 | -1.08 → -0.99 | 0.19/0.18 | 20.74/36.44 | CONTRIBUTES → CONTRIBUTES |
| (c) fixed_dwell | 0.005 | 3.08/3.50 → 3.29/3.46 | 0.0050 → 0.0048 ± 0.0009 | 1348.4 → 1349.0 (1357.0) | +0.74% → +0.73% | 7.53 → 7.59 | +2.49 → +2.65 | 0.13/0.19 | 24.56/34.72 | CONTRIBUTES → CONTRIBUTES |
| (d) lock_only | 0.005 | 3.08/3.58 → 3.21/3.58 | 0.0047 → 0.0047 ± 0.0007 | 1350.0 → 1350.5 (1361.3) | +0.85% → +0.84% | 12.95 → 12.97 | +7.91 → +8.03 | 0.16/0.16 | 23.61/36.33 | CONTRIBUTES → CONTRIBUTES |

**Verdicts: 0 of 10 change.** (a) single λ and (b) independent still show no contribution at both targets. (b′) independent_full, (c) fixed_dwell and (d) lock_only still contribute at both targets.
- **Distance from the 1 % / 2-flap thresholds.**
  - (b′) at 2 %: Δcost −1.19 % (old −1.25 %), the closest to its threshold.
  - (b) at 0.5 %: −0.75 % (old −0.69 %), still below 1 %.
  - (c) at 0.5 %: contributes only through flaps, +2.65 (old +2.49), with Δcost +0.73 %.
  - (d) at 2 %: Δcost +1.24 %, Δflaps +10.70.
- **Size of the changes.** All Δcost values move by ≤ 0.17 pp and all Δflaps by ≤ 0.16.
- **λ changes.** λ moved only for (e) (as in r63a), (c) (2 %: 2.21/2.50 vs 2.25/2.46; 0.5 %: 3.29/3.46 vs 3.08/3.50) and (d) (2.33/2.42 vs 2.29/2.46; 3.21/3.58 vs 3.08/3.58).
- **Unchanged λ.** (a), (b) and (b′) selected the same λ on every split as before; only their held-out values shift slightly, through σ̂.

Full table (with std, flaps incl. cancel-drain, acts, per-split rows): `out/abl_table.md`; raw: `out/abl.jsonl`; log: `out/abl_progress.log`.

## Task 2: Madrid T1 with the leakage-free λ (`madrid_t1.py`, 30 s)

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

## Task 3: test traces under the leakage-free bucket λ (`testtr.py`, `table_testtr.py`, 10 s)

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

### Figures
* `docs/paper-v2/figs/fig_eps_guarantee.pdf`: script `figs/scripts/fig_eps_guarantee.py`. Only the right panel's data source changed: it now reads r63a `out/bucket.jsonl` and takes the mean and std (ddof 0) over the six splits; style and the left panel are untouched.
  **Visual change (right panel):**
  - **Smaller error bars.** The 2 % bars are smaller in D1, D4, D7 and D10 (D7 std 0.37 → 0.09 pp); D5+6 is about the same (±0.6 pp); D8 and D9 are slightly smaller.
  - **Markers move.** D7 (2 %) moves from 1.92 to 2.11 %, now clearly above the line with a tiny bar. D4 (2 %) moves up to the line (1.80 → 1.97 %). D10 (0.5 %) drops onto ε (0.65 → 0.49 %). D9 (0.5 %) stays below (0.38 %). D5+6 (0.5 %) is still the high outlier (0.69 %).
  - **Overall.** The points hug the dashed ε lines a little more closely, except D7 at 2 % and D5+6 at 0.5 %.
* `docs/paper-v2/figs/fig_r62_decile_lambda.pdf`: script `figs/scripts/fig_r62_decile_lambda.py`, pointed to r63a `out/bucket.jsonl`. Held-out risk, SE and per-split λ come from there; the hollow "deployed full-library λ" risk markers still come from r62ab, unchanged, because that is the bucket risk of the deployed λ under the full-library Prior.
  **Visual change:**
  - **Top row.** It changes as in fig_eps_guarantee (SE bars). The filled markers sit nearer ε; the main exceptions are D5+6 at 0.5 % and D7 at 2 %.
  - **Bottom row (λ), the large change.** The old monotone climb is gone; λ is now nearly flat across buckets.
    - Old climb: λ_UP 2.25 → 4.50 at 0.5 % and 1.54 → 3.29 at 2 %; λ_VM 2.1 → 3.5 and 1.46 → 2.42.
    - New, λ_UP: about 3.0 in every 0.5 % bucket except D5+6 3.12 and D10 3.83. At 2 %: 2.00–2.50, peaking in D10.
    - New, λ_VM: scattered between 2.2 and 2.75 (0.5 %) and 1.54 and 2.00 (2 %), with no trend. The 0.5 % λ_VM is below the deployed 2.83 in every bucket.
    - Y-axis ranges shrink (0.5 %: 2.0–4.5 → 2.0–4.1; 2 %: 1.4–3.4 → 1.4–2.6), and the D1 points now sit near the dotted deployed-λ lines instead of far below them.
  - **The dotted deployed-λ lines are now only a reference level.** The bucket λ multiplies the bucket σ̂, not the full-library σ̂. This is noted in the script docstring; the caption needs the same change.
  - **Caption claim.** Any caption text saying "λ_UP rises with rise1" must be corrected; this agrees with §4.108.

## Files (/home/user/experiment/qsim/r63r/)
* `abl.py`, `analyze_abl.py` → `out/abl.jsonl`, `out/abl_table.md` (full), `out/abl_compact.md`, `out/abl_summary.json`, `out/abl_progress.log`, `out/abl_run.log`
* `madrid_t1.py` → `out/madrid_t1.json`, `out/madrid_t1_table.md`, `out/madrid_t1.log`
* `testtr.py`, `table_testtr.py` → `out/testtr.json`, `out/testtr_table.md`, `out/testtr.log`, `out/bucket_A.json` (r63a bucket results in the r62ab "A" schema)
* `frozen_md5_before.txt` (19 files, `md5sum -c` all OK after); `old_figs/` (previous PDFs and scripts, old/new PNG previews)
