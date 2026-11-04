# r68unif (spec §4.136)

Simulation only. Per-slot v8sim11, R38 off, whole library, r67band runner and bucket thresholds. (1) nest2gen variants full/independent_full/fixed_dwell vs frozen v8sim10_abl.sim_nest2: 120 cases -> IDENTICAL; 'apl' differs from independent_full on 20/20 (2) CtlGen (flags off) vs v8sim11.CtlSigma, R38 off: 20 cases -> IDENTICAL; CtlGen(w=1600) vs CtlS7(B=None, w=1600): 6 cases -> IDENTICAL; per-slot A-PL differs on 20/20 

Frozen-file md5 after: v8sim10.py 3daf1387, v8sim10_abl.py 7a2b02ec, v8sim11.py ecdfff61, v8sim2.py 4697713c, v8sim_b6.py b24eae16, prior_traces.json edb8e00c (before: 3daf1387, 7a2b02ec, ecdfff61, 4697713c, b24eae16, edb8e00c).

Deployed (six-split mean of the nest2 calibration, out/cal.jsonl): APL_2 λ 2.0/2.83 (infeasible splits 0/6); APL_05 λ 3.08/3.71 (infeasible splits 0/6); S4p_2 λ 1.5/1.92 (infeasible splits 0/6); S4p_05 λ 2.33/3.33 (infeasible splits 0/6)

## Table U1 (mp): bucket risk, max/min, std across buckets, Spearman(risk, mp) per trace, OLS slope of per-trace risk on mp with 95 % bootstrap CI

| group | arm | bucket risk (%) | max/min | max/min (min non-zero) | std (pp) | Spearman ρ | slope (pp per unit) | 95 % CI |
|---|---|---|---|---|---|---|---|---|
| 2 % | S4b | 3.5 / 2.4 / 2.2 / 2.3 / 1.9 / 2.4 / 1.7 / 2.0 / 1.8 / 1.5 | 2.35 | 2.35 | 0.53 | -0.144 | -3.64 | [-4.91, -2.29] |
| 2 % | S single 2.25 | 3.0 / 1.7 / 1.9 / 1.7 / 1.4 / 1.8 / 1.1 / 1.2 / 1.1 / 0.9 | 3.50 | 3.50 | 0.58 | -0.190 | -4.03 | [-5.21, -2.86] |
| 2 % | B4c2 3.75/300 | 5.0 / 2.6 / 2.8 / 2.2 / 1.3 / 1.4 / 0.9 / 0.6 / 0.2 / 0.2 | 23.05 | 23.05 | 1.40 | -0.436 | -10.31 | [-11.74, -8.89] |
| 2 % | B5c1 4.0/L2 | 5.2 / 3.2 / 3.3 / 2.7 / 1.7 / 1.7 / 1.0 / 1.0 / 0.7 / 0.5 | 10.90 | 10.90 | 1.42 | -0.443 | -10.57 | [-11.85, -9.34] |
| 2 % | B6 0.775 | 3.6 / 1.9 / 1.8 / 1.5 / 1.1 / 1.2 / 0.7 / 0.5 / 0.3 / 0.3 | 11.52 | 11.52 | 0.93 | -0.375 | -6.86 | [-7.95, -5.74] |
| 2 % | v6 | 4.9 / 3.1 / 3.3 / 3.0 / 2.3 / 2.2 / 1.7 / 1.7 / 1.3 / 0.8 | 6.14 | 6.14 | 1.13 | -0.318 | -8.47 | [-9.93, -7.04] |
| 2 % | B1 | 0.0 / 0.0 / 0.0 / 0.0 / 0.0 / 0.0 / 0.0 / 0.0 / 0.0 / 0.0 | inf | nan | 0.00 | +nan | +0.00 | [+0.00, +0.00] |
| 2 % | A-PL | 2.7 / 1.6 / 1.6 / 1.2 / 0.9 / 1.6 / 0.9 / 1.1 / 0.9 / 0.9 | 2.96 | 2.96 | 0.52 | -0.166 | -3.34 | [-4.42, -2.15] |
| 2 % | S4′ | 4.0 / 2.6 / 2.6 / 2.3 / 1.7 / 2.0 / 1.4 / 1.3 / 1.0 / 0.7 | 5.76 | 5.76 | 0.91 | -0.296 | -6.82 | [-8.08, -5.53] |
| 0.5 % | S4a | 1.0 / 0.4 / 0.6 / 0.5 / 0.4 / 0.7 / 0.3 / 0.3 / 0.2 / 0.1 | 7.04 | 7.04 | 0.24 | -0.144 | -1.49 | [-2.15, -0.82] |
| 0.5 % | S single 3.25 | 0.8 / 0.3 / 0.3 / 0.3 / 0.3 / 0.4 / 0.1 / 0.2 / 0.1 / 0.1 | 8.05 | 8.05 | 0.20 | -0.126 | -1.24 | [-1.91, -0.63] |
| 0.5 % | B4c2 3.0/300 | 1.6 / 0.3 / 0.2 / 0.2 / 0.2 / 0.2 / 0.1 / 0.0 / 0.0 / 0.0 | inf | 81.00 | 0.46 | -0.261 | -2.75 | [-3.62, -1.93] |
| 0.5 % | B5c1 3.5/L1 | 2.1 / 0.8 / 0.7 / 0.6 / 0.4 / 0.6 / 0.3 / 0.1 / 0.1 / 0.1 | 41.23 | 41.23 | 0.57 | -0.323 | -3.78 | [-4.67, -2.88] |
| 0.5 % | B6 0.70 | 2.1 / 0.8 / 0.7 / 0.5 / 0.3 / 0.5 / 0.3 / 0.1 / 0.0 / 0.1 | 68.72 | 68.72 | 0.58 | -0.335 | -3.81 | [-4.74, -2.96] |
| 0.5 % | v6 | 4.9 / 3.1 / 3.3 / 3.0 / 2.3 / 2.2 / 1.7 / 1.7 / 1.3 / 0.8 | 6.14 | 6.14 | 1.13 | -0.318 | -8.47 | [-9.93, -7.04] |
| 0.5 % | B1 | 0.0 / 0.0 / 0.0 / 0.0 / 0.0 / 0.0 / 0.0 / 0.0 / 0.0 / 0.0 | inf | nan | 0.00 | +nan | +0.00 | [+0.00, +0.00] |
| 0.5 % | A-PL | 0.7 / 0.2 / 0.2 / 0.1 / 0.1 / 0.3 / 0.1 / 0.2 / 0.2 / 0.1 | 7.31 | 7.31 | 0.16 | -0.090 | -0.82 | [-1.31, -0.35] |
| 0.5 % | S4′ | 1.6 / 0.5 / 0.5 / 0.3 / 0.3 / 0.6 / 0.1 / 0.2 / 0.1 / 0.1 | 31.41 | 31.41 | 0.44 | -0.219 | -2.78 | [-3.71, -1.90] |

