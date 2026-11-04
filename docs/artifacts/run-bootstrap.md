<!-- artifact file of the paper (docs/paper), written 2026-10-21 (R4rev, spec §4.112 D3). Table copied verbatim from experiment/qsim/r65boot/REPORT.md, produced by experiment/qsim/r65boot/boot.py; the results chapter (Section 2, paired differences) quotes the S4b − B5c1 and S4b − v6 rows. -->

# Run-level bootstrap of the paired cost differences on t6 and t7

Method (spec §4.112 D, written before the computation): for t6 and t7 separately, the mean `alloc_vm` difference between S4b and each of B4c2, B5c1, B6 and v6; each arm's three valid runs (paper_out_new/rq/rq_metrics.csv groups "MAIN tX <arm>"; B5c1 = "B5c1 (q11)", B6 = "B6 u=0.70") are resampled with replacement, three draws per arm, B = 10 000 resamples, seed 20261021; the interval is the 2.5 / 97.5 percentile of the resampled difference; relative values divide by the other arm's observed mean. This is run-to-run uncertainty on fixed traces, not uncertainty across workloads; with three runs per arm the intervals are narrow by construction.

| trace | S4b − arm | mean diff core-min (%) | 95 % run-bootstrap interval core-min (%) |
|---|---|---|---|
| t6 | B4c2 | -65.3 (-4.5 %) | [-71.3, -57.7] ([-4.9, -4.0] %) |
| t6 | B5c1 | -42.7 (-3.0 %) | [-45.0, -39.0] ([-3.1, -2.7] %) |
| t6 | B6 | -57.0 (-3.9 %) | [-72.0, -46.7] ([-5.0, -3.2] %) |
| t6 | v6 | +41.0 (+3.0 %) | [+31.7, +51.3] ([+2.3, +3.8] %) |
| t7 | B4c2 | -53.3 (-3.7 %) | [-55.0, -50.7] ([-3.8, -3.5] %) |
| t7 | B5c1 | -25.7 (-1.8 %) | [-27.7, -23.0] ([-2.0, -1.6] %) |
| t7 | B6 | -63.7 (-4.4 %) | [-67.0, -60.3] ([-4.6, -4.2] %) |
| t7 | v6 | +34.3 (+2.5 %) | [+32.3, +37.0] ([+2.4, +2.7] %) |

Table. S4b minus each arm: observed mean difference (relative) and 95 % run-bootstrap interval; negative = S4b cheaper.
