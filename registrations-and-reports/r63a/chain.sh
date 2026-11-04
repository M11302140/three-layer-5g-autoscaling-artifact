#!/bin/bash
# r63a chain: split -> boot 5 (runtime projection) -> boot N (200, or 100 if projection > 5 h) -> bucket
cd /home/user/experiment/qsim/r63a
PY="nice -n 19 taskset -c 13,14 python3"
$PY run.py split || exit 1
$PY run.py boot 5 || exit 1
T5=$(grep -o "DONE boot N=5 [0-9]*s" progress.log | tail -1 | grep -o "[0-9]*s$" | tr -d s)
PROJ=$(( T5 * 200 / 5 ))
if [ "$PROJ" -gt 18000 ]; then N=100; else N=200; fi
echo "[$(date '+%F %T')] [chain] boot 5 took ${T5}s -> projection for 200 = ${PROJ}s; running N=${N}" | tee -a progress.log
$PY run.py boot $N || exit 1
$PY run.py bucket || exit 1
$PY analyze.py > analyze.log 2>&1
echo "[$(date '+%F %T')] [chain] ALL DONE" | tee -a progress.log