Rule (S more uniform than a baseline = S max/min and std both smaller and slope CIs disjoint; max/min uses the min-non-zero version when a bucket risk is 0):

- mp, 2 %: S4b vs B4c2: max/min 2.35 vs 23.05, std 0.53 vs 1.40 pp, slope CI disjoint True -> S MORE UNIFORM
- mp, 2 %: S4b vs B5c1: max/min 2.35 vs 10.90, std 0.53 vs 1.42 pp, slope CI disjoint True -> S MORE UNIFORM
- mp, 2 %: S4b vs B6: max/min 2.35 vs 11.52, std 0.53 vs 0.93 pp, slope CI disjoint True -> S MORE UNIFORM
- mp, 0.5 %: S4a vs B4c2: max/min 7.04 vs 81.00, std 0.24 vs 0.46 pp, slope CI disjoint False -> not more uniform
- mp, 0.5 %: S4a vs B5c1: max/min 7.04 vs 41.23, std 0.24 vs 0.57 pp, slope CI disjoint True -> S MORE UNIFORM
- mp, 0.5 %: S4a vs B6: max/min 7.04 vs 68.72, std 0.24 vs 0.58 pp, slope CI disjoint True -> S MORE UNIFORM

## Table U1 (rise1): bucket risk, max/min, std across buckets, Spearman(risk, rise1) per trace, OLS slope of per-trace risk on rise1 with 95 % bootstrap CI

