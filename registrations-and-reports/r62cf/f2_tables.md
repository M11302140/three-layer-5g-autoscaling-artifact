| arm | trace | SLO without rule | SLO with rule | Δ SLO min | alloc without | alloc with | Δ alloc | latched ticks | why the force did not act (ticks) | forces attempted (t s, action, dispatched) |
|---|---|---|---|---|---|---|---|---|---|---|
| S4a | t3 | 57/60 | 57/60 | +0 | 1254 | 1254 | +0 | 6 | controller_scaled_out 1, no_action:slots_at_max_8 5 | — |
| S4a | t4 | 58/60 | 58/60 | +0 | 1452 | 1452 | +0 | 3 | no_action:slots_at_max_8 3 | — |
| S4a | t6 | 57/60 | 57/60 | +0 | 1448 | 1448 | +0 | 5 | no_action:slots_at_max_8 5 | — |
| S4a | t7 | 60/60 | 60/60 | +0 | 1432 | 1432 | +0 | 0 | — | — |
| S4b | t3 | 55/60 | 55/60 | +0 | 1138 | 1138 | +0 | 9 | refractory 1, controller_scaled_out 2, no_action:slots_at_max_8 5 | 240 up(noworker,worker booting) False |
| S4b | t4 | 56/60 | 56/60 | +0 | 1425 | 1425 | +0 | 6 | no_action:slots_at_max_8 6 | — |
| S4b | t6 | 55/60 | 55/60 | +0 | 1397 | 1397 | +0 | 8 | no_action:slots_at_max_8 8 | — |
| S4b | t7 | 60/60 | 60/60 | +0 | 1396 | 1396 | +0 | 0 | — | — |
| v6 | t3 | 55/60 | 55/60 | +0 | 1119 | 1119 | +0 | 9 | refractory 1, controller_scaled_out 2, no_action:slots_at_max_8 5 | 240 up(noworker,worker booting) False |
| v6 | t4 | 58/60 | 58/60 | +0 | 1382 | 1382 | +0 | 3 | no_action:slots_at_max_8 3 | — |
| v6 | t6 | 58/60 | 58/60 | +0 | 1365 | 1365 | +0 | 3 | no_action:slots_at_max_8 3 | — |
| v6 | t7 | 59/60 | 59/60 | +0 | 1368 | 1368 | +0 | 1 | controller_scaled_out 1 | — |
| B4c2 | t3 | 57/60 | 57/60 | +0 | 1234 | 1234 | +0 | 6 | refractory 2, controller_scaled_out 1, no_action:slots_at_max_8 2 | 240 up(noworker,worker booting) False |
| B4c2 | t4 | 60/60 | 60/60 | +0 | 1447 | 1447 | +0 | 0 | — | — |
| B4c2 | t6 | 60/60 | 60/60 | +0 | 1448 | 1448 | +0 | 0 | — | — |
| B4c2 | t7 | 60/60 | 60/60 | +0 | 1442 | 1442 | +0 | 0 | — | — |
| B5c1 | t3 | 55/60 | 55/60 | +0 | 1163 | 1163 | +0 | 10 | refractory 2, controller_scaled_out 1, no_action:slots_at_max_8 6 | 240 up(noworker,worker booting) False |
| B5c1 | t4 | 58/60 | 58/60 | +0 | 1410 | 1410 | +0 | 3 | no_action:slots_at_max_8 3 | — |
| B5c1 | t6 | 58/60 | 58/60 | +0 | 1375 | 1375 | +0 | 3 | no_action:slots_at_max_8 3 | — |
| B5c1 | t7 | 60/60 | 60/60 | +0 | 1410 | 1410 | +0 | 0 | — | — |
| B6 | t3 | 55/60 | 55/60 | +0 | 1218 | 1218 | +0 | 6 | refractory 2, controller_scaled_out 1, no_action:slots_at_max_8 2 | 240 up(noworker,worker booting) False |
| B6 | t4 | 60/60 | 60/60 | +0 | 1447 | 1447 | +0 | 0 | — | — |
| B6 | t6 | 60/60 | 60/60 | +0 | 1437 | 1437 | +0 | 0 | — | — |
| B6 | t7 | 60/60 | 60/60 | +0 | 1448 | 1448 | +0 | 0 | — | — |

