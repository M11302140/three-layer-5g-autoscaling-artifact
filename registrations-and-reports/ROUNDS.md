# Analysis rounds

One line per round directory. "Paper" = where the manuscript uses the round's output (via `docs/paper/numbers.md`, section numbers "N§"); "TR" = used by the technical report only. Dates are those in the round's REPORT.md or ledger section. REPORT.md files are kept as written.

| round | date (2026) | purpose (ledger §) | main outputs | used in |
|---|---|---|---|---|
| abl | 10-20 | component ablation at equal risk on the nest2 copy `v8sim10_abl.py` (§4.99 C) | ablation_table.md, ablation_raw.json, equiv_check.txt | TR (ablation); paper Section 1 mentions the ablation arms A1–A4 of the earlier hardware campaign only |
| m1 | 10-20 | M1: conditional risk of ε, library features vs measured tail risk, effective n (§4.99 A) | REPORT.md, analysis.json, features.csv, features_table.md | TR (calibration chapter); paper IV-A ε definition |
| madrid | 10-20 to 10-22 | second data set: Madrid LTE traces, feature tables, transfer and recalibration (§4.99 B, §4.104) | build_tables.md, features_*.csv, recal_table.md, bibtex.txt; traces in `data/madrid-derived/` | paper VI-F (Madrid paragraph); TR Madrid chapter |
| r62ab | 10-21 | conditional λ, uncertainty and event rates (§4.104 A, B) | REPORT.md, results.json, report_tables.md, matrix.npz | TR |
| r62cf | 10-21 | equal-risk baselines (C) and operations cost, emergency-rule parity (F) (§4.104) | REPORT.md, c_tables.md, f1_table.md, calib_results.json | TR (equal-risk baselines, emergency parity); paper Table X same-target knob definition via §4.33b |
| r62de | 10-21 | workload-conversion sensitivity (D) and lead-time tails (E) (§4.104) | REPORT.md, out/ | TR |
| r63a | 10-21 | σ̂ leakage correction and nested uncertainty (§4.107 A) | REPORT.md, results.json | TR; paper IV-A (leakage-free σ̂) |
| r63bf | 10-21 | §4.107 tasks B–F (minor items) | REPORT.md, results.json | TR |
| r63r | 10-21 | recomputations required by the §4.107 A rule failure (leakage-free σ̂): ablation, Madrid t1, test-trace tables | REPORT.md, out/ | TR |
| r65boot | 10-21/22 | run-bootstrap intervals of the cost differences S4b − arm (fourth-review response, §4.112 / §4.113) | REPORT.md | paper VI-B (bootstrap intervals); TR |
| r65slot | 10-21/22 | per-slot (v8sim11, R38 on) calibration of S (§4.112 A) | REPORT.md, tables.md, split_*.json | TR (per-slot calibration); paper IV-A |
| r66ab | 10-22/23 | emergency-rule A/B on the tuned baselines, acceptance (i)–(iii) (round 66, §4.114) | REPORT.md | TR (hardware A/B); paper VI-A sentence on the rule |
| r66audit | 10-24 | session-count audit of every run (median offset) (round 70, §4.117) | REPORT.md | paper voiding rule (r316, r407); TR chapter 9 |
| r66drain | 10-25 | drain-residue audit of the slot exclusion windows, decision audit, re-run rule (§4.118, §4.119) | audit_all*.md, decision_audit*.md, group_summary.md | paper Section V valid-run rule; `raw-runs/RUN_INDEX.csv` re-runs r502–r505 |
| r66h | 10-24/25 | B6 knob block H (u = 0.775) on hardware vs S4b (H item §4.116; re-run judgement §4.118) | REPORT.md, REPORT_rerun.md | paper Table X same-target B6 rows; Section 1 run count (4) |
| r66rr | 10-25 | judgement of the five re-runs and the t8 frontier (§4.121) | judge.py, judge_out.txt, frontier.py, frontier_out.txt | paper Section 1 run counts (t8 8 runs), Table IX t8 rows |
| r67band | 10-27 | load-band equal-risk cost decomposition (§4.135) | REPORT.md, out/, fig_band_cost.pdf | paper IV-E (N§5), Fig. load band |
| r68unif | 10-27 | risk uniformity, per-layer additive ablation, S4′ by band, per-slot whole-library risk (§4.136) | REPORT.md, out/cal.jsonl | paper IV-E, Table II planner deployment point (N§2, N§5) |
| r69chk | 10-27 | B5c1 check on t6/t7 traces and S8 calibration (§4.137) | REPORT.md, out/ | TR |
| r70eq | 10-27 | equal-risk frontier per slot, library calibration audit (§4.138) | REPORT.md, out/, fig_frontier_perslot.pdf | paper IV-D equal-risk table (N§4) |
| r71fin | 10-28 | equal-risk pinch-point refinement, S4′ hardware registration and predictions (§4.139) | REPORT.md, out/e1.json, out/predict.json | paper Table II, IV-D, VI-E endpoints (N§2, N§4) |
| r72hw | 10-28 to 10-31 | S4′ on hardware: 38 runs, endpoint judgement E, equivalence replay (§4.140) | REPORT.md, out/e.json, eval_e.py, equiv_nest2.py | paper VI-B paired cells, VI-E, IV-A/IV-B equivalence (N§3, N§6) |
| r73fill | 10-31 to 11-02 | the 22 fill-in runs: judgement, same-target recount (§4.141) | REPORT.md, out/f.json, out/b2.json, out/table4.json, out/same_target.{json,md} | paper Table X, VI-A exceptions, VI-B fill-in cells (N§6, N§7, N§14, N§15) |