| group | arm | bucket risk (%) | max/min | max/min (min non-zero) | std (pp) | Spearman ρ | slope (pp per unit) | 95 % CI |
|---|---|---|---|---|---|---|---|---|
| 2 % | S4b | 0.7 / 1.0 / 1.6 / 2.9 / 2.3 / 3.7 / 3.8 / 5.1 | 7.63 | 7.63 | 1.44 | +0.500 | +0.44 | [+0.39, +0.49] |
| 2 % | S single 2.25 | 0.3 / 0.7 / 1.1 / 1.5 / 1.9 / 2.8 / 3.2 / 4.5 | 13.01 | 13.01 | 1.31 | +0.513 | +0.39 | [+0.34, +0.45] |
| 2 % | B4c2 3.75/300 | 1.0 / 1.9 / 0.8 / 1.5 / 1.5 / 2.5 / 2.5 / 3.8 | 4.73 | 4.73 | 0.90 | +0.309 | +0.25 | [+0.18, +0.31] |
| 2 % | B5c1 4.0/L2 | 1.2 / 1.7 / 1.5 / 2.2 / 2.0 / 3.0 / 3.1 / 4.5 | 3.85 | 3.85 | 1.03 | +0.328 | +0.31 | [+0.25, +0.37] |
| 2 % | B6 0.775 | 0.6 / 1.3 / 0.8 / 1.4 / 1.3 / 2.0 / 1.9 / 2.7 | 4.51 | 4.51 | 0.63 | +0.299 | +0.19 | [+0.15, +0.24] |
| 2 % | v6 | 1.5 / 1.8 / 2.0 / 2.6 / 2.2 / 3.7 / 3.6 / 4.7 | 3.17 | 3.17 | 1.05 | +0.376 | +0.32 | [+0.26, +0.38] |
| 2 % | B1 | 0.0 / 0.0 / 0.0 / 0.0 / 0.0 / 0.0 / 0.0 / 0.0 | inf | nan | 0.00 | +nan | +0.00 | [+0.00, +0.00] |
| 2 % | A-PL | 0.2 / 0.6 / 0.8 / 1.4 / 1.5 / 2.7 / 2.7 / 4.0 | 18.87 | 18.87 | 1.21 | +0.526 | +0.36 | [+0.31, +0.41] |
| 2 % | S4′ | 1.0 / 1.2 / 1.3 / 2.3 / 2.0 / 2.9 / 2.9 / 4.7 | 4.69 | 4.69 | 1.15 | +0.408 | +0.34 | [+0.29, +0.40] |
| 0.5 % | S4a | 0.0 / 0.0 / 0.1 / 0.3 / 0.3 / 1.0 / 1.3 / 2.2 | inf | 44.30 | 0.74 | +0.454 | +0.20 | [+0.17, +0.24] |
| 0.5 % | S single 3.25 | 0.0 / 0.0 / 0.0 / 0.1 / 0.2 / 0.7 / 0.9 / 1.6 | inf | 127.36 | 0.54 | +0.400 | +0.15 | [+0.12, +0.18] |
| 0.5 % | B4c2 3.0/300 | 0.1 / 0.4 / 0.1 / 0.1 / 0.2 / 0.7 / 0.2 / 1.0 | 13.29 | 13.29 | 0.31 | +0.189 | +0.06 | [+0.04, +0.09] |
| 0.5 % | B5c1 3.5/L1 | 0.2 / 0.5 / 0.3 / 0.5 / 0.6 / 1.1 / 0.7 / 1.5 | 7.40 | 7.40 | 0.40 | +0.231 | +0.12 | [+0.09, +0.15] |
| 0.5 % | B6 0.70 | 0.2 / 0.6 / 0.3 / 0.5 / 0.6 / 1.0 / 0.6 / 1.3 | 6.28 | 6.28 | 0.34 | +0.202 | +0.09 | [+0.06, +0.12] |
| 0.5 % | v6 | 1.5 / 1.8 / 2.0 / 2.6 / 2.2 / 3.7 / 3.6 / 4.7 | 3.17 | 3.17 | 1.05 | +0.376 | +0.32 | [+0.26, +0.38] |
| 0.5 % | B1 | 0.0 / 0.0 / 0.0 / 0.0 / 0.0 / 0.0 / 0.0 / 0.0 | inf | nan | 0.00 | +nan | +0.00 | [+0.00, +0.00] |
| 0.5 % | A-PL | 0.0 / 0.0 / 0.1 / 0.0 / 0.2 / 0.5 / 0.5 / 1.5 | inf | 234.78 | 0.47 | +0.400 | +0.12 | [+0.10, +0.14] |
| 0.5 % | S4′ | 0.1 / 0.3 / 0.2 / 0.3 / 0.4 / 0.7 / 0.7 / 1.6 | 13.08 | 13.08 | 0.44 | +0.285 | +0.12 | [+0.08, +0.15] |

Rule (S more uniform than a baseline = S max/min and std both smaller and slope CIs disjoint; max/min uses the min-non-zero version when a bucket risk is 0):

- rise1, 2 %: S4b vs B4c2: max/min 7.63 vs 4.73, std 1.44 vs 0.90 pp, slope CI disjoint True -> not more uniform
- rise1, 2 %: S4b vs B5c1: max/min 7.63 vs 3.85, std 1.44 vs 1.03 pp, slope CI disjoint True -> not more uniform
- rise1, 2 %: S4b vs B6: max/min 7.63 vs 4.51, std 1.44 vs 0.63 pp, slope CI disjoint True -> not more uniform
- rise1, 0.5 %: S4a vs B4c2: max/min 44.30 vs 13.29, std 0.74 vs 0.31 pp, slope CI disjoint True -> not more uniform
- rise1, 0.5 %: S4a vs B5c1: max/min 44.30 vs 7.40, std 0.74 vs 0.40 pp, slope CI disjoint True -> not more uniform
- rise1, 0.5 %: S4a vs B6: max/min 44.30 vs 6.28, std 0.74 vs 0.34 pp, slope CI disjoint True -> not more uniform

## Table U2: per-layer VM-minutes relative to B1 (slot 480 / worker 240 / VyOS 180), mp deciles

