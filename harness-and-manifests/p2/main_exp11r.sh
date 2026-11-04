#!/bin/bash
P=/home/user/experiment/p2; cd $P
M="sshpass -p "$SSH_PASS" ssh -n -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR user@10.0.0.50"
declare -A SREP=([t4]=5 [t6]=6 [t8]=4 [t11]=8 [t12]=8) SWK=([t4]=3 [t6]=3 [t8]=2 [t11]=4 [t12]=4) SVY=([t4]=2 [t6]=2 [t8]=2 [t11]=3 [t12]=3)
LEDGER=$P/s_ledger.tsv; [ -f $LEDGER ] || echo -e "run\tphase\tblock\tarm\tslo\tburned\tflags\tclass\ttime" > $LEDGER
consec=0
log(){ echo "[$(date '+%F %T')] $*"; }
check_platform(){   # $1=run id(rNNN) $2=block
  local N=$1; local B=$2; local f=""; local l=${B}_v7$N.log
  grep -qE "workers not Ready|never converged|chain failed|prep abort" $l chain_v7${N}*.log 2>/dev/null && f="$f chain-abort"
  grep -qE "STALL" $l chain_v7${N}*.log 2>/dev/null && f="$f harness-stall"
  grep -q "FINISH rc=0" $l 2>/dev/null || f="$f no-finish"
  grep -qE "panic:|fatal error" v7${N}_daemon.log 2>/dev/null && f="$f daemon-panic"
  grep -q "NG dead by log marker" trace_v7_${N}.log 2>/dev/null && f="$f ng-dead"
  local st=$(python3 check_exclusions.py $N 2>/dev/null | grep -oE "stale=[0-9]+" | cut -d= -f2); [ -n "$st" ] && [ "$st" -gt 0 ] && f="$f excl-stale"
  local py=$(python3 - "$N" <<'PY' 2>/dev/null
import csv,sys
try: rows=list(csv.DictReader(open(f'/home/user/experiment/p2/trace_v7_{sys.argv[1]}.csv')))
except Exception: sys.exit(0)
out=[]
if rows and max(int(r.get('worker_n') or 0) for r in rows)>4: out.append('workers>4')
if rows and float(rows[0]['e2e_pct'] or 0)>1.0: out.append('start-transient')
print(' '.join(out))
PY
)
  echo "$f $py" | xargs
}
commit_raw(){
  local N=$1; cd /home/user
  local fs=$(ls -d experiment/p2/*v7r${N}* experiment/p2/trace_v7_r${N}* experiment/p2/prom/v7r${N}_* experiment/p2/s_ledger.tsv experiment/p2/s_exp.log 2>/dev/null)
  for k in 1 2 3 4 5; do git add -f -- $fs >/dev/null 2>&1 && git commit -q -m "r72hw raw r$N (spec §4.140; raw data only)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" -- $fs >/dev/null 2>&1 && { log "COMMIT raw r$N $(git log --oneline -1 | cut -c1-8)"; break; }; sleep 20; done
  cd $P
}
record(){   # $1=arm $2=block $3=id $4=phase
  local arm=$1 B=$2 N=$3 ph=$4
  local slo=$(grep -oE "SLO\(loss<=0.1% & p99<=1ms\): [0-9]+/60" finish_v7r$N.log 2>/dev/null | grep -oE "[0-9]+/60"); local burned=$(grep -oE "TOTAL=[0-9]+" finish_v7r$N.log 2>/dev/null | cut -d= -f2)
  local flags=$(check_platform r$N $B); local cls=ok
  case " $flags " in *" ng-dead "*|*" excl-stale "*|*" harness-stall "*|*" no-finish "*) cls=harness-fault;; esac
  [ "$cls" = ok ] && [ -n "$flags" ] && cls=flag-no-rerun
  echo -e "r$N\t$ph\t$B\t$arm\t${slo:-?}\t${burned:-?}\t${flags:-ok}\t$cls\t$(date '+%F %T')" >> $LEDGER
  log "DONE r$N $ph $B $arm flags=${flags:-ok} class=$cls"
  commit_raw $N
  if [ "$cls" = harness-fault ]; then local cell="$arm:$B"; case " $RETRIED " in *" $cell "*) log "harness-fault $cell already retried once — no further rerun";; *) RETRY="$RETRY $cell"; RETRIED="$RETRIED $cell";; esac; fi
  if [ -n "$flags" ]; then consec=$((consec+1)); else consec=0; fi
  case " $flags " in *" start-transient "*|*" chain-abort "*) log "STOP (§4.81 t7 condition 3): $flags in r$N — report before continuing"; touch $P/s_exp.STOP; exit 1;; esac
  if [ $consec -ge 2 ]; then log "STOP: two consecutive flagged runs ($flags) — diagnose before continuing"; touch $P/s_exp.STOP; exit 1; fi
}
pcf_refresh(){ log "PCF-REFRESH: rollout restart open5gs-pcf"; $M 'kubectl -n open5gs rollout restart deploy/open5gs-pcf >/dev/null; kubectl -n open5gs rollout status deploy/open5gs-pcf --timeout=120s >/dev/null' ; sleep 15; }
fleet_guard(){
  local extra=$($M 'kubectl get nodes --no-headers | grep -oE "^worker-[4-9]"' 2>/dev/null)
  for w in $extra; do log "FLEET-GUARD: deleting extra $w"; $M "curl -s -m 120 -X POST 'http://10.102.132.80:8080/scale/worker/down?name=$w&force=true'" >/dev/null; sleep 15; done
}
run_one(){   # $1=arm $2=block $3=id $4=phase
  local arm=$1 B=$2 N=$3 ph=$4
  grep -qP "^r$N\t" $LEDGER && { log "SKIP r$N (in ledger)"; return; }
  fleet_guard
  [ -f $P/s_exp.STOP ] && { log "STOP file present — exiting before $arm:$B:r$N"; exit 2; }
  log "RUN r$N $B $arm"
  if [[ $arm == S* ]]; then MAIN_WARMIN=trace_warmin_$B.json MAIN_START_REP=${SREP[$B]} MAIN_START_WK=${SWK[$B]} MAIN_START_VY=${SVY[$B]} bash abl_queue_main2.sh "$arm:$B:r$N" >> s_exp_queue.log 2>&1
  else bash abl_queue_main2.sh "$arm:$B:r$N" >> s_exp_queue.log 2>&1; fi
  record $arm $B $N $ph
}
probe(){ log "PROBE $1"; bash field_probe.sh $1 2>&1 | tee -a field_probe_results.log | grep -E "^PROBE" | tail -1; }
gate_probe(){   # $1=probe id
  grep -q "PROBE $1 " field_probe_results.log || probe $1
  local r=$(grep -E "^PROBE $1 " field_probe_results.log | tail -1); log "probe $1: $r"
  echo "$r" | awk '{exit !($10+0<=0.05 && $8+0<=450)}' || { log "STOP: probe $1 not clean (e2e>0.05 or p99>450)"; touch $P/s_exp.STOP; exit 1; }
}
phase(){   # $1=phase name $2=list $3=first retry id
  log "$1 START (resume)"; pcf_refresh; RETRY="${PRE_RETRY:-}"; RETRIED="${PRE_RETRY:-}"; consec=0
  for it in $2; do arm=${it%%:*}; rest=${it#*:}; B=${rest%%:*}; N=${rest#*:}; run_one $arm $B $N $1; done
  id=$3; for it in $RETRY; do arm=${it%%:*}; B=${it#*:}; log "RETRY $arm $B (harness-fault) as r$id"; run_one $arm $B $id $1-retry; id=$((id+1)); done
  log "$1 ALL DONE"
}
CLIST=${CLIST:-"S4p05:t6:530 S4p2:t6:531 S4p2:t4:532 S4p2:t4:533 S4p2:t8:534 S4p2:t8:535 S4p2:t4:536 S4p05:t6:537 S4p2:t6:538 S4p2:t6:539 S4p05:t6:540 S4p05:t4:541 S4p05:t8:542 S4p05:t8:543 S4p05:t4:544 S4p05:t8:545 S4p05:t4:546 S4p2:t8:547"}
DLIST=${DLIST:-"B5c1_slo:t12:560 B4A_375_300:t11:561 S4p2:t11:562 B5c1_slo:t11:563 S4p2:t11:564 B5c1_slo:t12:565 B6c5_h:t11:566 B6c5_h:t12:567 B4A_375_300:t11:568 S4b:t11:569 S4p2:t12:570 B4A_375_300:t12:571 S4b:t12:572 B5c1_slo:t11:573 B6c5_h:t11:574 S4p2:t12:575 B4A_375_300:t12:576 S4b:t11:577 B6c5_h:t12:578 S4b:t12:579"}
rm -f $P/s_exp.STOP; gate_probe p36b
PRE_RETRY="B6c5_h:t11 B6c5_h:t12" phase D "$DLIST" 580
gate_probe p37
log "C+D ALL DONE"
