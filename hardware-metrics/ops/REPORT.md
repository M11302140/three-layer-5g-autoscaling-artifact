# §4.99 D — M6 operational-cost table and flap decomposition (10-20, ledger/log only, read-only inputs)

Script: `ops_analysis.py` (run as `nice -n 19 taskset -c 8-11 python3 ops_analysis.py`; rewrites `ops_table.md`, `ops_per_run.csv`, `flap_decomp.md`, `xcheck.md`). Nothing on the testbed was touched; no constants changed.

## 1. Inputs and run selection

- Ledger `/home/user/experiment/p2/main_exp_ledger.tsv`; blocks t3/t4/t5/t6/t7 only; voided ids r302, r304, r307, r309, r368, r370, r376, r379 excluded; rows whose flags match `trial|void|no-finish|daemon-panic|start-transient` excluded; r382 keeps the non-VOID (replacement-for-r379) row. Result: **83 valid runs** (t3 19, t4 19, t5 7, t6 19, t7 19; per arm 13 for S4a/S4b/v6/B4c2/B5c1/B6, 5 for B1) **plus r381** (v6 confirm:post-IRQ, reported separately) = 84 scored logs (the "84" of §4.99 D).
- Daemon log `/home/user/experiment/p2/v7rNNN_daemon.log` (JSON lines). r368 has no daemon log (voided anyway).
- Arm labels: S4a, S4b, HHRO→v6, B4c2_slo→B4c2, B5c1_slo→B5c1, B6c4_slo→B6, B1_static→B1. Trace = ledger block.

## 2. Exact definitions

- **Scored segment**: from the LAST line with `"msg":"autoscale toggled","enabled":true` to the next `"msg":"autoscale toggled","enabled":false` (or EOF). Observed window lengths 3575–3589 s (every run has both toggles). All counters below are counted strictly inside that window.
- Timestamps truncated to integer seconds (same resolution as rq_metrics, which uses `time[11:19]`).
- Counters (exact `msg` string equality unless stated):
  - VyOS create = `hbo deploy_vyos`; VyOS delete = `hbo delete_vyos` (the `: ul drain confirmed` / `: repathed UEs off victim` / `skipped: …` / `: drain clear failed …` variants are NOT counted).
  - worker create = `hbo create_worker`; worker delete = `hbo delete_worker` (exact). The only other msg containing `hbo delete_worker` is `hbo delete_worker skipped: worker reserved for a pending eupf slot` (2 occurrences in the valid windows, not counted). Full distinct-msg list in §6.
  - slot start = `hbo scale_out_up (eupf)`; slot stop = `hbo scale_in_up (eupf)`. These are the actual slot creation/deletion lines. The variants `hbo scale_out_up (eupf): cancelled in-flight drain, slot retained` and `hbo scale_in_up (eupf) cancelled: slot retained (reversible scale-in)` are a **reversible scale-in that was retracted before the slot was deleted** (drain dispatched, demand returned, slot kept); they are reported in their own column "reversible scale-in cancelled" and are not slot starts/stops. `… rejected`, `… creating slot worker first`, `… slot worker still booting`, `… no free slot position …`, `… failed` are not counted.
  - drains = `drain: plan` (count of plans; a retracted drain that is re-planned counts each plan). "drain UE moves" = Σ number of `{ue slot}` entries in the `moves` field of `drain: plan` lines (UE rehomes caused by slot drains).
  - relief UE moves (pool) = Σ `moves` over `v6 pool relief` lines (as requested). The daemon also logs `v6 hot slot relief` with a `moves` field; its Σ is reported separately ("hot-slot relief UE moves").
  - emergency firings = `v6 emergency force`.
  - PFCP re-association: `grep -i 'assoc\|pfcp'` over all r3xx/r4xx daemon logs returns 0 lines → **no PFCP re-association log line exists**; column omitted.
