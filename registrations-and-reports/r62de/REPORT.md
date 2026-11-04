# §4.104 Tasks D and E (round 62): workload-conversion sensitivity and lead-time tails — 2026-10-21

Simulation and log analysis only. No hardware runs; deployed λ, daemon and harness untouched. Everything ran as **one** python process
(`nice -n 19 taskset -c 13,14`), strictly one after another. Frozen files were not modified: md5 of v8sim10.py, v8sim2.py, v8sim3.py,
v8sim7.py, v8sim10_cal.py, prior_traces.json, make_prior.py and make_newtraces.py matched before and after (`frozen_md5_before.txt`;
`md5sum -c` all OK). All new code is in this directory.

## 0. Engine and how it was validated

* `eng.py` is a copy of `v8sim10.sim_nest2` with the default flags. Changes: (i) it computes the dispatch and vmexist accounting in **one pass**;
  (ii) it caches unit counts between unit events, caches `observe()`, and memoises σ̂ lookups (about 5× faster); (iii) an optional `load` series
  for the per-UE-rate model. **Equivalence:** slo, alloc_dispatch and alloc_vmexist are bit-identical to the frozen `sim_nest2` (both acct) on
  180/180 trace×λ cases in the dev check and on 60/60 at the start of the baseline run.
* Calibration is a **lookup on a per-trace result matrix**, not a re-simulation per split. The arithmetic is the same as `v8sim10_cal.py` /
  `v8sim10_ablation.py`:
  `grouped_split(seed)` on the library being calibrated (seeds 0–5, 60 % of (loc,date) groups go to calibration). The calibration set is the first
  300 of those traces. Coarse grid VM {1.0…3.5} × UP {1.5…4.5}. The feasible set is cal risk ≤ target; among feasible points take the lowest cal
  alloc (dispatch). Then a ±0.25 refinement over the 8 neighbours, where only that split's own refine points join its table. Held-out evaluation
  uses all held-out traces: risk, plus alloc in vmexist (dispatch in brackets). The simulator is deterministic, so a lookup equals re-simulation.
  **Reproduction check:** on the frozen library with `cfg_measured()` (run `E_base_p90`) every one of the 12 split results equals ablation
  variant (e) (`abl/ablation_table.md`) to the printed digit: 2 % → λ 1.83±0.12/2.00, held-out risk 0.0194, alloc 1282.5; 0.5 % → 2.67±0.31/3.12±0.12,
  0.0051, 1338.6.
* Full ±0.25 refinement was used everywhere, including all 18 Task D variants. Projected time from the baseline run was 3.3 h, under the 4 h rule;
  actual time for the 17 new variants was 1.9 h (01:58 → 03:53).

## Task E — lead-time tails

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

## Task D — workload-conversion sensitivity

### Raw source and pipeline
The raw per-minute counts are on disk: `/home/user/Downloads/3b4c9b89-c976-49e7-8358-075fe3699297.csv` (Melbourne Pedestrian Counting System,
resource 3b4c9b89). They are read by the frozen `make_prior.py`. `D_build.py` generalises that script without touching it.

Steps kept identical:
* sum over directions per (loc, date, minute)
* reindex 0..1439 plus linear interpolation (`limit_direction='both'`)
* keep a loc-day only if it has ≥ 1200 rows
* the same 15 window starts, 06:00–20:00 hourly
* centred rolling mean inside the window (`min_periods=1`)
* rejection if the smoothed window peak is < 20 /min, applied to that variant's own smoothed series
* UE = clip(round(40·C/Cmax), 1, 40)
* EXCLUDE = the three evaluation loc-days plus the heldout.json t4/t5 loc-days, as in `make_prior.py --with-heldout`

Varied: smoothing window ∈ {1, 5, 10} min; compression k:1 with **window length 60·k real minutes** (1:1 → 60, 2:1 → 120, 4:1 → 240 real minutes per
60-minute trace; each experiment minute is the mean of k consecutive real minutes); deadband ∈ {0 (none), 2}.
**Reproduction:** variant (5 min, 4:1, 2) equals `prior_traces.json` exactly (1615 traces, list equality), but only with the heldout exclusion. Without
it the build gives 1645 traces. That variant therefore reuses `E_base_p90`.
rise1 = max{u[t+1]−u[t]}; rise10 = max{u[j]−u[i]: 0<j−i≤10} (the `lib_percentiles.py` definition, unclamped), over the 60 experiment minutes; numpy linear
percentiles. Each variant gets its **own Prior** σ̂ and its **own** grouped splits, since the group sets differ: 128/125/120 groups for 1/5/10-min smoothing.
"need-floor" = Σ_min Σ_layer cores·need_l(D) at zero margin and zero lead. It is a demand-only scale, used to compare costs across libraries whose
demand differs.

