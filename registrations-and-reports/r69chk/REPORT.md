# r69chk (spec §4.137)

Simulation only; frozen-file md5 after: 3daf1387 7a2b02ec ecdfff61 4697713c b24eae16 edb8e00c (before: 3daf1387 7a2b02ec ecdfff61 4697713c b24eae16 edb8e00c). Bench idle.

## Item 1: A-PL physical constraints (code read; line numbers)

| question | A-PL per-slot (r68unif/ctlgen.py) | A-PL fleet (r68unif/nest2gen.py, variant 'apl') | v8sim11 CtlSigma / Phys | same? |
|---|---|---|---|---|
| (a) slot waits for a ready worker; lead start | L32 no slot while one boots; L33 position wait `rep_up >= wk_ready*spw`; L34 dispatch through Phys.scale_out_up, which returns "noworker" unless the slot's worker is ready (v8sim11.py L88-92); lead counted from the dispatch (slot_api_s, L93), which only happens on a ready worker | L121 slot serial; L122 position wait `rep >= ready_wk*spw`; L124 ready = dispatch + H; 'apl' (L59) changes none of these | CtlSigma L294-296 (same three lines); Phys L88-93 | yes |
| (b) worker with slots cannot be released | L59 `eff_up > (eff_wk-1)*spw` -> keep; L60-61 idle worker only (no pods, age, idle_min); Phys.delete_wk refuses a worker with any slot (v8sim11.py L136) | L153 idle_min; L154 `eff_up > (eff_wk-1)*spw` -> keep | CtlSigma L319-322; Phys L136 | yes |
| (c) VyOS / UP ordering | replenish order vy, wk, up (L24); release order up, vy, wk (L39); no VyOS-UP dependency | same loops; no VyOS-UP dependency | CtlSigma L286 / L301; deploy_vy independent | yes |

The A-PL flags change only planning-level lines: the worker target (ctlgen L18, no WK > UP projection), the worker release need (L52) and the release test (L56 / L64, v6-type `target <= n - 1`). No A-PL-phys was needed.

## Item 2: B5c1 (4.0 / L2) per-minute, t6 and t7

| trace | run / sim | min-0 slot / VyOS / worker | alloc_vm | HPA ticks / raw < cur / held by the 600 s window | first divergence vs sim (initial_fleet) | first divergence vs sim (hardware min-0 start) |
|---|---|---|---|---|---|---|
| t6 | r406 | 7 / 3 / 4 | (rq) | 120 / 37 / 35 | wk: 0 (hardware holds more, to min 5); vy: 0 (hardware holds more, to min 17); slot: 0 (hardware holds more, to min 7) | wk: 5 (hardware holds more, to min 5); vy: 51 (hardware holds less, to min 51); slot: 3 (hardware holds more, to min 7) |
| t6 | r412 | 7 / 3 / 4 | (rq) | 120 / 39 / 37 | wk: 0 (hardware holds more, to min 5); vy: 0 (hardware holds more, to min 17); slot: 0 (hardware holds more, to min 7) | wk: 5 (hardware holds more, to min 5); vy: 51 (hardware holds less, to min 51); slot: 3 (hardware holds more, to min 7) |
| t6 | r417 | 7 / 3 / 4 | (rq) | 119 / 34 / 32 | wk: 0 (hardware holds more, to min 5); vy: 0 (hardware holds more, to min 17); slot: 0 (hardware holds more, to min 7) | wk: 5 (hardware holds more, to min 5); vy: 51 (hardware holds less, to min 51); slot: 3 (hardware holds more, to min 7) |
| t6 | sim, initial_fleet | 6 / 2 / 3 | 1375.3 | 120 / 28 / 28 | | |
| t6 | sim, hardware min-0 start | 7 / 3 / 4 | 1427.3 | 120 / 34 / 28 | | |
| t7 | r434 | 7 / 3 / 4 | (rq) | 119 / 48 / 39 | wk: none; vy: 0 (hardware holds more, to min 1); slot: 1 (hardware holds more, to min 1) | wk: none; vy: 39 (hardware holds less, to min 40); slot: 1 (hardware holds more, to min 1) |
| t7 | r440 | 7 / 3 / 4 | (rq) | 119 / 49 / 40 | wk: none; vy: 0 (hardware holds more, to min 1); slot: 1 (hardware holds more, to min 1) | wk: none; vy: 39 (hardware holds less, to min 40); slot: 1 (hardware holds more, to min 1) |
| t7 | r445 | 7 / 3 / 4 | (rq) | 120 / 49 / 39 | wk: none; vy: 0 (hardware holds more, to min 1); slot: 48 (hardware holds less, to min 48) | wk: none; vy: 40 (hardware holds less, to min 40); slot: 48 (hardware holds less, to min 48) |
| t7 | sim, initial_fleet | 7 / 2 / 4 | 1410.5 | 120 / 48 / 40 | | |
| t7 | sim, hardware min-0 start | 7 / 3 / 4 | 1414.0 | 120 / 48 / 40 | | |