- **Flap** (reproduces rq_metrics.py lines 100–104): actuation events = (t, layer, dir) from the six exact-msg actuation lines above (vyos ±1, worker ±1, eupf ±1); events sorted by time; for each event, if a later event of the same layer with opposite direction exists with t2−t ≤ 600 s (first such one), count 1 flap. Thus one out→in→out episode yields 2 flaps.
- **Lock-expiry type** (spec §4.99 D): a slot-layer scale-in (`hbo scale_in_up (eupf)`) whose gap to the most recent slot-layer scale-out (any slot) is 300–360 s AND is followed by a slot-layer scale-out within 600 s. "same-slot variant" uses the most recent scale-out of the same slot name instead. "slot scale-ins 300–360 s after prior slot scale-out" is the release count without the refill condition. "flaps attributable to lock-expiry episodes" = flap pairs in which either member is a lock-expiry scale-in (covers both the out→in half and the in→out half).

## 3. Ops-cost table (per scored hour; mean (min–max) over runs; a bare number means all runs identical)

| arm | trace | n | VyOS create | VyOS delete | worker create | worker delete | slot start | slot stop | reversible scale-in cancelled (slot retained) | drain plans | drain UE moves | relief UE moves (pool) | hot-slot relief UE moves | emergency firings | flaps |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S4a | t3 | 3 | 2.0 | 1.0 | 2.0 | 1.0 | 5.3 (5–6) | 5.0 | 1.0 (0–2) | 5.7 (5–6) | 3.0 | 0.0 | 0.0 | 0.0 | 5.7 (5–7) |
| S4a | t4 | 3 | 1.0 | 0.0 | 1.0 | 0.0 | 4.0 | 1.0 | 0.0 | 1.0 | 1.7 (1–2) | 0.0 | 0.7 (0–1) | 1.0 | 2.0 |
| S4a | t5 | 1 | 0.0 | 0.0 | 0.0 | 0.0 | 2.0 | 2.0 | 0.0 | 4.0 | 3.0 | 0.0 | 0.0 | 0.0 | 3.0 |
| S4a | t6 | 3 | 2.0 | 1.0 | 0.7 (0–1) | 0.0 | 4.3 (4–5) | 3.3 (3–4) | 1.7 (1–3) | 6.3 (6–7) | 4.3 (3–6) | 0.0 | 0.0 | 0.3 (0–1) | 5.7 (5–6) |
| S4a | t7 | 3 | 1.0 | 2.0 | 0.0 | 1.0 | 2.0 | 4.0 | 2.0 | 8.3 (7–9) | 5.0 (3–8) | 0.0 | 0.0 | 0.0 | 3.0 |
| S4b | t3 | 3 | 1.0 | 1.0 | 2.3 (2–3) | 1.3 (1–2) | 5.0 | 5.0 | 0.0 | 5.3 (5–6) | 6.0 (4–7) | 0.0 | 1.3 (1–2) | 0.0 | 7.0 |
| S4b | t4 | 3 | 1.0 | 0.0 | 1.0 | 0.0 | 3.0 | 0.0 | 1.0 | 1.0 | 2.3 (1–3) | 1.3 (1–2) | 0.7 (0–1) | 0.0 | 0.0 |
| S4b | t5 | 1 | 0.0 | 0.0 | 0.0 | 0.0 | 2.0 | 3.0 | 1.0 | 7.0 | 5.0 | 0.0 | 0.0 | 0.0 | 3.0 |
| S4b | t6 | 3 | 2.0 | 2.0 | 2.0 | 1.0 | 4.0 | 4.0 | 0.0 | 4.0 | 0.0 | 0.0 | 0.0 | 1.0 | 6.0 |
| S4b | t7 | 3 | 2.0 | 2.0 | 0.3 (0–1) | 1.3 (1–2) | 2.3 (2–3) | 4.3 (4–5) | 1.7 (1–2) | 6.3 (6–7) | 3.0 | 0.0 | 0.0 | 0.0 | 4.3 (3–6) |
| v6 | t3 | 3 | 1.0 | 1.0 | 3.0 | 2.0 | 5.0 (4–6) | 5.0 (4–6) | 0.0 | 5.7 (5–6) | 9.3 (8–11) | 1.7 (0–4) | 1.3 (1–2) | 1.3 (1–2) | 7.3 (4–10) |
| v6 | t4 | 3 | 1.0 | 0.0 | 1.0 | 0.0 | 3.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 1.0 | 0.0 | 0.0 |
| v6 | t5 | 1 | 1.0 | 1.0 | 0.0 | 0.0 | 1.0 | 2.0 | 0.0 | 3.0 | 3.0 | 0.0 | 0.0 | 0.0 | 3.0 |
| v6 | t6 | 3 | 1.0 | 1.0 | 1.0 | 1.0 | 2.7 (2–3) | 2.7 (2–3) | 0.0 | 3.7 (3–5) | 4.0 (2–7) | 0.0 | 0.7 (0–2) | 0.3 (0–1) | 1.3 (0–2) |
| v6 | t7 | 3 | 1.0 | 1.0 | 0.0 | 1.0 | 2.0 | 4.0 | 0.0 | 5.0 | 6.0 (5–7) | 0.0 | 0.0 | 0.0 | 2.7 (2–3) |
| B4c2 | t3 | 3 | 1.0 | 1.7 (1–2) | 0.0 | 1.0 | 4.0 | 3.0 | 0.0 | 4.3 (4–5) | 3.7 (1–7) | 1.3 (0–2) | 0.7 (0–1) | 0.0 | 0.7 (0–1) |
| B4c2 | t4 | 3 | 1.0 | 0.0 | 0.0 | 0.0 | 2.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| B4c2 | t5 | 1 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| B4c2 | t6 | 3 | 0.3 (0–1) | 0.0 | 0.0 | 0.0 | 1.0 | 0.0 | 0.0 | 0.7 (0–1) | 1.0 (0–2) | 0.0 | 0.3 (0–1) | 0.0 | 0.0 |
| B4c2 | t7 | 3 | 1.0 | 2.0 | 0.0 | 0.0 | 0.0 | 0.7 (0–1) | 0.0 | 1.7 (1–2) | 1.7 (1–2) | 0.0 | 0.0 | 0.0 | 2.0 |
| B5c1 | t3 | 3 | 1.0 | 1.0 | 3.0 | 2.0 | 4.0 | 4.0 | 0.0 | 6.3 (5–7) | 8.7 (8–10) | 0.3 (0–1) | 1.0 | 0.0 | 3.0 |
| B5c1 | t4 | 3 | 1.0 | 0.0 | 1.0 | 0.0 | 3.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| B5c1 | t5 | 1 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| B5c1 | t6 | 3 | 0.0 | 1.0 | 0.0 | 0.0 | 1.0 | 0.0 | 0.0 | 1.7 (1–2) | 1.3 (1–2) | 0.0 | 0.0 | 0.0 | 0.0 |
| B5c1 | t7 | 3 | 0.0 | 1.0 | 0.0 | 0.0 | 1.0 | 1.7 (1–2) | 0.0 | 2.7 (2–3) | 4.7 (4–5) | 0.0 | 0.0 | 0.0 | 0.0 |
| B6 | t3 | 3 | 2.3 (2–3) | 1.3 (1–2) | 1.7 (1–2) | 1.3 (1–2) | 4.3 (4–5) | 3.3 (3–4) | 0.0 | 4.0 (3–6) | 5.7 (4–7) | 1.0 (0–2) | 0.7 (0–1) | 0.0 | 2.3 (0–6) |
| B6 | t4 | 3 | 0.7 (0–1) | 0.0 | 0.7 (0–1) | 0.0 | 1.3 (0–2) | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| B6 | t5 | 1 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| B6 | t6 | 3 | 0.7 (0–1) | 0.7 (0–1) | 0.0 | 0.0 | 0.7 (0–1) | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| B6 | t7 | 3 | 0.7 (0–1) | 1.7 (1–2) | 0.0 | 0.0 | 0.0 | 0.7 (0–1) | 0.0 | 1.7 (1–2) | 1.3 (1–2) | 0.0 | 0.0 | 0.0 | 0.7 (0–1) |
| B1 | t3 | 1 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| B1 | t4 | 1 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| B1 | t5 | 1 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| B1 | t6 | 1 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| B1 | t7 | 1 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