## D1 library variants

| variant (smooth min, compression, deadband) | traces | (loc,date) groups | rise1 P10/P50/P90 | rise10 P10/P50/P90 | σ̂_win at D=20 VY/UP/WK | need-floor core-min/run |
|---|---|---|---|---|---|---|
| 1 / 1:1 / 0 | 1575 | 128 | 17/23/31 | 23/30/36 | 5.67/5.23/5.67 | 861.4 |
| 1 / 1:1 / 2 | 1575 | 128 | 17/23/31 | 23/30/36 | 5.67/5.26/5.67 | 861.3 |
| 1 / 2:1 / 0 | 1696 | 128 | 13/19/26 | 18/24/31 | 5.31/4.84/5.31 | 929.8 |
| 1 / 2:1 / 2 | 1696 | 128 | 13/19/26 | 18/24/31 | 5.31/4.88/5.31 | 929.7 |
| 1 / 4:1 / 0 | 1850 | 128 | 10/14/21 | 14/20/27 | 4.47/4.03/4.47 | 935.2 |
| 1 / 4:1 / 2 | 1850 | 128 | 10/14/21 | 14/20/27 | 4.48/4.07/4.48 | 935.2 |
| 5 / 1:1 / 0 | 1260 | 125 | 4/6/9 | 10/15/20 | 3.47/1.80/3.47 | 1160.0 |
| 5 / 1:1 / 2 | 1260 | 125 | 4/6/9 | 10/14/20 | 3.50/1.89/3.50 | 1160.1 |
| 5 / 2:1 / 0 | 1409 | 125 | 5/7/11 | 11/15/22 | 4.03/2.07/4.03 | 1088.2 |
| 5 / 2:1 / 2 | 1409 | 125 | 5/7/11 | 11/15/22 | 4.04/2.17/4.04 | 1088.5 |
| 5 / 4:1 / 0 | 1615 | 125 | 7/9/14 | 11/16/23 | 3.69/2.58/3.69 | 995.1 |
| 5 / 4:1 / 2 (= frozen library) | 1615 | 125 | 7/9/14 | 11/16/23 | 3.70/2.64/3.70 | 995.1 |
| 10 / 1:1 / 0 | 1166 | 120 | 2/3/5 | 5/9/14 | 1.80/0.95/1.80 | 1264.7 |
| 10 / 1:1 / 2 | 1166 | 120 | 3/4/5 | 5/9/14 | 1.87/1.05/1.87 | 1264.9 |
| 10 / 2:1 / 0 | 1311 | 120 | 3/4/6 | 7/11/17 | 2.30/1.05/2.30 | 1170.5 |
| 10 / 2:1 / 2 | 1311 | 120 | 3/4/6 | 6/11/16 | 2.36/1.19/2.36 | 1170.1 |
| 10 / 4:1 / 0 | 1502 | 120 | 4/5/8 | 8/13/20 | 2.90/1.36/2.90 | 1049.8 |
| 10 / 4:1 / 2 | 1502 | 120 | 4/5/8 | 8/13/19 | 2.91/1.47/2.91 | 1049.6 |


## D2 six-split recalibration per library variant (own Prior σ̂, own grouped splits)

