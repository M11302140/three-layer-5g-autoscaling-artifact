<!-- artifact file of the paper "Predictable-Cost Autoscaling of a Three-Layer 5G User Plane with Library-Calibrated Risk" (docs/paper), written 2026-10-21 for the round-62 analyses (spec §4.104 H item 4, results §4.105). Content copied from qsim/r62de/REPORT.md, sections "Task E" to "E2", with dashes replaced by a colon or n/a; simulation only, no hardware run. -->

# Lead-time tails

## Task E, lead-time tails

### Data and lead definitions
84 valid runs (`runs84.txt`): blocks t3–t7 of `p2/main_exp_ledger.tsv`, last row per run id (r382 = the replacement row), excluding the voided
r302, r304, r307, r309, r368, r370, r376, r379; r381 included. Per block: t3 19, t4 20, t5 7, t6 19, t7 19. Per arm: HHRO 14, S4a/S4b/B4c2/B5c1/B6c4 13 each,
B1_static 5 (B1 makes no actions). Scored window = last `autoscale toggled enabled=true` → next `enabled=false`. Only dispatches inside the window count.
Script: `E_leads.py` → `E_leads.json` (raw values and per-run lists).

| layer | dispatch | ready (primary definition) |
|---|---|---|
| VY | daemon `hbo deploy_vyos` (vyos-i) | first harness line (`trace_v7_rNNN.log`) after dispatch that admits data IP 10.0.1.(4+i) into the traffic pool: `minN: vyos-pool grow ['ip']` (event-driven check every 5 s, after `vyos_dataplane_ready`) or `SEG SA rebind (new vyos: [...ip...])` (minute-boundary admission). This is the moment the harness starts steering UEs onto it, i.e. when its capacity becomes usable. |
| UP | daemon `hbo scale_out_up (eupf)` slot=eupf-j (lines with `cancelled in-flight drain` are excluded: those keep an existing slot and dispatch no new one) | daemon `eupf rehome (scale-out) done` for the same slot. Tick-gated, so the resolution is 30 s. |
| WK | daemon `hbo create_worker` name=worker-k, or `hbo scale_out_up (eupf): creating slot worker first` worker=worker-k (the B4c2 path) | daemon `eupf worker provisioned` node=worker-k. Slot placement on the new worker follows this event at the next tick: r361 shows provisioned 00:25:08 → slot placed 00:25:24, before CREATE_WORKER's in-flight-done. |

Secondary definition: the daemon's `v6 inflight done` elapsed_s, matched to the dispatch by T_done − elapsed ≈ T_dispatch (±6 s). **This value is
censored from below and tick-quantised by construction.** The daemon logs it only when the count has moved **and** elapsed ≥ the arm's T_ready
constant (`hhro-daemon/internal/hbo/v6shadow.go` reconcileInflight: `done && el >= tr`; sigma arms use T_ready 30/150/120 s for UP/VY/WK). It is the
same quantity whose G2 p90 became `cfg_measured`'s HM = 30/150/120. It therefore mostly measures the T_ready setting, not the hardware.

Clock check: harness local time is UTC+8. Comparing each daemon `delete_vyos: repathed` (drain file written) with the harness `vyos drain announced`
gives 49 pairs: 44 within [0, +5] s, 3 at −1…−3 s, and 2 outliers at −26/−29 s. So the cross-log readiness times are good to about ±3 s.
Unmatched: 3 VyOS deploys (r402, r414, r419, all vyos-2, t6 S4a) were dispatched in the last ~40 s of the window and never admitted before the run
ended. They are right-censored and excluded.

## E1 lead distributions (s)