## Pooled over traces (per arm, mean (min–max) per run)

| arm | trace | n | VyOS create | VyOS delete | worker create | worker delete | slot start | slot stop | reversible scale-in cancelled (slot retained) | drain plans | drain UE moves | relief UE moves (pool) | hot-slot relief UE moves | emergency firings | flaps |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S4a | all | 13 | 1.4 (0–2) | 0.9 (0–2) | 0.8 (0–2) | 0.5 (0–1) | 3.8 (2–6) | 3.2 (1–5) | 1.1 (0–3) | 5.2 (1–9) | 3.5 (1–8) | 0.0 | 0.2 (0–1) | 0.3 (0–1) | 4.0 (2–7) |
| S4b | all | 13 | 1.4 (0–2) | 1.2 (0–2) | 1.3 (0–3) | 0.8 (0–2) | 3.5 (2–5) | 3.3 (0–5) | 0.7 (0–2) | 4.4 (1–7) | 3.0 (0–7) | 0.3 (0–2) | 0.5 (0–2) | 0.2 (0–1) | 4.2 (0–7) |
| v6 | all | 13 | 1.0 | 0.8 (0–1) | 1.2 (0–3) | 0.9 (0–2) | 3.0 (1–6) | 2.8 (0–6) | 0.0 | 3.5 (0–6) | 4.7 (0–11) | 0.4 (0–4) | 0.7 (0–2) | 0.4 (0–2) | 2.8 (0–10) |
| B4c2 | all | 13 | 0.8 (0–1) | 0.8 (0–2) | 0.0 | 0.2 (0–1) | 1.6 (0–4) | 0.8 (0–3) | 0.0 | 1.5 (0–5) | 1.5 (0–7) | 0.3 (0–2) | 0.2 (0–1) | 0.0 | 0.6 (0–2) |
| B5c1 | all | 13 | 0.5 (0–1) | 0.7 (0–1) | 0.9 (0–3) | 0.5 (0–2) | 2.1 (0–4) | 1.3 (0–4) | 0.0 | 2.5 (0–7) | 3.4 (0–10) | 0.1 (0–1) | 0.2 (0–1) | 0.0 | 0.7 (0–3) |
| B6 | all | 13 | 1.0 (0–3) | 0.8 (0–2) | 0.5 (0–2) | 0.3 (0–2) | 1.5 (0–5) | 0.9 (0–4) | 0.0 | 1.3 (0–6) | 1.6 (0–7) | 0.2 (0–2) | 0.2 (0–1) | 0.0 | 0.7 (0–6) |
| B1 | all | 5 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

