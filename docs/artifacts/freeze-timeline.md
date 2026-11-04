<!-- artifact file of the paper (docs/paper), written 2026-10-21 (R4rev, spec §4.112 D1): freeze timeline. The paper (Experimental setup, "Registration and held-out status") carries the five-row summary; this file adds the dated events with their sources and the per-run list. Per-run rows are copied from experiment/p2/main_exp_ledger.tsv (columns run, block, arm, slo, flags, time; the time column is the ledger write time at the end of each run; duplicate ledger lines removed); events from spec §4.25, §4.32 item 1, §4.33b, §4.37, §4.52, §4.53, §4.59, §4.77 B, §4.82, §4.86, §4.88 E and artifacts/registration-files.md. -->

# Freeze timeline of the main experiment

## Summary (as in the paper)

| block | runs | dates (2026) | vs. freeze |
|---|---|---|---|
| freeze | billing from r241, r247, r248, r250, r251 | λ 10-06, simulators 10-07 | 0 |
| t4 | r300 to r322 | 10-09 to 10-11 | +2 to +4 d |
| t5 | r330 to r336 | 10-11 | +4 d |
| t3 | r360 to r383 | 10-12 to 10-14 | +5 to +7 d |
| t6, t7 | r402 to r448 | 10-15 to 10-17 | +8 to +10 d |

"vs. freeze" counts calendar days from 2026-10-07, the date after which no simulator or λ change was made (Experimental setup; registration-files.md).

## Dated events

| date (2026) | event | source |
|---|---|---|
| 10-05 to 10-06 | G2 (r239 to r246) and G2b (r247 to r263) gate blocks on t1/t2; VM existence measured on r241, r247, r248, r250, r251 | §4.17, §4.19, §4.25, §4.31 |
| 10-06 00:30 | `vmexist` billing (create order + 30 s, delete order + 5 s) added to the simulator from those measurements; the daemon unchanged | §4.25 |
| 10-06 19:45 | method frozen: hhro-daemon tag `v7.1.3-frozen`, λ S4a 2.83/3.08, S4b 1.83/2.00 | §4.32 item 1 |
| 10-07 02:46 / 15:06 | t1 to t5 predictions registered (S4a/S4b nest2; v6 sim_v6); no simulator or λ change after 10-07 | §4.37; registration-files.md |
| 10-09 to 10-11 | t4 block, r300 to r321 and replacement r322 (voided r302, r304, r307, r309) | ledger; §4.51 |
| 10-11 | t5 reduced to one run per arm (ruling 10-11 12:50); t5 block r330 to r336; t6/t7 sampling thresholds frozen 19:17:32 | §4.52, §4.59; registration-files.md |
| 10-12 to 10-14 | t3 block, r360 to r383 without r381 (voided r368, r370, r376, r379; replacements r380, r382, r383 included) | ledger; §4.74 A |
| 10-14 | r381, v6 t4 confirmation after the interrupt re-pinning (not in any table) | §4.74 E, §4.88 E |
| 10-15 00:16 to 00:18 | t6/t7 sampled by the written rules, predictions of all registered arms registered (00:17), threshold hash checked before the first t6 run (00:18) | §4.77 B; registration-files.md |
| 10-15 to 10-16 | t6 block, r402 to r420 | §4.82 |
| 10-16 to 10-17 | t7 block, r430 to r448 | §4.86 |

## Per-run list (main-experiment ledger, t3 to t7)