| group | arm | D1 | D2 | D3 | D4 | D5 | D6 | D7 | D8 | D9 | D10 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2 % | S4b | 0.58/0.72/0.63 | 0.69/0.81/0.72 | 0.74/0.86/0.77 | 0.80/0.91/0.81 | 0.84/0.94/0.85 | 0.87/0.96/0.88 | 0.90/0.98/0.92 | 0.93/0.99/0.95 | 0.95/1.00/0.97 | 0.98/1.00/0.99 |
| 2 % | S single 2.25 | 0.59/0.73/0.66 | 0.69/0.82/0.75 | 0.75/0.87/0.80 | 0.81/0.92/0.84 | 0.85/0.95/0.88 | 0.88/0.97/0.91 | 0.91/0.98/0.95 | 0.94/0.99/0.97 | 0.96/1.00/0.98 | 0.99/1.00/1.00 |
| 2 % | B4c2 3.75/300 | 0.59/0.67/0.57 | 0.71/0.78/0.67 | 0.78/0.84/0.73 | 0.84/0.90/0.78 | 0.88/0.93/0.83 | 0.92/0.95/0.87 | 0.95/0.98/0.91 | 0.97/0.99/0.95 | 0.99/0.99/0.98 | 1.00/1.00/0.99 |
| 2 % | B5c1 4.0/L2 | 0.61/0.68/0.55 | 0.72/0.79/0.65 | 0.78/0.84/0.71 | 0.84/0.89/0.76 | 0.88/0.93/0.80 | 0.91/0.95/0.84 | 0.94/0.97/0.88 | 0.97/0.99/0.92 | 0.98/0.99/0.96 | 0.99/1.00/0.99 |
| 2 % | B6 0.775 | 0.62/0.69/0.60 | 0.72/0.79/0.69 | 0.78/0.85/0.75 | 0.84/0.90/0.80 | 0.88/0.93/0.84 | 0.92/0.96/0.87 | 0.95/0.98/0.91 | 0.97/0.99/0.94 | 0.98/0.99/0.97 | 1.00/1.00/0.99 |
| 2 % | v6 | 0.60/0.68/0.60 | 0.70/0.77/0.69 | 0.75/0.82/0.74 | 0.80/0.87/0.78 | 0.85/0.91/0.81 | 0.88/0.94/0.84 | 0.91/0.96/0.87 | 0.94/0.98/0.91 | 0.96/0.99/0.94 | 0.99/1.00/0.98 |
| 2 % | A-PL | 0.61/0.72/0.63 | 0.71/0.81/0.72 | 0.77/0.86/0.77 | 0.82/0.91/0.81 | 0.86/0.94/0.85 | 0.89/0.96/0.88 | 0.92/0.98/0.92 | 0.95/0.99/0.94 | 0.97/1.00/0.96 | 0.99/1.00/0.99 |
| 2 % | S4′ | 0.59/0.69/0.61 | 0.70/0.79/0.70 | 0.75/0.84/0.75 | 0.81/0.89/0.78 | 0.85/0.92/0.81 | 0.88/0.95/0.85 | 0.91/0.97/0.89 | 0.94/0.98/0.92 | 0.96/0.99/0.95 | 0.99/1.00/0.98 |
| 0.5 % | S4a | 0.63/0.78/0.69 | 0.73/0.87/0.78 | 0.79/0.91/0.83 | 0.85/0.95/0.88 | 0.88/0.97/0.92 | 0.91/0.98/0.94 | 0.94/0.99/0.97 | 0.96/1.00/0.98 | 0.98/1.00/0.99 | 0.99/1.00/1.00 |
| 0.5 % | S single 3.25 | 0.65/0.79/0.72 | 0.75/0.88/0.80 | 0.81/0.92/0.85 | 0.86/0.96/0.90 | 0.89/0.97/0.93 | 0.92/0.99/0.95 | 0.95/0.99/0.98 | 0.97/1.00/0.99 | 0.99/1.00/1.00 | 1.00/1.00/1.00 |
| 0.5 % | B4c2 3.0/300 | 0.66/0.74/0.64 | 0.79/0.85/0.75 | 0.85/0.91/0.82 | 0.92/0.96/0.88 | 0.95/0.97/0.91 | 0.97/0.99/0.95 | 0.98/0.99/0.97 | 0.99/1.00/0.99 | 1.00/1.00/1.00 | 1.00/1.00/1.00 |
| 0.5 % | B5c1 3.5/L1 | 0.65/0.72/0.60 | 0.77/0.83/0.71 | 0.83/0.88/0.77 | 0.89/0.93/0.82 | 0.93/0.96/0.86 | 0.95/0.97/0.90 | 0.97/0.99/0.94 | 0.99/0.99/0.97 | 0.99/1.00/0.99 | 1.00/1.00/1.00 |
| 0.5 % | B6 0.70 | 0.64/0.71/0.63 | 0.75/0.82/0.73 | 0.82/0.87/0.79 | 0.88/0.93/0.84 | 0.92/0.95/0.89 | 0.95/0.97/0.92 | 0.97/0.99/0.95 | 0.99/0.99/0.97 | 0.99/1.00/0.99 | 1.00/1.00/1.00 |
| 0.5 % | v6 | 0.60/0.68/0.60 | 0.70/0.77/0.69 | 0.75/0.82/0.74 | 0.80/0.87/0.78 | 0.85/0.91/0.81 | 0.88/0.94/0.84 | 0.91/0.96/0.87 | 0.94/0.98/0.91 | 0.96/0.99/0.94 | 0.99/1.00/0.98 |
| 0.5 % | A-PL | 0.66/0.78/0.70 | 0.77/0.87/0.78 | 0.82/0.91/0.83 | 0.87/0.95/0.88 | 0.91/0.97/0.91 | 0.93/0.98/0.94 | 0.96/0.99/0.96 | 0.98/1.00/0.98 | 0.99/1.00/0.99 | 1.00/1.00/1.00 |
| 0.5 % | S4′ | 0.65/0.73/0.66 | 0.75/0.83/0.75 | 0.81/0.88/0.80 | 0.86/0.93/0.84 | 0.89/0.95/0.88 | 0.92/0.97/0.92 | 0.95/0.99/0.95 | 0.97/0.99/0.97 | 0.99/1.00/0.99 | 1.00/1.00/1.00 |

(cell = slot / worker / VyOS share of B1)

## Table T6: t6 / t7 per trace, per-slot simulation (R38 off, own initial fleet; r62cf registered no per-layer t6/t7 predictions, recomputed) against hardware (rq_metrics.csv)

