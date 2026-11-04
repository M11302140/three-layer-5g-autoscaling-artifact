#!/bin/bash
set -u
M="sshpass -p "$SSH_PASS" ssh -n -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR user@10.0.0.50"
D=10.102.132.80:8080
st(){ $M "curl -s -m 5 $D/state" | python3 -c "import sys,json; m=json.load(sys.stdin)['mid']; print(m['G_up']['rep'], m['V']['count_v'], m['W']['n_w'], m['W'].get('idle_worker') or '')" 2>/dev/null; }
pods(){ $M "kubectl -n open5gs get pods -o custom-columns=NAME:.metadata.name,NODE:.spec.nodeName,PHASE:.status.phase --no-headers 2>/dev/null" | awk '$1 ~ /^eupf-/ && $3=="Running" {print $1, $2}'; }
read -r REP VY NW IDLE <<<"$(st)"; echo "align_fleet: now rep $REP vy $VY wk $NW idle=[$IDLE] target rep ${START_REP:-} wk ${START_WK:-} vy ${START_VY:-} $(date +%T)"
if [ -n "${START_REP:-}" ]; then
  while [ -n "$REP" ] && [ "$REP" -gt "$START_REP" ]; do
    # victim = a slot on the non-worker-0 worker with the fewest slots
    if [ -n "${VW:-}" ] && pods | awk -v w="$VW" '$2==w{f=1} END{exit !f}'; then V=$(pods | awk -v w="$VW" '$2==w{print $1; exit}');
    else VW=$(pods | awk '$2!="worker-0" && $2!="" {c[$2]++} END{best=""; for(w in c) if(best=="" || c[w]<c[best]) best=w; print best}'); V=$(pods | awk -v w="$VW" '$2==w{print $1; exit}'); fi
    [ -z "$V" ] && { echo "align_fleet: no drainable slot found"; break; }
    echo "align_fleet: drain $V: $($M "curl -s -m 10 -X POST '$D/scale/upf/down?name=$V&drain=true'")"
    for i in $(seq 1 36); do sleep 10; read -r R2 _ _ _ <<<"$(st)"; [ -n "$R2" ] && [ "$R2" -lt "$REP" ] && break; done
    read -r REP VY NW IDLE <<<"$(st)"; echo "align_fleet: rep now $REP $(date +%T)"
    [ "$i" -ge 36 ] && { echo "align_fleet: drain timeout"; exit 1; }
  done
fi
if [ -n "${START_WK:-}" ]; then
  for i in $(seq 1 12); do read -r REP VY NW IDLE <<<"$(st)"; { [ -n "$IDLE" ] || [ "$NW" -le "$START_WK" ]; } && break; sleep 10; done
  while [ -n "$NW" ] && [ "$NW" -gt "$START_WK" ] && [ -n "$IDLE" ]; do
    echo "align_fleet: delete idle worker $IDLE: $($M "curl -s -m 30 -X POST '$D/scale/worker/down?name=$IDLE'")"
    for i in $(seq 1 24); do sleep 10; read -r _ _ NW2 _ <<<"$(st)"; [ -n "$NW2" ] && [ "$NW2" -lt "$NW" ] && break; done
    for i in $(seq 1 12); do read -r REP VY NW IDLE <<<"$(st)"; { [ -n "$IDLE" ] || [ "$NW" -le "$START_WK" ]; } && break; sleep 10; done
    echo "align_fleet: workers now $NW idle=[$IDLE] $(date +%T)"
  done
  [ -n "$NW" ] && [ "$NW" -gt "$START_WK" ] && echo "align_fleet: no idle worker (n_w=$NW) — continuing as is"
fi
if [ -n "${START_VY:-}" ]; then
  while [ -n "$VY" ] && [ "$VY" -gt "$START_VY" ]; do
    N=$(( VY - 1 )); echo "align_fleet: delete vyos-$N (drain): $($M "curl -s -m 30 -X POST '$D/scale/vyos/down?name=vyos-$N&drain=true'")"
    for i in $(seq 1 30); do sleep 10; read -r _ V2 _ _ <<<"$(st)"; [ -n "$V2" ] && [ "$V2" -lt "$VY" ] && break; done
    read -r REP VY NW IDLE <<<"$(st)"; echo "align_fleet: vyos now $VY $(date +%T)"
    [ "$i" -ge 30 ] && { echo "align_fleet: vyos delete timeout"; break; }
  done
fi
echo "align_fleet: start fleet rep $REP vy $VY wk $NW $(date +%T)"
