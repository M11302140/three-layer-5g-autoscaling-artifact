<!-- numbers.md (2026-10-31): every number the rev. 4 main text cites, with its source. Written before the chapter edits (task step 0); checked line by line after them (the check list (working file, not in this record)). Sources: spec = docs/proposals/v8-echelon-algorithm-spec-2026-10.md; rq = experiment/paper_out_new/rq/rq_metrics.csv (group names in quotes); r72 = experiment/qsim/r72hw/{REPORT.md,out/e.json}; r71 = qsim/r71fin/REPORT.md; r70 = qsim/r70eq/REPORT.md; r68 = qsim/r68unif/REPORT.md, out/cal.jsonl; r67 = qsim/r67band/REPORT.md; ops = paper_out_new/ops/r75/ops_table.md and ops_analysis_r75.py functions re-run on the R72 runs (this file §12). Naming in the paper: planner = S4′ (S4p2 / S4p05 in the data), CR = coupled-release variant = S4 (S4b = ε 2 %, S4a = ε 0.5 %). -->

# Numbers for paper rev. 4 (source-checked list)

Check marks (✓) are set in the check list (working file, not in this record) after the chapter edits, not here.

## 1. Run counts

| item | value | source |
|---|---|---|
| main experiment valid runs (t3–t7, 7 arms) | 82 (81 in tables + r381 confirmation) | rq groups "MAIN *"; 04-results §1 (rev. 3) |
| independent stress trace t8 (4 arms × 2) | 8 | spec §4.121 G; figs/fig_cost_viol_t3t8_t8runs.csv |
| B6 u = 0.775 knob check (t3, t6 × 2) | 4 | spec §4.121 H (r493/r505, r498/r499) |
| pre-registered planner block (C 18 + D 20) | 38 | p2/s_ledger.tsv class ok; r72 |
| pre-registered fill-in block r73fill (planner t3 ×3, t5 ×1, t7 ×3 at both points = 14; same-target B4 3.75/300 and B6 0.775 × t4, t8 × 2 = 8) | 22 | p2/s_ledger.tsv phase F / F-retry class ok; r73 = experiment/qsim/r73fill/{REPORT.md,out/f.json} |
| total valid post-freeze hardware runs used in the paper | 154 = 82 + 8 + 4 + 38 + 22 | sum of the above |
| rq_metrics.csv groups only (MAIN + R72 + R73) | 142 = 82 + 38 + 22 | rq (t8 and H runs are computed with rq_metrics functions but are not csv groups) |
| D harness faults replaced | r566 → r580, r567 → r581 (TRex server died in warm-in) | spec §4.140 C/D record |
| F harness faults replaced | r585 → r604 (ng-dead), r591 → r605 (warm-in gate failed three times, chain-abort; driver STOP, resumed after SCP→AMF restart on worker-0) | spec §4.141 結果; p2/s_exp.log |
| probes around the blocks | p35 / p36 / p36b / p37 / p38 / p39: p99 397–398 µs, e2e 0.010 % | p2/s_exp.log |

Note for the author: the skeleton says "82 + 38 = 120 valid runs"; 120 is the rq_metrics.csv count, 132 includes t8 and the B6 knob check, both of which the paper uses (Table IX t8 column, Table XI/B6 0.775 rows). The text uses 154 with the breakdown once (Results §1; rev. 4.2) and "120" / "142" nowhere.

## 2. Arms, λ, operating points (Method III-D, Table II)

| item | value | source |
|---|---|---|
| planner λ_VM / λ_UP, ε = 2 % | 1.50 / 1.92 (six-split mean; per-split 1.5 / 1.75–2.25) | r68 cal.jsonl S4p 0.02 (this file §11) |
| planner λ, ε = 0.5 % | 2.33 / 3.33 (per-split 2.25–2.5 / 3.0–3.75) | r68 cal.jsonl S4p 0.005 |
| CR λ, ε = 2 % / 0.5 % (deployed) | 1.83 / 2.00 and 2.83 / 3.08 | spec §4.32, 01-method rev. 3 |
| CR six-split re-check | 1.88 / 2.00 and 2.75 / 3.12 | 02-simulation rev. 3 Table III |
| planner held-out risk / alloc (six splits, vmexist) | 2 %: 0.0202 ± 0.0022 / 1267.9 ± 5.7; 0.5 %: 0.0053 ± 0.0010 / 1321.0 ± 5.9 (flaps 2.81 / 3.31; dispatch 1275.2 / 1327.1) | r68 cal.jsonl (std = population over 6 splits, as Table III) |
| A-PL λ (simulation ablation only) | 2 %: 2.00 / 2.83; 0.5 %: 3.08 / 3.71 | r68 REPORT "Deployed" |
| planner deployment point, per-slot whole-library risk / alloc_vm | 2 %: 1.958 % / 1267.1 (CR 2.183 % / 1282.0); 0.5 %: 0.434 % / 1318.4 (CR 0.452 % / 1337.1) | spec §4.139 結果 2; r68 REPORT "per-slot 整庫" |
| equal-risk c of the planner vs 1.00 | 2 % 0.9685, 0.5 % 0.96 (differ > 0.02; deployment keeps the nest2 value) | spec §4.139 結果 2 |
| R2 weight w | 1600 core-min per violation minute | spec §4.131 / §4.136 |
| daemon flags | V6_S4P_INDEP_WK=true (b′), V6_S4P_R2_W=1600 (R2) | spec §4.140 image record |
| daemon image | hhro-daemon:6.0-s4p, branch s4p @ e6d0724, docker id sha256:9f29a2fe…, binary sha256 e0222c22… | spec §4.140 |
| CR image | 6.0-s4 (sha256:27f31bcc…5110) | spec §4.140 |
| freeze dates | CR λ frozen 2026-10-06; planner λ registered 2026-10-28 (§4.139, commit 867c453), unchanged before and after hardware | spec §4.139; 03-setup rev. 3 "Freeze" |
| R38 rule date | written 2026-10-11, renamed 2026-10-18 | 02-simulation rev. 3 §1 |

## 3. Equivalence and the four prediction versions (Simulation IV-A/IV-B)

