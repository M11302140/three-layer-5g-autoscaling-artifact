#!/bin/bash
# Task D: 17 library variants (s5_c4_d2 == frozen library, verified identical → reuse E_base_p90). REFINE flag set below.
cd /home/user/experiment/qsim/r62de
P="nice -n 19 taskset -c 13,14 python3"
RF="$1"   # "" = full refine, "--no-refine" = coarse only
for s in 1 5 10; do for c in 1 2 4; do for d in 0 2; do
  [ "$s$c$d" = "542" ] && continue
  $P run_cal.py --name D_s${s}_c${c}_d${d} --lib libs/lib_s${s}_c${c}_d${d}.json $RF > out_D_s${s}_c${c}_d${d}.log 2>&1
done; done; done
echo CHAIND_DONE >> progress.log
