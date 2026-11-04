# r63bf: spec §4.107 tasks B, C, D, E and F (Minor 4), 2026-10-21

This is log and CSV analysis only. No simulation was run and no input was modified.
- Scripts: `/home/user/experiment/qsim/r63bf/r63bf.py` and `r63bf_extra.py`. Both were run as `nice -n 19 taskset -c 13 python3`, one process.
- Raw outputs: `r63bf_out.txt`, `r63bf_extra_out.txt` and `results.json`. `results.json` holds all 117 violating minutes with their fleet fields.
- Baseline check: `cross_residual_out.txt` is the unchanged output of the scratchpad `cross_residual.py`. It gives 84 valid runs and 117 violating minutes (capacity 83, tail 10, type2 11, non-slot 12, nodist 1). r63bf.py reuses its run selection and its per-minute classification verbatim and reproduces the same 117 minutes.
- Arm names: in the ledger and logs, "HHRO" is the v6 arm and "B6c4_slo" is B6 u = 0.70.

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

## C. Burned host CPU, alloc_vm, UE moves and violations on t6/t7

Sources:
- burned, burned_wk, burned_vy, alloc_vm and slo (core-min per run): `rq_metrics.csv` groups `MAIN tX <arm>`. Group names used: B5c1 = "B5c1 (q11)", B6 = "B6 u=0.70".
- Moves: `paper_out_new/ops/ops_per_run.csv`, means per run over the same runs.
  - drain moves = Σ `{` in `drain: plan` moves.
  - relief = Σ `moves` of `v6 pool relief`.
  - hot-slot relief = Σ `moves` of `v6 hot slot relief`.

| trace | arm | n | burned (runs) | burned_wk / burned_vy | alloc_vm | viol. min (total) | drain UE moves/run | relief UE moves/run | hot-slot UE moves/run |
|---|---|---|---|---|---|---|---|---|---|
| t6 | S4a | 3 | 687.0 (689,683,689) | 483.3 / 203.7 | 1435.0 | 0 | 4.33 | 0 | 0 |
| t6 | **S4b** | 3 | **654.0** (648,652,662) | 457.7 / 196.3 | 1390.3 | **0** | 0.00 | 0 | 0 |
| t6 | v6 | 3 | 647.3 (638,647,657) | 470.3 / 177.0 | 1349.3 | 5 | 4.00 | 0 | 0.67 |
| t6 | B4c2 | 3 | 712.7 (713,732,693) | 504.0 / 209.0 | 1455.7 | 5 | 1.00 | 0 | 0.33 |
| t6 | B5c1 | 3 | 683.0 (692,673,684) | 485.3 / 197.7 | 1433.0 | 2 | 1.33 | 0 | 0 |
| t6 | B6 | 3 | 714.7 (733,706,705) | 513.3 / 201.3 | 1447.3 | 0 | 0.00 | 0 | 0 |
| t6 | B1 | 1 | 730.0 | 521.0 / 209.0 | 1464.0 | 0 | 0 | 0 | 0 |
| t7 | S4a | 3 | 667.7 (663,660,680) | 470.7 / 197.0 | 1427.0 | 1 | 5.00 | 0 | 0 |
| t7 | **S4b** | 3 | **644.3** (645,640,648) | 447.3 / 197.0 | 1387.3 | **0** | 3.00 | 0 | 0 |
| t7 | v6 | 3 | 641.7 (638,648,639) | 463.0 / 179.3 | 1353.0 | 0 | 6.00 | 0 | 0 |
| t7 | B4c2 | 3 | 715.7 (705,722,720) | 521.0 / 194.7 | 1440.7 | 0 | 1.67 | 0 | 0 |
| t7 | B5c1 | 3 | 679.7 (684,684,671) | 496.0 / 183.7 | 1413.0 | 0 | 4.67 | 0 | 0 |
| t7 | B6 | 3 | 711.7 (710,719,706) | 510.0 / 201.7 | 1451.0 | 0 | 1.33 | 0 | 0 |
| t7 | B1 | 1 | 733.0 | 526.0 / 207.0 | 1464.0 | 1 | 0 | 0 | 0 |

**S4b's burned is below all three tuned baselines on both traces.**
- t6: 654.0 against B4c2 712.7 (−58.7, −8.2%), B5c1 683.0 (−29.0, −4.2%) and B6 714.7 (−60.7, −8.5%).
- t7: 644.3 against 715.7 (−71.4, −10.0%), 679.7 (−35.4, −5.2%) and 711.7 (−67.4, −9.5%).
- Each single S4b run is below every single run of each baseline on the same trace. S4b max is 662 on t6 and 648 on t7; the baseline mins are 673 on t6 (B5c1 r412) and 671 on t7 (B5c1 r445).
- v6 is lower than S4b on both traces: −6.7 on t6 and −2.6 on t7.