| variant | target | λ_VM | λ_UP | cal risk | held-out risk | held-out alloc vmexist (dispatch) | Δalloc vs e | splits | alloc / need-floor |
|---|---|---|---|---|---|---|---|---|---|
| 1 / 1:1 / 0 | 0.02 | 1.58 ± 0.12 | 3.21 ± 0.39 | 0.0193 | 0.0192 ± 0.0016 | 1415.3 ± 3.6 (1420.8) | +10.35% | 6 | 1.643 |
| 1 / 1:1 / 0 | 0.005 | 2.38 ± 0.12 | 3.46 ± 0.17 | 0.0043 | 0.0044 ± 0.0014 | 1449.5 ± 4.0 (1451.9) | +8.29% | 6 | 1.683 |
| 1 / 1:1 / 2 | 0.02 | 1.58 ± 0.12 | 3.12 ± 0.12 | 0.0192 | 0.0190 ± 0.0021 | 1416.2 ± 4.0 (1421.7) | +10.43% | 6 | 1.644 |
| 1 / 1:1 / 2 | 0.005 | 2.42 ± 0.12 | 3.38 ± 0.12 | 0.0040 | 0.0042 ± 0.0014 | 1450.5 ± 4.0 (1452.7) | +8.36% | 6 | 1.684 |
| 1 / 2:1 / 0 | 0.02 | 1.54 ± 0.17 | 2.62 ± 0.28 | 0.0188 | 0.0197 ± 0.0026 | 1392.0 ± 6.8 (1396.9) | +8.53% | 6 | 1.497 |
| 1 / 2:1 / 0 | 0.005 | 2.29 ± 0.09 | 3.33 ± 0.19 | 0.0047 | 0.0050 ± 0.0016 | 1434.7 ± 4.9 (1437.4) | +7.18% | 6 | 1.543 |
| 1 / 2:1 / 2 | 0.02 | 1.54 ± 0.09 | 2.62 ± 0.19 | 0.0183 | 0.0189 ± 0.0020 | 1392.4 ± 5.5 (1397.3) | +8.57% | 6 | 1.498 |
| 1 / 2:1 / 2 | 0.005 | 2.33 ± 0.12 | 3.21 ± 0.17 | 0.0045 | 0.0049 ± 0.0021 | 1434.4 ± 6.3 (1436.8) | +7.16% | 6 | 1.543 |
| 1 / 4:1 / 0 | 0.02 | 1.75 ± 0.14 | 2.00 ± 0.00 | 0.0190 | 0.0196 ± 0.0015 | 1297.5 ± 6.7 (1304.7) | +1.17% | 6 | 1.387 |
| 1 / 4:1 / 0 | 0.005 | 2.38 ± 0.24 | 2.88 ± 0.12 | 0.0047 | 0.0052 ± 0.0011 | 1359.9 ± 9.8 (1364.5) | +1.59% | 6 | 1.454 |
| 1 / 4:1 / 2 | 0.02 | 1.71 ± 0.17 | 2.04 ± 0.09 | 0.0191 | 0.0195 ± 0.0020 | 1298.0 ± 8.5 (1305.3) | +1.21% | 6 | 1.388 |
| 1 / 4:1 / 2 | 0.005 | 2.50 ± 0.20 | 2.83 ± 0.12 | 0.0048 | 0.0050 ± 0.0011 | 1360.8 ± 9.7 (1365.2) | +1.66% | 6 | 1.455 |
| 5 / 1:1 / 0 | 0.02 | 1.92 ± 0.31 | 2.33 ± 0.12 | 0.0185 | 0.0189 ± 0.0037 | 1389.0 ± 4.8 (1394.9) | +8.30% | 6 | 1.197 |
| 5 / 1:1 / 0 | 0.005 | 2.83 ± 0.24 | 3.42 ± 0.31 | 0.0046 | 0.0047 ± 0.0012 | 1418.9 ± 5.2 (1422.0) | +6.00% | 6 | 1.223 |
| 5 / 1:1 / 2 | 0.02 | 2.08 ± 0.12 | 2.33 ± 0.12 | 0.0187 | 0.0189 ± 0.0025 | 1387.7 ± 5.2 (1393.5) | +8.20% | 6 | 1.196 |
| 5 / 1:1 / 2 | 0.005 | 3.12 ± 0.12 | 3.17 ± 0.12 | 0.0045 | 0.0045 ± 0.0012 | 1419.1 ± 5.2 (1422.0) | +6.01% | 6 | 1.223 |
| 5 / 2:1 / 0 | 0.02 | 1.83 ± 0.12 | 2.42 ± 0.12 | 0.0187 | 0.0188 ± 0.0011 | 1362.4 ± 4.8 (1367.9) | +6.23% | 6 | 1.252 |
| 5 / 2:1 / 0 | 0.005 | 2.79 ± 0.22 | 3.33 ± 0.24 | 0.0046 | 0.0047 ± 0.0011 | 1402.4 ± 5.8 (1405.3) | +4.76% | 6 | 1.289 |
| 5 / 2:1 / 2 | 0.02 | 2.00 ± 0.14 | 2.17 ± 0.19 | 0.0196 | 0.0193 ± 0.0017 | 1358.2 ± 8.1 (1364.0) | +5.90% | 6 | 1.248 |
| 5 / 2:1 / 2 | 0.005 | 2.79 ± 0.17 | 3.33 ± 0.12 | 0.0045 | 0.0047 ± 0.0009 | 1401.7 ± 5.9 (1404.6) | +4.71% | 6 | 1.288 |
| 5 / 4:1 / 0 | 0.02 | 1.79 ± 0.09 | 2.04 ± 0.09 | 0.0187 | 0.0192 ± 0.0020 | 1284.1 ± 6.5 (1291.6) | +0.12% | 6 | 1.290 |
| 5 / 4:1 / 0 | 0.005 | 2.54 ± 0.27 | 3.17 ± 0.19 | 0.0047 | 0.0050 ± 0.0007 | 1338.9 ± 4.7 (1344.1) | +0.02% | 6 | 1.345 |
| 5 / 4:1 / 2 | 0.02 | 1.83 ± 0.12 | 2.00 ± 0.00 | 0.0190 | 0.0194 ± 0.0017 | 1282.5 ± 5.9 (1290.1) | -0.00% | 6 | 1.289 |
| 5 / 4:1 / 2 | 0.005 | 2.67 ± 0.31 | 3.12 ± 0.12 | 0.0047 | 0.0051 ± 0.0007 | 1338.6 ± 5.8 (1344.0) | -0.00% | 6 | 1.345 |
| 10 / 1:1 / 0 | 0.02 | 1.50 ± 0.00 | 1.58 ± 0.12 | 0.0176 | 0.0189 ± 0.0010 | 1368.2 ± 4.9 (1373.7) | +6.68% | 6 | 1.082 |
| 10 / 1:1 / 0 | 0.005 | 2.42 ± 0.19 | 2.58 ± 0.19 | 0.0042 | 0.0049 ± 0.0008 | 1394.9 ± 3.8 (1398.8) | +4.21% | 6 | 1.103 |
| 10 / 1:1 / 2 | 0.02 | 1.92 ± 0.19 | 1.58 ± 0.19 | 0.0168 | 0.0184 ± 0.0022 | 1375.0 ± 6.8 (1379.7) | +7.21% | 6 | 1.087 |
| 10 / 1:1 / 2 | 0.005 | 2.67 ± 0.19 | 2.88 ± 0.24 | 0.0048 | 0.0054 ± 0.0009 | 1397.5 ± 4.8 (1400.8) | +4.40% | 6 | 1.105 |
| 10 / 2:1 / 0 | 0.02 | 1.83 ± 0.24 | 1.79 ± 0.39 | 0.0185 | 0.0205 ± 0.0023 | 1327.5 ± 5.3 (1333.9) | +3.51% | 6 | 1.134 |
| 10 / 2:1 / 0 | 0.005 | 2.79 ± 0.17 | 3.00 ± 0.00 | 0.0046 | 0.0056 ± 0.0006 | 1355.4 ± 6.2 (1360.6) | +1.25% | 6 | 1.158 |
| 10 / 2:1 / 2 | 0.02 | 1.71 ± 0.22 | 2.00 ± 0.00 | 0.0181 | 0.0197 ± 0.0032 | 1322.2 ± 7.8 (1328.7) | +3.09% | 6 | 1.130 |
| 10 / 2:1 / 2 | 0.005 | 2.71 ± 0.09 | 3.04 ± 0.09 | 0.0043 | 0.0053 ± 0.0006 | 1358.2 ± 6.1 (1362.8) | +1.46% | 6 | 1.161 |
| 10 / 4:1 / 0 | 0.02 | 2.00 ± 0.14 | 1.88 ± 0.19 | 0.0191 | 0.0216 ± 0.0026 | 1254.5 ± 10.0 (1262.2) | -2.18% | 6 | 1.195 |
| 10 / 4:1 / 0 | 0.005 | 2.75 ± 0.20 | 3.04 ± 0.09 | 0.0045 | 0.0060 ± 0.0006 | 1298.3 ± 8.7 (1304.4) | -3.01% | 6 | 1.237 |
| 10 / 4:1 / 2 | 0.02 | 1.67 ± 0.19 | 2.25 ± 0.00 | 0.0187 | 0.0218 ± 0.0034 | 1252.9 ± 10.2 (1260.7) | -2.30% | 6 | 1.194 |
| 10 / 4:1 / 2 | 0.005 | 2.88 ± 0.28 | 3.04 ± 0.09 | 0.0048 | 0.0062 ± 0.0006 | 1296.4 ± 7.4 (1302.6) | -3.15% | 6 | 1.235 |


