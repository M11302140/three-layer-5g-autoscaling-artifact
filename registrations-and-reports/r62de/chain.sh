#!/bin/bash
# sequential chain (one python process at a time) — r62de §4.104 E then D
cd /home/user/experiment/qsim/r62de
P="nice -n 19 taskset -c 13,14 python3"
$P run_cal.py --name E_ready_p95 --h 125,85,65   > out_E_p95.log 2>&1
$P run_cal.py --name E_ready_p99 --h 155,90,70   > out_E_p99.log 2>&1
$P run_cal.py --name E_inflight_p95p99 --h 60,180,150 > out_E_inf.log 2>&1
$P run_cal.py --name D_rates --rates > out_D_rates.log 2>&1
echo CHAIN1_DONE >> progress.log