| layer | definition | n | min | p50 | p90 | p95 | p99 | max |
|---|---|---|---|---|---|---|---|---|
| VY | deploy_vyos → harness pool admission | 76 | 59.8 | 73.7 | 81.5 | 83.5 | 86.4 | 87.7 |
| UP | scale_out_up → eupf rehome (scale-out) done | 204 | 30.0 | 30.0 | 78.1 | 121.0 | 150.8 | 163.0 |
| WK | create_worker → eupf worker provisioned | 72 | 44.3 | 51.7 | 62.0 | 63.7 | 67.4 | 68.5 |
| VY | daemon 'v6 inflight done' elapsed_s (censored ≥ T_ready) | 76 | 89 | 120 | 179 | 180 | 180 | 180 |
| UP | daemon 'v6 inflight done' elapsed_s (censored ≥ T_ready) | 198 | 28 | 30 | 59 | 60 | 60 | 60 |
| WK | daemon 'v6 inflight done' elapsed_s (censored ≥ T_ready) | 70 | 119 | 119 | 149 | 149 | 149 | 149 |


Per-arm p95 of the primary definition: VY 79–85 s in every arm. WK 59–65 s. UP p95 33 s (B4c2), 62 (S4a), 89 (B6c4), 117 (S4b), 127 (B5c1), 127 (HHRO).
**The UP lead is bimodal.** 152/204 slot leads are 30 s (one tick) and 29/204 exceed 45 s, up to 163 s. Those long cases are rehome jobs queued
behind another rehome or retried after `rehome agent unreachable` (for example r361, where eupf-6 took 141 s behind eupf-7's rehome). The other two
layers have short, tight leads. **VyOS dataplane admission (p95 84 s) and worker provisioning (p95 64 s) are much shorter than the 150/120 s in
cfg_measured.** Those 150/120 s come from the censored in-flight-done quantity.

### Recalibration with H_l = lead + g (g = 30 s)
`cfg_with_h(h)` = `cfg_measured()` with HM replaced by h. All derived fields follow `cfg_measured`'s own formulas: w = d+h; hout = win = {UP: h_UP+g,
VY: h_VY+g, WK: h_WK+h_UP+g}; delta from w; d, drain and cores unchanged. Leads are rounded **up** to the 5-s simulation grid. The simulator has one
lead per layer, so the change applies to both the simulated readiness (`sim_nest2` uses cfg.h) and the planner's exposure window (cfg.win). The
Prior σ̂ is re-estimated with each cfg: `Prior(lib, cfg_variant)`. Its "win" rises are taken over [h, h+g] and its "run" rises over win.
Three variants were run:
* ready-signal p95 → h UP/VY/WK = 125/85/65 (win 155/115/220)
* ready-signal p99 → 155/90/70 (win 185/120/255)
* in-flight-done p95 = p99 = 60/180/149 → 60/180/150 (win 90/210/240). p95 and p99 are identical, so one run covers both.

## E2 recalibration with H_l = lead + g

| variant | target | λ_VM | λ_UP | cal risk | held-out risk | held-out alloc vmexist (dispatch) | Δalloc vs e | splits |
|---|---|---|---|---|---|---|---|---|
| (e) baseline h 30/150/120 (cfg_measured, p90 G2 in-flight) | 0.02 | 1.83 ± 0.12 | 2.00 ± 0.00 | 0.0190 | 0.0194 ± 0.0017 | 1282.5 ± 5.9 (1290.1) | -0.00% | 6 |
| (e) baseline h 30/150/120 (cfg_measured, p90 G2 in-flight) | 0.005 | 2.67 ± 0.31 | 3.12 ± 0.12 | 0.0047 | 0.0051 ± 0.0007 | 1338.6 ± 5.8 (1344.0) | -0.00% | 6 |
| ready-signal p95 → h UP/VY/WK 125/85/65 | 0.02 | 1.75 ± 0.25 | 2.04 ± 0.09 | 0.0187 | 0.0205 ± 0.0025 | 1287.5 ± 7.8 (1295.8) | +0.39% | 6 |
| ready-signal p95 → h UP/VY/WK 125/85/65 | 0.005 | 2.54 ± 0.09 | 3.04 ± 0.09 | 0.0046 | 0.0048 ± 0.0008 | 1344.3 ± 5.5 (1350.3) | +0.43% | 6 |
| ready-signal p99 → h 155/90/70 | 0.02 | 1.54 ± 0.09 | 2.00 ± 0.00 | 0.0189 | 0.0203 ± 0.0015 | 1290.7 ± 4.8 (1298.6) | +0.64% | 6 |
| ready-signal p99 → h 155/90/70 | 0.005 | 2.46 ± 0.17 | 3.08 ± 0.12 | 0.0048 | 0.0054 ± 0.0012 | 1348.2 ± 6.0 (1353.7) | +0.71% | 6 |
| in-flight-done p95 = p99 → h 60/180/150 | 0.02 | 1.54 ± 0.09 | 2.00 ± 0.00 | 0.0181 | 0.0191 ± 0.0020 | 1285.8 ± 5.1 (1292.9) | +0.26% | 6 |
| in-flight-done p95 = p99 → h 60/180/150 | 0.005 | 2.54 ± 0.27 | 2.79 ± 0.09 | 0.0046 | 0.0048 ± 0.0010 | 1340.5 ± 4.7 (1345.4) | +0.14% | 6 |