## v6 confirmation run (reported separately)

| arm | trace | n | VyOS create | VyOS delete | worker create | worker delete | slot start | slot stop | reversible scale-in cancelled (slot retained) | drain plans | drain UE moves | relief UE moves (pool) | hot-slot relief UE moves | emergency firings | flaps |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| v6 (r381 confirm) | t4 | 1 | 1 | 0 | 1 | 0 | 4 | 1 | 0 | 2 | 3 | 0 | 2 | 0 | 1 |

## 4. Flap decomposition (S arms + v6)

| arm | trace | n | flaps total (mean, Σ) | slot-layer flaps (Σ) | slot scale-ins 300–360 s after prior slot scale-out (Σ) | …of which re-scale-out ≤10 min = lock-expiry type (Σ) | same-slot variant (Σ) | flaps attributable to lock-expiry episodes (Σ) | of which in→out half (Σ) | flaps involving any 300–360 s release (refilled or not) (Σ) | flaps as published in rq_metrics.csv (mean, Σ) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| S4a | t3 | 3 | 5.7, 17 | 17 | 6 | 1 | 1 | 2 | 1 | 10 | 7.7, 23 |
| S4a | t4 | 3 | 2.0, 6 | 6 | 0 | 0 | 0 | 0 | 0 | 0 | 2.0, 6 |
| S4a | t5 | 1 | 3.0, 3 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 3.0, 3 |
| S4a | t6 | 3 | 5.7, 17 | 14 | 0 | 0 | 0 | 0 | 0 | 0 | 9.3, 28 |
| S4a | t7 | 3 | 3.0, 9 | 6 | 3 | 0 | 0 | 0 | 0 | 3 | 7.0, 21 |
| **S4a** | **all** | 13 | 4.0, 52 | 46 | 9 | 1 | 1 | 2 | 1 | 13 | 6.2, 81 |
| S4b | t3 | 3 | 7.0, 21 | 20 | 5 | 3 | 2 | 5 | 3 | 9 | 7.0, 21 |
| S4b | t4 | 3 | 0.0, 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1.0, 3 |
| S4b | t5 | 1 | 3.0, 3 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 5.0, 5 |
| S4b | t6 | 3 | 6.0, 18 | 12 | 0 | 0 | 0 | 0 | 0 | 0 | 6.0, 18 |
| S4b | t7 | 3 | 4.3, 13 | 9 | 4 | 1 | 1 | 2 | 1 | 5 | 6.7, 20 |
| **S4b** | **all** | 13 | 4.2, 55 | 44 | 9 | 4 | 3 | 7 | 4 | 14 | 5.2, 67 |
| v6 | t3 | 3 | 7.3, 22 | 18 | 1 | 1 | 1 | 3 | 1 | 3 | 7.3, 22 |
| v6 | t4 | 3 | 0.0, 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0.0, 0 |
| v6 | t5 | 1 | 3.0, 3 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 3.0, 3 |
| v6 | t6 | 3 | 1.3, 4 | 4 | 1 | 0 | 0 | 0 | 0 | 1 | 1.3, 4 |
| v6 | t7 | 3 | 2.7, 8 | 8 | 0 | 0 | 0 | 0 | 0 | 0 | 2.7, 8 |
| **v6** | **all** | 13 | 2.8, 37 | 32 | 2 | 1 | 1 | 3 | 1 | 4 | 2.8, 37 |

