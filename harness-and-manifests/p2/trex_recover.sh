#!/bin/bash
set -u; P=/home/user/experiment/p2; L=$P/main_exp.log
log(){ echo "[$(date '+%F %T')] TREX-RECOVER: $*" | tee -a $L; }
cp /tmp/trex_win.log $P/trex_win_died_$(date +%m%d_%H%M).log 2>/dev/null
cd /home/user/trex/v3.08 && echo "$SUDO_PASS" | sudo -S bash -c '[ -d /sys/fs/cgroup/dataplane.slice ] && echo $$ > /sys/fs/cgroup/dataplane.slice/cgroup.procs; pkill -x _t-rex-64; sleep 2; rm -f /tmp/trex_win.log; LD_LIBRARY_PATH=/home/user/trex/v3.08 nohup setsid ./_t-rex-64 -i --no-scapy-server --no-watchdog > /tmp/trex_win.log 2>&1 &' 2>/dev/null
for i in $(seq 1 30); do grep -q "Starting  TRex" /tmp/trex_win.log 2>/dev/null && break; sleep 2; done; sleep 15
cd $P && echo "$SUDO_PASS" | sudo -S ./seg_vhost.sh --pin 2>&1 | tail -n 1
NR=/home/user/UERANSIM/build/nr-cli; for i in $(seq 0 39); do imsi=$(printf 'imsi-%015d' $((999700000000001+i))); timeout 6 $NR "$imsi" -e 'deregister switch-off' >/dev/null 2>&1 & done; wait; sleep 5
echo "$SUDO_PASS" | sudo -S pkill -x nr-ue.real 2>/dev/null; pkill -x nr-gnb.real 2>/dev/null; sleep 5
M="sshpass -p "$SSH_PASS" ssh -n -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o ConnectTimeout=8 user@10.0.0.50"
sleep 25; cnt=$($M 'kubectl -n open5gs logs deploy/open5gs-amf --since=2m 2>/dev/null | grep -oE "Number of gNBs is now [0-9]+" | tail -n 1')
(echo > /dev/tcp/127.0.0.1/4501) 2>/dev/null && ok=open || ok=CLOSED
log "trex 4501 $ok; $(grep -E 'HugePages_Free' /proc/meminfo | tr -s ' '); nr-gnb=$(ps -eo comm | grep -c '^nr-gnb') nr-ue=$(ps -eo comm | grep -c '^nr-ue'); AMF: ${cnt:-n/a}"