**Reading.**
* **Calibration transfers; λ does not.** In all 18 variants the six-split procedure returns a feasible λ, and held-out risk lands near the target.
  * At 2 %: 0.0184–0.0218. At 0.5 %: 0.0042–0.0062.
  * Exceptions: the two 10-min/4:1 libraries (0.0216/0.0218 at 2 %; 0.0060/0.0062 at 0.5 %, SD 0.0006) and the 10-min/2:1 libraries at 0.5 %
    (0.0053/0.0056). Their held-out risk sits above target by more than one standard error (6-split SD/√6). Calibrating on smooth traces under-protects
    slightly on held-out data.
  * The calibrated λ itself moves with the conversion: λ_VM 1.50–2.08 and λ_UP 1.58–3.21 at 2 %; λ_VM 2.29–3.12 and λ_UP 2.58–3.46 at 0.5 %. So a λ is
    only meaningful together with the library it was calibrated on.
* **Smoothing and compression dominate; the deadband does not matter.** Deadband 0 vs 2 changes λ by ≤ 0.42, cost by ≤ 0.5 %, and rise1/rise10 by
  at most one UE.
  * Removing smoothing (1-min) makes traces far more volatile: rise1 P50 14–23 vs 9; σ̂_win,UP at D=20 rises from 2.6 to 4.0–5.3.
  * That raises the cost relative to the need-floor from 1.29 (standard) to 1.39–1.64 at 2 % (1.45–1.68 at 0.5 %).
  * Heavier smoothing (10-min) lowers volatility and the cost/floor ratio (1.08–1.20).
  * Raw core-min (Δalloc vs e) mixes this with each library's demand level (the need-floor ranges 861–1265), so the ratio column is the comparable one.