| item | value | source |
|---|---|---|
| per-tick replay, t1–t12 × two points = 2880 ticks | CR (flags off) vs CtlSigma: 163 differing ticks (S4a 89, S4b 74); planner vs CtlGen: 75 (S4p2 23, S4p05 52) | spec §4.140 A′ table |
| after left-endpoint diagnostic | CR 46 (VyOS quantisation 40, slot scale-in interval 6); planner 28 (VyOS 19, slot 9) | spec §4.140 A′ |
| version (d) residual vs daemon | planner 1 / 2880 ticks; CR 3 / 2880 | spec §4.140 A″ |
| flags-off vs CR source | 96 replay cases + 48 dump files identical | spec §4.140 A′ (1) |
| three deviation classes | (1) peak-window left endpoint (daemon excludes now−W); (2) capacity quantisation (VyOS 16.56 UE/VM whole-UE; slots 5.072 UE/slot aggregate cap); (3) slot scale-in interval (daemon re-subtracts the in-flight scale-in; sim waits 150 s) | spec §4.140 A′ |
| I1 start audit | 68 / 113 earlier runs + 25 / 38 R72 runs + 16 / 22 R73 runs = 109 / 173 (R73 vs the simulator's own initial_fleet; vs the registered aligned start also 16 / 22) | r70 Table I1; r72 §3; r73 §4 |
| I1 pattern, R72 | planner 0.5 % C runs one slot below sim (9/9); planner 2 % D runs 8/3/4 vs sim 7/3/4 (4/4); CR D and A-group baselines equal to sim | r72 §3 |
| I2 | per-slot 46 cells: moved > 1 % 1 (B5c1 t6 1375.3 → 1427.3, −4.03 % → −0.40 %), moved out of ±2 % 0; fleet 32: 0 / 0 | r70 Table I2 |
| HPA prefill | B5c1 t6 hardware start + prefill 1433.7 vs hw 1433.0 (+0.05 %); other B4c2/B5c1 cells unchanged | r70 prefill table |
| R72 B5 A-group recomputation | hw start = sim start (8/3/4); t11 1324.5 vs 1323.5 (+0.08 %), t12 1455.8 vs 1454.5 (+0.09 %) | r72 §3 |

## 4. Equal-risk simulation table (IV-D, replaces Table IV; r71fin E1 at equal per-slot risk, R38 off)

Δcost vs CR with 95 % paired-bootstrap CI, flaps (rq definition), churn-adjusted (+3 core-min per flap) Δ vs CR, U1 std across mp deciles at the equal-risk point (r70eq E1). Baselines at the r67band library knobs (not equal-risk; their library risk is listed).

| variant | 2 %: Δcost | CI | flaps | +3·flap Δ | U1 std pp | risk % | 0.5 %: Δcost | CI | flaps | +3·flap Δ | U1 std | risk % |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CR | 0 | — | 7.87 | 0 | 0.53 | 2.183 | 0 | — | 6.29 | 0 | 0.24 | 0.452 |
| A-PL | −1.10 | [−1.17, −1.02] | 12.09 | −0.11 | 0.57 | 2.196 | −0.40 | [−0.45, −0.36] | 9.77 | +0.37 | 0.29 | 0.404 |
| CR + NB release (S8) | −1.06 | [−1.15, −0.98] | 2.92 | −2.18 | 0.88 | 2.183 (interp.) | −0.54 | [−0.58, −0.49] | 4.06 | −1.02 | 0.31 | 0.442 |
| planner | −1.29 | [−1.39, −1.19] | 2.98 | −2.39 | 0.94 | 2.183 (interp.) | −1.53 | [−1.62, −1.44] | 4.22 | −1.97 | 0.44 | 0.446 |
| B4 3.75/300 ; 3.0/300 | −0.22 | — | 3.60 | −1.19 | 1.40 | 1.717 | +0.73 | — | 2.48 | −0.13 | 0.46 | 0.293 |
| B5 4.0/L2 ; 3.5/L1 | −0.83 | — | 1.77 | −2.22 | 1.42 | 2.102 | −1.28 | — | 1.37 | −2.35 | 0.57 | 0.575 |
| B6 0.775 ; 0.70 | +0.34 | — | 2.23 | −0.96 | 0.93 | 1.296 | −1.31 | — | 1.62 | −2.33 | 0.58 | 0.553 |

Sources: Δcost/CI/flaps: r71 §1 table (2 %: A-PL −1.10 [−1.17, −1.02], S8 −1.06 [−1.15, −0.98], S4′ −1.29 [−1.39, −1.19]; 0.5 %: −0.40 [−0.45, −0.36], −0.54 [−0.58, −0.49], −1.53 [−1.62, −1.44]); +3·flap Δ: r71 §2 churn tables (flap version); U1 std at the equal-risk point: r70 E1 column "U1 mp max/min, std" (2 %: 0.53 / 0.57 / 0.88 / 0.94; 0.5 %: 0.24 / 0.29 / 0.31 / 0.44); baseline Δcost = (baseline alloc − CR alloc)/CR alloc from r67 library rows (2 %: 1279.2, 1271.3, 1286.4 vs 1282.0; 0.5 %: 1346.8, 1319.9, 1319.5 vs 1337.1); baseline std from r68 U1 (1.40 / 1.42 / 0.93; 0.46 / 0.57 / 0.58); baseline risks r71 churn table. Interpolation error ≤ 0.12 % (r71 §1). Point + U < 0 for all six S variants → "cheaper" by the registered rule (r71).

Deviation from the skeleton §5-C: the skeleton's baseline Δcost row (+0.2 / +0.8 / −0.3; −0.7 / +1.3 / +1.3) carries the S-minus-baseline sign of r67 Table B; this file uses baseline-minus-CR, consistent with the column header.

Attribution sentences (IV-D text): A-PL vs CR std 0.52 vs 0.53 pp at deployed λ (diff CI [−0.13, +0.09]), 0.57 vs 0.53 at equal risk (diff CI [−0.08, +0.16]) → uniformity from the additive margin (r68 item 3; r70 E1). Coupling (CR vs A-PL at equal risk): flaps 7.87 vs 12.09 (−35 %), cost +1.1 % (r71). NB release (S8 vs CR): flaps 2.92 vs 7.87 (−63 %), cost −1.06 %, std 0.53 → 0.88 (r71, r70).

## 5. Load-band analysis (new IV-E; r67band / r68unif, 2 % group unless stated)

| item | value | source |
|---|---|---|
| mp decile thresholds | 0.420 / 0.485 / 0.532 / 0.576 / 0.610 / 0.650 / 0.686 / 0.723 / 0.767; 160–164 traces per decile | r67 "Buckets by mp" |
| test traces' deciles | t8 D1, t3 D2, t1 D3, t2 D7, t6 / t7 D8, t4 / t5 D10; t11 (mp 0.608) D5, t12 (0.741) D9 | r67; t11/t12 mp from trace files |
| Δcost per decile, CR vs B4 / B5 / B6 (S − baseline, %) | D1 +5.52 / +4.61 / +1.68; D2 +2.69 / +2.32 / +0.79; D3–D4 0.0 to +1.6; D5–D7 −1.16 to +0.53; D8 −1.17 / −0.14 / −0.85; D9–D10 −0.17 to −0.95; library +0.21 / +0.84 / −0.34 | r67 Table B |
| registered verdicts | no decile "cheaper at equal risk" (≤ −2 % with Δrisk ≤ +0.2 pp); "more expensive" in D2 vs B4 (2 %), D3 vs B5/B6 (0.5 %), rise1 D10 vs B5; all other deciles "same level" | spec §4.135 結果 |
| planner (S4′) per decile vs B4 / B5 / B6 | D1 +3.06 / +2.17 / −0.69; D2 +0.82 / +0.46 / −1.05; D4–D10 −0.24 to −2.36; library −0.95 / −0.33 / −1.50 | r68 Table S4p (mp, 2 %) |
| U1 (mp, 2 %): max/min, std pp, slope [CI] | CR 2.35 / 0.53 / −3.64 [−4.91, −2.29]; A-PL 2.96 / 0.52 / −3.34; planner 5.76 / 0.91 / −6.82 [−8.08, −5.53]; B4c2 23.05 / 1.40 / −10.31 [−11.74, −8.89]; B5c1 10.90 / 1.42 / −10.57; B6 11.52 / 0.93 / −6.86 [−7.95, −5.74]; v6 6.14 / 1.13 / −8.47 | r68 Table U1 (mp) |
| U1 (mp, 0.5 %) | CR 7.04 / 0.24 / −1.49; A-PL 7.31 / 0.16 / −0.82; planner 31.41 / 0.44 / −2.78; B4c2 ∞ (81.0 non-zero) / 0.46 / −2.75; B5c1 41.23 / 0.57 / −3.78; B6 68.72 / 0.58 / −3.81 | r68 Table U1 |
| U1 (rise1, 2 %) | CR 7.63 / 1.44 / +0.44; planner 4.69 / 1.15 / +0.34; A-PL 18.87 / 1.21 / +0.36; B4c2 4.73 / 0.90 / +0.25; B5c1 3.85 / 1.03 / +0.31; B6 4.51 / 0.63 / +0.19 | r68 Table U1 (rise1) |
| uniformity verdicts (registered rule) | mp 2 %: CR more uniform than B4c2, B5c1, B6 (3/3); mp 0.5 %: CR vs B5c1, B6 yes, vs B4c2 no (slope CIs overlap); rise1: not more uniform in any pair | r68 rule lines |
| start-rule robustness | rule s4b: 2 % verdicts unchanged, 0.5 % B5c1 and B6 flip to "not"; rule b1: 2 % unchanged, 0.5 % B4c2 flips to "more uniform"; library Δcost "same level" in all six pairs under both rules | r70 library re-calibration |
| A-PL library risk / cost at deployed λ | 1.35 % / 1289.2 (2 %), 0.23 % / 1344.0 (0.5 %) — not equal risk | r68 |

Deviation from the skeleton IV-E (1): "等風險 Δcost 每桶 |·| < 2 %" does not hold in the low-load deciles (D1–D2: +2.3 to +5.5 % for CR; +2.2 to +3.1 % for the planner vs B4/B5); the text states the registered verdicts and the decile ranges instead.

## 6. Hardware: planner vs CR, twelve paired cells (VI-B Table 1; VI-E endpoints; six fill-in cells added 2026-11-02)

| cell | planner cost (runs) | CR cost | Δ % | planner viol/run (range) | CR viol/run (range) | planner flaps (rq) | CR flaps (rq) | planner flaps (ops def.) | CR flaps (ops def.) | planner J = cost + 3·flaps (rq) | CR J | ΔJ % |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| t4, 2 % | 1394.0 (1394/1394/1394) | 1420.0 | −1.83 | 2.00 (2–2) | 3.33 (2–4) | 0 | 1.0 | 0 | 0 | 1394.0 | 1423.0 | −2.04 |
| t4, 0.5 % | 1447.7 (1447/1448/1448) | 1449.3 | −0.11 | 0 | 1.00 (0–2) | 2.0 | 2.0 | 0 | 2.0 | 1453.7 | 1455.3 | −0.11 |
| t6, 2 % | 1362.0 (1367/1367/1352) | 1390.3 | −2.04 | 0 | 0 | 2.0 | 6.0 | 2.0 | 6.0 | 1368.0 | 1408.3 | −2.86 |
| t6, 0.5 % | 1424.0 (1420/1433/1419) | 1435.0 | −0.77 | 0 | 0 | 2.0 | 9.33 | 2.0 | 5.67 | 1430.0 | 1463.0 | −2.26 |
| t8, 2 % | 1045.7 (1007/1078/1052) | 1054.5 | −0.84 | 2.33 (2–3) | 2.5 (2–3) | 2.33 | 9.0 | 2.33 | 6.0 | 1052.7 | 1081.5 | −2.67 |
| t8, 0.5 % | 1100.0 (1102/1110/1088) | 1107.5 | −0.68 | 0 | 1.5 (1–2) | 5.0 | 11.5 | 1.67 | 7.5 | 1115.0 | 1142.0 | −2.36 |
| t3, 2 % | 1159.0 (1164/1153/1160) | 1137.0 (1135/1133/1143) | +1.93 | 3.67 (3–4) | 4.67 (3–6) | 2.00 | 7.00 | — | — | 1165.0 | 1158.0 | +0.60 |
| t3, 0.5 % | 1182.0 (1187/1178/1181) | 1233.3 (1234/1228/1238) | −4.16 | 5.67 (5–7) | 2.33 (2–3) | 2.67 | 7.67 | — | — | 1190.0 | 1256.3 | −5.28 |
| t5, 2 % (n = 1 each) | 1457.0 (1457) | 1453.0 (1453) | +0.28 | 0 | 0 | 2.00 | 5.00 | — | — | 1463.0 | 1468.0 | −0.34 |
| t5, 0.5 % (n = 1 each) | 1464.0 (1464) | 1462.0 (1462) | +0.14 | 0 | 0 | 0.00 | 3.00 | — | — | 1464.0 | 1471.0 | −0.48 |
| t7, 2 % | 1395.0 (1398/1394/1393) | 1387.3 (1390/1386/1386) | +0.55 | 1.67 (0–5) | 0 | 1.33 | 6.67 | — | — | 1399.0 | 1407.3 | −0.59 |
| t7, 0.5 % | 1427.7 (1428/1426/1429) | 1427.0 (1426/1426/1429) | +0.05 | 0 | 0.33 (0–1) | 6.00 | 7.00 | — | — | 1445.7 | 1448.0 | −0.16 |

Sources: planner r72 §1 tables (runs t4 2 % r532/r533/r536; t4 0.5 % r541/r544/r546; t6 2 % r531/r538/r539; t6 0.5 % r530/r537/r540; t8 2 % r534/r535/r547; t8 0.5 % r542/r543/r545); CR rq groups "MAIN t4 S4b" (r303/r314/r322), "MAIN t4 S4a" (r502/r312/r317), "MAIN t6 S4b", "MAIN t6 S4a", t8 S4b r476/r500, S4a r471/r478 (spec §4.139 table). CR violation ranges: 04-results rev. 3 Table 1 (t4 S4b 2–4, S4a 0–2); t8 S4b [20,21]/[20,21,22], S4a [20]/[20,21]. Ops-definition flaps (exact daemon messages, scored window, 600 s; ops_analysis_r75.analyse): this file §12. Pairing verdict (first block): weakly dominated 6 / 6 (cost lower in all six; violation minutes never higher; flaps lower in five, equal in t4 0.5 % under the rq definition). Flap change (rq): −100 / 0 / −67 / −79 / −74 / −57 %. Fill-in cells (r73 §1–§2; CR rq groups MAIN t3/t5/t7 S4b/S4a; planner runs t3 2 % r584/r589/r596, t3 0.5 % r590/r598/r600, t5 r582 / r593, t7 2 % r586/r599/r605, t7 0.5 % r583/r594/r601): weakly dominated 0 / 6 (t3 2 % cost +1.93 %; t3 0.5 % violations +3.33; t5 cost +4 / +2 core-min; t7 2 % cost +0.55 % and violations +1.67; t7 0.5 % cost +0.67 core-min) → endpoint (C) n = 6 / 12 (7 / 12 under a 1 core-min tolerance). Flap change (rq): −71 / −65 / −60 / −100 / −80 / −14 %. Table X verdicts vs CR (tolerance rule): t3 trade-off ×2, t5 dominated ×2 (n = 1, 4 / 2 core-min), t7 2 % dominated (cost +0.55 % outside ranges 1393–1398 vs 1386–1390; r586 five placement minutes 35–39), t7 0.5 % equal (ranges 1426–1429 both; viol 0 vs 0.33). Endpoint (A): consistent with the registered expectation in 2 / 6 (t3). Ops-definition flaps of the fill-in runs not computed (the actuation table names its traces explicitly; since rev. 4.3 it is in the TR, tr/22 §14). **rev. 4.3 secondary analysis (not registered; r73fill/out/same_target.md, eval_st.py; α = 3 core-min/flap, rq flap definition; t11 J planner 1303.5 vs CR 1296.0 (+0.58 %), t12 1452.5 vs 1464.0 (−0.79 %))**: planner J lower in 12 / 14 cells (dearer on t3 2 % +0.60 % and t11 +0.58 %); violation minutes ≤ CR's in 11 / 14 (t3 0.5 % +3.33, t7 2 % +1.67, t12 +0.50); flaps lower in 11 / 12 paired cells (−14 to −100 %), equal on t4 0.5 % (2.0 vs 2.0 rq; 0 vs 2.0 ops), t11 −78 %, t12 −38 %. VI-B opening three sentences: flaps 11/12 + both generalisation cells; t4 minutes 49/50 absent 3/3 and t8 0.5 % zero violations (CR 1–2); general-load cost difference −2.0 % (t6 2 %) to +2.25 % (t11).

Endpoints (registered §4.139 / §4.140 B; results r72 §1): (i) pooled 13.33 ≤ 19.4 → yes; per cell 5 / 6 (t4 0.5 %: 2.0 vs 1.0); (ii) minutes 49/50 absent in 3/3; majority [20, 21] = version (c); (a)(b)(d) symmetric difference 1; CR hardware majority on the same cell [20, 21, 49, 50], reproduced by (c) only; (iii) within ±2 %: (a) 6/6, (b) 5/6 (t8 0.5 % −2.01 %), (c) 6/6, (d) 6/6; max |err| of (a) 0.42 % (t8 2 %). Secondary t8 ratio planner/CR: 0.9916 (−0.84 %), 0.9932 (−0.68 %) vs predicted +0.84 / +1.02 % ((a)(c)), +2.21 / +1.68 % ((b)).

Planner prediction errors (a) per cell: t4 2 % −0.02, t4 0.5 % −0.04, t6 2 % +0.39, t6 0.5 % +0.18, t8 2 % +0.42, t8 0.5 % −0.37 (r72 §1). D planner cells: t11 +0.02 %, t12 −0.31 %. Fill-in planner cells (r73 §1): t3 2 % +0.16, t3 0.5 % +0.66, t5 2 % +0.02, t5 0.5 % −0.00, t7 2 % +0.30, t7 0.5 % +0.24 → 14 planner cells within 0.66 %. Same-target: t4 B4 +0.07, t4 B6 −0.12, t8 B4 −5.39 (913.0 vs 965.0), t8 B6 −1.44; (b): t3 −0.71 / −0.13, t5 +0.15 / −0.00, t7 +0.05 / +0.10, t4 B6 +0.67, t8 B6 +0.97; (d): t3 +0.16 / +0.12, t5 +0.08 / −0.08, t7 +0.20 / +0.14. Endpoint (B): (a)(c)(d) 9 / 10 cells (20 / 22 runs), (b) 8 / 8 (18 / 18).

Violation lists (hardware, each run): t4 2 % [20,21] ×3; t4 0.5 % none; t6 none; t8 2 % [20,21,22] (r534), [20,21], [20,21]; t8 0.5 % none (r72 §1). Fill-in (r73 §1): t3 2 % [3,4,5] (r584), [3,4,5,6] (r589, r596); t3 0.5 % [3,4,5,6,7,10,12] (r590), [3,4,5,6,7] (r598, r600); t5 none; t7 2 % [35–39] (r586), none (r599, r605); t7 0.5 % none; t4 B4 [] / [1] (r602); t4 B6 none; t8 B4 [20,21] (r592), [20–23] (r604); t8 B6 [20,21,22] (r588), [20–23] (r595). B2 classes (r73 §5): t3 minutes 3–5 fleet in 6/6 runs, 6–7 placement (r598/r600 minute 7 other), r590 10/12 placement; r586 35–39 all placement (full fleet 8/3/4, departures 30→22 UEs, loss 0.18–0.60 %, p99 ≤ 311 µs); t8 B4/B6 minute 20 fleet in 4/4, 21–23 placement/other; r602 minute 1 placement. Emergency rule ("v6 emergency force" in the formal-segment daemon log): r584, r586, r590 (×2), r605 → ‡ on planner t3 (both points) and t7 2 % in Table 2. B2 classes of the planner's violating minutes (classify_b2): minute 20 = fleet shortage in all six t4 2 %/t8 2 % runs; minute 21 = placement (5 runs) / other (r536); r534 minute 22 placement; r575 minute 51 placement; r571 (B4 t12) minutes 3/18/20/21/22 all placement (this file §12).

## 7. Hardware: planner vs baselines on the same trace (VI-B text; Table IX additions)

Table IX planner rows (mean viol/run (range) / mean alloc_vm (range)): t4 2 %: 2.00 (2–2) / 1394 (1394–1394); t4 0.5 %: 0 / 1448 (1447–1448); t6 2 %: 0 / 1362 (1352–1367); t6 0.5 %: 0 / 1424 (1419–1433); t8 2 %: 2.33 (2–3) / 1046 (1007–1078); t8 0.5 %: 0 / 1100 (1088–1110); t3 2 %: 3.67 (3–4) / 1159 (1153–1164); t3 0.5 %: 5.67 (5–7) / 1182 (1178–1187); t5 2 %: 0 / 1457; t5 0.5 %: 0 / 1464; t7 2 %: 1.67 (0–5) / 1395 (1393–1398); t7 0.5 %: 0 / 1428 (1426–1429). Same-target rows: B4 3.75/300 t4 0.50 (0–1) / 1437 (1437–1437), t8 3.00 (2–4) / 965 (964–966); B6 0.775 t4 0 / 1434 (1433–1434), t8 3.50 (3–4) / 1012 (1009–1016). Source r72 §1 / r73 §1 / rq groups "R72 *", "R73 *".

Table IX t8 column (existing arms, 2 runs each): CR 0.5 % 1.5 / 1107.5 (1091–1124); CR 2 % 2.5 / 1054.5 (1051–1058); v6 4.0 / 979 (965–993); B6 (u 0.70) 1.5 / 1064 (1060–1068) (04-results rev. 3 §2 "Independent stress trace"; fig_cost_viol_t3t8_t8runs.csv).

Table IX t11 / t12 columns (A-group baselines, 2 runs each; r72 §2): t11: planner 0 / 1297.5 (1296–1299); CR 2 % 0 / 1269.0 (1268–1270); B4 3.75/300 0 / 1309.5 (1305–1314); B5 4.0/L2 0 / 1323.5 (1323–1324); B6 0.775 0 / 1343.0 (1331–1355). t12: planner 0.5 (0–1) / 1437.5 (1436–1439); CR 2 % 0 / 1440.0 (1440–1440); B4 2.5 (0–5) / 1458.5 (1458–1459); B5 0 / 1454.5 (1454–1455); B6 0 / 1452.0 (1451–1453). Flaps (rq): t11 planner 2, CR 9, B4 2, B5 0, B6 1; t12 planner 5, CR 8, B4 0.5, B5 1, B6 1.

Same-trace comparisons (means; dominance with tolerance = cost difference outside both arms' run ranges and violation difference ≥ 1 minute/run):
- t4: planner 2 % (1394 / 2.00) vs B5c1 (1409.7 / 2.33): cost −1.1 % outside both ranges (1394–1394, 1409–1410), violations −0.33 → cheaper at equal violations within tolerance; vs B4c2 (1446.7 / 0.67) and B6 u0.70 (1446.5 / 0.50, n = 2): −3.6 %, +1.3 to +1.5 min → trade-off. planner 0.5 % (1447.7 / 0) vs B4c2 1446.7 / 0.67, B6 1446.5 / 0.50: cost inside the run ranges (1446–1447 vs 1447–1448), violations 0 vs 0.5–0.67 (< 1 min) → same cost, zero violations, not a dominance by the tolerance rule.
- t6: planner 2 % 1362 / 0 vs B5c1 1433 / 0.67 (−4.95 %), B6 u0.70 1439 / 0 (−5.35 %), B6 u0.775 1443.5 / 0 (−5.65 %), B4c2 1455.7 / 1.67 (−6.44 %) → cheaper at zero violations against all four; planner 0.5 % 1424 / 0: −0.63 / −1.04 / −1.35 / −2.18 %.
- t8: planner 2 % 1045.7 / 2.33 vs B6 u0.70 1064.0 / 1.5 (−1.72 %, +0.83 min) → trade-off; planner 0.5 % 1100 / 0 vs B6 (+3.4 %, −1.5 min) → trade-off; vs v6 979 / 4.0: planner 2 % +6.8 % cost, −1.67 min.
- t11: planner cheaper than B4 / B5 / B6 by 0.92 / 1.96 / 3.39 %, all zero violations; CR 2 % cheaper than the planner by 2.25 % (1269.0 vs 1297.5; predicted (a) +0.40 %, (d) +1.85 %).
- t12: planner cheaper than B4 / B5 / B6 by 1.44 / 1.17 / 1.00 %; vs CR −0.17 %; planner one violating minute in one run (r575 min 51, loss 0.12 %, p99 299 µs); B4 one run with 5 minutes (r571: minutes 3, 18, 20, 21, 22; loss 0.24–0.76 % at the full fleet 4/3; the other run r576 clean).
- t6 same-target B6 0.775: 1443.5 (r498 1434 / r499 1453) — 04-results rev. 3 §3.
- Fill-in cells (r73 §2–§3, out/table4.json; same tolerance rule): t3 2 % planner 1159 (1153–1164) / 3.67 vs B4c2 1233 / 3.67 → dominates (−6.0 %); vs B5c1 1153 (1151–1154) / 4.00 → equal (ranges overlap, viol −0.33); vs B6 u0.70 1228 / 2.00 → trade-off; vs B6 0.775 1179 (1174–1184) / 3.50 → dominates (−1.7 % outside ranges, viol +0.17). t3 0.5 % planner 1182 (1178–1187) / 5.67: vs B4c2 → trade-off (−4.1 %, +2.0 min); vs B5c1 → dominated (+2.5 %, +1.67); vs B6 u0.70 → trade-off; vs B6 0.775 → dominated (ranges overlap, +2.17 min). t5 (n = 1 everywhere): planner 2 % 1457 vs B4c2/B5c1/B6 1464 → dominates ×3 (−7 core-min); planner 0.5 % 1464 = 1464 → equal ×3. t7 2 % planner 1395 (1393–1398) / 1.67: vs B4c2 1441 / 0, B5c1 1413 (1412–1414) / 0, B6 1451 / 0 → trade-off ×3; t7 0.5 % 1428 (1426–1429) / 0: vs B4c2 → dominates (−0.9 %), vs B5c1 → dominated (+1.1 %), vs B6 → dominates (−1.6 %). t4 same-target (planner side): 2 % vs B4 1437 (1437–1437) / 0.50 → trade-off (−2.99 %, +1.5 min), vs B6 1434 (1433–1434) / 0 → trade-off (−2.76 %, +2.0); 0.5 % (1447.7, 1447–1448 / 0) vs B4 → dominated (+0.74 % outside ranges, viol −0.5 < 1), vs B6 → dominated (+0.99 %, viol 0). t8 same-target: 2 % (1045.7, 1007–1078 / 2.33) vs B4 965 (964–966) / 3.00 → dominated (B4 −8.4 % outside ranges; viol +0.67 < 1), vs B6 1012 (1009–1016) / 3.50 → dominates (planner's range contains B6's → cost does not count; viol −1.17); 0.5 % (1100, 1088–1110 / 0) vs B4 → trade-off (+14.0 %, −3.0 min), vs B6 → trade-off (+8.6 %, −3.5). Registered expectations (spec §4.141 item 3 (iii)): t4 2 % trade-off ×2 ✓; t4 0.5 % 'equal or planner dominates' ✗ (dominated ×2); t8 B6 2 % trade-off ✗ (dominates by the rule), 0.5 % ✓; t8 B4 no expectation.
- **rev. 4.3 (2026-11-02, spec §4.141 更正; r73fill/eval_st.py → out/same_target.{json,md}): same-target = baseline knob recalibrated to the planner's ε (§4.33b). Table X 2 % rows against B4* 3.75/300 (t4, t8, t11, t12), B5 4.0/L2 = deployed B5c1 (t3–t7, t11, t12), B6* 0.775 (t3, t4, t6, t8, t11, t12): 17 cells → dominates 12, trade-off 3 (t4 B4*, t4 B6*, t7 B5), equal 1 (t3 B5), dominated 1 (t8 B4*: −8.36 % outside ranges, viol +0.67 < 1). 0.5 % rows against B6 0.70 (t3–t8): 6 cells → dominates 2 (t6 −1.04 %, t7 −1.61 %), trade-off 2 (t3 −3.72 % / +3.67 min; t8 +3.38 % / −1.5 min), equal 2 (t4 ranges 1446–1447 vs 1447–1448 overlap, viol −0.5; t5 1464 = 1464), dominated 0; B4 3.0/300 and B5 3.5/L1 not run. Every verdict identical to the table4.json cell of the same pairing (regrouping only). Cross-target pairings removed from the paper (TR tr/22 §14): t3 0.5 % vs B6* (dominated), t4 0.5 % vs B4* (dominated, +0.74 %), t4 0.5 % vs B6* (dominated, +0.99 %); deployed-but-not-same-target pairings (B4c2 both points, B6 0.70 at 2 %, B5c1 at 0.5 %) also in the TR. Abstract / intro / contribution 2 / conclusion use these counts; "four of eighteen" removed. t8 B4* sentence: 8.4 % cheaper, 0.67 more violation minutes per run, consistent with the load-band statement (1) (baselines cheaper at low load, D1). B4* t8 fidelity miss (−5.39 %) attributed (author, 11-02) to the per-slot HPA model scaling in more than the deployed HPA at low load; recorded as a known implementation deviation in spec §4.141 更正 (no earlier registration; [推測]).**
- [superseded 2026-11-02 by the fill-in block: the planner is dominated by the same-target B4 and B6 on t4 at 0.5 %, by the same-target B4 on t8 at 2 %, by the same-target B6 on t3 at 0.5 % and by B5c1 on t3 and t7 at 0.5 %; 4 of 18 same-target cells (t3 B6 ×2, t4 B4/B6 ×2, t6 B6 ×2, t8 B4/B6 ×2, t11 ×3, t12 ×3); the abstract now says "dominated by a same-target baseline in four of eighteen cells".] "dominated on no trace" (rev. 4 text): by the tolerance rule the planner is not dominated by any arm in any of the ten cells (t4 ×2, t6 ×2, t8 ×2, t11, t12 at 2 %; no arm has both lower cost and ≤ violations). Checked cell by cell above (t11: CR cheaper but flaps 9 vs 2 and the rule is on cost/violations only — CR has lower cost and equal violations (0 / 0) → by the cost/violation definition CR DOES weakly dominate the planner on t11 (−2.25 % outside the run ranges 1268–1270 vs 1296–1299, violations equal). → The sentence "the planner is dominated on no trace at either operating point" must be qualified: "by no baseline"; against CR it is dominated on t11 (cost only). Written so in VI-B and VI-G (3).)

Same-target A-group fidelity: B4 +0.56 / +0.08 %, B5 +0.08 / +0.09 %, B6 −2.26 / −0.06 % (t11 / t12); CR (a) +1.86 / +0.24, (d) +0.33 / +0.04 (r72 §2).

## 8. Cost fidelity, Fig. 4 and VI-A

| item | value | source |
|---|---|---|
| existing cells (S4a/S4b t3–t7, v6 t3–t7, B6 u0.70 t6/t7, B6 0.775 t3/t6) | 19 cells, 18 within ±2 %; outside: v6 t3 +2.93 % (dispatch accounting) | figs/scripts/fig_h2_pred_vs_meas.py residual print (this file §12) |
| new cells (planner 6 C + 5 arms × 2 traces D = 16) | 15 within ±2 %; outside: B6 0.775 t11 −2.26 % | r72 §2 |
| fill-in cells (planner t3/t5/t7 × 2 + same-target B4/B6 × t4/t8 = 10) | 9 within ±2 %; outside: B4 3.75/300 t8 −5.39 % (913.0 vs 965; runs 964/966) | r73 §6 |
| total | 45 cells, 42 within ±2 % | sum |
| planner cells | 14 (6 C + t11/t12 + 6 fill-in), max |err| 0.66 % (t3 0.5 %) | r72; r73 |
| VI-A exceptions named (rev. 4.3) | v6 t3 +2.9 % (dispatch accounting); B6 0.775 t11 −2.3 % (1355 / 1331); B4* t8 −5.4 % (913 predicted vs 965 measured; mechanism not isolated — rev. 4.4 wording, the HPA low-load attribution of rev. 4.3 withdrawn) | this file §7; spec §4.141 更正 |
| four-version adjudication | t4 2 %: (c); CR t11: (d) +0.33 % vs (a) +1.86 %; fill-in: (a)(c)(d) 9/10, (b) 8/8 | r72 §1, §2; r73 §2 |
| B6 t11 two runs | 1355 / 1331 (24 core-min apart) | r72 §2 |
| absolute cell error of the earlier S cells | 2.7 to 23.7 core-min, ≤ 2.8 % of the controllable cost above the 396 core-min floor | 04-results rev. 3 §1 (unchanged) |

## 9. Traces (Setup Table VII additions)

| trace | sensor, window | mean / peak | mp | rise1 | rise10 (pct.) | note |
|---|---|---|---|---|---|---|
| t11 | 4, 2026-10-27 17:00 | 24.3 / 40 | 0.608 | 8 | 11 (P10) | general band, pool rank 7 (6 rejected) |
| t12 | 3, 2026-10-27 17:00 | 29.6 / 40 | 0.741 | 8 | 11 (P10) | high-load fallback band (no stress-band passer in the pool), rank 32 (31 rejected) |

Source: trace files trace_ue_60min_v3_t11/t12.json (features recomputed 2026-10-31: mean, peak, rise1 = max one-minute rise, rise10 = max rise within ten minutes), r71 §4 (ranks, bands), spec §4.139 結果 (pool: Melbourne live 2026-10-26/27, 25,808 rows, 57 windows; same dates as the sealed S7R pool). Library rise10 P10 = 11 (03-setup Table VII caption).

## 10. Operations (VI-F; the actuation table (rev. 4.2 Table XII) moved to the TR tr/22 §14 in rev. 4.3, one sentence kept: planner slot starts 2.5 / 3.1, flaps 2.1 / 1.2 vs CR 3.5 / 3.8 and 4.2 / 4.0; ops definition = exact daemon messages in the scored window, flap = reversal on the same layer within 600 s)

| arm | runs | slot start / stop | emergency | flaps (ops def.) | flaps (rq def.) |
|---|---|---|---|---|---|
| planner 2 % (t4, t6, t8, t11, t12) | 13 | 2.5 / 2.0 | 0.23 | 2.08 | 2.08 |
| planner 0.5 % (t4, t6, t8) | 9 | 3.1 / 1.4 | 0.44 | 1.22 | 3.0 |
| CR 2 % (S4b, t3–t7) | 13 | 3.5 / 3.3 | 0.2 | 4.2 | — |
| CR 0.5 % (S4a, t3–t7) | 13 | 3.8 / 3.2 | 0.2 | 4.0 | — |
| CR 2 % on t11 / t12 | 4 | 4.5 / 6.0 | 0 | 8.0 | 8.5 |
| A:B4 / A:B5 / A:B6 on t11 / t12 | 4 each | 0.2/1.8, 0.0/1.5, 0.0/1.5 | 0 | 1.25 / 0.5 / 1.0 | same |

Sources: planner and D rows this file §12 (ops_analysis_r75.analyse re-run); CR t3–t7 rows ops_table.md pooled (04-results rev. 3 Table 4). rq-definition flaps also count a reversible scale-in that was withdrawn (rq_metrics parses `scale_in_up … cancelled` as a scale-in); the ops definition counts actuations only. Churn-adjusted (α = 3 core-min per flap, simulation, r71 §2): planner vs CR −2.39 % (2 %), −1.97 % (0.5 %); vs the cheapest baseline (B5): 2 % −2.39 vs −2.22 (−0.17 pp), 0.5 % −1.97 vs −2.35 (+0.38 pp).

## 11. Violation attribution (VI-D; unchanged from rev. 3 plus planner)

113 minutes of the 82 main runs: 58 fleet shortage, 43 placement overflow, 12 other (04-results rev. 3 §4). Planner fleet-shortage minutes (B2 rule): t4 2 % minute 20 in 3/3 runs; t8 2 % minute 20 in 3/3; none on t4 0.5 %, t6, t8 0.5 %, t11, t12; fill-in: t3 minutes 3, 4, 5 in 6/6 runs (both points; fleet prediction (b) [3, 4, 5] → hit 18, miss 0, false alarm 0), none on t5, t7 → planner fleet-shortage run-minutes with a fleet-level prediction: 6 + 18 = 24, all predicted (text VI-D: "22 CR and 24 planner run-minutes, no miss"). Fleet-level prediction (b) for the planner: t4 2 % [20, 21, 22] → hit 3 (minute 20), false alarm 6 (21, 22 are placement/other on hardware); t8 2 % [20] → hit 3 / miss 0 / false alarm 0; t8 0.5 % [20] → false alarm 3 (no hardware violation); t4 0.5 %, t6: none / none. Per-slot (c) list [20, 21] equals the hardware violation set in 3/3 t4 2 % runs and in 2/3 t8 2 % runs (r534 adds minute 22).

## 12. Derived values computed for this file (2026-10-31, idle testbed, nice/taskset)

- Fig. 4 residual print (fig_h2_pred_vs_meas.py, unchanged script): cells t3 B6 +0.34, t3 S4a −1.88, t3 S4b +0.71, t3 v6 +2.93, t4 S4a −0.32, t4 S4b −0.49, t4 v6 −0.65, t5 S4a −0.14, t5 S4b −0.07, t5 v6 +0.14, t6 B6(0.775) +0.87, t6 B6 −0.69, t6 S4a −0.97, t6 S4b −0.19, t6 v6 −1.00, t7 B6 +0.42, t7 S4a −0.21, t7 S4b −0.55, t7 v6 −1.96 → 19 cells, 1 outside.
- ops_analysis_r75.analyse on the 38 R72 runs: per-run (ops flaps, rq flaps): r530 2/2, r531 2/2, r532 0/0, r533 0/0, r534 1/1, r535 4/4, r536 0/0, r537 2/2, r538 2/2, r539 2/2, r540 2/2, r541 0/2, r542 2/6, r543 2/5, r544 0/2, r545 1/4, r546 0/2, r547 2/2, r560 1/1, r561 2/2, r562 2/2, r563 0/0, r564 2/2, r565 1/1, r568 2/2, r569 9/9, r570 5/5, r571 1/1, r572 7/8, r573 0/0, r574 1/1, r575 5/5, r576 0/0, r577 9/9, r578 1/1, r579 7/8, r580 1/1, r581 1/1. Cell means (ops): t4 S4p05 0, t8 S4p05 1.67; all other planner cells equal to the rq values.
- ops flaps of the CR reference runs: t4 S4b r303/r314/r322 0/0/0; t4 S4a r502/r312/r317 2/2/2; t6 S4b r405/r411/r416 6/6/6; t6 S4a r402/r414/r419 5/6/6; t8 S4b r476/r500 6/6; t8 S4a r471/r478 8/7; B6 0.775 r493/r505 4/2, r498/r499 0/1.
- classify_b2.classify: r532 {20 fleet, 21 placement}; r533 same; r536 {20 fleet, 21 other}; r534 {20 fleet, 21 placement, 22 placement}; r535, r547 {20 fleet, 21 placement}; r575 {51 placement}; r571 {3, 18, 20, 21, 22 all placement}.
- r68 cal.jsonl summary: S4p 2 %: λ 1.500/1.917, per-split a 1.5 ×6, b 1.75/2.0/1.75/2.0/1.75/2.25; ho risk 0.0202 ± 0.0022, alloc 1267.9 ± 5.7, dispatch 1275.2, flaps 2.81, 0 infeasible. S4p 0.5 %: a 2.25/2.5/2.25/2.25/2.25/2.5, b 3.25/3.5/3.25/3.25/3.75/3.0; 0.0053 ± 0.0010, 1321.0 ± 5.9, dispatch 1327.1, flaps 3.31. APL 2 %: 2.000/2.833, 0.0202 ± 0.0022, 1286.2 ± 5.4; 0.5 %: 3.083/3.708, 0.0050 ± 0.0008, 1341.2 ± 4.1.

## 13. Pending-run markers used in the text

[2026-11-02: all filled by the r73fill block (this file §6–§8, §11, §14); no "[pending runs]" marker remains. The Table X row "t11 / t12, 0.5 %" (never scheduled) was removed.]

## 14. Fill-in block r73fill (2026-11-02; experiment/qsim/r73fill/REPORT.md, out/f.json, out/b2.json, out/table4.json; spec §4.141)

- Runs r582–r605: 22 valid (r585 ng-dead → r604; r591 warm-in gate failed three times → r605). Probes p38 / p39 p99 397 µs, e2e 0.010 %.
- Endpoints: (A) 2 / 6 consistent (t3 trade-off ×2; t5 dominated ×2 at n = 1 with 4 / 2 core-min; t7 2 % dominated, t7 0.5 % equal); (B) (a)(c)(d) 9 / 10 cells, 20 / 22 runs; (b) 8 / 8, 18 / 18; (C) 6 / 12 (none of the six new cells; t7 0.5 % misses by 0.67 core-min).
- I1: hardware start = own initial_fleet in 16 / 22 (t7 2 % 7/2/4 = own but registered alignment 7/3/4, align_fleet did not add the third VyOS, daemon added it in minute 2; t7 0.5 % 7/3/4 = registered, own 8/3/4; t4 B6 6/2/3 vs 5/2/3 ×2; t4 B4 r602 5/2/3 vs 6/2/3).
- Text claims changed in rev. 4.2: 132 → 154 runs; 38 → 60 pre-registered runs; 35/33 → 45/42 cells; planner 8 cells within 0.42 % → 14 within 0.66 %; "weakly dominates CR in all six paired cells" → "six of twelve"; "dominated by no baseline" → "dominated by a same-target baseline in four of eighteen cells"; Table 4 gains t3, t5, t7 rows and same-target verdicts on t4 / t8 (¶ marks where the deployed knob differs).

## 15. rev. 4.3 (2026-11-02; same-target recount, claims re-cut, 14 pages; spec §4.141 更正; r73fill/eval_st.py)

- Same-target counts (this file §7): 2 % 17 cells → 12 / 3 / 1 / 1 (dominates / trade-off / equal / dominated); 0.5 % 6 cells → 2 / 2 / 2 / 0. Removed claim: "dominated by a same-target baseline in four of eighteen cells" (three of the four were cross-target).
- Secondary α = 3 analysis (this file §6): J lower 12 / 14; violations ≤ CR 11 / 14; flaps lower 11 / 12 (t4 0.5 % equal).
- Table VII: two J columns added (planner, CR); range columns kept. Table X: columns B4 / B5 / B6 / CR, 2 % rows at the 2 % knobs, 0.5 % rows at B6 0.70, "not run" for B4 3.0/300 and B5 3.5/L1, ‡ n = 1 (7 / 4 / 2 core-min vs median run range 7 planner / 4 CR), § t8 B6* rule artefact. Table XII (actuations) → TR.
- VI-A exception list (this file §8); Limitations 2 (≤ 2.3 %, n = 2–3, t5 n = 1), 3 (CR cheaper on t11 and t3 2 %; r586), 4 (t8 B4), 5–8 renumbered.
- Differences from the author's task text, reported in the spec: flaps 11 / 12 not 12 / 12 (range −14 to −100 %); violations ≤ CR 11 / 14 strictly (12 / 14 at the one-minute threshold); t5 n = 1 note uses the median run range, not "all".

## 16. rev. 4.4 (2026-11-02; page cuts, no number changed)

- Text only: Fig. 7 (t4 burst mechanism) → TR; Related Work NFV paragraph 173 → 118 words, reproducibility paragraph 76 → 53; VI-D 235 → 146 words (per-minute hit detail → TR); Limitations 8 → 6 (2+3, 7+8 merged); Table VII / X captions ≤ 3 lines, verdict definitions in the body; VI-A B4* t8 sentence = observation (913 vs 965; mechanism not isolated), the rev. 4.3 HPA attribution withdrawn (spec §4.141 更正 synced; §8 row updated); author block placeholders (4 lines); Fig. 6 (fig_cost_viol_t3t8) t3 labels in two columns with crossing-free leaders; Fig. 5 width 0.64 → 0.60 textwidth; float spacing tightened (preamble). Build 14 pages incl. references and author block.

## 17. rev. 4.5 (2026-11-02; no number changed)

- [40] author field plain text; Fig. 6 = t8 panel only (t3 panel → TR ch. 14, figs/fig_cost_viol_t3.pdf); Fig. 5 at 0.88 columnwidth; Section V artifact path → "[artifact DOI]". 14 pages.

## 18. rev. 4.6 (2026-11-02; architecture figure, terminology, page cuts; no number changed)

- Fig. 4 redrawn as a double-column architecture diagram (tex/fig_testbed_tikz.tex: 7 in × 2.15 in picture, 7 pt minimum, plus a four-row hardware/software table). The V-B specification sentence of rev. 4.5 is now that table, values unchanged: sender Ryzen 7 7700, E810, UERANSIM 3.2.8 (40 pairs), TRex v3.08, VPP v26.06; host Ryzen 9 9950X, 60 GB, ConnectX-5 VFs, Harvester v1.7.1, RKE2 v1.33.10; worker-0 6 vCPU (open5gs 2.7.5 + 2 slots), worker-1..3 3 vCPU, vyos-0..2 VyOS 1.5 / VPP 25.10.0 / 2 vCPU, eUPF 0.6.0, master daemon 30 s tick, DN reflector XDP_TX. Per-layer marks in the figure are Table II's: ready lead 30 / 150 / 120 s, unit 5 UE / 16.5 UE / 2 slots, 0.8 / 2 / 3 cores, fleet 2–8 / 1–3 / 1–4.
- Terminology (text, table headers and figure legends): B4c2 → HPA (code at first mention, Intro), B5c1 → Holt-forecast HPA (code at first mention, Related Work), B6 → multi-predictor (idem), v6 → "hand-tuned model-based controller (v6)" at first mention; worker VM defined as a Kubernetes worker node hosting the eUPF pods; VyOS marked VNF and eUPF CNF at first mention (Intro §1); Index Terms = 5G user plane, NFV, Kubernetes, autoscaling, SLO, risk calibration, eUPF, SecGW. Legend labels of Figs. 3, 5, 6 renamed (figs/scripts/palette.py and the three scripts); **Fig. 3 legend corrected**: the plotted baselines are the same-target knobs HPA 3.75/300, Holt-forecast HPA 4.0/L2, multi-predictor 0.775 (the rev. 4.x legend had said "B6 (u = 0.70)" while plotting r67band/out/B6_0.775.json; data unchanged).
- V-A scope sentence added (SR-IOV, VPP, XDP on a single-host KubeVirt testbed; no RAN, no mobility, 40 UEs); Limitations item 5 adds "every hardware number comes from one single-host testbed".
- Page cuts (word count of the paragraph before → after; ≈ 11 words per column line): V-B specification 96 → 0 (moved to the Fig. 4 table); V-D harness 281 → 209; IV-B(2) 181 + 70 → 149 (two paragraphs merged; the registration-list parenthetical and the systematic-start-pattern sentence are in the technical report); VI-C 171 → 132; Related Work reproducibility 56 → 41; Fig. 1 inset table removed (its rows are Table II), figure height 3.2 → 2.65 in. Additions: Intro §1 +51 words, V-A +20, Related Work baseline names +9, Limitations +10, Fig. 4 float ≈ +38 column lines over the rev. 4.5 single-column figure.
- Pages: 14 with microtype (tex/preamble.tex, layout only); without it 14 pages + 5 lines. The target of ≤ 13.5 pages is not reached (about 70 column lines short); candidates are listed in the check list (working file, not in this record).