Moves and violations:
- S4b made 0 drain UE moves per run on t6 and 3.0 on t7.
- No arm made any pool-relief UE moves on t6/t7.
- Hot-slot relief appears only in v6 t6 (2 moves in r420) and B4c2 t6 (1).
- S4b scored 0 violating minutes in all 6 formal t6/t7 runs, so its UE moves caused no scored violation.

## D. Calibration cost by method

Wall times are taken from the logs named below.
- `[Ns]` in the v8sim10 logs is cumulative elapsed time since script start.
- The process count of the v8sim10 runs was not logged. Script defaults: `v8sim10_cal.py` 3 (`v8sim10_cal.py:31`), `v8sim10_full.py` 2 (`v8sim10_full.py:35`).

| method | prior data needed | offline simulation actually spent on calibration (log) | simulator model existed when tuned | hardware profiling | hardware tuning runs |
|---|---|---|---|---|---|
| **S4 planner (S4a/S4b)** | Melbourne prior library, 1615 60-min traces / 125 (loc, date) groups (`qsim/prior_traces.json`); σ̂ fitted on it | **Deployed λ:** `v8sim10_CAL_2026-10-05.txt`, 3 splits × 2 targets, 528 s ≈ 0.15 h (≈ 86 s/split). **6-split confirmation:** `v8sim10_FULL_2026-10-06.txt` part (a) 4442 s ≈ 1.23 h (whole file 5091 s incl. (b) lower bound and (c) levers; λ unchanged). Sensitivity `v8sim10_CAL_nosensor_2026-10-10.txt` 1233 s. Post-hoc re-runs: `abl/progress.log` variant (e) 12 splits 146–153 s each ≈ 0.49 h, nproc 2, inside a 2.55 h ablation of 6 variants × 12 splits. Superseded calibrations (v8sim7_CAL / v8sim8 / v8sim9, 10-04/05) have no time stamps in their logs. | yes: nest2 (v8sim10), the daemon-equivalent simulator (the equivalence test is cited at the G2b registration, spec 10-05 15:35) | Lead p90 from the G2 runs r201–r206 (daemon in-flight-done → `measuredTReady` UP/VY/WK 30/150/120, `hhro-daemon/internal/hbo/sigma.go:127-131`). VM existence period from r241/r247/r248/r250/r251 (spec §4.25; vmexist accounting). | **0** (λ never selected on hardware; G2/G2b/G2c runs were gates only, and G2 was used to diagnose and correct the simulator, §4.105 G) |
| **v6** | none (hand-set constants) | none for tuning. sim_v6 (v8sim2, 10-03) was written later and used only for predictions. | no (hand-tuned on hardware) | T_ready constants hand-set from daemon logs (`calib.go` comments: 09-03 measurements, 09-14 r52 → VyOS 85 s) | hand-tuned in September on t1/t2. `rq_metrics.csv` has groups "HHRO t1" (r108, r110, r112, r114, r119) and "HHRO t2" (r107, r109, r115, r117, r118) = **10 formal runs after the freeze**. As an upper bound on all hardware runs during v6 development: `p2/trace_v7_rN.csv` exists for **116 distinct run ids N ≤ 119** (r1 2026-09-03 → r119 09-23), including aborted, diagnostic and infrastructure-debug runs. |
| **B4c2** | none for the deployed knob | none at tuning time. Post-hoc equal-risk recalibration (`r62cf/calib_progress.log`): B4on 1356 s (incl. 834 s of an interrupted first pass whose cache was kept) + B4off 1395 s = **2751 s ≈ 0.76 h** | no (its model exists only in v8sim11, built 10-11 after tuning on 10-08/09) | none beyond the shared testbed | **5 (+1 voided)** (§4.106) |
| **B5c1** | none (Holt (0.3, 0.05) fixed) | Post-hoc: B5on 1604 s + B5off 1728 s = **3332 s ≈ 0.93 h** | no (v8sim11, post-tuning) | none | **4** |
| **B6** | prior library (forecasters AR(3)/Holt/MLP trained on 1615 traces; `qsim/b6_models.json`, 10-08 07:53) | Pre-screen at tuning time: `v8sim_b6` u sweep on t1/t2 plus library check at u 0.78 (scratchpad `b6_train.log` 07:53:39, `b6_eval.log` 07:54:14, `b6_eval_lib.log` 07:56:45–07:56:59; start time not logged, the stamps span about 3.3 min). Post-hoc: B6b6 620 s + B6on 841 s + B6off 656 s = **2117 s ≈ 0.59 h** | yes: aggregate-physics `v8sim_b6` (spec §4.43/§4.44, 10-08 07:54), used to pick hardware candidates | none | **5 (+2 voided)** |

- r62cf total: 9540 s (00:53:08–03:32:08) = the 9 phases above plus S-in-v8sim11 (Son 794 s + Soff 546 s). Its REPORT counts 185 grid points × 1615 traces = 2.63 h of single-process simulation.
- For scale, the post-hoc r62ab matrix (§4.105 A+B) took 7124 s. It is not calibration of the deployed method.