Reading: on the slot layer, S4a/S4b each show 9 scale-ins that land 300–360 s after the previous slot scale-out (the 300 s lock + one 30 s tick → gaps of 323–333 s); v6 shows 2. Only 1 (S4a) / 4 (S4b) / 1 (v6) of those are refilled by a scale-out within 10 min, i.e. the strict "release-then-refill" lock-expiry type of §4.99 D is rare: 2/52 (S4a), 7/55 (S4b), 3/37 (v6) of all flaps. Counting every flap pair that involves a 300–360 s release (refilled or not, i.e. mostly the scale-out→release half) gives 13/52 (S4a), 14/55 (S4b), 4/37 (v6). The majority of S-arm flaps are therefore NOT lock-expiry releases but ordinary demand-following reversals (out→in or in→out within 10 min with gaps of 400–600 s), concentrated in t3 and t6; t4 has none for S4b/v6 and only 6 (2/run) for S4a.

## 5. Cross-check against rq_metrics.csv (`flaps` column, groups "MAIN tX arm")

A replica of the rq_metrics parser (its `msg[4:].split(" ")[0]` keying, its trace-t0 60-min window) reproduces the csv exactly for all 84 runs (column "replica"). Rows below are the runs where the exact-msg/scored-window count differs from the csv:

| run | arm | trace | flaps (this: exact msgs, scored window) | rq_metrics.csv | replica (rq parsing, trace-t0 window) | rq parsing, scored window | exact msgs, trace-t0 window | cancelled reversible scale-ins in run |
|---|---|---|---|---|---|---|---|---|
| r303 | S4b | t4 | 0 | 1 | 1 | 1 | 0 | 1 |
| r314 | S4b | t4 | 0 | 1 | 1 | 1 | 0 | 1 |
| r322 | S4b | t4 | 0 | 1 | 1 | 1 | 0 | 1 |
| r333 | S4b | t5 | 3 | 5 | 5 | 5 | 3 | 1 |
| r360 | S4a | t3 | 5 | 7 | 7 | 7 | 4 | 1 |
| r377 | S4a | t3 | 5 | 9 | 9 | 9 | 4 | 2 |
| r402 | S4a | t6 | 5 | 7 | 7 | 7 | 5 | 1 |
| r414 | S4a | t6 | 6 | 9 | 9 | 9 | 6 | 1 |
| r419 | S4a | t6 | 6 | 12 | 12 | 12 | 6 | 3 |
| r430 | S4a | t7 | 3 | 7 | 7 | 7 | 3 | 2 |
| r433 | S4b | t7 | 4 | 7 | 7 | 7 | 4 | 2 |
| r439 | S4b | t7 | 6 | 7 | 7 | 7 | 6 | 1 |
| r442 | S4a | t7 | 3 | 7 | 7 | 7 | 3 | 2 |
| r444 | S4b | t7 | 3 | 6 | 6 | 6 | 3 | 2 |
| r447 | S4a | t7 | 3 | 7 | 7 | 7 | 3 | 2 |