**Reading.** Moving every layer's lead to its p95 or p99 tail changes the recalibrated held-out cost by only **+0.1 % to +0.7 %** against (e),
at both targets. Each recalibration absorbs most of the change through λ, together with the re-estimated σ̂, whose windows get longer.
Held-out risk stays within one 6-split SD of the target in every case. The largest is 0.0205 ± 0.0025 at 2 % for the p95 variant; the
largest at 0.5 % is 0.0054 ± 0.0012 (p99). The ready-signal variants lengthen UP from 30 to 125–155 s but shorten VY/WK from 150/120 to 85–90/65–70,
so the net effect is small. In this simulator the slot tail is modelled as a *deterministic* 125–155 s lead on every slot. In the measured data
85 % of slot leads are 30 s, so this is a pessimistic stress test of the UP tail, not a fitted model of it.

## Three lead definitions per layer (round 63)

<!-- 2026-10-21 (spec §4.107 E, §4.108): copied verbatim from qsim/r63bf/REPORT.md "E". -->


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



## Three lead definitions per layer (moved from the Results chapter, 2026-10-21 R64)

| layer | controller lead $H_l$ | simulator h / d | measured ready p50 / p90 / p95 / p99 (n) |
|---|---|---|---|
| UP (slot) | 30 + 30 = 60 | 30 / 150 | 30.0 / 78.1 / 121.0 / 150.8 (204) |
| VY | 150 + 30 = 180 | 150 / 60 | 73.7 / 81.5 / 83.5 / 86.4 (76) |
| WK | 120 + 30 + 30 = 180 | 120 / 90 | 51.7 / 62.0 / 63.7 / 67.4 (72) |

Table 3. Three lead definitions per layer, in seconds: the controller horizon of the S arms (ready constant plus one 30 s tick; for WK also the slot lead), the fleet-level simulator's ready and teardown constants, and the ready latency measured in the 84 valid runs (VyOS deploy to traffic-pool admission, slot scale-out to completed rehome, worker create to provisioned). <!-- r63bf/REPORT.md E table: H_l (S arms) 60 / 180 / 180 (h_UP + g, h_VY + g, h_WK + h_UP + g, g = 30 s); nest2 cfg_measured h / d 30 / 150, 150 / 60, 120 / 90 (v8sim7.py:14); measured from r62de/E_leads.json primary, n 204 / 76 / 72; daemon TReadySec S out/in 30/150, 150/60, 120/90 and v6 15/120, 85/30, 100/60 and v8sim11 constants 15 (+20 relief) / 80 / 90 in artifacts/lead-tails.md -->


## Text of Results §8 before R65 (moved from the Results chapter, 2026-10-21)