| trace | arm / knob | sim alloc_vm | sim viol | sim worker / VyOS / slot min | hardware runs | hw alloc_vm (mean) | hw viol | hw worker / VyOS / slot min (mean) |
|---|---|---|---|---|---|---|---|---|
| t6 | S4b | 1389.7 | 0 | 235.8 / 166.1 / 437.5 | r405,r411,r416 | 1390.3 | 0/3 runs | 236 / 166 / 436 |
| t6 | S4a | 1447.9 | 0 | 240.0 / 179.1 / 462.2 | r402,r414,r419 | 1435.0 | 0/3 runs | 240 / 174 / 460 |
| t6 | B4_3.75_300 | 1433.1 | 0 | 240.0 / 170.1 / 466.2 | — | — | — | — |
| t6 | B4_3.0_300 | 1464.0 | 0 | 240.0 / 180.0 / 480.0 | — | — | — | — |
| t6 | B4_3.5_600 | 1448.1 | 0 | 240.0 / 174.2 / 474.5 | r404,r410,r415 | 1455.7 | 5/3 runs | 240 / 178 / 474 |
| t6 | B5_4.0_L2 | 1375.3 | 0 | 234.2 / 154.1 / 455.5 | r406,r412,r417 | 1433.0 | 2/3 runs | 240 / 171 / 462 |
| t6 | B5_3.5_L1 | 1448.1 | 0 | 240.0 / 174.2 / 474.5 | — | — | — | — |
| t6 | B6_0.775 | 1431.0 | 0 | 240.0 / 168.1 / 468.5 | r498,r499 | 1443.5 | 0/2 runs | 240 / 170 / 477 |
| t6 | B6_0.7 | 1436.6 | 0 | 240.0 / 170.1 / 470.5 | r413,r418 | 1439.0 | 0/2 runs | 240 / 169 / 474 |
| t7 | S4b | 1396.3 | 0 | 233.8 / 171.9 / 438.7 | r433,r439,r444 | 1387.3 | 0/3 runs | 233 / 169 / 434 |
| t7 | S4a | 1432.3 | 0 | 239.3 / 173.8 / 458.2 | r430,r442,r447 | 1427.0 | 1/3 runs | 238 / 172 / 455 |
| t7 | B4_3.75_300 | 1426.1 | 0 | 239.8 / 167.9 / 463.4 | — | — | — | — |
| t7 | B4_3.0_300 | 1453.0 | 0 | 240.0 / 175.4 / 477.7 | — | — | — | — |
| t7 | B4_3.5_600 | 1441.8 | 0 | 240.0 / 168.9 / 480.0 | r432,r438,r443 | 1440.7 | 0/3 runs | 240 / 167 / 480 |
| t7 | B5_4.0_L2 | 1410.5 | 0 | 240.0 / 158.6 / 466.7 | r434,r440,r445 | 1413.0 | 0/3 runs | 240 / 159 / 466 |
| t7 | B5_3.5_L1 | 1442.8 | 0 | 240.0 / 169.4 / 480.0 | — | — | — | — |
| t7 | B6_0.775 | 1427.5 | 0 | 238.3 / 172.2 / 460.2 | — | — | — | — |
| t7 | B6_0.7 | 1448.2 | 0 | 240.0 / 173.8 / 475.7 | r435,r441,r446 | 1451.0 | 0/3 runs | 240 / 173 / 478 |

- (a) t6: S4b vs B6_0.775: sim -2.89 %, hardware -3.68 %
- (a) t6: S4b vs B6_0.7: sim -3.26 %, hardware -3.38 %
- (a) t6: S4b vs B5_4.0_L2: sim +1.04 %, hardware -2.98 %
- (a) t7: S4b vs B6_0.775: sim -2.18 %, hardware n/a
- (a) t7: S4b vs B6_0.7: sim -3.58 %, hardware -4.39 %
- (a) t7: S4b vs B5_4.0_L2: sim -1.00 %, hardware -1.82 %
- (b) t6 S4b worker-min: sim 235.8; hardware (rq_metrics) 236.3; user value 228; B4c2 / B6 hardware 240.
- (c) t6 mp 0.6937 at 22 % of D8 (0.6857, 0.7225]; S4b vs B4_3.75_300: trace -3.03 %, D8 mean -1.17 %, difference -1.86 pp
- (c) t6 mp 0.6937 at 22 % of D8 (0.6857, 0.7225]; S4b vs B5_4.0_L2: trace +1.04 %, D8 mean -0.14 %, difference +1.18 pp
- (c) t6 mp 0.6937 at 22 % of D8 (0.6857, 0.7225]; S4b vs B6_0.775: trace -2.89 %, D8 mean -0.85 %, difference -2.03 pp
- (c) t7 mp 0.6950 at 25 % of D8 (0.6857, 0.7225]; S4b vs B4_3.75_300: trace -2.08 %, D8 mean -1.17 %, difference -0.91 pp
- (c) t7 mp 0.6950 at 25 % of D8 (0.6857, 0.7225]; S4b vs B5_4.0_L2: trace -1.00 %, D8 mean -0.14 %, difference -0.87 pp
- (c) t7 mp 0.6950 at 25 % of D8 (0.6857, 0.7225]; S4b vs B6_0.775: trace -2.18 %, D8 mean -0.85 %, difference -1.33 pp