Cause (all 15 mismatches, all S arms): rq_metrics keys `hbo …` lines on the first token, so `hbo scale_in_up (eupf) cancelled: slot retained (reversible scale-in)` is taken as a slot scale-in and `hbo scale_out_up (eupf): cancelled in-flight drain, slot retained` (logged 4 ms earlier) as a slot scale-out. The pair is simultaneous, so it always produces an in→out flap, and the real scale-out that preceded the drain plan often gets a second (out→"in") flap. These are retracted reversible scale-ins in which no slot was deleted or created (UEs were, however, partially rehomed by the drain, see "drain UE moves"). r433 additionally has `hbo delete_worker skipped: …` counted as a worker delete by rq_metrics. The trace-t0 vs scored-window difference does not change any csv value (column "rq parsing, scored window" equals the csv everywhere); it only drops a final scale-in in r360/r377 under the exact-msg definition (column "exact msgs, trace-t0 window"). Net: rq_metrics.csv over-states S-arm flaps by 29 (S4a 81 vs 52) and 12 (S4b 67 vs 55) over 13 runs each; v6 and all B arms are unaffected (no reversible scale-in cancellations occur there). Decision for the paper (which definition to publish) is left to the author; this report uses actual actuations.

## 6. Distinct actuation-related msgs seen inside the valid scored windows (for audit)

Counted: `hbo deploy_vyos`, `hbo delete_vyos`, `hbo create_worker`, `hbo delete_worker`, `hbo scale_out_up (eupf)`, `hbo scale_in_up (eupf)`, `drain: plan`, `v6 pool relief`, `v6 hot slot relief`, `v6 emergency force`.
Seen but not counted as actuations (count over the 83 valid windows): `drain: live UE on victim after plan — re-planning` 45; `drain: slot-drain retract failed` 15; `hbo delete_vyos skipped: drain in flight` 1; `hbo delete_vyos: drain clear failed after retries` 4; `hbo delete_vyos: repathed UEs off victim` 69; `hbo delete_vyos: ul drain confirmed` 68; `hbo delete_worker skipped: worker reserved for a pending eupf slot` 2; `hbo scale_in_up (eupf) cancelled: slot retained (reversible scale-in)` (own column); `hbo scale_out_up (eupf) rejected` 6; `hbo scale_out_up (eupf): cancelled in-flight drain, slot retained` 23; `hbo scale_out_up (eupf): creating slot worker first` 9; `hbo scale_out_up (eupf): no free slot position; worker layer owns creation (sigma)` 13; `hbo scale_out_up (eupf): slot worker still booting` 25. No msg mentions association/assoc/PFCP.

Per-run values: `ops_per_run.csv` (one row per run incl. r381, with every counter, flap variants, the rq cross-check columns and the list of slot scale-in gaps in seconds).