Hardware alloc_vm (rq_metrics): t6 r406 / r412 / r417 = 1433 / 1433 / 1433; t7 r434 / r440 / r445 = 1412 / 1413 / 1414. Figures: fig_t6_b5c1_trace.pdf, fig_t7_b5c1_trace.pdf.

Checks (b):
- HPA scale-down stabilization window: manifest B5c1_slo.yaml `HPA_DOWN_WINDOW=600s` (daemon log `win=10m0s`); simulator `HPA(down=600)` with the same max-over-window rule (internal/hbo/hpa.go Step vs v8sim11.HPA.step) -> same.
- Holt leads: manifest `B5_LEAD_TICKS_VY=5`, UP and WK at their defaults 2 and 5; simulator lead (2, 5, 5); both use max(x, L + ticks·T) -> same. (Code defaults VY 4 / window 300 s are overridden by the manifest.)
- DASA: μ 14, n0 1, kmax 2, margin 0.8 in both -> same.
- Scale-ins held by the window: hardware 35 / 37 / 32 ticks (t6), simulator 28; the hardware runs never released a worker (240 worker-min in all three).
- Run-to-run: the three t6 runs have identical worker and VyOS series and the same three decisions (SCALE_OUT_UP at about min 17, DELETE_VYOS at about min 51, SCALE_IN_UP at about min 59) -> no run-to-run variation.
- Start fleet: every hardware run starts at 7 slots / 3 VyOS / 4 workers (the warm-in end state). v8sim11.initial_fleet("B4", 24, target 4, μ 14) gives 6 / 2 / 3. Started from 7 / 3 / 4 the simulator gives 1427.3 (hardware 1433.0), and the remaining divergence is a slot released at second 0 and a worker at 270 s: the simulated HPA starts without the warm-in history that holds the hardware's scale-down.
- (c) t7: initial_fleet("B4", 27) = 7 / 2 / 4, the same slots and workers as the hardware, and only one VyOS fewer (added at 90 s). 24 / 4.0 = 6 slots exactly on t6 against ceil(27 / 4.0) = 7 on t7: the start demand alone decides whether the simulated fleet starts one slot and one worker below the hardware's warm-in fleet.

## Item 3: S8 = S4 + R2 (w 1600)

Deployed (nest2 six-split mean): 2: λ 1.54/1.75, infeasible splits 0/6, nest2 held-out risk 1.99 % vmexist 1272.6 flaps 2.70; 05: λ 2.58/2.92, infeasible splits 0/6, nest2 held-out risk 0.52 % vmexist 1331.5 flaps 3.15

### U1 (mp)

