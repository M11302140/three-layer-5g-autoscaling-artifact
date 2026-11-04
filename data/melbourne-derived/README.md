# Trace libraries derived from the City of Melbourne pedestrian counts

Source: City of Melbourne Open Data Portal, dataset "Pedestrian Counting System – Past Hour (counts per minute)", collected 2026-06 to 2026-10 with `../../sim-and-library/ped_poll.sh` (download URL inside the script). Licence of the source: Creative Commons Attribution 4.0 International. Attribution: City of Melbourne.

Derived files (CC BY 4.0, attribution to the City of Melbourne and to the authors of this record):

- `gtrace2/ped2026_merged_1022.csv`: the merged per-minute count table (merge report alongside), built by `ped_merge.py`.
- `gtrace2/g2_pool.json`, `g2_result.json`, `g2_sampling_log.txt`: the 1615-trace pool and the sampling that produced the prior library `../../sim-and-library/prior_traces.json` (`make_gtrace2.py`, `make_prior.py`, `export_prior.py`).
- `t910/`: the high-load pool used for the test traces t9 to t12 (`make_t910.py`, `merge.py`, thresholds, sampling log).

The test traces played on the testbed (`trace_ue_60min_v3_t3.json` to `_t12.json`) are in `../../harness-and-manifests/traces/`; the t6/t7 sampling thresholds and log, and `heldout.json`, are in `../../sim-and-library/`.
