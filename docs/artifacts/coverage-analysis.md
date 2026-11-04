<!-- artifact file of the paper "Risk-Calibrated Autoscaling of a Three-Layer 5G User Plane" (docs/paper), written 2026-10-20 when the main paper and the supplementary material were merged into one PDF (spec §4.103). Content moved from S-supplement.md S.15; numbers unchanged. -->

# Empirical coverage of the deviation margin


The replenish margin is λ_l · σ̂_l(D, H_l), where σ̂_l is the library standard deviation of the demand rise over the arrival window of layer l (the peak of demand in the last tick of the horizon above the current demand; windows [30, 60] s for UP and [150, 180] s for VY and WK). <!-- v8sim2.py:39-42; qsim/cov/coverage.py --> The table below gives, for every minute of the 1615 library traces and each 10-UE demand bucket, the fraction of minutes whose actual rise exceeds the margin, next to the Gaussian reading 1 − Φ(λ). <!-- qsim/cov/coverage_table.md --> The exceedance is 3 to 5 % at S4a and 10 to 17 % at S4b, 3.5 to 37 times the Gaussian value, because the rise is a point mass at zero with a heavy tail; λ is therefore a deviation multiplier whose coverage is measured, not a quantile. The SLO risk the multipliers are calibrated to (0.5 % and 2 % of minutes) is lower than this margin exceedance because each layer's need is rounded up to whole units. The figures are in-sample: σ̂ is fitted on the same traces.

| operating point | layer | λ | 1 − Φ(λ) | 0–9 UE | 10–19 | 20–29 | 30–40 | all |
|---|---|---|---|---|---|---|---|---|
| S4a | UP | 3.08 | 0.10 % | 1.95 % | 3.40 % | 3.79 % | 2.16 % | 3.09 % |
| S4a | VY, WK | 2.83 | 0.23 % | 3.66 % | 5.84 % | 7.35 % | 2.91 % | 5.42 % |
| S4a | WK (slot-path term) | 3.08 | 0.10 % | 2.69 % | 4.36 % | 5.69 % | 1.69 % | 3.98 % |
| S4b | UP | 2.00 | 2.28 % | 8.03 % | 9.85 % | 11.16 % | 8.39 % | 9.81 % |
| S4b | VY, WK | 1.83 | 3.36 % | 12.81 % | 16.27 % | 20.49 % | 12.22 % | 16.52 % |
| S4b | WK (slot-path term) | 2.00 | 2.28 % | 10.23 % | 13.30 % | 16.08 % | 10.34 % | 13.32 % |

Table. Fraction of library minutes whose demand rise over the arrival window exceeds the margin λ · σ̂, per 10-UE demand bucket (minutes per cell: UP 5938 / 22666 / 37684 / 28997, VY and WK 5682 / 21817 / 36728 / 27828).
