#!/bin/bash
N=${1:?e.g. r67}; P=/home/user/experiment/p2; cd $P
wait_done(){ # $1=trace log
  local t0=$(date +%s)
  while :; do
    sleep 30
    grep -q "TRACE-RUN-DONE" "$1" && { echo "DONE $1 $(date +%T)"; return 0; }
    local age=$(( $(date +%s) - $(stat -c %Y "$1") ))
    [ $age -gt 360 ] && { echo "STALL $1 age=${age}s $(date +%T)"; return 1; }
    [ $(( $(date +%s) - t0 )) -gt 5400 ] && { echo "TIMEOUT $1"; return 1; }
    ps -eo comm,args | grep -q '^python3.*trace_run\.py' || { echo "harness gone $1 $(date +%T)"; return 1; }
  done
}
tail_loss(){ tail -30 "$1" | awk -F, '{s+=$6;n++} END{if(n) printf "%.3f", s/n; else print "nan"}'; }
echo "== trace2 $N $(date +%T)"
WARM=trace_warmin_pm5.json; [ "${STATIC_FLEET:-0}" = "1" ] && WARM=trace_warmin_static.json; [ -n "${WARMIN_TRACE:-}" ] && WARM=$WARMIN_TRACE
if [ "${2:-}" = "--from-warmin" ]; then echo "adopting running warm-in v7${N}w"; else
REAPERS=${WARMIN_REAP:-0} bash run_chain.sh v7${N}w $WARM > chain_v7${N}w.log 2>&1 || { echo "warm-in chain failed"; tail -5 chain_v7${N}w.log; exit 1; }
tail -1 chain_v7${N}w.log
fi
wait_done trace_v7_${N}w.log || exit 1
tail -2 trace_v7_${N}w.log
WL=$(tail_loss trace_v7_${N}w_1s.csv); echo "warm-in tail30 loss=${WL}%"
k=2
while [ "$(awk -v x="$WL" 'BEGIN{print (x>0.1)?1:0}')" = "1" ] && [ $k -le 3 ]; do
  sleep 15
  REAPERS=${WARMIN_REAP:-0} bash run_chain.sh v7${N}w${k} $WARM --resume > chain_v7${N}w${k}.log 2>&1 || { echo "warm-in $k chain failed"; tail -5 chain_v7${N}w${k}.log; exit 1; }
  tail -1 chain_v7${N}w${k}.log
  wait_done trace_v7_${N}w${k}.log || exit 1
  WL=$(tail_loss trace_v7_${N}w${k}_1s.csv); echo "warm-in $k tail30 loss=${WL}%"; k=$((k+1))
done
[ "$(awk -v x="$WL" 'BEGIN{print (x>0.1)?1:0}')" = "1" ] && { echo "warm-in never converged (${WL}%)"; exit 1; }
FLEET=$(sshpass -p "$SSH_PASS" ssh -n -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR user@10.0.0.50 "curl -s -m 5 10.102.132.80:8080/state" | python3 -c "import sys,json; d=json.load(sys.stdin); m=d['mid']; print('rep',m['G_up']['rep'],'vy',m['V']['count_v'],'wk',m['W']['n_w'])" 2>/dev/null); echo "warm-in fleet: $FLEET"; [ "$FLEET" = "rep 6 vy 2 wk 3" ] || echo "WARN warm-in fleet not (6,2,3) — 09-22 r111w: 7→6 hold 12 min → worker 刪除來不及"
if [ -n "${START_REP:-}${START_WK:-}${START_VY:-}" ]; then
  [ -n "${START_REP:-}" ] && export START_VY=${START_VY:-2}
  bash /home/user/experiment/p2/align_fleet.sh || { echo "align_fleet failed"; exit 1; }
  sleep 30
fi
sleep 15
bash /home/user/experiment/p2/session_gate.sh 2>&1 | tee -a chain_v7${N}.gate.log | tail -3; [ "${PIPESTATUS[0]}" = 0 ] || { echo "SESSION-GATE-FAIL (r34b) — not launching formal segment"; exit 1; }
bash run_chain.sh v7${N} ${FORMAL_TRACE:-trace_ue_60min_v3_pm.json} --resume > chain_v7${N}.log 2>&1 || { echo "resume chain failed"; tail -5 chain_v7${N}.log; exit 1; }
tail -1 chain_v7${N}.log
wait_done trace_v7_${N}.log || exit 1
sleep 20
bash run_finish.sh v7${N} > finish_v7${N}.log 2>&1; echo "FINISH rc=$? $(date +%T)"
grep -A8 "^== trace_v7" finish_v7${N}.log | head -12
