<!-- artifact file of the paper "Predictable-Cost Autoscaling of a Three-Layer 5G User Plane with Library-Calibrated Risk" (docs/paper), written 2026-10-21 for the round-62 analyses (spec §4.104 H item 4, results §4.105). Content copied from qsim/r62cf/REPORT.md, section F2, with dashes replaced by a colon or n/a; simulation only, no hardware run. -->

# Emergency-rule parity in simulation

## F2 Emergency-rule parity (v8sim11 copy `v8sim11_emerg.py`)

**What v8sim11 models.** The frozen v8sim11 has **no emergency rule for any arm** (no S, v6 or baseline code path; `grep -i emerg` empty). The S arms are therefore reported unchanged: "S without the rule" = frozen v8sim11. To make the parity question answerable, the copy adds the daemon rule as an optional wrapper (`run(..., emerg=True)`) that can be applied to **every** arm. "S/v6 with the rule" is the deployed-like configuration; "B4c2/B5c1/B6 with the rule" is the parity variant. With `emerg=False` the copy is bit-identical to frozen `v8sim11.run` (SLO, violating minutes and alloc on all 24 arm×trace cells: `equiv True`).

**Rule as ported** (planner.go `EmergencyV6` 647–672, v6shadow.go 882–900 latch and EWMA, controller.go 236–290 force block):
- offered = D × 250 kpps (sigma-mode daemon uses UECount × PerUEBidir); offeredEWMA = 0.7·prev + 0.3·offered per 30 s tick, used in every branch (as the daemon passes `v.offeredEWMA`).
- **Measured loss mapping:** meas_UP = P90 over the last 60 s (12 × 5 s physics steps) of the slot-overflow loss / D, and meas_VY = the same for VyOS-overflow loss (daemon: `DropUP.P90_60`, `VyosLossRatio.P90_60`). This is valid when D ≥ 1 (≥ 200 kpps). e2e = 1 − (1 − meas_VY)(1 − meas_UP).
- NUP = RepUP (booting + ready + draining pods); NVY = admitted VyOS. uVY = EWMA / (NVY · 4.45 M); uUP = EWMA / (NUP · 1.35 M).
- raw = (e2e ≥ 0.001 ∧ (uVY ≥ 0.5 ∨ uUP ≥ 0.5)) ∨ uVY ≥ 1.001 ∨ uUP ≥ 1.020. Here 1.001 = ThetaCritVY with the empty pre-cliff table (1 − 1/u = 0.001), and 1.020 = ThetaCritUP = 1 + ln(1.001)/0.05. The rule latches after 2 consecutive raw ticks.
- Force: if latched, the controller dispatched no scale-out (or drain cancel) in this tick, and more than 90 s have passed since the last force, then:
  - if meas_VY ≥ meas_UP and VyOS VMs < 3, deploy a VyOS;
  - else, if RepUP < 8 and no slot is booting, scale out one slot (cancel a drain if one is in flight). If there is no ready worker position, create the slot's worker first when none is booting (executor behaviour).
  - The force is suppressed if the reverse action was dispatched within T_ready(rev) + T_ready(act) + 30 s (VyOS 145 s, slot 165 s), as in the daemon.

