<!-- artifact file of the paper "Risk-Calibrated Autoscaling of a Three-Layer 5G User Plane" (docs/paper), written 2026-10-20 when the main paper and the supplementary material were merged into one PDF (spec §4.103). Content moved from S-supplement.md S.12; numbers unchanged. -->

# Madrid LTE: feature percentiles, KS distances and the compressed-library contrast


The table gives the P10 / P50 / P90 of each load feature for the three libraries of the Madrid transfer test in the paper, with the two-sample Kolmogorov-Smirnov distances; the figure `../figs/fig_madrid_features.pdf` shows the distributions.

Figure `../figs/fig_madrid_features.pdf`: Load features of the Melbourne prior library (1615 windows), the Madrid LTE 1:1 library (556 windows) and the Madrid library passed through the Melbourne pipeline (135 windows): density histograms of mean-to-peak ratio, fraction of minutes at or above 36 UE, minimum UE, rise10, rise1, lag-1 autocorrelation and stationarity.

| feature | Melbourne P10 / P50 / P90 | Madrid 1:1 P10 / P50 / P90 | Madrid compressed P10 / P50 / P90 | KS 1:1 vs Melbourne | KS compressed vs 1:1 | KS compressed vs Melbourne |
|---|---|---|---|---|---|---|
| mean-to-peak | 0.420 / 0.610 / 0.767 | 0.716 / 0.790 / 0.840 | 0.674 / 0.761 / 0.827 | 0.70 | 0.23 | 0.61 |
| f36 | 0.017 / 0.067 / 0.167 | 0 / 0 / 0 | 0 / 0 / 0.017 | 0.91 | 0.04 | 0.87 |
| minUE | 4 / 12 / 22 | 7 / 12 / 16 | 8 / 14 / 20 | 0.23 | 0.29 | 0.19 |
| rise10 | 11 / 16 / 23 | 5 / 9 / 20 | 3.4 / 7 / 15.6 | 0.48 | 0.24 | 0.70 |
| rise1 | 7 / 9 / 14 | 3 / 6 / 13 | 2 / 4 / 9 | 0.49 | 0.28 | 0.73 |
| lag-1 | 0.449 / 0.785 / 0.919 | 0.266 / 0.545 / 0.771 | 0.475 / 0.738 / 0.877 | 0.44 | 0.43 | 0.18 |
| stationarity | −11.5 / 0.8 / 14.4 | −2.4 / 0.0 / 2.4 | −5.8 / 0.1 / 5.1 | 0.36 | 0.19 | 0.27 |

Table. Load features of the Melbourne library (n = 1615), the Madrid 1:1 library (n = 556) and the Madrid library passed through the Melbourne pipeline (n = 135): P10 / P50 / P90 and the two-sample Kolmogorov-Smirnov distance between the libraries. <!-- madrid/REPORT.md step 4 table, features_table.md; KS rounded to two decimals -->

Compressed-library contrast. The pipeline shifts every burstiness feature in the expected direction when applied to the same Madrid minutes, lowering rise1 (median 6 to 4), rise10 (9 to 7) and mean-to-peak (0.79 to 0.76), raising lag-1 (0.55 to 0.74) and widening stationarity (±2.4 to −5.8 / +5.1), with KS 0.19 to 0.43 between the two Madrid libraries. The compressed Madrid library nevertheless remains far from Melbourne (KS 0.18 to 0.87), so the remaining gap is the source, RRC-connected users at one eNB against pedestrian counts at a city sensor, and not the pipeline. <!-- madrid/REPORT.md step 4 reading -->


## Text of Results §10 Dataset and Feature contrast before the 2026-10-22 cut (verbatim, spec §4.113 equal-trade cut a)

Dataset. The second dataset is the IMDEA Madrid LTE dataset \cite{perez2023madridlte}: per-second counts of RRC-connected users at six eNB cells, decoded from the PDCCH. <!-- madrid/REPORT.md header and LICENSE; §4.100 B0 (GPL-3.0, WiNTECH'23 DOI 10.1145/3615453.3616509; the bib key perez2023madridlte is a placeholder to be filled with that DOI) --> The pipeline is 1:1: each wall-clock minute's mean user count is scaled to UE = clip(round(40·C / Cmax), 0, 40) with Cmax the station's 99th percentile of per-minute means, followed by the 2-UE dead band of the Melbourne traces; there is no five-minute smoothing and no 4:1 compression, so one trace minute is one real minute. <!-- §4.99 B1 items 2, 3; madrid/REPORT.md step 2 --> A completeness rule written before the data were examined (segments missing 1 % or more of their seconds) excluded BS1 to BS3 and kept BS4 to BS6 with linear interpolation of the missing seconds. <!-- madrid/REPORT.md step 1: 1.684 / 1.478 / 8.938 %, 0.363 / 0.674 / 0.045 % --> Sixty-minute windows at a 60-minute stride, filtered by the same three admission rules as the Melbourne library with thresholds recomputed on the Madrid library's own percentiles, give 556 windows in 39 (station, day) groups, so the effective n is 39 against Melbourne's 125; adjacent windows do not overlap. <!-- madrid/REPORT.md step 2: 822 → 556 windows, 39 groups, 14.26 windows per group, overlap 0 -->

Feature contrast. On every load feature the Madrid 1:1 windows are flatter and smoother than the Melbourne windows, with two-sample Kolmogorov-Smirnov distances of 0.23 to 0.91 (mean-to-peak 0.70, fraction of minutes at or above 36 UE 0.91, rise10 0.48, rise1 0.49), and the same Madrid minutes passed through the Melbourne pipeline (five-minute centred rolling mean, 4:1 compression; 135 windows) remain far from Melbourne (0.18 to 0.87), so the gap lies in the source rather than in the pipeline. <!-- madrid/REPORT.md step 4 table and reading, features_table.md; KS rounded to two decimals; feature percentiles, the full KS table and the feature figure (old supplement Table S13, Fig. S3, Section S12) in artifacts/madrid-features.md -->
