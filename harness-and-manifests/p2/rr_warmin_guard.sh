#!/bin/bash
P=/home/user/experiment/p2; cd $P; last=0
while [ ! -f $P/rr_guard.STOP ]; do
  sleep 60
  L=$(ls -t trace_v7_r50[0-9]w*.log 2>/dev/null | head -1); [ -z "$L" ] && continue
  [ $(( $(date +%s) - $(stat -c %Y $L) )) -gt 120 ] && continue
  ls -t trace_v7_r50[0-9].log 2>/dev/null | head -1 | xargs -r stat -c %Y 2>/dev/null | { read f; [ -n "$f" ] && [ "$f" -gt "$(stat -c %Y $L)" ]; } && continue
  [ $(( $(date +%s) - last )) -lt 240 ] && continue
  tag=$(basename $L .log | sed 's/^trace_v7_//'); now=$(date +%s)
  rep=$(tail -n 300 $L | grep -oE "^\[[0-9:]+\] min[0-9]+: UE-[0-9]+ datapath black" | while read -r a b c d; do hms=${a//[\[\]]/}; t=$(date -d "today $hms" +%s); [ $((now-t)) -le 150 ] && echo "${c} ${b}"; done | sort -u | awk '{n[$1]++} END{for(u in n) if(n[u]>=2) print u}' | tr '\n' ' ')
  [ -z "$rep" ] && continue
  arm=$(grep -oE "RUN r[0-9]+ t[0-9] [A-Za-z0-9_]+" rr_exp.log | tail -1 | awk '{print $4}')
  if [[ "$arm" == B6* ]]; then
    echo "[$(date '+%F %T')] WARMIN-GUARD: $tag ($arm) repeated black: $rep → bounce_black.sh $tag" >> rr_exp.log
    bash bounce_black.sh $tag >> rr_exp.log 2>&1; last=$(date +%s)
  else
    echo "[$(date '+%F %T')] WARMIN-GUARD: $tag ($arm) repeated black: $rep → NO intervention; S/v6 needing 3-step = §4.81 condition 2 → STOP after this run" >> rr_exp.log
    touch rr_exp.STOP; last=$(date +%s)
  fi
done
