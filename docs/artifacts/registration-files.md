<!-- artifact file of the paper "Predictable-Cost Autoscaling of a Three-Layer 5G User Plane with Library-Calibrated Risk" (docs/paper), written 2026-10-21 (R64, spec §4.109) when Appendix D (registration files, simulator revisions, code and data, artifact index) was moved out of the paper for the page limit; text and numbers verbatim from the r63 version (docs/paper/snapshots/r63/), source comments kept. -->

# Registration files, simulator revisions, code and data, and the artifact index

The experimental-setup chapter keeps one paragraph with the three-part evidence chain (contemporaneous evidence, retrospective snapshot, held-out status); the full former Appendix D follows.


<!-- Compiled 2026-10-20 from spec §4.32 item 1 (tag v7.1.3-frozen), §4.37 (t3 to t5 registration, 2026-10-07 02:50), §4.77 B (t6/t7 registration, 2026-10-15 00:17), §4.53 execution rule 3 (prior_traces.json sha256 7d5a247b…ceebbb), m1/REPORT.md (reproduction check), ops/madrid/abl reports. [TBD: path/URL] marks items without a public location yet. -->

Contemporaneous evidence. The registration files carry embedded generation timestamps and are identified by their SHA-256 hashes, listed below with the first 12 hexadecimal digits. The campaign log records the hash of the t6/t7 threshold file before the first t6 run (2026-10-15 00:18), and its timestamps record the first block start at 2026-10-09 12:38:55, after all t3 to t5 registrations. The hashes of the prediction files were not logged; their numbers are quoted in specification entries dated before each block. <!-- spec §4.103 (main_exp.log line 372 "PASS 門檻雜湊一致 (file d828f20ff5c07c18)" before line 383 "[2026-10-15 00:18:29] BLOCK t6 START"; prediction numbers quoted in §4.37 (2026-10-07) and §4.77 B (2026-10-15)); §4.102 (7) (first block start); hashes from scratchpad/prereg_sha256.txt and §4.102 (7) --> <!-- 2026-10-21 (spec §4.107 F, Minor 2): the former paragraph "Registration evidence" split into contemporaneous evidence and retrospective snapshot; the first-block-start sentence moved here from below the file list -->

Retrospective snapshot. The repository snapshot containing all registration files was committed on 2026-10-20 (commit fd62007, tag prereg-snapshot-2026-10-20) and is available to reviewers; it anchors the files at the time of commit, not earlier. <!-- spec §4.103 (snapshot commit fd6200729763b697238d9cd8c3d611ca8b0a75e1, 2026-10-20 23:32:53 +0800) --> The registration files, with their embedded generation timestamps and hash prefixes, are:

- `v8_predict_t345_2026-10-07.txt` (t1 to t5, S4a and S4b): generated 2026-10-07 02:46:35, SHA-256 3a07476271e7.
- `v8_predict_v6_t345_2026-10-07.txt` (t1 to t5, v6): 2026-10-07 15:06:53, a9eaaf4ae50f.
- `t6t7_thresholds.json` (sampling thresholds, with the hashes of the library and of the sampling script): frozen at 2026-10-11 19:17:32, d828f20ff5c0.
- `t6t7_sampling_log.txt`: 2026-10-15 00:16:56, 1d07de25adf0.
- `v8_predict_t67_2026-10-15.txt` (t6 and t7, all registered arms): 2026-10-15 00:16:57, 5def27dea12b.

<!-- 2026-10-21: sentence 'The campaign log records the first block start at 2026-10-09 12:38:55, after all t3 to t5 registrations' moved into the paragraph 'Contemporaneous evidence' above; §4.102 (7); old S.14 -->

Simulator revisions and held-out status. The table below dates every change of the simulator or of its cost accounting against the hardware blocks. <!-- added 2026-10-21 from drafts/G-timeline-algorithm.md (R62 item G, §4.105 G); sources per row as in the draft: §4.17, §4.19, §4.25, §4.31, §4.37, §4.77 B -->