| group | arm | bucket risk (%) | max/min | max/min (non-zero min) | std (pp) | Spearman | slope [95 % CI] |
|---|---|---|---|---|---|---|---|
| 2 % | S4b | 3.5 / 2.4 / 2.2 / 2.3 / 1.9 / 2.4 / 1.7 / 2.0 / 1.8 / 1.5 | 2.35 | 2.35 | 0.53 | -0.144 | -3.64 [-4.91, -2.29] |
| 2 % | S8_2 | 4.0 / 2.6 / 2.4 / 2.5 / 1.9 / 2.1 / 1.8 / 1.5 / 1.1 / 0.8 | 5.07 | 5.07 | 0.86 | -0.281 | -6.43 [-7.67, -5.19] |
| 2 % | B4_3.75_300 | 5.0 / 2.6 / 2.8 / 2.2 / 1.3 / 1.4 / 0.9 / 0.6 / 0.2 / 0.2 | 23.05 | 23.05 | 1.40 | -0.436 | -10.31 [-11.74, -8.89] |
| 2 % | B5_4.0_L2 | 5.2 / 3.2 / 3.3 / 2.7 / 1.7 / 1.7 / 1.0 / 1.0 / 0.7 / 0.5 | 10.90 | 10.90 | 1.42 | -0.443 | -10.57 [-11.85, -9.34] |
| 2 % | B6_0.775 | 3.6 / 1.9 / 1.8 / 1.5 / 1.1 / 1.2 / 0.7 / 0.5 / 0.3 / 0.3 | 11.52 | 11.52 | 0.93 | -0.375 | -6.86 [-7.95, -5.74] |
| 0.5 % | S4a | 1.0 / 0.4 / 0.6 / 0.5 / 0.4 / 0.7 / 0.3 / 0.3 / 0.2 / 0.1 | 7.04 | 7.04 | 0.24 | -0.144 | -1.49 [-2.15, -0.82] |
| 0.5 % | S8_05 | 1.2 / 0.3 / 0.5 / 0.4 / 0.4 / 0.6 / 0.2 / 0.3 / 0.2 / 0.1 | 23.02 | 23.02 | 0.30 | -0.167 | -1.83 [-2.51, -1.17] |
| 0.5 % | B4_3.0_300 | 1.6 / 0.3 / 0.2 / 0.2 / 0.2 / 0.2 / 0.1 / 0.0 / 0.0 / 0.0 | inf | 81.00 | 0.46 | -0.261 | -2.75 [-3.62, -1.93] |
| 0.5 % | B5_3.5_L1 | 2.1 / 0.8 / 0.7 / 0.6 / 0.4 / 0.6 / 0.3 / 0.1 / 0.1 / 0.1 | 41.23 | 41.23 | 0.57 | -0.323 | -3.78 [-4.67, -2.88] |
| 0.5 % | B6_0.7 | 2.1 / 0.8 / 0.7 / 0.5 / 0.3 / 0.5 / 0.3 / 0.1 / 0.0 / 0.1 | 68.72 | 68.72 | 0.58 | -0.335 | -3.81 [-4.74, -2.96] |

### U1 (rise1)

| group | arm | bucket risk (%) | max/min | max/min (non-zero min) | std (pp) | Spearman | slope [95 % CI] |
|---|---|---|---|---|---|---|---|
| 2 % | S4b | 0.7 / 1.0 / 1.6 / 2.9 / 2.3 / 3.7 / 3.8 / 5.1 | 7.63 | 7.63 | 1.44 | +0.500 | +0.44 [+0.39, +0.49] |
| 2 % | S8_2 | 0.7 / 1.4 / 1.9 / 2.4 / 2.0 / 3.3 / 3.3 / 4.5 | 6.06 | 6.06 | 1.13 | +0.427 | +0.35 [+0.31, +0.40] |
| 2 % | B4_3.75_300 | 1.0 / 1.9 / 0.8 / 1.5 / 1.5 / 2.5 / 2.5 / 3.8 | 4.73 | 4.73 | 0.90 | +0.309 | +0.25 [+0.18, +0.31] |
| 2 % | B5_4.0_L2 | 1.2 / 1.7 / 1.5 / 2.2 / 2.0 / 3.0 / 3.1 / 4.5 | 3.85 | 3.85 | 1.03 | +0.328 | +0.31 [+0.25, +0.37] |
| 2 % | B6_0.775 | 0.6 / 1.3 / 0.8 / 1.4 / 1.3 / 2.0 / 1.9 / 2.7 | 4.51 | 4.51 | 0.63 | +0.299 | +0.19 [+0.15, +0.24] |
| 0.5 % | S4a | 0.0 / 0.0 / 0.1 / 0.3 / 0.3 / 1.0 / 1.3 / 2.2 | inf | 44.30 | 0.74 | +0.454 | +0.20 [+0.17, +0.24] |
| 0.5 % | S8_05 | 0.0 / 0.2 / 0.1 / 0.3 / 0.3 / 0.9 / 1.0 / 1.9 | 64.91 | 64.91 | 0.59 | +0.400 | +0.16 [+0.13, +0.20] |
| 0.5 % | B4_3.0_300 | 0.1 / 0.4 / 0.1 / 0.1 / 0.2 / 0.7 / 0.2 / 1.0 | 13.29 | 13.29 | 0.31 | +0.189 | +0.06 [+0.04, +0.09] |
| 0.5 % | B5_3.5_L1 | 0.2 / 0.5 / 0.3 / 0.5 / 0.6 / 1.1 / 0.7 / 1.5 | 7.40 | 7.40 | 0.40 | +0.231 | +0.12 [+0.09, +0.15] |
| 0.5 % | B6_0.7 | 0.2 / 0.6 / 0.3 / 0.5 / 0.6 / 1.0 / 0.6 / 1.3 | 6.28 | 6.28 | 0.34 | +0.202 | +0.09 [+0.06, +0.12] |

