<!-- artifact file of the paper "Predictable-Cost Autoscaling of a Three-Layer 5G User Plane with Library-Calibrated Risk" (docs/paper), written 2026-10-21 (R64, spec §4.109) when Table I of the Method chapter was set one line per rule with the Constant and Origin columns merged; the full r63 table with its origin notes is kept here verbatim, source comments kept. -->

# Decision-path rules of the frozen planner (full table)

In rule 16, "Appendix B" referred to the former appendix on emergency-rule firings, now emergency-firings.md.

| # | Rule | Constant | Origin |
|---|---|---|---|
| 1 | Replenish to $\mathrm{need}_l$(D + $\lambda_l$ $\hat{\sigma}_{\mathrm{win},l}$($H_l$)) | $\lambda_{\mathrm{UP}}$ 2.00 / 3.08, $\lambda_{\mathrm{VM}}$ 1.83 / 2.83 | calibrated <!-- §4.20 rule 1 --> |
| 2 | $\hat{\sigma}$ from prior-library rises, 10-UE buckets, interpolation | n < 30 uses global | estimator <!-- §4.20 rule 2 --> |
| 3 | Horizon $H_l$ = $T_{\mathrm{ready},l}$ + g | 60 / 180 / 180 s | measured + derived <!-- §4.20 rule 3 --> |
| 4 | WK position ≥ UP target (replenish) and ≥ order-up-to (release) | none | derived <!-- §4.20 rule 4 --> |
| 5 | Release candidate: $\mathrm{need}_l$(D + $\lambda_l$ $\hat{\sigma}_{\mathrm{run},l}$($W_l$)) ≤ $n_l$ − 1 | W 60 / 180 / 180 s | derived <!-- §4.20 rule 5 --> |
| 6 | Release hold on peak over $W_l$, net of in-flight scale-in | same | derived <!-- §4.20 rule 6 --> |
| 7 | Post-scale-out same-layer lock | UP 300 s, VM 600 s | inherited <!-- §4.20 rule 7 --> |
| 8 | No release at episode start | 2·$W_l$ | inherited <!-- §4.20 rule 8 --> |
| 9 | Scale-in in flight lives ≥ one lead, serialized | d 150 / 60 / 90 s | inherited <!-- §4.20 rule 9 --> |
| 10 | Reversible drain | none | inherited <!-- §4.20 rule 10 --> |
| 11 | One worker booting; no slot order while a slot boots | none | inherited <!-- §4.20 rule 11 --> |
| 12 | Worker idle ≥ 10 min and empty before deletion | 600 s | inherited <!-- §4.20 rule 12 --> |
| 13 | Slot order waits for a free position on a ready worker | none | execution layer <!-- §4.20 rule 13 --> |
| 14 | D = integer UE count × 250 kpps | 250 kpps/UE | measured <!-- §4.20 rule 14 --> |
| 15 | Tick 30 s; cap_VY 4.45 Mpps × 0.93; cap_UP 5 UE; 2 slots per worker | none | platform <!-- §4.20 rule 15 --> |
| 16 | Emergency +1 when measured loss is at or above the SLO with a layer at ≥50 % utilisation, or a layer past its critical utilisation | refractory 90 s | inherited; fired in 7 of 26 S-arm runs, all at formal minute 0 to 1 on a start transient; net cost effect ≤ +0.4 % (Appendix~\ref{sec:appA-2}) <!-- §4.95, §4.96 --> |

Table. Decision-path rules of the frozen planner. <!-- §4.20 item 2 -->
