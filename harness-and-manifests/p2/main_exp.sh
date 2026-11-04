#!/bin/bash
P=/home/user/experiment/p2; cd $P
M="sshpass -p "$SSH_PASS" ssh -n -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR user@10.0.0.50"
ARMS=(S4a HHRO B4c2_slo S4b B5c1_slo B6c4_slo)
BLOCKS=${BLOCKS:-"t4 t5 t3"}
declare -A BASE=([t4]=300 [t5]=330 [t3]=360)
declare -A PROBE=([t4]=p16 [t5]=p17 [t3]=p18)
declare -A SREP=([t4]=5 [t5]=8 [t3]=6) SWK=([t4]=3 [t5]=4 [t3]=3) SVY=([t4]=2 [t5]=3 [t3]=2)
LEDGER=$P/main_exp_ledger.tsv; [ -f $LEDGER ] || echo -e "run\tblock\tarm\tslo\tburned\tflags\ttime" > $LEDGER
consec=0
log(){ echo "[$(date '+%F %T')] $*"; }
check_platform(){
  local N=$1 B=$2 f="" l=${B}_v7$N.log
  grep -qE "workers not Ready|STALL|never converged|chain failed|prep abort" $l chain_v7${N}*.log 2>/dev/null && f="$f chain-abort"
  grep -q "FINISH rc=0" $l 2>/dev/null || f="$f no-finish"
  grep -qE "panic:|fatal error" v7${N}_daemon.log 2>/dev/null && f="$f daemon-panic"
  python3 - "$N" <<'PY' 2>/dev/null
import csv,sys
try:
    rows=list(csv.DictReader(open(f'/home/user/experiment/p2/trace_v7_{sys.argv[1]}.csv')))
except Exception: sys.exit(0)
w=max(int(r.get('worker_n') or 0) for r in rows); 
if w>4: print(' workers>4')
if rows and float(rows[0]['e2e_pct'] or 0)>1.0: print(' start-transient')
PY
  echo "$f"
}
run_one(){
  local arm=$1 B=$2 N=$3
  [ -f $P/main_exp.STOP ] && { log "STOP file present — exiting before $arm:$B:r$N"; exit 2; }
  log "RUN r$N $B $arm"
  if [[ $arm == S* ]]; then MAIN_WARMIN=trace_warmin_$B.json MAIN_START_REP=${SREP[$B]} MAIN_START_WK=${SWK[$B]} MAIN_START_VY=${SVY[$B]} bash abl_queue_main.sh "$arm:$B:r$N" >> main_exp_queue.log 2>&1
  else bash abl_queue_main.sh "$arm:$B:r$N" >> main_exp_queue.log 2>&1; fi
  local slo=$(grep -oE "SLO\(loss<=0.1% & p99<=1ms\): [0-9]+/60" finish_v7r$N.log 2>/dev/null | grep -oE "[0-9]+/60"); local burned=$(grep -oE "TOTAL=[0-9]+" finish_v7r$N.log 2>/dev/null | cut -d= -f2)
  local flags=$(check_platform r$N $B | xargs); flags=$(echo "$flags" | xargs)
  echo -e "r$N\t$B\t$arm\t${slo:-?}\t${burned:-?}\t${flags:-ok}\t$(date '+%F %T')" >> $LEDGER
  log "DONE r$N $B $arm slo=${slo:-?} burned=${burned:-?} flags=${flags:-ok}"
  if [ -n "$flags" ]; then consec=$((consec+1)); RETRY="$RETRY $arm"; else consec=0; fi
  if [ $consec -ge 2 ]; then log "STOP: two consecutive platform-flagged runs ($flags) — diagnose before continuing"; touch $P/main_exp.STOP; exit 1; fi
}
probe(){ log "PROBE $1"; bash field_probe.sh $1 2>&1 | tee -a field_probe_results.log | grep -E "^PROBE" | tail -1; }
probe p15
for B in $BLOCKS; do
  log "BLOCK $B START"; id=${BASE[$B]}; RETRY=""
  for round in 1 2 3; do
    for k in 0 1 2 3 4 5; do arm=${ARMS[$(( (round-1+k) % 6 ))]}; run_one $arm $B $id; id=$((id+1)); done
    [ $round = 1 ] && { run_one B1_static $B $id; id=$((id+1)); }
  done
  for arm in $RETRY; do log "RETRY $arm (platform-flagged earlier)"; run_one $arm $B $id; id=$((id+1)); done
  log "BLOCK $B DONE (next id $id)"; probe ${PROBE[$B]}
done
log "MAIN EXPERIMENT ALL DONE"