### (a) uniformity kept? (mp; r68unif rule vs three baselines, and S8 - S4 std paired-bootstrap CI)

- 2 %: S8 vs B4c2: max/min 5.07 vs 23.05, std 0.86 vs 1.40 pp, slope CI disjoint True -> more uniform
- 2 %: S8 vs B5c1: max/min 5.07 vs 10.90, std 0.86 vs 1.42 pp, slope CI disjoint True -> more uniform
- 2 %: S8 vs B6: max/min 5.07 vs 11.52, std 0.86 vs 0.93 pp, slope CI disjoint False -> not
- 2 %: S8 - S4b std +0.32 pp, paired 95 % CI [+0.19, +0.43] -> excludes 0
- 0.5 %: S8 vs B4c2: max/min 23.02 vs 81.00, std 0.30 vs 0.46 pp, slope CI disjoint False -> not
- 0.5 %: S8 vs B5c1: max/min 23.02 vs 41.23, std 0.30 vs 0.57 pp, slope CI disjoint True -> more uniform
- 0.5 %: S8 vs B6: max/min 23.02 vs 68.72, std 0.30 vs 0.58 pp, slope CI disjoint True -> more uniform
- 0.5 %: S8 - S4a std +0.06 pp, paired 95 % CI [-0.02, +0.13] -> contains 0

### (b)(c) library

- 2 %: S8 flaps 2.93 (S4b 7.87); alloc_vm 1271.8 vs 1282.0 (-0.80 %); risk 2.08 % vs 2.18 % (-0.10 pp); worker / VyOS / slot min 218.3 / 148.4 / 399.8 vs 219.4 / 152.9 / 397.5
- 0.5 %: S8 flaps 3.82 (S4a 6.29); alloc_vm 1331.4 vs 1337.1 (-0.43 %); risk 0.43 % vs 0.45 % (-0.02 pp); worker / VyOS / slot min 225.7 / 159.9 / 418.1 vs 226.9 / 161.7 / 416.3

### Table B (mp, 2 %): S8 against each baseline

