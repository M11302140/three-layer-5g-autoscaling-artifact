<!-- artifact file of the paper "Risk-Calibrated Autoscaling of a Three-Layer 5G User Plane" (docs/paper), written 2026-10-20 when the main paper and the supplementary material were merged into one PDF (spec §4.103). Content moved from 02-simulation.md §5 (old Tables 3 and 4); the paper keeps the S4b values in one paragraph; numbers unchanged. -->

# Lever decomposition at equal risk (S4b and S4a)

Each lever is switched off and λ is recalibrated to the same target risk, so costs are comparable at equal risk. <!-- §4.38 --> `lead0` sets every ready lead to zero and `d0` sets every teardown lead to zero; both are platform time properties. `lock0` and `win0` remove controller rules. <!-- §4.38 -->

| Variant (S4b, 2 %) | Held-out risk | alloc | Δ cost |
|---|---|---|---|
| base | 0.0190 | 1291.7 | none |
| lead0 | 0.0183 | 1272.3 | −1.5 % |
| lock0 | 0.0187 | 1292.7 | +0.1 % |
| win0 | 0.0197 | 1314.8 | +1.8 % |
| d0 | 0.0192 | 1273.7 | −1.4 % |
| all_off | 0.0192 | 1239.4 | −4.0 % |

Table (a). S4b levers at equal risk. <!-- §4.38 -->

| Variant (S4a, 0.5 %) | Held-out risk | alloc | Δ cost |
|---|---|---|---|
| base | 0.0047 | 1346.7 | none |
| lead0 | 0.0054 | 1324.2 | −1.7 % |
| lock0 | 0.0045 | 1344.6 | −0.2 % |
| win0 | 0.0053 | 1355.9 | +0.7 % |
| d0 | 0.0045 | 1335.8 | −0.8 % |
| all_off | 0.0049 | 1295.9 | −3.8 % |

Table (b). S4a levers at equal risk. <!-- §4.38 -->

The main cost is the margin against uncertainty and the unit granularity, not platform speed. <!-- §4.38 --> Platform start and teardown times together account for about 3 % of cost; idealising everything saves 4 %. <!-- §4.38 --> The look-back window has real value, since removing it costs 1.8 % at the 2 % operating point. The lock is cost-neutral and acts on flapping. <!-- §4.38 -->

For reference, with λ held fixed the raw effects differ: at S4b the window removal raises risk by 0.0124 and the lock removal by 0.0033, while `d0` lowers cost by 19 core-min with almost no risk change. <!-- §4.32 item 5 --> Those fixed-λ numbers mix risk and cost and are not reported in the main text. <!-- §4.36 -->