## Item 3: A-PL attribution (paired bootstrap of A-PL minus S, mp buckets)

- 2 %: A-PL std 0.52 pp vs S 0.53 (diff CI [-0.13, +0.09]); max/min (non-zero) 2.96 vs 2.35 (diff CI [+0.13, +2.43]); baselines std 1.40, 1.42, 0.93 pp, max/min 23.05, 10.90, 11.52; A-PL library risk 1.35 % cost 1289.2 -> in between
- 0.5 %: A-PL std 0.16 pp vs S 0.24 (diff CI [-0.15, -0.04]); max/min (non-zero) 7.31 vs 7.04 (diff CI [-21.60, +16.43]); baselines std 0.46, 0.57, 0.58 pp, max/min 81.00, 41.23, 68.72; A-PL library risk 0.23 % cost 1344.0 -> in between

## Table S4p: S4′ against each baseline per bucket (r67band Table B format)

### mp, 2 %

| bucket | baseline | Δcost % | Δrisk pp | Δworker-min | verdict |
|---|---|---|---|---|---|
| D1 | B4c2 | +3.06 | -1.05 | +4.9 | same level |
| D1 | B5c1 | +2.17 | -1.26 | +2.5 | same level |
| D1 | B6 | -0.69 | +0.39 | -0.3 | same level |
| D2 | B4c2 | +0.82 | +0.02 | +1.6 | same level |
| D2 | B5c1 | +0.46 | -0.66 | -0.7 | same level |
| D2 | B6 | -1.05 | +0.69 | -1.3 | same level |
| D3 | B4c2 | -0.35 | -0.12 | -0.5 | same level |
| D3 | B5c1 | +0.03 | -0.67 | -1.4 | same level |
| D3 | B6 | -1.47 | +0.84 | -2.4 | same level |
| D4 | B4c2 | -1.54 | +0.08 | -2.2 | same level |
| D4 | B5c1 | -0.56 | -0.41 | -1.3 | same level |
| D4 | B6 | -2.25 | +0.82 | -3.3 | same level |
| D5 | B4c2 | -1.91 | +0.43 | -2.4 | same level |
| D5 | B5c1 | -1.06 | +0.02 | -2.0 | same level |
| D5 | B6 | -2.36 | +0.58 | -2.7 | same level |
| D6 | B4c2 | -1.92 | +0.60 | -1.5 | same level |
| D6 | B5c1 | -0.78 | +0.31 | -0.9 | same level |
| D6 | B6 | -1.92 | +0.75 | -1.9 | same level |
| D7 | B4c2 | -2.16 | +0.48 | -1.7 | same level |
| D7 | B5c1 | -0.93 | +0.36 | -0.6 | same level |
| D7 | B6 | -1.96 | +0.65 | -1.5 | same level |
| D8 | B4c2 | -1.82 | +0.74 | -1.3 | same level |
| D8 | B5c1 | -0.79 | +0.37 | -0.2 | same level |
| D8 | B6 | -1.50 | +0.82 | -0.9 | same level |
| D9 | B4c2 | -1.40 | +0.81 | -0.7 | same level |
| D9 | B5c1 | -0.62 | +0.31 | +0.1 | same level |
| D9 | B6 | -1.19 | +0.71 | -0.5 | same level |
| D10 | B4c2 | -0.53 | +0.44 | -0.3 | same level |
| D10 | B5c1 | -0.24 | +0.21 | +0.0 | same level |
| D10 | B6 | -0.41 | +0.35 | -0.2 | same level |
| library | B4c2 | -0.95 | +0.24 | -0.4 | same level |
| library | B5c1 | -0.33 | -0.14 | -0.4 | same level |
| library | B6 | -1.50 | +0.66 | -1.5 | same level |

### mp, 0.5 %

| bucket | baseline | Δcost % | Δrisk pp | Δworker-min | verdict |
|---|---|---|---|---|---|
| D1 | B4c2 | -0.13 | -0.01 | -0.9 | same level |
| D1 | B5c1 | +2.97 | -0.50 | +3.5 | same level |
| D1 | B6 | +2.76 | -0.50 | +4.8 | same level |
| D2 | B4c2 | -3.13 | +0.16 | -6.8 | cheaper |
| D2 | B5c1 | +0.59 | -0.28 | -0.2 | same level |
| D2 | B6 | +0.94 | -0.31 | +1.8 | same level |
| D3 | B4c2 | -3.59 | +0.31 | -6.9 | same level |
| D3 | B5c1 | -0.06 | -0.16 | -0.9 | same level |
| D3 | B6 | +0.25 | -0.13 | +1.3 | same level |
| D4 | B4c2 | -4.24 | +0.10 | -7.5 | cheaper |
| D4 | B5c1 | -0.83 | -0.30 | -2.1 | same level |
| D4 | B6 | -0.73 | -0.24 | -0.7 | same level |
| D5 | B4c2 | -3.33 | +0.15 | -5.2 | cheaper |
| D5 | B5c1 | -0.91 | -0.04 | -1.9 | same level |
| D5 | B6 | -0.89 | +0.00 | -0.7 | same level |
| D6 | B4c2 | -2.86 | +0.35 | -3.9 | same level |
| D6 | B5c1 | -0.73 | -0.01 | -1.1 | same level |
| D6 | B6 | -0.82 | +0.09 | -0.6 | same level |
| D7 | B4c2 | -1.82 | +0.04 | -1.6 | same level |
| D7 | B5c1 | -0.54 | -0.14 | -0.4 | same level |
| D7 | B6 | -0.65 | -0.18 | -0.3 | same level |
| D8 | B4c2 | -1.17 | +0.21 | -0.9 | same level |
| D8 | B5c1 | -0.41 | +0.09 | -0.1 | same level |
| D8 | B6 | -0.45 | +0.11 | -0.1 | same level |
| D9 | B4c2 | -0.63 | +0.05 | -0.4 | same level |
| D9 | B5c1 | -0.21 | +0.02 | -0.0 | same level |
| D9 | B6 | -0.22 | +0.04 | -0.0 | same level |
| D10 | B4c2 | -0.19 | +0.05 | -0.1 | same level |
| D10 | B5c1 | -0.07 | -0.07 | +0.0 | same level |
| D10 | B6 | -0.05 | -0.07 | +0.0 | same level |
| library | B4c2 | -2.11 | +0.14 | -3.4 | cheaper |
| library | B5c1 | -0.11 | -0.14 | -0.3 | same level |
| library | B6 | -0.09 | -0.12 | +0.6 | same level |