* At the standard conversion, the 4:1 rows with 1-min smoothing and 0 deadband stay within +1.7 % of (e). The deadband-0 twin of the standard library
  is within ±0.1 %.

### Per-UE rate model
Simulation only; not validated on hardware.
* **Where UE becomes pps.** v8sim2/v8sim10 never convert to pps explicitly. Demand is `d = S.expand(ue)*cfg.scale` in UE units of 250 kpps, and
  capacities are in the same units: `Cfg.cap_up = 5` UE per slot, `cap_vy = 4.45e6·0.93/250e3` UE per VyOS.
* **The copy.** `eng.sim2(..., load=...)` keeps the controller on the integer UE count n(t). This matches daemon v7.1.3, which plans on the agent's UE
  count; its logged `offered` is exactly n×250 k. The **loss model** instead sees `load(t) = Σ_{i<n(t)} r_i / 250`.
* **Which UEs are active.** UE identity is LIFO by index, as in the harness (`trace_run.py`: departures pop the most recent arrival), so the active set
  is UE 0..n−1.
* **Rate draws.** r_i ∈ {150, 250, 350} kpps uniform, drawn once per UE index per trace: `np.random.default_rng(20261021)`, 40 draws per trace in
  library order.
* **Prior.** The standard one, fitted on UE counts. Command: `run_cal.py --name D_rates --rates`.

## D3 per-UE rate model (rates {150,250,350} kpps, seed 20261021) — simulation only; not validated on hardware