| bucket | baseline | Δcost % | Δrisk pp | Δworker-min | verdict |
|---|---|---|---|---|---|
| D1 | B4c2 | +4.27 | -1.00 | +8.6 | same level |
| D1 | B5c1 | +3.37 | -1.21 | +6.2 | same level |
| D1 | B6 | +0.48 | +0.44 | +3.4 | same level |
| D2 | B4c2 | +1.84 | +0.09 | +5.2 | same level |
| D2 | B5c1 | +1.48 | -0.58 | +3.0 | same level |
| D2 | B6 | -0.04 | +0.76 | +2.4 | same level |
| D3 | B4c2 | +0.34 | -0.33 | +2.3 | same level |
| D3 | B5c1 | +0.73 | -0.88 | +1.4 | same level |
| D3 | B6 | -0.78 | +0.63 | +0.5 | same level |
| D4 | B4c2 | -0.78 | +0.30 | +1.1 | same level |
| D4 | B5c1 | +0.20 | -0.20 | +1.9 | same level |
| D4 | B6 | -1.50 | +1.04 | -0.0 | same level |
| D5 | B4c2 | -1.44 | +0.67 | -0.1 | same level |
| D5 | B5c1 | -0.58 | +0.26 | +0.3 | same level |
| D5 | B6 | -1.89 | +0.82 | -0.3 | same level |
| D6 | B4c2 | -1.79 | +0.70 | -0.2 | same level |
| D6 | B5c1 | -0.65 | +0.41 | +0.5 | same level |
| D6 | B6 | -1.80 | +0.84 | -0.5 | same level |
| D7 | B4c2 | -2.08 | +0.91 | -0.5 | same level |
| D7 | B5c1 | -0.85 | +0.80 | +0.5 | same level |
| D7 | B6 | -1.88 | +1.09 | -0.3 | same level |
| D8 | B4c2 | -1.88 | +0.88 | -0.5 | same level |
| D8 | B5c1 | -0.85 | +0.51 | +0.5 | same level |
| D8 | B6 | -1.56 | +0.97 | -0.2 | same level |
| D9 | B4c2 | -1.50 | +0.92 | -0.1 | same level |
| D9 | B5c1 | -0.72 | +0.42 | +0.7 | same level |
| D9 | B6 | -1.29 | +0.83 | +0.0 | same level |
| D10 | B4c2 | -0.54 | +0.54 | -0.1 | same level |
| D10 | B5c1 | -0.26 | +0.31 | +0.2 | same level |
| D10 | B6 | -0.43 | +0.46 | +0.0 | same level |
| library | B4c2 | -0.59 | +0.37 | +1.6 | same level |
| library | B5c1 | +0.04 | -0.02 | +1.5 | same level |
| library | B6 | -1.14 | +0.79 | +0.5 | same level |

### Table B (mp, 0.5 %): S8 against each baseline

| bucket | baseline | Δcost % | Δrisk pp | Δworker-min | verdict |
|---|---|---|---|---|---|
| D1 | B4c2 | +2.89 | -0.45 | +8.2 | same level |
| D1 | B5c1 | +6.09 | -0.93 | +12.6 | same level |
| D1 | B6 | +5.88 | -0.93 | +13.9 | same level |
| D2 | B4c2 | -1.01 | +0.00 | +0.8 | same level |
| D2 | B5c1 | +2.79 | -0.44 | +7.4 | same level |
| D2 | B6 | +3.15 | -0.47 | +9.4 | same level |
| D3 | B4c2 | -2.10 | +0.32 | -1.2 | same level |
| D3 | B5c1 | +1.48 | -0.15 | +4.8 | same level |
| D3 | B6 | +1.80 | -0.12 | +7.0 | same level |
| D4 | B4c2 | -2.68 | +0.27 | -2.2 | same level |
| D4 | B5c1 | +0.78 | -0.13 | +3.3 | same level |
| D4 | B6 | +0.88 | -0.07 | +4.7 | same level |
| D5 | B4c2 | -2.36 | +0.18 | -1.7 | cheaper |
| D5 | B5c1 | +0.09 | -0.01 | +1.5 | same level |
| D5 | B6 | +0.11 | +0.03 | +2.8 | same level |
| D6 | B4c2 | -2.07 | +0.41 | -0.9 | same level |
| D6 | B5c1 | +0.08 | +0.04 | +1.9 | same level |
| D6 | B6 | -0.01 | +0.15 | +2.3 | same level |
| D7 | B4c2 | -1.44 | +0.16 | -0.3 | same level |
| D7 | B5c1 | -0.16 | -0.03 | +0.9 | same level |
| D7 | B6 | -0.27 | -0.06 | +1.0 | same level |
| D8 | B4c2 | -1.06 | +0.30 | -0.4 | same level |
| D8 | B5c1 | -0.29 | +0.18 | +0.4 | same level |
| D8 | B6 | -0.34 | +0.20 | +0.4 | same level |
| D9 | B4c2 | -0.54 | +0.18 | -0.1 | same level |
| D9 | B5c1 | -0.11 | +0.14 | +0.3 | same level |
| D9 | B6 | -0.12 | +0.17 | +0.3 | same level |
| D10 | B4c2 | -0.16 | +0.05 | -0.1 | same level |
| D10 | B5c1 | -0.04 | -0.07 | +0.1 | same level |
| D10 | B6 | -0.03 | -0.07 | +0.1 | same level |
| library | B4c2 | -1.14 | +0.14 | +0.2 | same level |
| library | B5c1 | +0.87 | -0.14 | +3.3 | same level |
| library | B6 | +0.90 | -0.12 | +4.2 | same level |

