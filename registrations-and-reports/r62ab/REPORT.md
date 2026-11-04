# r62 Tasks A and B (spec §4.104): conditional λ, uncertainty, event rates

Simulation only (2026-10-21). All computation ran as `nice -n 19 taskset -c 13,14 python3` with at most 2 worker processes. No frozen file was modified (v8sim10.py, v8sim2.py, v8sim3.py, v8sim7.py, v8sim11.py, v8sim10_cal.py, prior_traces.json). Results go to §4.105.

## Commands and runtimes

| step | command (cwd /home/user/experiment/qsim/r62ab) | wall time |
|---|---|---|
| dual-sim equivalence | `nice -n 19 taskset -c 13,14 python3 verify_dual.py 60` | ~10 s |
| step-0 matrix | `nohup nice -n 19 taskset -c 13,14 python3 matrix.py 2 > matrix.log` then `python3 matrix.py merge` | 7124 s (1.98 h) on 2 workers |
| all analyses A + B | `nice -n 19 taskset -c 13,14 python3 analyze.py > analyze.log` (single process) | 200 s |
| figure | `cd /home/user/docs/paper-v2/figs && nice -n 19 taskset -c 13 python3 scripts/fig_r62_decile_lambda.py` | ~5 s |

**Projection.** Before the run, a single nest2 call took 13.7 ms (frozen) and 15.5 ms (dual), measured on 20 traces. That projects 3.3 s per trace × 221 points, about 45 min on 2 idle workers. The actual run took 1.98 h because cores 13 and 14 were shared with other agents. The 4 h trigger was not reached, so **the full grid was used** (λ_VM 0.5–3.5 × λ_UP 0.5–4.5, step 0.25, 221 points) and the reduced grid was not needed.

**vmexist in the same run.** The `acct` argument changes only the billing sum, which never feeds back into the dynamics. `dual.py` therefore builds `sim_nest2_dual` at import time from the frozen source (`inspect.getsource(v8sim10.sim_nest2)`). It applies a textual patch, asserted to match exactly once, that bills both modes in one pass. Each matrix call therefore yields alloc (dispatch) and alloc_vm (vmexist).

**Stored per (trace, point)** in `matrix.npz`:
- slo
- the 60-bit violation vector (minute m violates iff pct > 0.1 %)
- alloc dispatch and alloc vmexist
- flaps: same-layer opposite-direction 'out'/'in' events within 600 s of the previous same-layer event, from r['ev']
- the number of actions

**Off-matrix points.** Refinement around a coarse optimum on the matrix edge (λ_VM 3.75 or λ_UP 4.75) occurred only in the high-rise1 buckets at 0.5 %. Those points were simulated fresh with the dual sim and cached in `offgrid_cache.json` (747 runs).

## Step 0 verification

- **Dual sim vs frozen.** `verify_dual.py` ran 60 random (trace, λ) pairs: 0 mismatches against frozen `sim_nest2` (dispatch and vmexist; slo, pct, ev and alloc compared exactly). It also found 0 mismatches between `sim_v6_pm` and frozen `sim_v6` (slo, alloc, acts, flaps).
- **Lookup vs fresh frozen sim.** 5 random traces × all 221 points × both acct modes (1105 pairs) gave **0 mismatches**.
- **Frozen six-split reproduction.** Calibration on the matrix reproduces the frozen results (v8sim10_FULL_2026-10-06.txt) **exactly, split by split**: the same λ, calibration risk, held-out risk and held-out dispatch alloc for all 12 (target, split) cells. The procedure is grouped_split seeds 0–5, cal[:300], coarse 6×7, cheapest dispatch, ±0.25 refinement and python-min tie order:
  - 2 %: λ 1.83±0.12 / 2.00±0.00, held-out 0.0194±0.0017
  - 0.5 %: λ 2.67±0.31 / 3.12±0.12, held-out 0.0051±0.0007
  - Held-out vmexist alloc: 1282.5 at 2 % and 1338.6 at 0.5 %.

Six-split calibration on the matrix vs frozen v8sim10_FULL_2026-10-06.txt (grouped_split seeds 0-5, cal[:300], coarse 6x7 + ±0.25):

