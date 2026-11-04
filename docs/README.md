# docs/

- `paper/numbers.md`: every number the manuscript cites, with its source (ledger section, report, table). Start here to check a number.
- `artifacts/`: the table files the technical report reproduces (one table family per file) and `registration-files.md` (the registration files with their embedded timestamps and hashes); `artifacts/README.md` is their index.
- `figure-scripts/`: the matplotlib scripts of the figures in the paper (`fig_cost_viol_t3t8.py` with `CV_PANELS=t8` draws the paper's cost/violation figure; `fig_eps_guarantee.py`, `fig_h2_pred_vs_meas.py`, `fig_layers_timeline.py`, `fig_load_band.py`, `fig_t4_burst.py`; `common.py`, `palette.py`). The architecture figure is TikZ in the manuscript source and has no script here.

Manuscript revision numbers. Comments in these files refer to manuscript revisions as "rev. N"; they are the authors' internal revision counter and correspond to these dates:

| rev. | date (2026) | what changed |
|---|---|---|
| 0 | 10-21 | page-limit pass after review rounds 64–66 |
| 1 | 10-22 | fourth-review response (per-slot calibration) |
| 2 | 10-22 (approx.) | claim-and-evidence restructure with the companion technical report (round 67) |
| 3 | 10-26 (approx.) | contradiction-check fixes, page fit (round 77) |
| 4 | 10-31 | planner (S4′) results added, numbers.md written first, page fit to 14 pages |
| 4.1 | 10-31 | abstract, dominance table, residual plot, testbed diagram |
| 4.2 | 11-01/02 | fill-in block tables (r73fill) |
| 4.3 | 11-02 | same-target recount, claims re-cut |
| 4.4 | 11-02 | page cuts, author block |
| 4.5 | 11-02 | reference and figure fixes |
| 4.6 | 11-02 | double-column architecture figure, terminology |
| 4.7 | 11-02 | figure path and legend fixes; the submitted manuscript |

The ledger sections and run ids never changed meaning across revisions; only the manuscript text did.
