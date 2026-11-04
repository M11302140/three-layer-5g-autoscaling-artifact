#!/bin/bash
P=/home/user/experiment/p2; cd $P; last=0
while [ ! -f $P/ab_guard.STOP ]; do
  sleep 60
  L=$(ls -t trace_v7_r46[0-9]w*.log 2>/dev/null | head -1); [ -z "$L" ] && continue
  [ $(( $(date +%s) - $(stat -c %Y $L) )) -gt 120 ] && continue
  ls -t trace_v7_r46[0-9].log 2>/dev/null | head -1 | xargs -r stat -c %Y 2>/dev/null | { read f; [ -n "$f" ] && [ "$f" -gt "$(stat -c %Y $L)" ]; } && continue
  [ $(( $(date +%s) - last )) -lt 240 ] && continue
  tag=$(basename $L .log | sed 's/^trace_v7_//'); now=$(date +%s)
  rep=$(tail -n 300 $L | grep -oE "^\[[0-9:]+\] min[0-9]+: UE-[0-9]+ datapath black" | while read -r a b c d; do hms=${a//[\[\]]/}; t=$(date -d "today $hms" +%s); [ $((now-t)) -le 150 ] && echo "${c} ${b}"; done | sort -u | awk '{n[$1]++} END{for(u in n) if(n[u]>=2) print u}' | tr '\n' ' ')
  [ -z "$rep" ] && continue
  echo "[$(date '+%F %T')] WARMIN-GUARD: $tag repeated black: $rep → bounce_black.sh $tag" >> ab_exp.log
  bash bounce_black.sh $tag >> ab_exp.log 2>&1; last=$(date +%s)
done