| target | split | λ lookup | λ frozen | cal risk lookup / frozen | ho risk lookup / frozen | ho alloc dispatch lookup / frozen | ho alloc vmexist |
|---|---|---|---|---|---|---|---|
| 0.02 | 0 | 1.75/2.0 | 1.75/2.0 | 0.0186 / 0.0186 | 0.0190 / 0.0190 | 1295.9 / 1295.9 | 1288.5 |
| 0.02 | 1 | 2.0/2.0 | 2.0/2.0 | 0.0182 / 0.0182 | 0.0175 / 0.0175 | 1296.3 / 1296.3 | 1288.8 |
| 0.02 | 2 | 1.75/2.0 | 1.75/2.0 | 0.0193 / 0.0193 | 0.0205 / 0.0205 | 1282.7 / 1282.7 | 1274.8 |
| 0.02 | 3 | 1.75/2.0 | 1.75/2.0 | 0.0199 / 0.0199 | 0.0214 / 0.0214 | 1288.3 / 1288.3 | 1280.8 |
| 0.02 | 4 | 1.75/2.0 | 1.75/2.0 | 0.0191 / 0.0191 | 0.0211 / 0.0211 | 1283.4 / 1283.4 | 1275.4 |
| 0.02 | 5 | 2.0/2.0 | 2.0/2.0 | 0.0187 / 0.0187 | 0.0169 / 0.0169 | 1294.2 / 1294.2 | 1286.7 |
| 0.02 | mean | 1.83±0.12 / 2.00±0.00 | | | 0.0194±0.0017 | 1290.1 | 1282.5 |
| 0.005 | 0 | 3.0/3.0 | 3.0/3.0 | 0.0048 / 0.0048 | 0.0050 / 0.0050 | 1351.9 / 1351.9 | 1346.9 |
| 0.005 | 1 | 2.75/3.25 | 2.75/3.25 | 0.0041 / 0.0041 | 0.0037 / 0.0037 | 1350.9 / 1350.9 | 1345.9 |
| 0.005 | 2 | 2.75/3.0 | 2.75/3.0 | 0.0048 / 0.0048 | 0.0053 / 0.0053 | 1337.4 / 1337.4 | 1331.6 |
| 0.005 | 3 | 2.25/3.25 | 2.25/3.25 | 0.0047 / 0.0047 | 0.0062 / 0.0062 | 1342.6 / 1342.6 | 1337.0 |
| 0.005 | 4 | 3.0/3.0 | 3.0/3.0 | 0.0048 / 0.0048 | 0.0054 / 0.0054 | 1338.9 / 1338.9 | 1333.4 |
| 0.005 | 5 | 2.25/3.25 | 2.25/3.25 | 0.0049 / 0.0049 | 0.0053 / 0.0053 | 1342.1 / 1342.1 | 1336.6 |
| 0.005 | mean | 2.67±0.31 / 3.12±0.12 | | | 0.0051±0.0007 | 1344.0 | 1338.6 |

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

### Operator use (described only, not implemented)

At each decision point the operator computes rise1 over the last 10 minutes of observed UE counts. To keep a 60-minute statistic comparable, use the same max one-minute rise; the shorter window biases it low, so either recompute the library thresholds on 10-minute windows or treat the result as a lower bound. The operator then looks up the bucket from the frozen threshold table (P10..P90 = 7, 7, 8, 9, 9, 10, 11, 12, 14 UE/min, with D2 and D5 merged). The bucket row gives two things:
- the **conditional risk of the current λ**: the "full-λ risk (bucket)" column. For example, D10 under S4b is 4.0 %, not the advertised 2 %.
- the **bucket-calibrated λ** that brings held-out risk back to about ε, with its held-out cost.

The operator can either just report the conditional risk or switch λ to the bucket value. A switch should take effect only at a quiet point; this lookup does not model a mid-run change of λ, and the D10 0.5 % row is infeasible on the grid (minimum achievable held-out risk about 0.65 %).

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

## Files

- `/home/user/experiment/qsim/r62ab/`:
  - dual.py (dual-billing nest2 and per-minute v6, generated from frozen source)
  - verify_dual.py
  - matrix.py
  - matrix.npz (1615 × 221 matrix)
  - mat/ (chunk checkpoints)
  - look.py (lookup calibration)
  - analyze.py
  - results.json (all numbers, including per-split rows)
  - report_tables.md
  - analyze.log, matrix.log
  - offgrid_cache.json
- Figure: `/home/user/docs/paper-v2/figs/fig_r62_decile_lambda.pdf`, script `/home/user/docs/paper-v2/figs/scripts/fig_r62_decile_lambda.py`. It plots per-bucket held-out risk ± SE against ε together with the full-λ bucket risk, and the bucket λ_VM/λ_UP against the deployed λ; both targets.