### rise1, 2 %

| bucket | baseline | Δcost % | Δrisk pp | Δworker-min | verdict |
|---|---|---|---|---|---|
| D1 | B4c2 | -0.86 | -0.00 | -0.1 | same level |
| D1 | B5c1 | -0.43 | -0.17 | -0.6 | same level |
| D1 | B6 | -1.12 | +0.41 | -1.0 | same level |
| D3 | B4c2 | -0.80 | -0.71 | -0.1 | same level |
| D3 | B5c1 | -0.17 | -0.50 | -0.3 | same level |
| D3 | B6 | -1.32 | -0.03 | -1.3 | same level |
| D4 | B4c2 | -1.39 | +0.54 | -0.8 | same level |
| D4 | B5c1 | -0.67 | -0.13 | -0.8 | same level |
| D4 | B6 | -1.69 | +0.55 | -1.8 | same level |
| D6 | B4c2 | -0.95 | +0.74 | -0.4 | same level |
| D6 | B5c1 | -0.34 | +0.10 | -0.7 | same level |
| D6 | B6 | -1.57 | +0.85 | -1.6 | same level |
| D7 | B4c2 | -1.22 | +0.41 | -1.1 | same level |
| D7 | B5c1 | -0.65 | -0.07 | -1.0 | same level |
| D7 | B6 | -1.81 | +0.66 | -2.2 | same level |
| D8 | B4c2 | -0.86 | +0.43 | -0.3 | same level |
| D8 | B5c1 | -0.15 | -0.09 | -0.1 | same level |
| D8 | B6 | -1.56 | +0.97 | -1.3 | same level |
| D9 | B4c2 | -0.99 | +0.45 | -0.6 | same level |
| D9 | B5c1 | -0.03 | -0.22 | +0.4 | same level |
| D9 | B6 | -1.45 | +1.02 | -1.1 | same level |
| D10 | B4c2 | -0.30 | +0.95 | -0.2 | same level |
| D10 | B5c1 | +0.25 | +0.19 | +0.2 | same level |
| D10 | B6 | -2.01 | +2.04 | -2.0 | same level |
| library | B4c2 | -0.95 | +0.24 | -0.4 | same level |
| library | B5c1 | -0.33 | -0.14 | -0.4 | same level |
| library | B6 | -1.50 | +0.66 | -1.5 | same level |

### rise1, 0.5 %

| bucket | baseline | Δcost % | Δrisk pp | Δworker-min | verdict |
|---|---|---|---|---|---|
| D1 | B4c2 | -2.34 | +0.04 | -3.8 | cheaper |
| D1 | B5c1 | -0.34 | -0.09 | -1.0 | same level |
| D1 | B6 | -0.06 | -0.09 | +0.2 | same level |
| D3 | B4c2 | -2.13 | -0.12 | -3.6 | cheaper |
| D3 | B5c1 | -0.12 | -0.17 | -0.4 | same level |
| D3 | B6 | +0.10 | -0.34 | +0.8 | same level |
| D4 | B4c2 | -2.00 | +0.12 | -3.2 | same level |
| D4 | B5c1 | -0.18 | -0.09 | -0.2 | same level |
| D4 | B6 | -0.14 | -0.05 | +0.6 | same level |
| D6 | B4c2 | -2.41 | +0.22 | -4.3 | same level |
| D6 | B5c1 | -0.34 | -0.25 | -0.9 | same level |
| D6 | B6 | -0.28 | -0.16 | -0.1 | same level |
| D7 | B4c2 | -1.93 | +0.12 | -2.6 | same level |
| D7 | B5c1 | -0.16 | -0.21 | -0.2 | same level |
| D7 | B6 | -0.28 | -0.23 | +0.4 | same level |
| D8 | B4c2 | -1.86 | +0.03 | -2.9 | same level |
| D8 | B5c1 | +0.11 | -0.34 | +0.4 | same level |
| D8 | B6 | +0.07 | -0.27 | +1.2 | same level |
| D9 | B4c2 | -1.87 | +0.57 | -2.5 | same level |
| D9 | B5c1 | +0.13 | +0.01 | +0.6 | same level |
| D9 | B6 | -0.11 | +0.12 | +1.0 | same level |
| D10 | B4c2 | -1.89 | +0.59 | -3.7 | same level |
| D10 | B5c1 | +0.56 | +0.04 | +0.8 | same level |
| D10 | B6 | +0.00 | +0.28 | +1.2 | same level |
| library | B4c2 | -2.11 | +0.14 | -3.4 | cheaper |
| library | B5c1 | -0.11 | -0.14 | -0.3 | same level |
| library | B6 | -0.09 | -0.12 | +0.6 | same level |

