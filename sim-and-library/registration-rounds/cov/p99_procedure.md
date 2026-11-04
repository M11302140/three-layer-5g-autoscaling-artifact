# p99 measurement procedure (spec §4.102 item 5)

Facts read from code, configs and run CSVs only. Line numbers are the current files: `experiment/trace_run.py` (mtime 10-18; `git diff` vs the 09-16 commit touches no latency line), `experiment/trex_traffic.py` (mtime 09-15, before every main-experiment run), `experiment/paper_out_new/rq_metrics.py`, `/etc/trex_cfg.yaml` (mtime 08-22). The numbers come from `experiment/qsim/cov/p99_latn.py`, and the raw output is in `p99_latn.json`.

## 1. What is measured
- **Instrument.** TRex v3.08 native latency streams (`STLFlowLatencyStats`), not timestamped GTP-U packets captured with tcpdump. The tcpdump/`LAT_MAGIC` path (`trex_traffic.py:1145-1268`, `measure_latency_trex`, `LatencySampler`) is legacy code that trace_run never calls. Every stream is a real GTP-U UL packet on a live UE's TEID (`trex_traffic.py:643-648`).
- **Path.** The probe goes TRex UL → VyOS → eUPF → DN reflector → DL back to the same TRex port (`trex_traffic.py:758-762`). The TRex port is port 0, the only real port (`trex_traffic.py:36`). In `/etc/trex_cfg.yaml:3,6` that port is a virtio-user vdev attached to the SEG VPP vhost-user socket on the sender host, so the loop also passes through the SEG.
- **Round trip, not derived.** The same TRex instance stamps the packet on send and receives it on the same port, so there is one clock and no clock sync. `latency_stats()` is documented as "Round-trip latency (usec)" (`trex_traffic.py:1038`). The value goes into `lat_p99_us` unchanged: no halving and no subtraction of an idle baseline (`trace_run.py:2032,2048`). **The reported p99 is the round-trip p99 of the full UL+DL loop.**
- **Timestamp source.** The timestamps come from TRex software. The streams are built with the default `ieee_1588=False` (`trex/v3.08/.../trex_stl_streams.py:353`; the harness never sets it), and port 0 is a virtio-user vdev (`/etc/trex_cfg.yaml:6`), which has no NIC hardware timestamping. TRex runs its latency handling on a dedicated thread (`latency_thread_id: 1`, `/etc/trex_cfg.yaml`). How TRex timestamps packets internally is not visible in repo code.
- **Precision as recorded.** Percentiles come from TRex's log-binned histogram. Bins are one tenth of a decade wide, so 100 µs bins between 1 and 10 ms (`trex_traffic.py:1039-1041`, `_bucket_edge` at 1081-1086). Within the bin that holds the target rank, `_hist_pcts` interpolates linearly (`trex_traffic.py:1089-1112`). Near the 1 ms SLO threshold the p99 is therefore interpolated inside the [900, 1000) or [1000, 2000) bin. `lat_max_us` is TRex's exact `total_max` and is not binned (`trex_traffic.py:1057-1058`).

## 2. Which streams and at what rate
- **Slot probe.** There is one probe per active eUPF slot, i.e. per distinct eUPF octet among the active UEs, with pg_id = slot octet 31–38. Each probe stays on one UE for as long as that UE is present (`trex_traffic.py:518-532`). It runs at `LAT_PG_PPS = 500` pps (`trex_traffic.py:1076,647`).
- **Per-UE health stream.** Each active UE also has a 50 pps stream with pg_id = 100 + UE index (`trex_traffic.py:638-641`). Its main job is black-UE detection, but it is also an `STLFlowLatencyStats` stream. `latency_stats()` merges every pg_id that TRex returns and does not filter out pg ≥ 100 (`trex_traffic.py:1052-1069`), so **these streams are pooled into the reported p99 too**.
- **Servo scaling.** All profiles share the rate servo multiplier. It is applied with `update(ports=None)` (`trex_traffic.py:499,851`) and clamped to 0.2–6.0 (`:848`). Actual probe rates are therefore 500·mult and 50·mult pps. The servo target is UE × `pps_per_ue` = 125 000 pps UL per UE (trace JSON `pps_per_ue: 125000`; `trace_run.py:38,2044`).
- **Nominal samples per minute at mult = 1.** That is 30 000 per active slot plus 3 000 per active UE. At the full fleet of 8 slots and 40 UE it comes to 360 000. The observed maximum is 376 950.
- **Fitted rates.** A least-squares fit of lat_n / covered_s / (txreal/offered) on (daemon up_rep, active_ue) over the 4 980 formal minutes gives about 444 pps per slot and 41 pps per UE (R² 0.42). These are near the nominal 500 and 50 pps, which supports reading both stream types as pooled. This is an inference: the CSV has no per-stream counts.
- **Example run r452** (`p2/trace_v7_r452.csv`): lat_n per minute has min 78 953, median 244 913, max 351 109. Minute 0, with 27 UE and 7/8 slots, has 224 701 samples.