R38-off repeat (counterfactual knee38 = 5), same table condensed:

| arm | trace | SLO without / with | alloc without / with | latched | forces |
|---|---|---|---|---|---|
| S4a | t3 | 57 / 57 | 1255 / 1255 | 5 | — |
| S4a | t4 | 60 / 60 | 1452 / 1452 | 0 | — |
| S4a | t6 | 60 / 60 | 1448 / 1448 | 0 | — |
| S4a | t7 | 60 / 60 | 1432 / 1432 | 0 | — |
| S4b | t3 | 55 / 55 | 1138 / 1138 | 8 | 270 up(noworker,worker booting) False |
| S4b | t4 | 59 / 59 | 1425 / 1425 | 1 | — |
| S4b | t6 | 60 / 60 | 1390 / 1390 | 0 | — |
| S4b | t7 | 60 / 60 | 1396 / 1396 | 0 | — |
| v6 | t3 | 55 / 55 | 1119 / 1119 | 8 | 270 up(noworker,worker booting) False |
| v6 | t4 | 59 / 59 | 1382 / 1382 | 1 | — |
| v6 | t6 | 60 / 60 | 1360 / 1360 | 0 | — |
| v6 | t7 | 60 / 60 | 1368 / 1368 | 0 | — |
| B4c2 | t3 | 57 / 57 | 1234 / 1234 | 5 | 270 up(noworker,worker booting) False |
| B4c2 | t4 | 60 / 60 | 1447 / 1447 | 0 | — |
| B4c2 | t6 | 60 / 60 | 1448 / 1448 | 0 | — |
| B4c2 | t7 | 60 / 60 | 1442 / 1442 | 0 | — |
| B5c1 | t3 | 55 / 55 | 1163 / 1163 | 9 | 270 up(noworker,worker booting) False |
| B5c1 | t4 | 59 / 59 | 1410 / 1410 | 1 | — |
| B5c1 | t6 | 60 / 60 | 1375 / 1375 | 0 | — |
| B5c1 | t7 | 60 / 60 | 1410 / 1410 | 0 | — |
| B6 | t3 | 55 / 55 | 1218 / 1218 | 5 | 270 up(noworker,worker booting) False |
| B6 | t4 | 60 / 60 | 1447 / 1447 | 0 | — |
| B6 | t6 | 60 / 60 | 1437 / 1437 | 0 | — |
| B6 | t7 | 60 / 60 | 1448 / 1448 | 0 | — |

Whole-library supplement (1615 traces, R38 on; without-rule reference = frozen `v8sim11_lib_<arm>_r38on.json`):

| arm | risk without | risk with | Δ risk (pp) | cost without | cost with | Δ cost | forces attempted / dispatched | traces changed |
|---|---|---|---|---|---|---|---|---|
| S4a | 5.110 % | 5.118 % | +0.007 | 1337.5 | 1337.8 | +0.4 (+0.03 %) | 308 / 184 | 171 |
| S4b | 7.528 % | 7.492 % | -0.036 | 1282.4 | 1284.2 | +1.8 (+0.14 %) | 948 / 577 | 458 |
| v6 | 5.676 % | 5.607 % | -0.069 | 1258.8 | 1261.3 | +2.5 (+0.20 %) | 1152 / 608 | 483 |
| B4c2 | 2.215 % | 2.189 % | -0.026 | 1310.4 | 1311.2 | +0.8 (+0.06 %) | 545 / 216 | 185 |
| B5c1 | 3.948 % | 3.912 % | -0.036 | 1271.4 | 1273.2 | +1.8 (+0.14 %) | 1053 / 537 | 421 |
| B6 | 1.980 % | 1.979 % | -0.001 | 1319.6 | 1320.3 | +0.7 (+0.05 %) | 344 / 91 | 82 |