| block | run | arm (ledger name) | SLO | flags | ledger time |
|---|---|---|---|---|---|
| t4 | r300 | S4a | 60/60 | ok | 2026-10-09 14:28:26 |
| t4 | r301 | HHRO | 58/60 | ok | 2026-10-09 16:13:50 |
| t4 | r302 | B4c2_slo | 57/60 | start-transient | 2026-10-09 18:00:06 |
| t4 | r303 | S4b | 56/60 | ok | 2026-10-09 19:45:51 |
| t4 | r304 | B5c1_slo | 21/60 | daemon-panic | 2026-10-09 22:09:24 |
| t4 | r305 | B6c4_slo | 59/60 | ok | 2026-10-10 00:02:32 |
| t4 | r306 | B1_static | 60/60 | ok | 2026-10-10 01:19:56 |
| t4 | r307 | HHRO | 59/60 | void:compute-overlap(cal 02:36-02:57,go-test 02:39-02:41,q11 build 02:42 on sender cores 0,8 during formal 02:04-03:05) | 2026-10-10 03:05:07 |
| t4 | r308 | B4c2_slo | 60/60 | ok | 2026-10-10 05:37:35 |
| t4 | r309 | S4b | 55/60 | void:harness(gNB-8 NG death min25, bounced; same class as r302 start transient; round-29 ruling) → rerun r322 | 2026-10-10 07:24:27 |
| t4 | r310 | B5c1_slo | 58/60 | ok | 2026-10-10 09:47:58 |
| t4 | r311 | B6c4_slo | 60/60 | ok | 2026-10-10 11:33:18 |
| t4 | r312 | S4a | 59/60 | ok | 2026-10-10 13:22:49 |
| t4 | r313 | B4c2_slo | 60/60 | ok | 2026-10-10 15:08:07 |
| t4 | r314 | S4b | 58/60 | ok | 2026-10-10 16:56:10 |
| t4 | r315 | B5c1_slo | 57/60 | ok | 2026-10-10 18:42:23 |
| t4 | r316 | B6c4_slo | 60/60 | ok | 2026-10-10 21:46:31 |
| t4 | r317 | S4a | 58/60 | ok | 2026-10-10 23:46:20 |
| t4 | r318 | HHRO | 59/60 | ok | 2026-10-11 01:31:37 |
| t4 | r319 | B5c1_slo | 58/60 | ok | 2026-10-11 03:16:53 |
| t4 | r320 | B4c2_slo | 58/60 | ok | 2026-10-11 05:03:22 |
| t4 | r321 | HHRO | 58/60 | ok | 2026-10-11 06:48:33 |
| t5 | r330 | S4a | 60/60 | ok | 2026-10-11 08:51:32 |
| t5 | r331 | HHRO | 60/60 | ok | 2026-10-11 10:41:58 |
| t5 | r332 | B4c2_slo | 60/60 | ok | 2026-10-11 12:30:54 |
| t5 | r333 | S4b | 60/60 | ok | 2026-10-11 14:19:51 |
| t5 | r334 | B5c1_slo | 60/60 | ok | 2026-10-11 16:08:16 |
| t5 | r335 | B6c4_slo | 60/60 | ok | 2026-10-11 17:56:32 |
| t5 | r336 | B1_static | 60/60 | ok | 2026-10-11 19:16:58 |
| t4 | r322 | S4b | 56/60 | ok | 2026-10-11 21:18:38 |
| t3 | r360 | S4a | 58/60 | ok | 2026-10-12 07:01:28 |
| t3 | r361 | HHRO | 53/60 | ok | 2026-10-12 08:47:20 |
| t3 | r362 | B4c2_slo | 57/60 | ok | 2026-10-12 10:33:47 |
| t3 | r363 | S4b | 54/60 | ok | 2026-10-12 12:19:37 |
| t3 | r364 | B5c1_slo | 57/60 | ok | 2026-10-12 14:05:34 |
| t3 | r365 | B6c4_slo | 58/60 | ok | 2026-10-12 15:51:01 |
| t3 | r366 | B1_static | 60/60 | ok | 2026-10-12 17:08:35 |
| t3 | r367 | HHRO | 53/60 | ok | 2026-10-12 18:54:17 |
| t3 | r368 | B4c2_slo | ? | no-finish | 2026-10-12 19:06:54 |
| t3 | r369 | S4b | 57/60 | ok | 2026-10-12 21:05:51 |
| t3 | r370 | B5c1_slo | 30/60 | ok | 2026-10-12 22:52:16 |
| t3 | r371 | B6c4_slo | 57/60 | ok | 2026-10-13 00:42:24 |
| t3 | r372 | S4a | 58/60 | ok | 2026-10-13 02:28:40 |
| t3 | r373 | B4c2_slo | 55/60 | ok | 2026-10-13 04:30:10 |
| t3 | r374 | S4b | 55/60 | ok | 2026-10-13 06:16:29 |
| t3 | r375 | B5c1_slo | 55/60 | ok | 2026-10-13 08:01:54 |
| t3 | r376 | B6c4_slo | 53/60 | ok | 2026-10-13 09:47:52 |
| t3 | r377 | S4a | 57/60 | ok | 2026-10-13 11:34:26 |
| t3 | r378 | HHRO | 57/60 | ok | 2026-10-13 13:19:48 |
| t3 | r379 | B4c2_slo | 56/60 | ok | 2026-10-13 15:09:23 |
| t3 | r380 | B5c1_slo | 56/60 | replacement-for-r370 | 2026-10-13 17:58:09 |
| t3 | r382 | B4c2_slo | ? | VOID:bringup-failed(UE-13 reject[90] PCF client_pool exhausted); rerun pending | 2026-10-13 18:02:08 |
| t4 | r381 | HHRO | 56/60 | confirm:post-IRQ | 2026-10-14 02:39:26 |
| t3 | r383 | B6c4_slo | 55/60 | replacement-for-r376 | 2026-10-14 04:26:44 |
| t6 | r402 | S4a | 60/60 | ok | 2026-10-15 02:09:36 |
| t6 | r403 | HHRO | 60/60 | ok | 2026-10-15 03:56:59 |
| t6 | r404 | B4c2_slo | 60/60 | ok | 2026-10-15 05:44:51 |
| t6 | r405 | S4b | 60/60 | ok | 2026-10-15 07:36:29 |
| t6 | r406 | B5c1_slo | 60/60 | ok | 2026-10-15 09:23:02 |
| t6 | r407 | B6c4_slo | 60/60 | ok | 2026-10-15 11:17:38 |
| t6 | r408 | B1_static | 60/60 | ok | 2026-10-15 12:47:32 |
| t6 | r409 | HHRO | 60/60 | ok | 2026-10-15 14:34:21 |
| t6 | r410 | B4c2_slo | 55/60 | ok | 2026-10-15 16:21:56 |
| t6 | r411 | S4b | 60/60 | ok | 2026-10-15 18:09:35 |
| t6 | r412 | B5c1_slo | 58/60 | ok | 2026-10-15 19:56:04 |
| t6 | r413 | B6c4_slo | 60/60 | ok | 2026-10-15 21:42:59 |
| t6 | r414 | S4a | 60/60 | ok | 2026-10-15 23:34:00 |
| t6 | r415 | B4c2_slo | 60/60 | ok | 2026-10-16 01:20:24 |
| t6 | r416 | S4b | 60/60 | ok | 2026-10-16 03:07:59 |
| t6 | r417 | B5c1_slo | 60/60 | ok | 2026-10-16 04:56:26 |
| t6 | r418 | B6c4_slo | 60/60 | ok | 2026-10-16 06:44:15 |
| t6 | r419 | S4a | 60/60 | ok | 2026-10-16 08:34:49 |
| t6 | r420 | HHRO | 55/60 | ok | 2026-10-16 10:21:12 |
| t7 | r430 | S4a | 60/60 | ok | 2026-10-16 12:25:20 |
| t7 | r431 | HHRO | 60/60 | ok | 2026-10-16 14:13:50 |
| t7 | r432 | B4c2_slo | 60/60 | ok | 2026-10-16 17:01:00 |
| t7 | r433 | S4b | 60/60 | ok | 2026-10-16 18:48:56 |
| t7 | r434 | B5c1_slo | 60/60 | ok | 2026-10-16 20:37:22 |
| t7 | r435 | B6c4_slo | 60/60 | ok | 2026-10-16 22:25:27 |
| t7 | r436 | B1_static | 59/60 | ok | 2026-10-16 23:45:07 |
| t7 | r437 | HHRO | 60/60 | ok | 2026-10-17 01:32:51 |
| t7 | r438 | B4c2_slo | 60/60 | ok | 2026-10-17 03:21:18 |
| t7 | r439 | S4b | 60/60 | ok | 2026-10-17 05:09:20 |
| t7 | r440 | B5c1_slo | 60/60 | ok | 2026-10-17 06:57:46 |
| t7 | r441 | B6c4_slo | 60/60 | ok | 2026-10-17 08:45:21 |
| t7 | r442 | S4a | 59/60 | ok | 2026-10-17 10:33:16 |
| t7 | r443 | B4c2_slo | 60/60 | ok | 2026-10-17 12:23:36 |
| t7 | r444 | S4b | 60/60 | ok | 2026-10-17 14:11:40 |
| t7 | r445 | B5c1_slo | 60/60 | ok | 2026-10-17 16:02:08 |
| t7 | r446 | B6c4_slo | 60/60 | ok | 2026-10-17 17:49:38 |
| t7 | r447 | S4a | 60/60 | ok | 2026-10-17 20:17:22 |
| t7 | r448 | HHRO | 60/60 | ok | 2026-10-17 22:05:47 |
