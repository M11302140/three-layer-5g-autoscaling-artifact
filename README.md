# Data and scripts for "Offline-Calibrated Three-Layer Autoscaling for the 5G User Plane: Pre-Registered Hardware Validation of Cost, Churn and Risk Shape"

This record holds everything needed to check every number in the paper (IEEE TNSM submission, manuscript rev. 4.7) and in its companion technical report (arXiv): the pre-registration ledger, the frozen simulators and their trace library, the per-round analysis reports, the per-run hardware metrics, the raw per-run output of the testbed, the controller source, the harness scripts. The paper and the report themselves are not part of this record (manuscript via the journal, report via arXiv).

Record licence on Zenodo: "Other (Open)". Three licences apply, see `LICENSE` and the Licences section below.

## How to check a number in the paper

1. Every sentence with a number in the paper source carries an HTML comment naming its source, such as `N§7` (section 7 of `docs/paper/numbers.md`) or `r73fill/REPORT.md §2`.
2. `docs/paper/numbers.md` maps each number to the report or table that produced it.
3. The report is under `registrations-and-reports/<round>/REPORT.md`; its JSON outputs are in `<round>/out/`, and the script that wrote them sits next to it.
4. Per-run hardware numbers come from `hardware-metrics/rq/rq_metrics.csv` (one row per run, group column = block). They are computed by `rq_metrics.py` from the raw per-run files in `raw-runs/`.
5. Run validity is in `raw-runs/RUN_INDEX.csv`: one row per run id (trace, arm, block, status valid / voided / harness-fault / trial / not-used, reason, replacing run id, whether raw files exist, and the source ledger of the row). It is merged from the six run ledgers in `harness-and-manifests/p2/` (`main_exp_ledger.tsv`, `a_`, `ab_`, `g_`, `h_`, `s_ledger.tsv`), from the group column of `rq_metrics.csv` and from the voided-run table of report chapter 9; the ledgers keep the operator's original wording.
6. The pre-registered predictions and thresholds are the files listed in `docs/artifacts/registration-files.md`, with their embedded timestamps and SHA-256 prefixes; the registration text is in the specification ledger `ledger/v8-echelon-algorithm-spec-2026-10.md` (index of the cited sections: `ledger/INDEX.md`) (sections 4.139 to 4.141 for the planner block, the execution and the fill-in block).

## Directory layout