| date (2026) | event | runs | held-out status |
|---|---|---|---|
| 10-05 | G2, registered in dispatch accounting; t1 cost gate fails three times (−5.0, −3.0, −2.1 %) | r239 to r246 | used to diagnose the simulator <!-- §4.17, §4.19 item 0 --> |
| 10-05 14:50 | hardware cost metric fixed to VM-existence billing (alloc_vm) | n/a | n/a <!-- §4.19 --> |
| 10-05 to 10-06 | G2b, λ frozen (v7.1.3), registered in dispatch accounting | r247 to r263 | 12 of 12 within ±1 % under vmexist: not held out <!-- §4.25, §4.31; §4.105 G --> |
| 10-06 00:30 | vmexist accounting added (create +30 s, delete +5 s) from VM existence measured on r241, r247, r248, r250, r251 | n/a | n/a <!-- §4.25 --> |
| 10-07 02:46 | t3 to t5 predictions registered (vmexist used for H2) | n/a | held out <!-- §4.37 --> |
| 10-09 to 10-14 | main experiment, t4, t5, t3 | r300 to r383 | fully held out |
| 10-15 00:17 | t6, t7 predictions registered (vmexist) | n/a | held out <!-- §4.77 B --> |
| 10-15 to 10-17 | main experiment, t6, t7 | r402 to r448 | fully held out |

Table. Simulator revisions and the held-out status of each hardware block; QEMU appears 22 to 38 s after the create order and vanishes 3 to 8 s after the delete order (Simulation chapter, Validation). <!-- drafts/G-timeline-algorithm.md table, shortened 2026-10-21 for the page budget; accounting column merged into the event column -->

No simulator or λ change was made after 2026-10-07; every main-experiment run is held out with respect to both the calibration and the accounting. <!-- drafts/G-timeline-algorithm.md; §4.105 G --> Algorithm 1 of the calibration is given in the Method chapter, calibration procedure (Algorithm 1). <!-- §4.105 G -->

Code and data. The frozen controller is the hhro-daemon tag `v7.1.3-frozen` (image 6.0-s4, operating-point files S4a.yaml and S4b.yaml); the frozen simulators (`v8sim2`, `v8sim3`, `v8sim7`, `v8sim10`, `v8sim11`), the calibration script `v8sim10_cal.py` and the prior library `prior_traces.json` (SHA-256 7d5a247b...ceebbb) are in `experiment/qsim/`; per-run hardware results are in `rq_metrics.csv`, the trace CSVs, the daemon logs and the run ledger `main_exp_ledger.tsv`. On 2026-10-20 the frozen simulators reproduced the whole-library risks at the deployed λ (S4a 0.467 %, S4b 1.886 %, v6 2.388 %) and all 21 registered per-trace predictions identically, and a second run of t6 gave the same result. A public location for these artifacts is still to be set up [TBD: URL]. <!-- old S.14 items 2 to 8; §4.32 item 1; §4.53 execution rule 3; m1/REPORT.md Checks; §4.100 A -->

Artifact repository (docs/paper/artifacts/, one Markdown file per item): per-run-t3.md to per-run-t7.md (per-run results, all runs); secondary-statistics.md; warm-in-interventions.md; t4-slot-holding.md; conditional-risk-three-levels.md; ablation-per-split.md; lever-decomposition.md (S4b and S4a); simulator-sensitivity.md; operations-per-trace.md; flap-decomposition.md (with both flap definitions); madrid-features.md (with the compressed-library contrast); coverage-analysis.md; fairness-full.md; voiding-sensitivity.md. Added 2026-10-21 (round-62 analyses, simulation only): equal-risk-baselines.md, conditional-calibration-rise1.md (with the bucket figure), knob-monotonicity.md, calibration-uncertainty.md, conversion-sensitivity.md, lead-tails.md, operations-price-J.md and emergency-parity.md; moved out of the paper for the page budget: voided-runs.md, operations-per-arm.md, residual-minutes.md, emergency-firings.md and madrid-transfer.md. Added 2026-10-21 (round 63): risk-fidelity-and-violation-classes.md, host-cpu-burned.md and calibration-cost.md; calibration-uncertainty.md, ablation-per-split.md, conditional-calibration-rise1.md, madrid-transfer.md and lead-tails.md now open with the leakage-free recomputation and keep the earlier tables below it. <!-- spec §4.107 A to E; files written 2026-10-21 from qsim/r63a, r63r, r63bf reports -->  <!-- §4.104 H item 4; files written 2026-10-21 from qsim/r62ab, r62cf, r62de reports -->

Added 2026-10-21 (R64, spec §4.109), moved out of the paper: relaxed-reference-derivation.md (former Appendix A), registration-files.md (this file, former Appendix D), decision-path-rules.md (full Table I with its origin notes), decision-equivalence.md (former Simulation subsections "Decision equivalence" and "The −2 % source", full text); emergency-firings.md, residual-minutes.md and risk-fidelity-and-violation-classes.md received the text of former Appendices B and C and of the H2b section; figs/fig_timeseries_t6_r63.pdf is the five-row version of the t6 time-series figure.