### Table B (rise1, 2 %): S8 against each baseline

| bucket | baseline | Δcost % | Δrisk pp | Δworker-min | verdict |
|---|---|---|---|---|---|
| D1 | B4c2 | -0.49 | -0.27 | +1.9 | same level |
| D1 | B5c1 | -0.06 | -0.43 | +1.4 | same level |
| D1 | B6 | -0.75 | +0.15 | +1.0 | same level |
| D3 | B4c2 | -0.49 | -0.56 | +1.7 | same level |
| D3 | B5c1 | +0.14 | -0.35 | +1.5 | same level |
| D3 | B6 | -1.01 | +0.12 | +0.4 | same level |
| D4 | B4c2 | -1.10 | +1.14 | +1.0 | same level |
| D4 | B5c1 | -0.38 | +0.47 | +0.9 | same level |
| D4 | B6 | -1.40 | +1.15 | -0.0 | same level |
| D6 | B4c2 | -0.64 | +0.83 | +1.4 | same level |
| D6 | B5c1 | -0.03 | +0.19 | +1.1 | same level |
| D6 | B6 | -1.26 | +0.95 | +0.1 | same level |
| D7 | B4c2 | -0.86 | +0.51 | +1.1 | same level |
| D7 | B5c1 | -0.30 | +0.03 | +1.3 | same level |
| D7 | B6 | -1.46 | +0.76 | +0.0 | same level |
| D8 | B4c2 | -0.50 | +0.83 | +1.8 | same level |
| D8 | B5c1 | +0.21 | +0.30 | +2.0 | same level |
| D8 | B6 | -1.20 | +1.36 | +0.8 | same level |
| D9 | B4c2 | -0.69 | +0.81 | +1.3 | same level |
| D9 | B5c1 | +0.27 | +0.14 | +2.3 | same level |
| D9 | B6 | -1.14 | +1.38 | +0.8 | same level |
| D10 | B4c2 | +0.47 | +0.74 | +2.7 | same level |
| D10 | B5c1 | +1.03 | -0.01 | +3.1 | same level |
| D10 | B6 | -1.25 | +1.83 | +0.9 | same level |
| library | B4c2 | -0.59 | +0.37 | +1.6 | same level |
| library | B5c1 | +0.04 | -0.02 | +1.5 | same level |
| library | B6 | -1.14 | +0.79 | +0.5 | same level |

### Table B (rise1, 0.5 %): S8 against each baseline

| bucket | baseline | Δcost % | Δrisk pp | Δworker-min | verdict |
|---|---|---|---|---|---|
| D1 | B4c2 | -1.31 | -0.05 | +0.1 | same level |
| D1 | B5c1 | +0.71 | -0.18 | +2.9 | same level |
| D1 | B6 | +0.99 | -0.18 | +4.1 | same level |
| D3 | B4c2 | -1.14 | -0.24 | +0.3 | same level |
| D3 | B5c1 | +0.89 | -0.29 | +3.5 | same level |
| D3 | B6 | +1.11 | -0.45 | +4.7 | same level |
| D4 | B4c2 | -1.19 | +0.00 | -0.1 | same level |
| D4 | B5c1 | +0.65 | -0.22 | +2.8 | same level |
| D4 | B6 | +0.68 | -0.17 | +3.6 | same level |
| D6 | B4c2 | -1.51 | +0.25 | -0.8 | same level |
| D6 | B5c1 | +0.58 | -0.22 | +2.7 | same level |
| D6 | B6 | +0.64 | -0.13 | +3.5 | same level |
| D7 | B4c2 | -1.02 | +0.10 | +0.7 | same level |
| D7 | B5c1 | +0.77 | -0.24 | +3.0 | same level |
| D7 | B6 | +0.64 | -0.26 | +3.7 | same level |
| D8 | B4c2 | -0.96 | +0.17 | +0.5 | same level |
| D8 | B5c1 | +1.03 | -0.20 | +3.8 | same level |
| D8 | B6 | +0.99 | -0.13 | +4.6 | same level |
| D9 | B4c2 | -1.02 | +0.81 | +0.6 | same level |
| D9 | B5c1 | +1.00 | +0.25 | +3.6 | same level |
| D9 | B6 | +0.76 | +0.36 | +4.1 | same level |
| D10 | B4c2 | -0.45 | +0.90 | +1.3 | same level |
| D10 | B5c1 | +2.03 | +0.34 | +5.9 | more expensive |
| D10 | B6 | +1.47 | +0.58 | +6.2 | same level |
| library | B4c2 | -1.14 | +0.14 | +0.2 | same level |
| library | B5c1 | +0.87 | -0.14 | +3.3 | same level |
| library | B6 | +0.90 | -0.12 | +4.2 | same level |