<!-- 2026-10-21 R65 (spec §4.110): Results §8 (sensitivity of the calibration) was cut by half for the page budget; the paragraph below is the r64a text of the paper, verbatim with its source comments; the paper keeps one conclusion sentence with its key number. -->

Lead-time tails. Ready leads were extracted from the daemon and harness logs of the 84 valid runs, with ready meaning that the new unit carries traffic: a VyOS from deploy to admission into the traffic pool, a slot from scale-out to completed rehome, a worker from create to provisioned. <!-- r62de/REPORT.md "Data and lead definitions" --> The p50 / p95 / p99 are 73.7 / 83.5 / 86.4 s for VyOS (n = 76), 30.0 / 121.0 / 150.8 s for slots (n = 204, bimodal: 152 leads of one 30 s tick and 29 above 45 s from queued or retried rehomes) and 51.7 / 63.7 / 67.4 s for workers (n = 72). <!-- r62de/REPORT.md E1 table and text --> Real VyOS and worker readiness is thus faster than the 150 s and 120 s the simulator assumes, which come from the daemon's in-flight signal, censored at its own ready constant. <!-- r62de/REPORT.md E1 reading; §4.105 E --> The three lead definitions differ: the S arms' controller horizon $H_l$ is 60 / 180 / 180 s for UP / VY / WK, the simulator's ready constants are 30 / 150 / 120 s, and the measured p95 ready latencies are those above (table in the artifact repository, lead-tails.md). The daemon's in-flight signal, from which the constants were taken, is logged only once the count has changed and the constant has elapsed, on a 30 s tick, so it reflects only the constants. <!-- r63bf/REPORT.md E ('The in-flight-done signal reflects only the constants': logged only when the count has changed and elapsed ≥ TReadySec, only on a 30-s tick, v6shadow.go:702-708); §4.107 E -->

 Recalibrating with every layer's lead at its p95 (125 / 85 / 65 s for UP / VY / WK), at its p99 (155 / 90 / 70 s) or at the in-flight constants (60 / 180 / 150 s), with σ̂ re-estimated each time, changes the held-out cost by +0.39, +0.64 and +0.26 % at 2 % and +0.43, +0.71 and +0.14 % at 0.5 %, with held-out risk within one split standard deviation of the target in every case: lead tails cost at most 0.7 %. <!-- r62de/REPORT.md E2 table and reading --> The test is pessimistic for slots, as every slot gets the tail lead. <!-- r62de/REPORT.md E2 reading -->


## Text of Results §8 "Lead-time tails" before the 2026-10-22 cut (verbatim, spec §4.113 equal-trade cut b)

Lead-time tails. Measured VyOS and worker ready leads in the 84 valid runs (p95 83.5 s and 63.7 s) are shorter than the 150 s and 120 s the simulator assumes, which come from the daemon's in-flight signal and reflect only its own constants; slot leads are bimodal (p95 121.0 s against 30 s), and the S arms' controller horizon $H_l$ is 60 / 180 / 180 s for UP / VY / WK (definitions and distributions in the artifact repository, lead-tails.md). Recalibrating with every lead at its p95, at its p99 or at the in-flight constants, with $\hat{\sigma}$ re-estimated each time, keeps the held-out modeled risk within one split standard deviation of the target: lead tails cost at most 0.7 %, a test pessimistic for slots, as every slot gets the tail lead. <!-- r62de/REPORT.md "Data and lead definitions" --> <!-- r62de/REPORT.md E1 table and text --> <!-- r62de/REPORT.md E1 reading; §4.105 E --> <!-- r63bf/REPORT.md E ('The in-flight-done signal reflects only the constants': logged only when the count has changed and elapsed ≥ TReadySec, only on a 30-s tick, v6shadow.go:702-708); §4.107 E --> <!-- 2026-10-21 R64b (§4.109): lead-definition table (old Table 3) moved to artifacts/lead-tails.md; key numbers kept in the sentence above --> <!-- r62de/REPORT.md E2 table and reading --> <!-- r62de/REPORT.md E2 reading -->
