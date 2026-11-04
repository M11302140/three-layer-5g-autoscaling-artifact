#!/bin/bash
P=/home/user/experiment/p2; cd $P
M="sshpass -p "$SSH_PASS" ssh -n -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR user@10.0.0.50"
declare -A SREP=([t3]=6 [t5]=8 [t7]=7 [t4]=5 [t6]=6 [t8]=4 [t11]=8 [t12]=8) SWK=([t3]=3 [t5]=4 [t7]=4 [t4]=3 [t6]=3 [t8]=2 [t11]=4 [t12]=4) SVY=([t3]=2 [t5]=3 [t7]=3 [t4]=2 [t6]=2 [t8]=2 [t11]=3 [t12]=3)   # t3/t5 main_exp10, t7 t6t7_start.json
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
  for k in 1 2 3 4 5; do git add -f -- $fs >/dev/null 2>&1 && git commit -q -m "r73fill raw r$N (spec §4.141; raw data only)

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
  log "$1 START"; pcf_refresh; RETRY=""; RETRIED=""; consec=0
  for cell in $(awk -F'\t' -v ph="$1" '$2==ph && $8=="harness-fault"{print $4":"$3}' $LEDGER); do
    awk -F'\t' -v ph="$1-retry" -v c="$cell" '$2==ph && $4":"$3==c{f=1} END{exit !f}' $LEDGER && continue
    case " $RETRIED " in *" $cell "*) ;; *) RETRY="$RETRY $cell"; RETRIED="$RETRIED $cell"; log "RETRY-SEED $cell (from ledger)";; esac
  done
  for it in $2; do arm=${it%%:*}; rest=${it#*:}; B=${rest%%:*}; N=${rest#*:}; run_one $arm $B $N $1; done
  id=$3; for it in $RETRY; do arm=${it%%:*}; B=${it#*:}; log "RETRY $arm $B (harness-fault) as r$id"; run_one $arm $B $id $1-retry; id=$((id+1)); done
  log "$1 ALL DONE"
}
FLIST=${FLIST:-"S4p2:t5:582 S4p05:t7:583 S4p2:t3:584 B4A_375_300:t8:585 S4p2:t7:586 B6c5_h:t4:587 B6c5_h:t8:588 S4p2:t3:589 S4p05:t3:590 S4p2:t7:591 B4A_375_300:t8:592 S4p05:t5:593 S4p05:t7:594 B6c5_h:t8:595 S4p2:t3:596 B4A_375_300:t4:597 S4p05:t3:598 S4p2:t7:599 S4p05:t3:600 S4p05:t7:601 B4A_375_300:t4:602 B6c5_h:t4:603"}
# pre-flight: frozen files, image digest, idle field
MD5=$(cd /home/user/experiment/qsim && md5sum v8sim10.py v8sim10_abl.py v8sim11.py v8sim2.py v8sim_b6.py prior_traces.json | cut -c1-8 | tr '\n' ' ')
[ "$MD5" = "3daf1387 7a2b02ec ecdfff61 4697713c b24eae16 edb8e00c " ] || { log "STOP: frozen-file md5 mismatch: $MD5"; exit 1; }
DIG=$($M 'sudo ctr -n k8s.io images ls 2>/dev/null | grep "hhro-daemon:6.0-s4p " | grep -oE "sha256:[0-9a-f]{12}"' | head -1)
[ "$DIG" = "sha256:9f29a2fe8d93" ] || { log "STOP: 6.0-s4p digest on master = '$DIG' (expected sha256:9f29a2fe8d93)"; exit 1; }
log "pre-flight ok: md5 frozen, image $DIG"
pgrep -f "trace_run.py|run_chain.sh|run_queue2.sh|abl_queue_main2.sh" >/dev/null && { log "STOP: field busy"; exit 1; }
rm -f $P/s_exp.STOP
gate_probe p38
phase F "$FLIST" 604
gate_probe p39
log "F ALL DONE"
