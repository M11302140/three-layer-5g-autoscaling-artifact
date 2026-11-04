#!/bin/bash
P=/home/user/experiment/p2; cd $P
for item in $1; do
  kind=${item%%:*}; N=${item##*:}
  echo "== queue start $item $(date +%T)"
  echo "   seg-rss pre-run: $(timeout 60 bash /home/user/experiment/p2/seg_rss_probe.sh 2>&1 | tail -2 | tr '\n' ' ')"
  if [ "$kind" = "t2" ]; then bash run_trace2.sh $N > t2_v7$N.log 2>&1; log=t2_v7$N.log
  elif [[ "$kind" =~ ^t([3-9]|1[0-2])$ ]]; then
    W=trace_warmin_$kind.json; [ "${STATIC_FLEET:-0}" = "1" ] && W=trace_warmin_${kind}_static.json
    FORMAL_TRACE=trace_ue_60min_v3_$kind.json WARMIN_TRACE=${WARMIN_TRACE:-$W} bash run_trace2.sh $N > ${kind}_v7$N.log 2>&1; log=${kind}_v7$N.log
  else bash run_trace1.sh $N > t1_v7$N.log 2>&1; log=t1_v7$N.log; fi
  tail -3 $log
  grep -q "FINISH rc=0" $log || { echo "== queue STOP: $item did not finish cleanly $(date +%T)"; exit 1; }
  grep -q "SLO(loss<=0.1% & p99<=1ms): 60/60" finish_v7$N.log || { if [ "${KEEP_GOING:-0}" = "1" ]; then echo "== queue NOTE: $item not 60/60 $(date +%T) — continuing"; else echo "== queue STOP: $item not 60/60 $(date +%T)"; exit 2; fi; }
  sleep 30
done
echo "== queue ALL DONE $(date +%T)"
