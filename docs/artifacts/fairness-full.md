<!-- artifact file of the paper "Risk-Calibrated Autoscaling of a Three-Layer 5G User Plane" (docs/paper), written 2026-10-20 when the main paper and the supplementary material were merged into one PDF (spec §4.103). Content moved from S-supplement.md S.2; numbers unchanged. -->

# Baseline fairness, full descriptions


| item | S4a / S4b | v6 | B4c2 | B5c1 | B6 (u = 0.70) |
|---|---|---|---|---|---|
| decision type | risk-calibrated deviation margin + commitment-aware release, joint three layers | batch prior + commitment window | reactive thresholds, layers independent | reactive + Holt point forecast | multi-predictor point forecast + back-test selection, layers independent |
| demand information | prior library, 1615 traces (demand distribution) | same | none | none (online Holt) | prior library (trains AR/MLP) |
| lead times | measured lead distribution (σ̂ buckets) | measured lead | none | measured p90 (UP 2 / VY 5 / WK 5 ticks) | as B5c1 |
| risk margin | ε (0.5% / 2%) | batch +1 | tolerance band 0.05 | none | none (u = capacity discount) |
| commitment / dwell | release criterion (break-even) | commitment window | down 600 s | down 600 s | dwell UP 300 s / VM 600 s |
| how knobs were chosen | prior-library calibration, never sees the target trace | expert hand-tuning on t1/t2 (t3 evaluated, not tuned) | SLO-first pick on t1, re-check on t2 (3 + 3 runs) | same (2 + 1 + 1 runs) | same (3 + 1 runs; 2 further runs voided) |
| same actuation / relief / drain | yes, one daemon path | yes | yes | yes | yes (q9 adds only the B6 decision branch) |
| emergency +1 rule (measured loss ≥ SLO and a layer at ≥50% utilisation forces one unit; refractory 90 s) | yes (inherited from v6; fired in 7 of 26 main-experiment runs, all at formal minute 0 to 1) | yes (fired 5 times in 4 t3/t6 runs) | no (reactive threshold is itself the whole rule) | no | no |
| worker pre-build | joint planning | joint planning | executor, reactive | predictive (WK lead) | predictive (WK lead; slots wait for worker) |
| pre-formal fleet alignment | yes: after warm-in the fleet is trimmed downward to the registered start fleet (drain/delete only, never add); side effects, all counted against the S arms: a VyOS-side loss-ratio reading of 0.26 to 0.37 (fraction) for 2 to 3 ticks at formal minute 0 to 1 in 9 of 26 runs, with minute-level e2e loss ≤ 0.02 % in those minutes <!-- §4.97 -->, six early VyOS orders and one early slot order by the emergency rule, net cost ≤ +0.4 % | no | no | no | no |
| t1 measured SLO / alloc_vm (development set; runs and per-run alloc_vm) | S4a: 60/60 ×3, 1155/1148/1145, mean 1149 (r264/r265/r266, post-fix v9) / S4b: 60/60 ×3, 1073/1076/1080, mean 1076 (r251/r255/r261; G2b, pre-platform-fix, no post-fix S4b t1 runs exist) | 60/60 ×2, 1073/1081, mean 1077 (r267/r268, post-fix v9); earlier controls r247 60/60 1073, r257 58/60 1063 | 58/60, 1129 (r272) | 60/60, 1142 (r274) | 58/60, 1161 (r285) |

Table. Baseline fairness, full descriptions of each arm (compact form: the baseline fairness table of the experimental-setup chapter of the paper).