## Item 4: the four S4′ checks

- 2 % (1) low-load D1–D3 Δworker-min vs the three baselines: +4.9, +2.5, -0.3, +1.6, -0.7, -1.3, -0.5, -1.4, -2.4 -> NOT all within ±2 (S S4b: +10.6, +8.2, +5.4, +6.7, +4.5, +3.8, +4.0, +3.1, +2.1)
- 2 % (2) high-load D8–D10 Δrisk: +0.74, +0.37, +0.82, +0.81, +0.31, +0.71, +0.44, +0.21, +0.35 pp -> NOT all within ±0.5 pp
- 2 % (3) library mean flaps (per-slot): S4′ 3.13 vs S4b 7.87 -> <= 4
- 2 % (4) t4: S4′ per-slot viol 1 [20] alloc_vm 1394 vs S4b per-slot 1 [20] 1425; fleet S4′ 3 / 1397 vs S4b 1 / 1427
- 2 % (4) t8: S4′ per-slot viol 2 [20, 21] alloc_vm 1050 vs S4b per-slot 2 [20, 21] 1041; fleet S4′ 1 / 1039 vs S4b 1 / 1017
- 0.5 % (1) low-load D1–D3 Δworker-min vs the three baselines: -0.9, +3.5, +4.8, -6.8, -0.2, +1.8, -6.9, -0.9, +1.3 -> NOT all within ±2 (S S4a: +10.1, +14.4, +15.8, +3.7, +10.2, +12.2, +1.4, +7.4, +9.6)
- 0.5 % (2) high-load D8–D10 Δrisk: +0.21, +0.09, +0.11, +0.05, +0.02, +0.04, +0.05, -0.07, -0.07 pp -> all within ±0.5 pp
- 0.5 % (3) library mean flaps (per-slot): S4′ 4.16 vs S4a 6.29 -> > 4
- 0.5 % (4) t4: S4′ per-slot viol 0 [] alloc_vm 1447 vs S4a per-slot 0 [] 1452; fleet S4′ 0 / 1450 vs S4a 0 / 1454
- 0.5 % (4) t8: S4′ per-slot viol 2 [20, 21] alloc_vm 1096 vs S4a per-slot 2 [20, 21] 1085; fleet S4′ 1 / 1078 vs S4a 1 / 1060

## Conclusions (registered reading rules only; one sentence per item)

1. **Uniformity:** on mp, S4b is more uniform than B4c2, B5c1 and B6 at 2 %, and S4a is more uniform than B5c1 and B6 at 0.5 % but not than B4c2 (slope CIs overlap); on rise1, S is not more uniform than any baseline in either group (its max/min, std and slope are all larger).
2. **t6/t7:**
   - (a) The simulation reproduces S4b's advantage over B6 (t6 −2.89 % at u 0.775 and −3.26 % at 0.70 against hardware −3.68 % and −3.38 %; t7 −3.58 % against −4.39 %). It does not reproduce the advantage over B5c1 on t6 (+1.04 % against −2.98 %; simulated B5c1 1375 against hardware 1433); on t7 it gives −1.00 % against −1.82 %.
   - (b) Simulated S4b worker-min on t6 is 235.8, against 236.3 in rq_metrics, 228 in the brief and 240 for B4c2 / B6.
   - (c) t6 and t7 sit at 22 % and 25 % of D8. Their per-trace Δcost is 0.9 to 2.0 pp more negative than the D8 mean, except S4b against B5c1 on t6 (+1.18 pp).
3. **A-PL attribution:** by the registered rule both groups are "in between". At 2 % the std difference is not significant while A-PL's max/min is higher (2.96 against 2.35); at 0.5 % A-PL's std is lower (0.16 against 0.24 pp) while the max/min difference is not significant. A-PL's statistics stay far from the three baselines (std 0.93 to 1.42 and 0.46 to 0.58 pp). Its per-slot library risk is 1.35 % and 0.23 %, against S4b 2.18 % and S4a 0.45 %.
4. **S4′:**
   - (1) No: low-load Δworker-min is outside ±2 (2 % up to +4.9; 0.5 % −6.9 to +4.8), against S4b +2.1 to +10.6 and S4a +1.4 to +15.8.
   - (2) No at 2 % (up to +0.82 pp); yes at 0.5 %.
   - (3) Yes at 2 % (3.13 flaps); no at 0.5 % (4.16).
   - (4) t4 at 2 %: per-slot 1 violation minute and 1394 against S4b's 1 and 1425; fleet 3 against S4b's 1. t8: the same 2 violation minutes as S4, at +9 (2 %) and +11 (0.5 %) core-min per-slot.