### U2: S8 per-layer share of B1 (slot / worker / VyOS), mp deciles

| group | arm | D1 | D2 | D3 | D4 | D5 | D6 | D7 | D8 | D9 | D10 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2 % | S4b | 0.58/0.72/0.63 | 0.69/0.81/0.72 | 0.74/0.86/0.77 | 0.80/0.91/0.81 | 0.84/0.94/0.85 | 0.87/0.96/0.88 | 0.90/0.98/0.92 | 0.93/0.99/0.95 | 0.95/1.00/0.97 | 0.98/1.00/0.99 |
| 2 % | S8_2 | 0.59/0.71/0.61 | 0.70/0.80/0.70 | 0.75/0.85/0.75 | 0.81/0.90/0.78 | 0.84/0.93/0.81 | 0.87/0.95/0.85 | 0.90/0.98/0.89 | 0.93/0.99/0.92 | 0.95/0.99/0.95 | 0.98/1.00/0.98 |
| 0.5 % | S4a | 0.63/0.78/0.69 | 0.73/0.87/0.78 | 0.79/0.91/0.83 | 0.85/0.95/0.88 | 0.88/0.97/0.92 | 0.91/0.98/0.94 | 0.94/0.99/0.97 | 0.96/1.00/0.98 | 0.98/1.00/0.99 | 0.99/1.00/1.00 |
| 0.5 % | S8_05 | 0.64/0.77/0.68 | 0.74/0.86/0.77 | 0.80/0.90/0.81 | 0.85/0.95/0.86 | 0.89/0.97/0.90 | 0.91/0.98/0.93 | 0.94/0.99/0.96 | 0.96/1.00/0.98 | 0.98/1.00/0.99 | 0.99/1.00/1.00 |

### t3-t8 per trace (violation minutes / alloc_vm / flaps)

