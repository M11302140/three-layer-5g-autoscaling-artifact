#!/bin/bash
P=/home/user/experiment/p2; D=/home/user/hhro-daemon/deploy; cd $P
M="sshpass -p "$SSH_PASS" ssh -n -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR user@10.0.0.50"
apply(){ sshpass -p "$SSH_PASS" scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR "$1" user@10.0.0.50:/tmp/abl.yaml && $M "kubectl apply -f /tmp/abl.yaml | grep deployment; kubectl -n hhro-system rollout status deploy/hhro-daemon --timeout=180s | tail -1; sleep 5; kubectl -n hhro-system get pods -o custom-columns=IMG:.spec.containers[0].image --no-headers | head -1; curl -s -m 5 http://10.102.132.80:8080/autoscale/status"; echo; }
for item in $1; do
  v=${item%%:*}; runs=${item#*:}
  echo "== ablation $v $(date +%T)"; if [ "$v" = "HHRO" ]; then apply $D/manifest.yaml; else apply $D/ablation/$v.yaml; fi   # 09-28 HHRO=base manifest
  q=$(echo "$runs" | tr ',' '\n' | sed -E 's/^(t[0-9]+:)?/\1/; /^t[0-9]+:/! s/^/t1:/' | paste -sd' ')
  export STATIC_FLEET=0 STATIC_NV=3 KEEP_VYOS=0 WARMIN_REAP=0
  case "$v" in B*|Q*|S*) export WARMIN_REAP=1;; esac
  export WARMIN_TRACE=""
  case "$v" in B1_*) export STATIC_FLEET=1 STATIC_NV=3;; B2_*) export STATIC_FLEET=1 STATIC_NV=1;; B3_*) export KEEP_VYOS=1;; B3t2_*) export STATIC_FLEET=1 STATIC_NV=3 WARMIN_TRACE=trace_warmin_b3.json;; esac
  unset START_REP START_WK START_VY; case "$v" in S*) export WARMIN_TRACE=${MAIN_WARMIN:-trace_warmin_pm6.json} START_REP=${MAIN_START_REP:-6} START_WK=${MAIN_START_WK:-3} START_VY=${MAIN_START_VY:-2};; esac
  KEEP_GOING=1 bash run_queue2.sh "$q"
  echo "== ablation $v done $(date +%T)"
done
echo "== restore base manifest $(date +%T)"; apply $D/manifest.yaml
echo "== ABLATION ALL DONE $(date +%T)"
