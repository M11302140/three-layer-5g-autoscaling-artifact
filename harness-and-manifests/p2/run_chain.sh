#!/bin/bash
set -u
TAG=${1:?tag e.g. v7r52}; N=${TAG#v7}
pgrep -f '^bash postrun_cleanup\.sh' >/dev/null && { echo "postrun_cleanup still running — refuse"; exit 1; }
TRACE=${2:-trace_ue_60min_v3_40.json}
E=/home/user/experiment; P=$E/p2; cd $P
M="sshpass -p "$SSH_PASS" ssh -n -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR user@10.0.0.50"
H="sshpass -p "$SSH_PASS" ssh -n -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR rancher@10.0.0.193"
D=http://10.102.132.80:8080
echo "== run_chain $TAG $(date +%T)"
if [ "${3:-}" = "--resume" ]; then
  n_ue=$(ps -eo comm | grep -c "^nr-ue"); echo "resume: $n_ue nr-ue alive"
  [ "$n_ue" -lt 1 ] && { echo "nothing to resume"; exit 1; }
  [ "$($M "curl -s -m 5 $D/autoscale/status")" = '{"enabled":false}' ] || { echo "autoscale not off"; exit 1; }
  $H "pkill -f '^/bin/bash /tmp/vmcpu_sampler2'; sleep 1; setsid nohup /tmp/vmcpu_sampler2.sh /tmp/host_vmcpu_$TAG.csv >/dev/null 2>&1 </dev/null &" ; sleep 2
  for fp in $(ps -eo pid,comm,args | awk '$2=="ssh" && /logs -f deploy\/hhro-daemon/{print $1}'); do kill $fp 2>/dev/null; done
  setsid nohup bash -c "cd $E && exec sshpass -p "$SSH_PASS" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR user@10.0.0.50 'kubectl -n hhro-system logs -f deploy/hhro-daemon --since=1s'" > $P/${TAG}_daemon.log 2>&1 </dev/null &
  sleep 1
  setsid nohup bash -c "cd $E && exec taskset -c 13-14 env REAPERS=${REAPERS:-0} SECGW=1 HAIRPIN_STATIC=1 python3 trace_run.py $TRACE p2/trace_v7_$N.csv" > $P/trace_v7_$N.log 2>&1 </dev/null &
  sleep 30
  $M "curl -s -m 5 -X POST $D/autoscale/enable" > enable_$TAG.log 2>&1
  sleep 20
  echo "autoscale: $(cat enable_$TAG.log) / $($M "curl -s -m 5 $D/autoscale/status")"; head -3 trace_v7_$N.log
  ps -eo comm,args | grep -q '^python3.*trace_run\.py' && echo "LAUNCHED $TAG $(date +%T)" || { echo "trace_run not running"; exit 1; }
  exit 0
fi
if [ "${3:-}" != "--from-prep" ]; then
bash vf_guard.sh || { echo "VF-GUARD-FAIL"; exit 1; }
if [ "${3:-}" != "--resume" ] && [ "${SKIP_RSS_GATE:-0}" != "1" ]; then
  RSS=$(VYOS_IPS="4 5 6" timeout 60 bash seg_rss_probe.sh 2>&1 | grep -E "^vyos-[012] " | tr '\n' ' ')
  W1=$(echo "$RSS" | tr ' ' '\n' | grep -c "wk_1=[1-9][0-9][0-9]"); echo "RSS-GATE: $RSS → on wk_1: $W1/3"
  if [ "$W1" != "3" ]; then echo "RSS-GATE: not 3-on-wk_1 → seg_rss_target"; MAXROLL=8 bash seg_rss_target.sh 2>&1 | tail -2; RSS=$(VYOS_IPS="4 5 6" timeout 60 bash seg_rss_probe.sh 2>&1 | grep -E "^vyos-[012] " | tr '\n' ' '); W1=$(echo "$RSS" | tr ' ' '\n' | grep -c "wk_1=[1-9][0-9][0-9]"); echo "RSS-GATE(after): $RSS → on wk_1: $W1/3"; fi
  [ "$W1" != "3" ] && { echo "RSS-GATE-FAIL"; exit 1; }; echo "RSS-GATE-OK"
fi
if [ "${SKIP_PIN_GATE:-0}" != "1" ]; then bash /home/user/experiment/p2/pin_loop_gate.sh || { echo "PIN-LOOP-GATE-FAIL → 停"; exit 1; }; fi
for p in $(top -b -n 2 -d 2 2>/dev/null | awk 'p{print}/PID USER/{p=1}' | awk '$12 ~ /nr-gnb/ && $9>50 {print $1}' | sort -u); do echo "spinning gNB pid $p — kill (harness 起跑會重生)"; kill $p 2>/dev/null; done
# 0. host sampler
$H "pkill -f '^/bin/bash /tmp/vmcpu_sampler2'; sleep 1; setsid nohup /tmp/vmcpu_sampler2.sh /tmp/host_vmcpu_$TAG.csv >/dev/null 2>&1 </dev/null &" ; sleep 2
W0="sshpass -p "$SSH_PASS" ssh -n -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR user@10.0.0.52"
avail=$($W0 "free -m | awk '/^Mem:/{print \$7}'"); echo "worker-0 available MiB: $avail"
if [ "${avail:-0}" -lt 1500 ]; then
  echo "-- worker-0 記憶體不足,重啟 SCP → AMF 釋放"
  $M 'kubectl -n open5gs rollout restart deploy/open5gs-scp >/dev/null; kubectl -n open5gs rollout status deploy/open5gs-scp --timeout=120s >/dev/null; sleep 5; kubectl -n open5gs rollout restart deploy/open5gs-amf >/dev/null; kubectl -n open5gs rollout status deploy/open5gs-amf --timeout=120s >/dev/null'
  for i in $(seq 1 24); do n_amf=$($M "kubectl -n open5gs get pods --no-headers 2>/dev/null | grep -c '^open5gs-amf-'"); [ "$n_amf" = "1" ] && break; sleep 5; done; echo "amf pods: $n_amf"
  sleep 30; avail=$($W0 "free -m | awk '/^Mem:/{print \$7}'"); echo "worker-0 available MiB after restart: $avail"
  [ "${avail:-0}" -lt 1000 ] && { echo "worker-0 memory still low"; exit 1; }
fi
if [ "${SKIP_PCF_GATE:-0}" != "1" ]; then
  npool=$($M "kubectl -n open5gs logs deploy/open5gs-pcf --tail=50000 2>/dev/null | grep -c 'No memory in client_pool'")
  if [ "${npool:-0}" != "0" ]; then
    echo "-- PCF client_pool 已耗盡($npool 行)→ rollout restart PCF"
    $M 'kubectl -n open5gs rollout restart deploy/open5gs-pcf >/dev/null; kubectl -n open5gs rollout status deploy/open5gs-pcf --timeout=120s >/dev/null'
    for i in $(seq 1 24); do n_pcf=$($M "kubectl -n open5gs get pods --no-headers 2>/dev/null | grep -c '^open5gs-pcf-'"); [ "$n_pcf" = "1" ] && break; sleep 5; done
    sleep 10; echo "PCF-GATE: restarted (pods=$n_pcf)"
  else echo "PCF-GATE-OK"; fi
fi
want=$($M "kubectl -n hhro-system get deploy hhro-daemon -o jsonpath='{.spec.template.spec.containers[0].env[?(@.name==\"EUPF_IMAGE\")].value}'")
[ -z "$want" ] && { echo "cannot read EUPF_IMAGE from daemon deploy"; exit 1; }
bad=$($M "kubectl -n open5gs get pods --no-headers -o custom-columns=N:.metadata.name,I:.spec.containers[0].image | grep eupf | grep -vc '$want'")
[ "${bad:-0}" != "0" ] && { echo "eupf pods not on $want:"; $M "kubectl -n open5gs get pods -o custom-columns=N:.metadata.name,I:.spec.containers[0].image | grep eupf"; exit 1; }
# 1. workers → 4
nw=$($M 'kubectl get nodes --no-headers | grep -cE "^worker-[0-9]+ +Ready"')
if [ "$nw" -lt 4 ]; then
  NEW=""
  for i in $(seq $nw 3); do r=$($M "curl -s -m 120 -X POST '$D/scale/worker/up?force=true'"); echo "$r"; NEW="$NEW $(echo "$r" | grep -o 'worker-[0-9]*')"; sleep 3; done
  for i in $(seq 1 60); do n=$($M 'kubectl get nodes --no-headers | grep -cE "^worker-[0-9]+ +Ready"'); [ "$n" = "4" ] && break; sleep 5; done
  [ "$n" != "4" ] && { echo "workers not Ready: $n"; exit 1; }
  for w in $NEW; do echo "-- provision $w"; $M "curl -s -m 600 -X POST '$D/provision/worker?node=$w'"; echo; done
fi
tag=${want##*:}
for w in 0 1 2 3; do
  ip=$((52+w)); [ $w = 0 ] && ip=52; [ $w = 1 ] && ip=54; [ $w = 2 ] && ip=55; [ $w = 3 ] && ip=56
  WS="sshpass -p "$SSH_PASS" ssh -n -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10 -o LogLevel=ERROR user@10.0.0.$ip"
  ok=$($WS "echo "$SUDO_PASS" | sudo -S -p '' bash -c '[ -x /usr/local/sbin/eupf-vf-provision.sh ] && ctr -n k8s.io images ls -q 2>/dev/null | grep -q \"$tag\" && echo ok'" 2>/dev/null)
  if [ "$ok" != "ok" ]; then
    echo "-- worker-$w 未 provision(script/image 缺)→ POST /provision/worker"; $M "curl -s -m 600 -X POST '$D/provision/worker?node=worker-$w'"; echo
    ok=$($WS "echo "$SUDO_PASS" | sudo -S -p '' bash -c '[ -x /usr/local/sbin/eupf-vf-provision.sh ] && ctr -n k8s.io images ls -q 2>/dev/null | grep -q \"$tag\" && echo ok'" 2>/dev/null)
    [ "$ok" != "ok" ] && { echo "worker-$w provision still incomplete"; exit 1; }
  fi
done
echo "WORKER-PROVISION-OK"
if [ "${SKIP_COALESCE_GATE:-0}" != "1" ]; then bash /home/user/experiment/p2/vf_coalesce_all.sh check | tee -a /dev/stderr | grep -q DIFF && { echo "VF-COALESCE-GATE-FAIL → 停"; exit 1; }; echo "VF-COALESCE-GATE-OK"; fi
NV=1; [ "${STATIC_FLEET:-0}" = "1" ] && NV=${STATIC_NV:-3}; [ "${KEEP_VYOS:-0}" = "1" ] && NV=3
bash prep_field.sh $NV 1 > prep_$TAG.log 2>&1
if ! grep -q "BRINGUP DONE" prep_$TAG.log && grep -q "抗性孤兒" prep_$TAG.log; then
  echo "prep: resistant orphan sessions — running ddance.sh once"; bash ddance.sh > ddance_$TAG.log 2>&1; tail -1 ddance_$TAG.log
  grep -q "DDANCE-OK" ddance_$TAG.log && bash prep_field.sh $NV 1 > prep_$TAG.log 2>&1
fi
grep -q "BRINGUP DONE" prep_$TAG.log || { echo "PREP FAILED"; cat prep_$TAG.log; exit 1; }
fi
for cfg in $(ps -eo args | grep "nr-ue.real" | grep -oE "mue-[0-9]+\.yaml" | sort | uniq -d); do
  for pid in $(ps -eo pid,etimes,args | grep "nr-ue.real" | grep "$cfg" | grep -v grep | sort -k2 -nr | awk 'NR>1{print $1}'); do
    pp=$(ps -o ppid= -p $pid); ppp=$(ps -o ppid= -p $pp 2>/dev/null); echo "dup $cfg: kill old $pid"; echo "$SUDO_PASS" | sudo -S -p '' kill -9 $pid $pp $ppp 2>/dev/null; done
done
[ "$(ps -eo comm | grep -c '^nr-ue')" = "40" ] || { echo "nr-ue count != 40"; exit 1; }
bash xdp_guard.sh || exit 1
[ "${3:-}" = "--prep-only" ] && { echo "PREP-ONLY DONE $TAG $(date +%T)"; exit 0; }
if [ "${STATIC_FLEET:-0}" = "1" ]; then
  bash park_static.sh > park_$TAG.log 2>&1
  grep -q "PARK-STATIC-OK" park_$TAG.log || { echo "PARK-STATIC FAILED"; tail -5 park_$TAG.log; exit 1; }
else
  bash park_to_base.sh > park_$TAG.log 2>&1
  grep -q "PARK-BASE-OK" park_$TAG.log || { echo "PARK FAILED"; tail -5 park_$TAG.log; exit 1; }
fi
$M "curl -s -m 120 -X POST $D/host/vfio-pin" >/dev/null
for i in $(seq 1 18); do python3 -c "import json,sys; u=json.load(open('/tmp/uemap.json')); m=json.load(open('/tmp/m32.json')); sys.exit(0 if not u['assign'] and not m else 1)" && break; sleep 5; done
python3 -c "import json,sys; u=json.load(open('/tmp/uemap.json')); m=json.load(open('/tmp/m32.json')); sys.exit(0 if not u['assign'] and not m else 1)" || { echo "state files not zeroed"; exit 1; }
curl -s -m 3 localhost:9801/status | grep -q pending_releases || { echo "rehome agent down"; exit 1; }
[ "$($M "curl -s -m 5 $D/autoscale/status")" = '{"enabled":false}' ] || { echo "autoscale not off"; exit 1; }
for fp in $(ps -eo pid,comm,args | awk '$2=="ssh" && /logs -f deploy\/hhro-daemon/{print $1}'); do kill $fp 2>/dev/null; done
setsid nohup bash -c "cd $E && exec sshpass -p "$SSH_PASS" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR user@10.0.0.50 'kubectl -n hhro-system logs -f deploy/hhro-daemon --since=1s'" > $P/${TAG}_daemon.log 2>&1 </dev/null &
sleep 1
setsid nohup bash -c "cd $E && exec taskset -c 13-14 env REAPERS=${REAPERS:-0} SECGW=1 HAIRPIN_STATIC=1 python3 trace_run.py $TRACE p2/trace_v7_$N.csv" > $P/trace_v7_$N.log 2>&1 </dev/null &
sleep 30
$M "curl -s -m 5 -X POST $D/autoscale/enable" > enable_$TAG.log 2>&1
sleep 20
echo "autoscale: $(cat enable_$TAG.log) / $($M "curl -s -m 5 $D/autoscale/status")"; head -2 trace_v7_$N.log
ps -eo comm,args | grep -q '^python3.*trace_run\.py' && echo "LAUNCHED $TAG $(date +%T)" || { echo "trace_run not running"; exit 1; }
