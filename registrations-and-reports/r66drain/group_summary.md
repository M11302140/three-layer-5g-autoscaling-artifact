| group | runs | runs with affected arrivals | affected arrivals (per run) | violation minutes ≤3 min after affected arrival (per run) |
|---|---|---|---|---|
| HHRO t3 eq-start(5 slots) | 1 | 1 | r174:32 | r174:7 |
| S2a 0.5% t2 | 1 | 1 | r208:2 | r208:0 |
| S3a 0.5% final t2 | 2 | 2 | r240:23 / r246:19 | r240:0 / r246:0 |
| S3b 2% final t2 | 1 | 1 | r242:6 | r242:0 |
| S4a 0.5% G2b t2 | 3 | 3 | r250:23 / r254:23 / r260:16 | r250:0 / r254:0 / r260:0 |
| S4b 2% G2b t2 | 3 | 3 | r252:6 / r256:6 / r262:6 | r252:0 / r256:0 / r262:0 |
| MAIN t4 S4a | 3 | 3 | r300:27 / r312:26 / r317:27 | r300:0 / r312:1 / r317:2 |
| MAIN t4 S4b | 3 | 3 | r303:15 / r314:15 / r322:15 | r303:2 / r314:0 / r322:2 |
| MAIN t4 v6 confirm post-IRQ | 1 | 1 | r381:13 | r381:2 |
| MAIN t3 S4a | 3 | 3 | r360:14 / r372:16 / r377:14 | r360:0 / r372:0 / r377:0 |
| MAIN t3 v6 | 3 | 3 | r361:16 / r367:16 / r378:13 | r361:0 / r367:0 / r378:0 |
| MAIN t3 B4c2 | 3 | 3 | r362:14 / r373:14 / r382:14 | r362:0 / r373:0 / r382:0 |
| MAIN t3 S4b | 3 | 3 | r363:16 / r369:11 / r374:16 | r363:0 / r369:0 / r374:0 |
| MAIN t3 B5c1 (q11) | 3 | 3 | r364:14 / r375:14 / r380:14 | r364:0 / r375:0 / r380:0 |
| MAIN t3 B6 u=0.70 | 3 | 3 | r365:15 / r371:34 / r383:34 | r365:0 / r371:3 / r383:5 |
| B3 HPA-only t1 (post-IRQ) | 3 | 3 | r396:3 / r397:3 / r398:3 | r396:0 / r397:0 / r398:0 |
| B3 HPA-only t2 (post-IRQ) | 3 | 3 | r399:2 / r400:13 / r401:2 | r399:0 / r400:3 / r401:0 |
| MAIN t5 S4a | 1 | 1 | r330:20 | r330:0 |
| MAIN t5 v6 | 1 | 1 | r331:26 | r331:0 |
| MAIN t6 S4a | 3 | 3 | r402:36 / r414:51 / r419:45 | r402:0 / r414:0 / r419:0 |
| MAIN t6 v6 | 3 | 3 | r403:17 / r409:3 / r420:18 | r403:0 / r409:0 / r420:2 |
| MAIN t6 S4b | 3 | 3 | r405:38 / r411:41 / r416:41 | r405:0 / r411:0 / r416:0 |
| MAIN t7 S4a | 3 | 3 | r430:25 / r442:25 / r447:25 | r430:0 / r442:1 / r447:0 |
| MAIN t7 v6 | 3 | 3 | r431:25 / r437:25 / r448:25 | r431:0 / r437:0 / r448:0 |
| MAIN t7 S4b | 3 | 3 | r433:41 / r439:43 / r444:44 | r433:0 / r439:0 / r444:0 |
| MAIN t7 B5c1 (q11) | 3 | 3 | r434:7 / r440:10 / r445:7 | r434:0 / r440:0 / r445:0 |
| MAIN t7 B6 u=0.70 | 3 | 2 | r435:2 / r441:0 / r446:2 | r435:0 / r441:0 / r446:0 |
| MAIN t5 S4b | 1 | 1 | r333:44 | r333:0 |
| S2b 2% t2 | 1 | 1 | r214:20 | r214:1 |

clean groups (no affected arrivals): 98
HHRO t1, HHRO t2, B1 static t1, B1 static t2, B4 DASA+HPA t1, B4 DASA+HPA t2, B5 predictive t1, B5 predictive t2, B2 DASA-only t1, B2 DASA-only t2, B3 HPA-only t1, B3 HPA-only t2, HHRO t3, B1 static t3, B4 DASA+HPA t3, HHRO-Q e05 r0 t1, HHRO-Q e05 r0 t2, HHRO-Q e10 r0 t1, HHRO-Q e10 r0 t2, HHRO-Q e10 r1 t1, HHRO-Q e10 r1 t2, HHRO-Q v7.0.4 rho05 t1, HHRO-Q v7.0.4 rho05 t2, HHRO-Q v7.0.4 t1, HHRO-Q v7.0.4 t2, HHRO-Q v7.0.5 t2, HHRO-Q final t1 (r200), HHRO-Q final t2 (r198), A1 hold-off t1, A2 lead2 t1, A3a lambda x4 t1, A3b lambda /4 t1, A3c lambda x16 t1, A4 layered t1, A4 layered t2, S1 sigma 1.5/3.5 t1, S1 sigma 1.5/3.5 t2, S2a 0.5% t1, HHRO ctrl 10-04 t1, HHRO ctrl 10-04 t2, HHRO ctrl restored t1, HHRO ctrl restored t2, S2a 0.5% restored-extra t1, S2a 0.5% restored-extra t2, S2b 2% restored-extra t1, S2b 2% restored-extra t2, S3a 0.5% final t1, S3b 2% final t1, HHRO ctrl final t1, HHRO ctrl final t2, HHRO ctrl G2b t1, HHRO ctrl G2b t2, S4a 0.5% G2b t1, S4b 2% G2b t1, HHRO ctrl G2c t1 (post-fix v9), S4a 0.5% G2c t1 (post-fix v9), B4 DASA+HPA G2d t1 (post-fix v9), B5 predictive G2d t1 (post-fix v9), B4c1 SLO-tune 4.0/14 t1, B4c2 SLO-tune 3.5/12 t1, B4c3 SLO-tune 3.0/11 t1, B5c1 SLO-tune 4.0/14 t1, B5c2 SLO-tune 3.5/12 t1, B4c2 SLO-tune t2 (reverify), B5c1 SLO-tune t2 (reverify), B6 Toka u=0.78 t1 (q7), B4c3 SLO-tune t2 (rerun), B6 Toka u=0.85 t1 (q9), B6 Toka u=0.78 t1 (q9), B6 Toka u=0.70 t1 (q9), B6 Toka u=0.70 t2 (q9), B5c1 SLO-tune t2 (extra, clean start), MAIN t4 v6, MAIN t4 B4c2, MAIN t4 B4c2 r302 (start transient; replaced by r320), MAIN t4 B5c1 (q11), MAIN t4 B6 u=0.70, MAIN t4 B1, MAIN t3 B1, B2 DASA-only t1 (post-IRQ), B2 DASA-only t2 (post-IRQ), MAIN t5 B4c2, MAIN t6 B4c2, MAIN t6 B5c1 (q11), MAIN t6 B6 u=0.70, MAIN t6 B1, MAIN t7 B4c2, MAIN t7 B1, MAIN t5 B5c1 (q11), MAIN t5 B6 u=0.70, MAIN t5 B1, S2b 2% t1, G t8 S4a, G t8 B6c4_slo, G t8 HHRO, G t8 S4b, H t3 B6c5_h, H t6 B6c5_h