## 3. Per-minute p99
- **Window.** At the start of each minute, `m.clear_latency()` zeroes the TRex latency histograms (`trace_run.py:1171`, which calls `trex_traffic.py:1023-1035` with `clear_latency_stats=True`). The histograms are read after `win.close()` (`trace_run.py:2006,2032`). The latency window is the measurement minute, with `covered_s` median 60 s.
- **Pooling.** `latency_stats()['all']` sums the histograms of every latency pg_id (all slot probes plus all per-UE health streams) and computes p50/p95/p99 from the merged histogram (`trex_traffic.py:1062-1071`). **The p99 is pooled over streams. It is not a maximum over slots and not a mean of per-slot p99s.** Per-slot entries exist in the returned dict but are not written to the CSV.
- **Lost probes.** Only probes that come back enter the histogram. Lost probes go into `dropped` (`trex_traffic.py:1059`), which is not written to the minute CSV and not used by the SLO. Loss is judged separately through `e2e_pct`.
- **SLO minute.** A minute is good iff `e2e_pct ≤ 0.1` **and** `lat_p99_us ≤ 1000` (`rq_metrics.py:86-87`). The 1 Hz sidecar (`*_1s.csv`) is not used.

## 4. Few or zero samples
- **No sample-count threshold exists.** `lat_n` is written (`trace_run.py:2049`) but never read by `trace_run.py` or `rq_metrics.py`. A minute with few samples is judged like any other.
- **Zero samples counts as a violation.** With n = 0, `_hist_pcts` returns p99 = None (`trex_traffic.py:1094-1095`). `latency_stats()` then has no 'all' entry, and trace_run writes an empty `lat_p99_us` (`trace_run.py:2032,2048`). `rq_metrics.f(..., 1e9)` turns the empty field into 1e9 (`rq_metrics.py:20-22,86`), so the minute **fails** the SLO. It is kept in the denominator and excluded only from the p99max/p99avg statistics (`rq_metrics.py:91`).
- **Formal runs, t3–t7.** These are the rq_metrics MAIN groups: 83 runs, 4 980 minutes, with void, replaced and confirm runs excluded. The ledger runs that are excluded are r302, r304, r307, r309, r368, r370, r376, r379 and r381.
  - lat_n per minute: **min 18 521, median 263 708, max 376 950** (p1 73 478, p5 132 814).
  - Minutes with lat_n = 0 or an empty p99: **0**. Under the only implicit threshold (n = 0) no minute is affected.
  - Minutes below illustrative levels: <10 000: 0; <50 000: 27 (18 SLO-good, 9 bad); <100 000: 103 (72 good, 31 bad). At the minimum lat_n the p99 still rests on about 185 tail samples.
  - The lowest minutes cluster at minute 4–5 of t3 runs at 40 UE with e2e 3.7–5.6% (r365, r382, r362, r367, r371), which fail on loss anyway, and at min 44–45 of t7 runs (r442, r432, r447, r430).
- **Per block (formal):**

| block | runs | lat_n min | median | max | <50k | <100k |
|---|---|---|---|---|---|---|
| t3 | 19 | 18 521 | 194 594 | 335 791 | 14 | 55 |
| t4 | 19 | 21 479 | 304 373 | 376 950 | 3 | 6 |
| t5 | 7 | 76 900 | 308 190 | 370 588 | 0 | 4 |
| t6 | 19 | 35 798 | 273 827 | 359 464 | 4 | 14 |
| t7 | 19 | 23 098 | 271 769 | 370 643 | 6 | 24 |

- **Sensitivity, all t3–t7 ledger rows with a CSV** (91 runs, 5 460 min): min 18 521, median 261 619, max 376 950. Zero-sample minutes: 0. <50k: 39; <100k: 128.