| trace | arm | per-slot R38 off | per-slot R38 on (frozen default) | fleet nest2 (vmexist) |
|---|---|---|---|---|
| t3 | 2 % S8 | [3, 4, 5, 7, 8] / 1177 / 3 | [3, 4, 5, 7, 8] / 1177 / 3 | 3 min / 1167 |
| t3 | 2 % S4b | [3, 4, 5, 7, 8] / 1138 / 4 | [3, 4, 5, 7, 8] / 1138 / 4 | 3 min / 1129 |
| t3 | 0.5 % S8 | [3, 4, 5] / 1236 / 3 | [3, 4, 5] / 1236 / 3 | 3 min / 1235 |
| t3 | 0.5 % S4a | [3, 4, 5] / 1255 / 5 | [3, 4, 5] / 1254 / 5 | 3 min / 1257 |
| t4 | 2 % S8 | [20] / 1395 / 0 | [20, 21] / 1395 / 0 | 3 min / 1397 |
| t4 | 2 % S4b | [20] / 1425 / 0 | [20, 21, 49, 50] / 1425 / 0 | 1 min / 1427 |
| t4 | 0.5 % S8 | [] / 1446 / 3 | [20, 21] / 1446 / 3 | 0 min / 1448 |
| t4 | 0.5 % S4a | [] / 1452 / 2 | [20, 21] / 1452 / 2 | 0 min / 1454 |
| t5 | 2 % S8 | [] / 1457 / 3 | [] / 1457 / 3 | 0 min / 1459 |
| t5 | 2 % S4b | [] / 1453 / 2 | [] / 1453 / 2 | 0 min / 1454 |
| t5 | 0.5 % S8 | [] / 1463 / 2 | [] / 1463 / 2 | 0 min / 1464 |
| t5 | 0.5 % S4a | [] / 1463 / 3 | [] / 1463 / 3 | 0 min / 1464 |
| t6 | 2 % S8 | [] / 1385 / 2 | [17, 18, 43] / 1387 / 2 | 1 min / 1388 |
| t6 | 2 % S4b | [] / 1390 / 5 | [17, 18, 32, 33, 43] / 1397 / 4 | 0 min / 1393 |
| t6 | 0.5 % S8 | [] / 1438 / 2 | [17] / 1438 / 2 | 0 min / 1439 |
| t6 | 0.5 % S4a | [] / 1448 / 5 | [17, 43, 44] / 1448 / 5 | 0 min / 1449 |
| t7 | 2 % S8 | [] / 1396 / 2 | [] / 1396 / 2 | 0 min / 1393 |
| t7 | 2 % S4b | [] / 1396 / 5 | [] / 1396 / 5 | 0 min / 1395 |
| t7 | 0.5 % S8 | [] / 1431 / 5 | [] / 1431 / 5 | 0 min / 1430 |
| t7 | 0.5 % S4a | [] / 1432 / 4 | [] / 1432 / 4 | 0 min / 1430 |
| t8 | 2 % S8 | [20, 21] / 1050 / 4 | [20, 21] / 1050 / 4 | 1 min / 1039 |
| t8 | 2 % S4b | [20, 21] / 1041 / 7 | [20, 21] / 1041 / 7 | 1 min / 1017 |
| t8 | 0.5 % S8 | [20, 21] / 1088 / 6 | [20, 21] / 1088 / 6 | 1 min / 1071 |
| t8 | 0.5 % S4a | [20, 21] / 1085 / 11 | [20, 21] / 1085 / 11 | 1 min / 1060 |

### Four verdicts

- 2 %: (a) no; (b) yes (2.93); (c) Δcost -0.80 %, Δrisk -0.10 pp; (d) t4 per-slot R38 on [20, 21, 49, 50] -> [20, 21] (became [20, 21]), t8 per-slot R38 off alloc_vm 1041 -> 1050
- 0.5 %: (a) no; (b) yes (3.82); (c) Δcost -0.43 %, Δrisk -0.02 pp; (d) t4 per-slot R38 on [20, 21] -> [20, 21] (became [20, 21]), t8 per-slot R38 off alloc_vm 1085 -> 1088


## Conclusions (registered reading rules only)

1. A-PL already obeys the three execution-layer constraints of CtlSigma (same lines; only planning-level lines differ), so by the §4.137 rule the item-3 attribution is kept. Note: the attribution registered and reported in §4.136 was "in between", not "additive margin"; this check does not change it.
2. The B5c1 t6 gap is not an HPA cooldown or lead implementation difference (both identical), not hardware metric jitter, and not run-to-run variation (three identical runs). It comes from the simulator's start state: initial_fleet 6 / 2 / 3 against the warm-in fleet 7 / 3 / 4, plus an empty HPA history at minute 0. Category: start-setting deviation of the simulator (the extra class registered in §4.137). From the hardware start the gap is 1427.3 against 1433.0. On t7 the start demand of 27 UEs gives the same slots and workers, which is why t7 matches.
3. S8 = S4 + R2:
   - (a) No: S8 is more uniform than B4c2 and B5c1 but not than B6 at 2 % (slope CIs overlap), and not than B4c2 at 0.5 %. Its std exceeds S4b's by 0.32 pp (CI [+0.19, +0.43]) at 2 %; at 0.5 % it is within S4a's (CI [−0.02, +0.13]).
   - (b) Yes: library flaps 2.93 and 3.82 (S4 7.87 and 6.29).
   - (c) Library alloc_vm −0.80 % / −0.43 % and risk −0.10 / −0.02 pp against S4.
   - (d) t4 per-slot R38-on: [20, 21, 49, 50] → [20, 21] at 2 %; S4a was already [20, 21]. t8 per-slot cost +9 and +3 core-min.