| arm | trace | SLO without rule | SLO with rule | Δ SLO min | alloc without | alloc with | Δ alloc | latched ticks | why the force did not act (ticks) | forces attempted (t s, action, dispatched) |
|---|---|---|---|---|---|---|---|---|---|---|
| S4a | t3 | 57/60 | 57/60 | +0 | 1254 | 1254 | +0 | 6 | controller_scaled_out 1, no_action:slots_at_max_8 5 |: |
| S4a | t4 | 58/60 | 58/60 | +0 | 1452 | 1452 | +0 | 3 | no_action:slots_at_max_8 3 |: |
| S4a | t6 | 57/60 | 57/60 | +0 | 1448 | 1448 | +0 | 5 | no_action:slots_at_max_8 5 |: |
| S4a | t7 | 60/60 | 60/60 | +0 | 1432 | 1432 | +0 | 0 |: |: |
| S4b | t3 | 55/60 | 55/60 | +0 | 1138 | 1138 | +0 | 9 | refractory 1, controller_scaled_out 2, no_action:slots_at_max_8 5 | 240 up(noworker,worker booting) False |
| S4b | t4 | 56/60 | 56/60 | +0 | 1425 | 1425 | +0 | 6 | no_action:slots_at_max_8 6 |: |
| S4b | t6 | 55/60 | 55/60 | +0 | 1397 | 1397 | +0 | 8 | no_action:slots_at_max_8 8 |: |
| S4b | t7 | 60/60 | 60/60 | +0 | 1396 | 1396 | +0 | 0 |: |: |
| v6 | t3 | 55/60 | 55/60 | +0 | 1119 | 1119 | +0 | 9 | refractory 1, controller_scaled_out 2, no_action:slots_at_max_8 5 | 240 up(noworker,worker booting) False |
| v6 | t4 | 58/60 | 58/60 | +0 | 1382 | 1382 | +0 | 3 | no_action:slots_at_max_8 3 |: |
| v6 | t6 | 58/60 | 58/60 | +0 | 1365 | 1365 | +0 | 3 | no_action:slots_at_max_8 3 |: |
| v6 | t7 | 59/60 | 59/60 | +0 | 1368 | 1368 | +0 | 1 | controller_scaled_out 1 |: |
| B4c2 | t3 | 57/60 | 57/60 | +0 | 1234 | 1234 | +0 | 6 | refractory 2, controller_scaled_out 1, no_action:slots_at_max_8 2 | 240 up(noworker,worker booting) False |
| B4c2 | t4 | 60/60 | 60/60 | +0 | 1447 | 1447 | +0 | 0 |: |: |
| B4c2 | t6 | 60/60 | 60/60 | +0 | 1448 | 1448 | +0 | 0 |: |: |
| B4c2 | t7 | 60/60 | 60/60 | +0 | 1442 | 1442 | +0 | 0 |: |: |
| B5c1 | t3 | 55/60 | 55/60 | +0 | 1163 | 1163 | +0 | 10 | refractory 2, controller_scaled_out 1, no_action:slots_at_max_8 6 | 240 up(noworker,worker booting) False |
| B5c1 | t4 | 58/60 | 58/60 | +0 | 1410 | 1410 | +0 | 3 | no_action:slots_at_max_8 3 |: |
| B5c1 | t6 | 58/60 | 58/60 | +0 | 1375 | 1375 | +0 | 3 | no_action:slots_at_max_8 3 |: |
| B5c1 | t7 | 60/60 | 60/60 | +0 | 1410 | 1410 | +0 | 0 |: |: |
| B6 | t3 | 55/60 | 55/60 | +0 | 1218 | 1218 | +0 | 6 | refractory 2, controller_scaled_out 1, no_action:slots_at_max_8 2 | 240 up(noworker,worker booting) False |
| B6 | t4 | 60/60 | 60/60 | +0 | 1447 | 1447 | +0 | 0 |: |: |
| B6 | t6 | 60/60 | 60/60 | +0 | 1437 | 1437 | +0 | 0 |: |: |
| B6 | t7 | 60/60 | 60/60 | +0 | 1448 | 1448 | +0 | 0 |: |: |

R38-off repeat (counterfactual knee38 = 5), same table condensed:

