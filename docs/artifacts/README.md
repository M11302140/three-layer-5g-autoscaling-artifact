<!-- rev. 4.4 (2026-11-02): index of the artifact repository (third layer of paper / technical report / repository). Numbers are never defined here; they live in numbers.md with their sources. -->
# Artifact repository index

## Three layers and how they divide the work

| layer | what it holds | where | identity |
|---|---|---|---|
| Paper (IEEE TNSM manuscript) | the claims and the numbers that support them, 14 pages, 11 tables, 6 figures; every number traceable through numbers.md | docs/paper/0*.md → tex/main.pdf | git commit of docs/paper (rev. 4.2 a6a58fc, rev. 4.3 f3a1ddf, rev. 4.4: this commit) |
| Technical report (arXiv) | the analyses, full tables, per-run results, registration record, rejected variants and removed figures that the paper cites once (\cite{companion-tr}); 14 topic chapters | docs/paper/tr/*.md → tr/arxiv/tr.pdf | same commit; arXiv id to be filled |
| Repository (this index; Zenodo record) | raw data, scripts, reports of every analysis round, the lab ledger (ledger/), and the build chain from raw run to paper number | this record (docs/artifacts, registrations-and-reports/, ledger/) | Zenodo DOI in the root README |

Reading order for a number in the paper: paper sentence → its HTML comment in the chapter .md (source tag such as "N§7" or "r73fill/REPORT.md §2") → numbers.md section → the cited REPORT.md or rq table below → the raw run files.

## Contents of this directory

| group | files | what they are | produced by |
|---|---|---|---|
| Lab ledger (specification) | ../../proposals/v8-echelon-algorithm-spec-2026-10.md | the running specification: registrations §4.139 (planner block), §4.140 (execution and results), §4.141 (fill-in block, results, correction note of 2026-11-02); rulings, voiding rules, stop conditions | the author and the assistant, dated entries; git history = time anchor |
| Analysis-round reports | ../../../experiment/qsim/r62ab, r62cf, r62de, r63a, r63bf, r63r, r66rr, r67band, r68unif, r70eq, r71fin, r72hw, r73fill, m1, madrid: REPORT.md + out/ | one report per round, each with its script (eval_*.py, report_*.py) and JSON outputs; the sources cited in numbers.md | the round's scripts on the frozen simulators |
| Derived metrics | ../../../experiment/paper_out_new/rq/rq_metrics.py, rq_metrics.csv, rq_metrics.md; paper_out_new/ops/* | per-run alloc_vm, SLO minutes, flaps and the group table of all valid runs (MAIN, R72, R73 groups); the actuation counts under the ops definition | rq_metrics.py over experiment/p2/trace_v7_r*.csv and the daemon logs |
| Raw runs | ../../../experiment/p2/trace_v7_rNNN.csv / .log, chain_v7rNNN*, s_ledger.tsv, main_exp*.log | harness per-minute output of every run (valid and voided), chain logs, the ledger with the validity class and reason | trace_run.py (harness), run_chain.sh, main_exp*.sh drivers |
| Scripts | ../../../experiment/qsim/*.py (frozen simulators and calibration), experiment/p2/*.sh *.py (harness, drivers, guards), docs/paper/figs/scripts/*.py (figures), tex/md2tex.py, tex/build.sh, tr/arxiv/build_tr.py | the whole chain from raw run to PDF | — |
| Artifact tables (this directory) | 46 *.md files, one table family each (per-run-t3…t7, operations-per-arm, flap-decomposition, equal-risk-baselines, lever-decomposition, calibration-*, madrid-*, registration-files, freeze-timeline, …) | verbatim table files that the TR chapters reproduce; each carries its source comment | copied from the round reports when the paper was restructured (R67–R74) |

## Hash and version map

| object | version / tag | how to check |
|---|---|---|
| paper rev. 4.4 | git commit of docs/paper (see the root README, Hashes and versions) | `git log --oneline -1 -- docs/paper/tex/main.pdf` |
| technical report | same commit; tr/arxiv/tr.pdf | `git log --oneline -1 -- docs/paper/tr/arxiv/tr.pdf` |
| frozen simulators | v8sim10.py 3daf1387, v8sim10_abl.py 7a2b02ec, v8sim11.py ecdfff61, v8sim2.py 4697713c, v8sim_b6.py b24eae16, prior_traces.json edb8e00c (md5, first 8 hex) | `md5sum experiment/qsim/{v8sim10,v8sim10_abl,v8sim11,v8sim2,v8sim_b6}.py experiment/qsim/prior_traces.json` |
| daemon images per arm | 6.0-s4 (planner / CR, frozen), 6.0-q6 (v6, B1, B4, B5), 6.0-q9 (B6), 6.0-q11 (B5c1 in the main experiment, same-target B6), 6.0-s9 (planner block); code-name map in the TR introduction | hhro-daemon git tags; deploy/ablation/*.yaml |
| harness | trace_run.py r33b (main experiment), r34a / r34c (later blocks) | experiment/p2/trace_run.py header |
| registration anchors | spec §4.139 / §4.140 B / §4.141 entries with their dates; registration files with embedded sha256 (thresholds, sampling log, predict_*.json); the TR freeze-timeline chapter lists the commit hashes | `git log -- docs/proposals/v8-echelon-algorithm-spec-2026-10.md` |
| run validity | experiment/p2/s_ledger.tsv (class ok / void with reason per run id); the voided runs and reasons are in the TR harness chapter | — |