| directory | contents | size |
|---|---|---|
| `sim-and-library/` | the six frozen files (`v8sim10.py`, `v8sim10_abl.py`, `v8sim11.py`, `v8sim2.py`, `v8sim_b6.py`, `prior_traces.json`; byte-identical to the registered md5, see `FROZEN_MD5`), the calibration and library scripts (`make_prior.py`, `export_prior.py`, `make_gtrace*.py`, `ped_merge.py`, `ped_poll.sh`, `lib_percentiles.py`, `cv*.py`, `fit_holt.py`), the registered prediction files (`v8_predict_*.txt` with their scripts), the t6/t7 sampling files (`t6t7_*.json`, `t6t7_sampling_log.txt`), `heldout.json`, and `registration-rounds/` (s4t, s5, s6, s7, s7r, s9, serial, cov: the calibration rounds with `out/cal.jsonl` and `out/predict.json`) | 2.7 MB |
| `registrations-and-reports/` | one directory per analysis round (r62ab, r62cf, r62de, r63a, r63bf, r63r, r65boot, r65slot, r66ab, r66audit, r66drain, r66h, r66rr, r67band, r68unif, r69chk, r70eq, r71fin, r72hw, r73fill, m1, abl) with `REPORT.md`, the evaluation scripts (`eval_*.py`, `report_*.py`, `ctlgen*.py`, `dver.py`, `equiv*.py`) and `out/`; `madrid/` holds the Madrid feature and transfer scripts and tables (not the traces, see `data/`) | 182 MB |
| `hardware-metrics/` | `rq/rq_metrics.py`, `rq_metrics.csv`, `rq_metrics.md` (all hardware runs, per-run metrics and group tables), `ops/` (actuation counts, flap decomposition), `fig-side-tables/` and `tables/` (CSV side tables of the figures and of the report chapters) | 0.6 MB |
| `raw-runs/` | `RUN_INDEX.csv` (status of every run id; in the repository) and, in the release asset `raw-runs.tar.zst` only, the per-run raw output for every run id r1 to r605 (valid and voided): `trace_v7_rN.csv` (harness per-minute rows), `trace_v7_rN_1s.csv` (per-second), `trace_v7_rN.log` (harness log), `v7rN_daemon.log` (controller log), `host_vmcpu_v7rN.csv` (host CPU per VM), `chain_v7rN*.log` / `prep_` / `enable_` / `park_` / `finish_` / `postrun_` (driver stages), `tK_v7rN.log` (block driver log for trace K), `prom/v7rN_*.csv` (Prometheus per-minute samples: node CPU allocation, pod CPU, pod memory) | 659 MB |
| `harness-and-manifests/` | `trace_run.py` (workload harness), `trex_traffic.py` (TRex streams), `traces/` (the per-minute UE traces played by the harness: `trace_ue_60min_v3_tK.json` for t3 to t12, warm-in traces `trace_warmin_*.json`), `p2/` (block drivers `main_exp*.sh`, `run_chain.sh`, `run_trace2.sh`, `run_queue2.sh`, `abl_queue*.sh`, `align_fleet.sh`, `trex_recover.sh`, `deploy_daemon.sh`, warm-in guards, the run ledgers `main_exp_ledger.tsv`, `a_ledger.tsv`, `ab_ledger.tsv`, `g_ledger.tsv`, `h_ledger.tsv` and `s_ledger.tsv`, the driver logs `main_exp*.log`, `s_exp*.log`), `deploy/` (controller manifest and the per-arm operating-point manifests `deploy/ablation/*.yaml`: S4a/S4b = CR, S4p2/S4p05 = planner, B1 to B5 baselines, A1 to A4 ablations, Q* quantile variants) | 1.4 MB |
| `daemon-source/` | controller source snapshots without git history: `hhro-daemon-s4p/` (branch s4p at 1236cea, which contains e6d0724; image 6.0-s4p; with both planner flags off it is decision-identical to the frozen 6.0-s4 source, tag v7.1.3-frozen), `hhro-daemon-q6/` (tag v7.0.5-q6; image 6.0-q6: v6, B1, B4, B5 arms), `hhro-daemon-q9/` (image 6.0-q9: multi-predictor B6 u = 0.70) and `hhro-daemon-q11/` (image 6.0-q11: Holt-forecast HPA and same-target multi-predictor), both recovered from the images' build-stage layers and tied to the image binaries by sha256, `src_q11e/` (image 6.0-q11e, emergency-parity test build), each with its `Dockerfile`; `IMAGES.md` lists tags, commits, binary and image digests | 11 MB |
| `data/melbourne-derived/` | the trace libraries derived from the City of Melbourne pedestrian counts: `gtrace2/` (the merged count table `ped2026_merged_1022.csv`, the 1615-trace pool `g2_pool.json`, sampling result and log), `t910/` (the high-load pool used for t9 to t12 and its scripts) | 48 MB |
| `data/madrid-derived/` | the traces derived from the IMDEA Madrid LTE dataset (`madrid_*.json`), under GPL-3.0 with its own `LICENSE` and `README.md` (citation requirement) | 3 MB |
| `ledger/` | the specification ledger `v8-echelon-algorithm-spec-2026-10.md` (every protocol, registration, ruling, voiding rule, result record and correction, dated sections §4.1–§4.141, in Chinese, kept byte for byte), the design proposal it implements, `README.md` (nature, language, how to read it) and `INDEX.md` (every ledger section the paper cites: date, content, paper table, registration file) | 0.9 MB |
| `docs/` | `paper/numbers.md` (every number of the paper with its source), `artifacts/` (46 table files reproduced by the report, `registration-files.md`, `README.md` index), `figure-scripts/` (the scripts of the paper's figures, `palette.py`), `README.md` (contents and the manuscript revision-number table) | 0.5 MB |
| `LICENSE`, `SANITIZATION.md`, `FROZEN_MD5`, `SHA256SUMS` | licences; what was redacted and how; the registered md5 of the six frozen files; SHA-256 of every file | |

Total ≈ 0.9 GB: 248 MB in the repository, 659 MB (101 MB compressed) in the release asset `raw-runs.tar.zst`. After unpacking the asset in the repository root, `sha256sum -c SHA256SUMS` checks every file of the record.

## Not included, and why

- The Melbourne pedestrian source data (4.6 GB CSV snapshots, City of Melbourne Open Data Portal, CC BY 4.0). `sim-and-library/ped_poll.sh` holds the download URL and the polling recipe; `ped_merge.py` and `make_gtrace2.py` rebuild the merged table and the pool, whose SHA-256 are in `SHA256SUMS`.
- The Madrid LTE source files (`users_*.csv`, 263 MB, GPL-3.0, IMDEA Networks). Only the derived traces, the derivation scripts (`registrations-and-reports/madrid/mad_*.py`) and their checksums are included.
- Docker images. Each snapshot has its `Dockerfile`; the image digests used on the testbed are in `daemon-source/IMAGES.md`.
- Git history, of either repository. The full history of both the controller repository and the authors' main repository (specification ledger, registration files, paper) was scanned with the same pattern set as `SANITIZATION.md`; both contain testbed addresses and credentials in older commits (main repository: 96 of 740 commits since 2026-06-13 carry a password), so no git bundle is attached. Registration timestamps are the commit times recorded in the ledger; repository history is available to reviewers on request. The commit hashes named in the paper and the report are listed in `daemon-source/IMAGES.md` and in the Hashes section below, and working-tree snapshots at those commits are what this record holds.
- The paper and report LaTeX sources (journal and arXiv submissions).
- Files with real addresses, credentials or kubeconfigs: everything here was passed through the redaction described in `SANITIZATION.md`.

## Hashes and versions

| object | identity |
|---|---|
| paper rev. 4.7 and report | commit 9fc2872 of the paper repository (`docs/paper`), 2026-11-02 |
| pre-registration snapshot | commit fd62007, tag `prereg-snapshot-2026-10-20` (registration files, campaign log, ledger, spec as of 2026-10-20) |
| frozen simulators | md5 (first 8 hex) v8sim10.py 3daf1387, v8sim10_abl.py 7a2b02ec, v8sim11.py ecdfff61, v8sim2.py 4697713c, v8sim_b6.py b24eae16, prior_traces.json edb8e00c (sha256 7d5a247b06b6…); full md5 in `FROZEN_MD5` |
| controller, CR and planner arms | hhro-daemon branch s4p @ 1236cea (planner flags added in e6d0724), image 6.0-s4p, docker image id sha256:9f29a2fe8d93e2c64d81a549e95e708835afca43624ae9ce54448e492564333b; frozen CR source tag v7.1.3-frozen (1bd509b), image 6.0-s4 digest sha256:27f31bccc9002f96b511cc443f3c9bcd4b0f5cf5fc2793da890a5cc476775110 |
| controller, v6 / B1 / B4 / B5 arms | tag v7.0.5-q6 (3a5d8c9), image 6.0-q6 id sha256:394e4e4d428939f35a09f319bacd5a78a77afcc5292319b84685df0253e82939 |
| controller, multi-predictor B6 u = 0.70 (main experiment) | `hhro-daemon-q9` (build-stage source), image 6.0-q9 id sha256:994e432739b3…, binary sha256 6fee327e… |
| controller, Holt-forecast HPA and same-target multi-predictor | `hhro-daemon-q11` (build-stage source), image 6.0-q11 id sha256:611af382e1b1…, binary sha256 f0e0b574… |
| harness | `trace_run.py` (header carries the revision; r33b for the main experiment, r34a / r34c for the later blocks) |
| registration files | listed with SHA-256 prefixes in `docs/artifacts/registration-files.md` |

The controller snapshots in `daemon-source/` are the redacted copies of the source trees; rebuilding an image from them does not reproduce the image digests in the table, because the redaction changed bytes of the source (see `daemon-source/IMAGES.md`, section "What the snapshots can and cannot reproduce").

## How to run (environment variables)

The redaction replaced every credential in the scripts by an environment variable and every default password in the controller source by the empty string. Nothing in this record contains a usable credential; to run the harness or the controller on a testbed, set:

| variable | used by | purpose |
|---|---|---|
| `SUDO_PASS` | `harness-and-manifests/trace_run.py`, `p2/*.sh` | sudo password on the traffic-generator host (`echo "$SUDO_PASS" \| sudo -S`) |
| `SSH_PASS` | `trace_run.py`, `p2/*.sh` (`sshpass -p "$SSH_PASS"`) | ssh password of the user on the master VM, the worker VMs and the traffic-generator host |
| `VYOS_PASS` | `p2/*.sh` | ssh password of the VyOS (SecGW) VMs |
| `HOST_SSH_USER`, `HOST_SSH_PASSWORD` | controller (`internal/sshexec`) | default ssh user and password for the hosts below; each may be overridden by `UERANSIM_SSH_USER/_PASSWORD`, `WORKER_SSH_USER/_PASSWORD`, `HARVESTER_SSH_USER/_PASSWORD`, `HOST_SUDO_PASSWORD` |
| `UERANSIM_HOST`, `WORKER_HOST`, `HARVESTER_HOST_SSH`, `HOST_MGMT` | controller | `host:22` addresses of the traffic-generator host, worker-0, and the virtualisation host (placeholders `10.0.0.x` in the source) |
| `HOST_USER`, `HOST_PASS` | controller (`cmd/hhro-daemon/daemon.go`) | ssh user and password of the virtualisation host for the CPU-housekeeping calls |
| `IPSEC_SEG_MGMT`, `IPSEC_SEG_USER`, `IPSEC_SEG_PASS` | controller (`internal/actuate/vyos.go`) | the IPsec endpoint on the traffic-generator host (VPP SEG) |
| `VYOS_USER_PASSWORD` | controller (`internal/actuate/cfg.go`) | password set in the cloud-init of new SecGW VMs |
| `WORKER_MGMT_PREFIX`, `WORKER_MGMT_GATEWAY`, `VYOS_MGMT_PREFIX`, `VYOS_MGMT_GATEWAY` | controller | management-network prefix and gateway of new VMs |
| `KUBECONFIG` | harness, controller manifests | cluster access; no kubeconfig is included |

The controller reads these through `internal/envcfg`; the manifests in `harness-and-manifests/deploy/` show where they are set (values redacted to `<REDACTED>`). The remaining knobs (`V6_*`, `BASELINE_*`) are the control-law parameters documented in the report and in each manifest.

## Citation

This record is published as a public GitHub repository, https://github.com/M11302140/three-layer-5g-autoscaling-artifact, release tag `v1.0.0` (https://github.com/M11302140/three-layer-5g-autoscaling-artifact/releases/tag/v1.0.0). The repository holds everything except the per-run raw output; `raw-runs.tar.zst` (zstd-compressed tar of `raw-runs/`, 101 MB, 10,706 files) and its checksum `ARCHIVES.sha256` are attached to the release. Cite the repository at tag `v1.0.0` together with the paper (IEEE TNSM, under review) and the companion technical report (arXiv id to be filled):

> [authors], "Artifact record: predictable-cost autoscaling of a three-layer 5G user plane," GitHub repository M11302140/three-layer-5g-autoscaling-artifact, tag v1.0.0, 2026.

## Reproducing the simulation numbers

The frozen simulators are plain Python 3 (numpy). A round is re-run from its own directory, for example:

```
cd registrations-and-reports/r73fill
python3 eval_f.py      # writes out/f.json
python3 eval_st.py     # writes out/same_target.json and .md
python3 report_f.py    # rebuilds the tables quoted in REPORT.md
```

The scripts import the frozen simulators by relative path from `experiment/qsim/`; place `sim-and-library/` where `qsim/` was, or put it on `PYTHONPATH`. The md5 of the six frozen files must match `FROZEN_MD5` before any result is compared with the paper. Hardware runs cannot be re-run without the testbed; their raw output is in `raw-runs/` and the metrics are recomputed with `hardware-metrics/rq/rq_metrics.py`.

## Licences

- Code and scripts written by the authors (simulators, calibration, controller source, harness, drivers, analysis and figure scripts): Apache License 2.0. Copyright holder: [to be confirmed before publication].
- Data measured and written by the authors (per-run raw output, hardware metrics, registration files, analysis reports, the specification ledger, the removed text, the tables): Creative Commons Attribution 4.0 International (CC BY 4.0).
- `data/melbourne-derived/` and `sim-and-library/prior_traces.json`: derived from the City of Melbourne Pedestrian Counting System (Open Data Portal, CC BY 4.0); released under CC BY 4.0 with attribution to the City of Melbourne.
- `data/madrid-derived/`: derived from the IMDEA Networks Madrid LTE dataset released under GPL-3.0, which asks for the citation of P. Fernández Pérez, C. Fiandrino and J. Widmer, "Characterizing and Modeling Mobile Networks User Traffic at Millisecond Level", ACM WiNTECH '23, doi 10.1145/3615453.3616509. The derived traces are released under GPL-3.0 with the same citation requirement; see that directory's `LICENSE` and `README.md`.

The full text of the three licences is in `LICENSE` (Apache-2.0 and CC BY 4.0) and `data/madrid-derived/LICENSE` (GPL-3.0).

## Notes on the files

- Scripts keep the paths of the lab tree (`/home/user/experiment/...`); see `SANITIZATION.md` for the placeholders.
- Names. `hhro-daemon` (and the image tags `hhro-daemon:6.0-*`) is the name of the controller program; every arm of the study is built from it with different flags and manifests. As an arm label in the run ledgers and in `rq_metrics.csv` ("HHRO t1", arm `HHRO`), it denotes the hand-tuned controller that the paper calls v6; `HHRO-Q` groups are an earlier quantile variant that is not a paper arm. The code names are kept because the ledgers, the reports and the image tags use them.
- Comments in Chinese were removed from the copied code files (not from the six frozen files, whose bytes are fixed by their registered md5, and not from the Markdown reports and the specification ledger, which are written partly in Chinese). The code is otherwise the version that ran. Chinese that remains is (a) runtime message strings in scripts, (b) quotations of ledger headings and wording in `docs/paper/numbers.md` and `docs/artifacts/*.md` (for example 結果 = results, 更正 = correction), and (c) the generated ablation table `registrations-and-reports/abl/ablation_table.md`, reproduced verbatim in `docs/artifacts/ablation-per-split.md`.
- The specification ledger (`ledger/`) is the lab notebook of the study and is written in Chinese; `ledger/INDEX.md` lists the sections the paper cites, and the English technical report reproduces their content. Comments in the copied files refer to manuscript revisions as "rev. N"; the table in `docs/README.md` maps them to dates.
- Working files of the manuscript (outline, check lists, progress reports, submission lists, removed text, the report's Markdown sources, bibliography checks) are not part of this record; they carry no number or registration that the paper relies on.