| variant | target | λ_VM | λ_UP | cal risk | held-out risk | held-out alloc vmexist (dispatch) | Δalloc vs e | splits |
|---|---|---|---|---|---|---|---|---|
| (e) standard (250 kpps/UE) | 0.02 | 1.83 ± 0.12 | 2.00 ± 0.00 | 0.0190 | 0.0194 ± 0.0017 | 1282.5 ± 5.9 (1290.1) | -0.00% | 6 |
| (e) standard (250 kpps/UE) | 0.005 | 2.67 ± 0.31 | 3.12 ± 0.12 | 0.0047 | 0.0051 ± 0.0007 | 1338.6 ± 5.8 (1344.0) | -0.00% | 6 |
| per-UE random rate | 0.02 | 3.04 ± 0.34 | 3.38 ± 0.24 | 0.0195 | 0.0212 ± 0.0017 | 1351.3 ± 11.8 (1355.9) | +5.36% | 6 |
| per-UE random rate | 0.005 | infeasible in all splits (6) |||||||


* 2 %: the recalibration needs a much larger λ (3.04/3.38 vs 1.83/2.00) and costs **+5.4 %**. Held-out risk is 0.0212 ± 0.0017, slightly above target.
* **0.5 % is infeasible on the grid in all six splits.** Minimum cal risk is 1.56–1.88 %, always at the corner 3.5/4.5. Held-out risk at that corner is
  0.0180 ± 0.0010 at 1382.9 core-min.
* The cause is structural, not λ. With heterogeneous rates the offered load exceeds the **maximum fleet** (8 slots × 5 = 40 UE-eq on UP;
  3 VyOS = 49.6 UE-eq) in **1.63 %** of all library minutes. With the standard 250 kpps per UE it never does. That is an irreducible risk floor above
  0.5 %, so the 0.5 % target cannot be met by any λ under FMAX = 8/3. Lowest reachable risk ≈ 1.6–1.8 %.

## Commands
```
cd /home/user/experiment/qsim/r62de
P="nice -n 19 taskset -c 13,14 python3"
$P E_leads.py                                   # Task E leads → E_leads.json          (~5 s)
$P D_build.py                                   # 18 libraries → libs/, reproduction    (~10 s)
$P run_cal.py --name E_base_p90 --equiv 20      # (e) reproduction, cfg_measured        (762 s)
./chain.sh      # E_ready_p95 (--h 125,85,65), E_ready_p99 (--h 155,90,70), E_inflight_p95p99 (--h 60,180,150), D_rates (--rates)
./chainD.sh ''  # 17 library variants: run_cal.py --name D_sS_cC_dB --lib libs/lib_sS_cC_dB.json (full refine)
python3 make_report.py                          # tables → REPORT_tables.md
```
Outputs: `out/<name>.json` (per-split rows, summaries, σ̂ at D=20, library stats), `out/<name>.pkl` (per-trace result matrices), `progress.log`.
Wall time 00:58 → 03:53 (2.9 h). The run sped up partway, when the shared cores freed.

## runtimes

| run | total s | trace-sims |
|---|---|---|
| D_rates | 637 | 82340 |
| D_s10_c1_d0 | 233 | 65920 |
| D_s10_c1_d2 | 234 | 68913 |
| D_s10_c2_d0 | 254 | 77226 |
| D_s10_c2_d2 | 246 | 76710 |
| D_s10_c4_d0 | 267 | 85530 |
| D_s10_c4_d2 | 267 | 85575 |
| D_s1_c1_d0 | 802 | 90664 |
| D_s1_c1_d2 | 651 | 88754 |
| D_s1_c2_d0 | 707 | 96431 |
| D_s1_c2_d2 | 768 | 95794 |
| D_s1_c4_d0 | 490 | 102606 |
| D_s1_c4_d2 | 347 | 105255 |
| D_s5_c1_d0 | 261 | 75835 |
| D_s5_c1_d2 | 282 | 72340 |
| D_s5_c2_d0 | 331 | 79506 |
| D_s5_c2_d2 | 356 | 81429 |
| D_s5_c4_d0 | 391 | 89300 |
| E_base_p90 | 762 | 90205 |
| E_inflight_p95p99 | 695 | 91030 |
| E_ready_p95 | 768 | 89550 |
| E_ready_p99 | 747 | 90466 |

## Limitations
* The lead in the simulator is deterministic per layer. Task E maps a tail quantile onto every action, which overstates the UP tail.
* Bootstrap-free: the spread reported is the 6-split SD.
* The per-UE rate draw is a single seed.
* rise1/rise10 are computed on the 60-minute experiment traces after conversion.
