#!/bin/bash
P=/home/user/experiment/p2; cd $P
M="sshpass -p "$SSH_PASS" ssh -n -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR user@10.0.0.50"
declare -A SREP=([t4]=5 [t5]=8 [t3]=6 [t8]=4) SWK=([t4]=3 [t5]=4 [t3]=3 [t8]=2) SVY=([t4]=2 [t5]=3 [t3]=2 [t8]=2)
if [ -f $P/t6t7_start.json ]; then for b in t6 t7; do read rep wk vy < <(python3 -c 'import json,sys; d=json.load(open(sys.argv[1]))[sys.argv[2]]; print(d["rep"], d["wk"], d["vy"])' $P/t6t7_start.json $b); SREP[$b]=$rep; SWK[$b]=$wk; SVY[$b]=$vy; done; fi
LEDGER=$P/a_ledger.tsv; [ -f $LEDGER ] || echo -e "run\tblock\tarm\tslo\tburned\tflags\ttime" > $LEDGER
consec=0
log(){ echo "[$(date '+%F %T')] $*"; }
check_platform(){   # $1=run id(rNNN) $2=block
  local N=$1; local B=$2; local f=""; local l=${B}_v7$N.log
  grep -qE "workers not Ready|STALL|never converged|chain failed|prep abort" $l chain_v7${N}*.log 2>/dev/null && f="$f chain-abort"
  grep -q "FINISH rc=0" $l 2>/dev/null || f="$f no-finish"
  grep -qE "panic:|fatal error" v7${N}_daemon.log 2>/dev/null && f="$f daemon-panic"
  grep -q "NG dead by log marker" trace_v7_${N}.log 2>/dev/null && f="$f ng-dead"
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
record(){
  local arm=$1 B=$2 N=$3
  local slo=$(grep -oE "SLO\(loss<=0.1% & p99<=1ms\): [0-9]+/60" finish_v7r$N.log 2>/dev/null | grep -oE "[0-9]+/60"); local burned=$(grep -oE "TOTAL=[0-9]+" finish_v7r$N.log 2>/dev/null | cut -d= -f2)
  local flags=$(check_platform r$N $B)
  echo -e "r$N\t$B\t$arm\t${slo:-?}\t${burned:-?}\t${flags:-ok}\t$(date '+%F %T')" >> $LEDGER
  log "DONE r$N $B $arm slo=${slo:-?} burned=${burned:-?} flags=${flags:-ok}"
  if [ -n "$flags" ]; then consec=$((consec+1)); RETRY="$RETRY $arm:$B"; else consec=0; fi
  case " $flags " in *" start-transient "*|*" chain-abort "*) log "STOP (§4.81 t7 condition 3): $flags in r$N — report before continuing"; touch $P/a_exp.STOP; exit 1;; esac
  if [ $consec -ge 2 ]; then log "STOP: two consecutive platform-flagged runs ($flags) — diagnose before continuing"; touch $P/a_exp.STOP; exit 1; fi
}
pcf_refresh(){
  log "PCF-REFRESH: rollout restart open5gs-pcf"; $M 'kubectl -n open5gs rollout restart deploy/open5gs-pcf >/dev/null; kubectl -n open5gs rollout status deploy/open5gs-pcf --timeout=120s >/dev/null' ; sleep 15
}
fleet_guard(){
  local extra=$($M 'kubectl get nodes --no-headers | grep -oE "^worker-[4-9]"' 2>/dev/null)
  for w in $extra; do log "FLEET-GUARD: deleting extra $w"; $M "curl -s -m 120 -X POST 'http://10.102.132.80:8080/scale/worker/down?name=$w&force=true'" >/dev/null; sleep 15; done
}
run_one(){   # $1=arm $2=block $3=run id
  local arm=$1 B=$2 N=$3
  grep -qP "^r$N\t" $LEDGER && { log "SKIP r$N (in ledger)"; return; }
  case ",${SKIP_ARMS:-}," in *,$arm,*) log "SKIP r$N $B $arm (SKIP_ARMS; id reserved)"; return;; esac
  fleet_guard
  [ -f $P/a_exp.STOP ] && { log "STOP file present — exiting before $arm:$B:r$N"; exit 2; }
  log "RUN r$N $B $arm"
  if [[ $arm == S* ]]; then MAIN_WARMIN=trace_warmin_$B.json MAIN_START_REP=${SREP[$B]} MAIN_START_WK=${SWK[$B]} MAIN_START_VY=${SVY[$B]} bash abl_queue_main.sh "$arm:$B:r$N" >> main_exp_queue.log 2>&1
  else bash abl_queue_main.sh "$arm:$B:r$N" >> main_exp_queue.log 2>&1; fi
  record $arm $B $N
}
probe(){ log "PROBE $1"; bash field_probe.sh $1 2>&1 | tee -a field_probe_results.log | grep -E "^PROBE" | tail -1; }
probe(){ log "PROBE $1"; bash field_probe.sh $1 2>&1 | tee -a field_probe_results.log | grep -E "^PROBE" | tail -1; }
LIST=${LIST:-"S4b:t4:520 B5c1_slo:t4:521 S4b:t4:522 B5c1_slo:t4:523 S4b:t4:524 B5c1_slo:t4:525"}
[ "${OPTIONAL:-0}" = "1" ] && LIST="$LIST S4a:t4:526 B6c4_slo:t4:527"
grep -q "PROBE p33 " field_probe_results.log || probe p33
r=$(grep -E "^PROBE p33 " field_probe_results.log | tail -1); log "pre-probe: $r"
echo "$r" | awk '{exit !($10+0<=0.05 && $8+0<=450)}' || { log "STOP: pre-probe p33 not clean (e2e>0.05 or p99>450)"; touch $P/a_exp.STOP; exit 1; }
log "A START"; pcf_refresh; RETRY=""
for it in $LIST; do arm=${it%%:*}; rest=${it#*:}; B=${rest%%:*}; N=${rest#*:}; run_one $arm $B $N; done
id=528; for it in $RETRY; do arm=${it%%:*}; B=${it#*:}; log "RETRY $arm $B (platform-flagged) as r$id"; run_one $arm $B $id; id=$((id+1)); done
grep -q "PROBE p34 " field_probe_results.log || probe p34
log "A ALL DONE"