## E. Three lead definitions per layer (s)

| layer | controller lead H_l (S arms) | daemon TReadySec: S (`sigma.go:130-131`) / v6 (`calib.go:149-179`) | simulator nest2 `cfg_measured` h / d (`v8sim7.py:14`) | v8sim11 constant (`v8sim11.py:27-29`) | measured ready latency, 84 runs (`r62de/E_leads.json` primary): n, p50 / p90 / p95 / p99 (max) | daemon "v6 inflight done" elapsed (`E_leads.json` inflight): n, p50 / p90 / p95 / p99 |
|---|---|---|---|---|---|---|
| UP (slot) | h_UP + g = 30 + 30 = **60** | out 30 / 15; in 150 / 120 | h 30 / d 150 | slot_api_s 15 (+ relief_delay_s 20) | scale_out_up → rehome done: n 204, 30.0 / 78.1 / 121.0 / 150.8 (163.0) | n 198: 30 / 59 / 60 / 60 |
| VY | h_VY + g = 150 + 30 = **180** | out 150 / 85; in 60 / 30 | h 150 / d 60 | vy_admit_s 80 | deploy_vyos → harness pool admission: n 76, 73.7 / 81.5 / 83.5 / 86.4 (87.7) | n 76: 120 / 179 / 180 / 180 (min 89) |
| WK | h_WK + h_UP + g = 120 + 30 + 30 = **180** | out 120 / 100; in 90 / 60 | h 120 / d 90 | wk_ready_s 90 | create_worker → worker provisioned: n 72, 51.7 / 62.0 / 63.7 / 67.4 (68.5) | n 70: 119 / 149 / 149 / 149 |

How the lead columns are built:
- H_l uses g = 30 s (one tick). cfg_measured sets `win = hout = {UP: h_UP+g, VY: h_VY+g, WK: h_WK+h_UP+g}` (`v8sim7.py:18`), which equals the daemon's `qOutHorizon` (`hhro-daemon/internal/hbo/qplan.go:61-71`) with the S-mode TReadySec.
- v6 uses the calib.go defaults, giving horizons 45 / 115 / 145 s.
- The nest2 h values equal the S-mode `measuredTReady` scale-out values, and the d values equal its scale-in values. Both are the G2 p90 of the in-flight-done signal.

**The in-flight-done signal reflects only the constants.**
- It is logged only when the count has changed **and** elapsed ≥ TReadySec, and only on a 30-s tick (`v6shadow.go:702-708`).
- Its values cluster at tick multiples just after the constants: UP 29–30 / 59–60, VY 89–90 / 119–120 / 179–180, WK 119–120 / 149.
- The pooled data mixes arms with different constants, and `E_leads.json` has no per-run tags for this signal.

The measured readiness is well below the controller's VY/WK leads.
- VY p99 86 s and WK p99 67 s, against 150 and 120.
- UP is bimodal: 152/204 are one tick (30 s), and the p95/p99 come from queued or retried rehomes (r62de REPORT E1).

## F (Minor 4). p99 near the 1 ms threshold (84 valid runs, 5040 scored minutes)

The run selection is that of cross_residual.py. The SLO is violated if e2e_pct > 0.1 or lat_p99_us > 1000.

| trace | scored min | p99 ∈ [900, 1100] µs | of which SLO-violating | violating on p99 alone | p99 ∈ [900, 1000) and passing | p99 > 1000 (all) | violating on p99 alone (any p99) |
|---|---|---|---|---|---|---|---|
| t3 | 1140 | 1 | 0 | 0 | 1 | 54 | 4 |
| t4 | 1200 | 0 | 0 | 0 | 0 | 18 | 1 |
| t5 | 420 | 0 | 0 | 0 | 0 | 0 | 0 |
| t6 | 1140 | 0 | 0 | 0 | 0 | 2 | 0 |
| t7 | 1140 | 0 | 0 | 0 | 0 | 0 | 0 |
| all | 5040 | **1** | **0** | **0** | **1** | 74 | 5 |

- Only one minute in 5040 lands in 0.9–1.1 ms: r363 (t3 S4b) min 10, p99 946 µs, loss 0.00%, which passes.
- No minute has p99 in (1000, 1436) µs. The largest p99 ≤ 1 ms is 946 µs and the smallest p99 > 1 ms is 1436 µs.
- p99 distribution over all minutes: <500 µs 4959, 500–800 5, 800–900 1, 900–1000 1, 1000–1100 0, 1100–2000 2, 2000–3000 56, ≥3000 16. No minute has lat_n = 0.
- The 5 minutes that violate on p99 alone are r320 min 1 (4077 µs), r363 min 7 (2391) and min 9 (2732), r375 min 8 (1436), and r380 min 7 (2864). All are well above 1.1 ms.
- So the SLO verdict of no scored minute depends on how p99 is interpolated within the 100 µs bucket below 1 ms or the 1 ms bucket above it.