| arm | trace | SLO without / with | alloc without / with | latched | forces |
|---|---|---|---|---|---|
| S4a | t3 | 57 / 57 | 1255 / 1255 | 5 |: |
| S4a | t4 | 60 / 60 | 1452 / 1452 | 0 |: |
| S4a | t6 | 60 / 60 | 1448 / 1448 | 0 |: |
| S4a | t7 | 60 / 60 | 1432 / 1432 | 0 |: |
| S4b | t3 | 55 / 55 | 1138 / 1138 | 8 | 270 up(noworker,worker booting) False |
| S4b | t4 | 59 / 59 | 1425 / 1425 | 1 |: |
| S4b | t6 | 60 / 60 | 1390 / 1390 | 0 |: |
| S4b | t7 | 60 / 60 | 1396 / 1396 | 0 |: |
| v6 | t3 | 55 / 55 | 1119 / 1119 | 8 | 270 up(noworker,worker booting) False |
| v6 | t4 | 59 / 59 | 1382 / 1382 | 1 |: |
| v6 | t6 | 60 / 60 | 1360 / 1360 | 0 |: |
| v6 | t7 | 60 / 60 | 1368 / 1368 | 0 |: |
| B4c2 | t3 | 57 / 57 | 1234 / 1234 | 5 | 270 up(noworker,worker booting) False |
| B4c2 | t4 | 60 / 60 | 1447 / 1447 | 0 |: |
| B4c2 | t6 | 60 / 60 | 1448 / 1448 | 0 |: |
| B4c2 | t7 | 60 / 60 | 1442 / 1442 | 0 |: |
| B5c1 | t3 | 55 / 55 | 1163 / 1163 | 9 | 270 up(noworker,worker booting) False |
| B5c1 | t4 | 59 / 59 | 1410 / 1410 | 1 |: |
| B5c1 | t6 | 60 / 60 | 1375 / 1375 | 0 |: |
| B5c1 | t7 | 60 / 60 | 1410 / 1410 | 0 |: |
| B6 | t3 | 55 / 55 | 1218 / 1218 | 5 | 270 up(noworker,worker booting) False |
| B6 | t4 | 60 / 60 | 1447 / 1447 | 0 |: |
| B6 | t6 | 60 / 60 | 1437 / 1437 | 0 |: |
| B6 | t7 | 60 / 60 | 1448 / 1448 | 0 |: |

Whole-library supplement (1615 traces, R38 on; without-rule reference = frozen `v8sim11_lib_<arm>_r38on.json`):

| arm | risk without | risk with | Δ risk (pp) | cost without | cost with | Δ cost | forces attempted / dispatched | traces changed |
|---|---|---|---|---|---|---|---|---|
| S4a | 5.110 % | 5.118 % | +0.007 | 1337.5 | 1337.8 | +0.4 (+0.03 %) | 308 / 184 | 171 |
| S4b | 7.528 % | 7.492 % | -0.036 | 1282.4 | 1284.2 | +1.8 (+0.14 %) | 948 / 577 | 458 |
| v6 | 5.676 % | 5.607 % | -0.069 | 1258.8 | 1261.3 | +2.5 (+0.20 %) | 1152 / 608 | 483 |
| B4c2 | 2.215 % | 2.189 % | -0.026 | 1310.4 | 1311.2 | +0.8 (+0.06 %) | 545 / 216 | 185 |
| B5c1 | 3.948 % | 3.912 % | -0.036 | 1271.4 | 1273.2 | +1.8 (+0.14 %) | 1053 / 537 | 421 |
| B6 | 1.980 % | 1.979 % | -0.001 | 1319.6 | 1320.3 | +0.7 (+0.05 %) | 344 / 91 | 82 |

Reading: on t3, t4, t6 and t7 the rule changes **nothing for any arm** (Δ SLO 0, Δ alloc 0 in all 24 cells, in both physics variants). The latch does fire (0–10 ticks per run), but when it fires:
- in nearly every case all **8 slots are already open**, VyOS loss is 0 (so meas_VY < meas_UP), and the rule has no action left;
- otherwise the controller is itself scaling out in that tick, or the 90 s refractory blocks it;
- the single attempted force (t3 ≈ min 4, all arms) needs a slot on a worker that is still booting, so nothing is dispatched.

The violating minutes in these traces are per-slot placement overflow at full fleet, which +1 capacity cannot fix. Over the whole library the rule does dispatch (91–608 forces per arm over 1615 traces), but the effect is tiny: risk changes by −0.07 to +0.01 pp and cost by +0.03 to +0.20 %. B4c2, B5c1 and B6 gain −0.026, −0.036 and −0.001 pp. **Parity conclusion: giving the baselines the daemon's emergency rule, or removing it from S, would not change any t3–t7 comparison in this simulator.** Caveat: the simulator's "measured loss" is model loss, without the measurement noise and transients that make the real latch fire (the reason the daemon requires 2 ticks and u ≥ 0.5). Real-testbed emergency firings (ops_per_run `emergency` column) are therefore not reproduced one-to-one.
