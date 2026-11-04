# P1 causal replay: independent review (2026-10-26)

Recomputed from protocol.json P1_replay, out/P1/causal/<run>.json and p2/trace_v7_<run>.csv only; summary read afterwards.

## Numbers
- Runs: 23/23 registered model_validation_runs present; 23/23 CSVs present, 60 rows each (min 0-59), no unparseable cells.
- hw.viol vs CSV rule (e2e_pct > 0.1 or lat_p99_us > 1000): identical in 23/23 runs. Every hw.viol minute has a class; no class on a clean minute.
- Episodes (fleet/placement): 12 over 10 runs; recalled 7; recall 7/12 = 0.583. Support condition (>= 5 over >= 3 runs) met; recall gate (>= 0.80) FAILS.
  - Misses: r471 [20], r478 [20-21], r495 [24-26], r495 [47-50], r504 [20-22].
  - r479 [20] counts as recalled only because model minute 21 falls at last+1, and hw minute 21 is classed 'other'.
- False alarm: 17 / 1340 hardware-clean minutes = 0.0127 (gate 0.05, PASS). The denominator is not zero. 10 of the 17 come from one repeated pattern, model minutes [33,34] in r461/463/464/466/498. The other 7 are r476 [22,23], r493 [8,9], r495 [8,9], r503 [5].
- Cost MAPE: 0.01038 (max 0.02965, r464; r466 0.0296, r498 0.0291). Gate 0.03, PASS. hw.alloc_vm was taken from the JSON; I did not re-derive it from rq_metrics.csv.

## Verdict
P1 causal replay FAILS on recall (0.583 < 0.80). False alarm and cost pass. No zero denominators and no missing runs. The state gate (observed replay) was not in scope.

## Comparison with causal_summary.md
- All headline values match exactly: episodes 12, runs 10, recalled 7, recall 0.5833, fa 17/1340 = 0.01269, MAPE 0.01038, n_runs 23, and GATE recall=false, support/false_alarm/cost=true.
- The per-run viol/classes/model/FA lists and the episode list match. APE % and alloc values are rounded consistently.
- No numeric discrepancy found.
- Presentation notes only:
  1. The "skipped injections" column counts `skipped` only. Deferred injections (10 in 10 runs, e.g. r460 out_up deferred 113 s, r477 two deferrals) are not shown.
  2. Two of the five misses (r471, r478) are runs where an early out_wk injection (31 s / 39 s) was skipped as model-infeasible. This possible link is not stated.
  3. r504 (the disclosed trigger / smoke-test run) is in the validation set and is a miss.
