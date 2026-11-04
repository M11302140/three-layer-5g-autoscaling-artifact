#!/bin/bash
# deploy_daemon.sh TAG  — import p2/hhro-TAG.tar on master+worker-0, apply manifest, rollout, show status
set -u; TAG=$1; T=/home/user/experiment/p2/hhro-$TAG.tar; [ -f "$T" ] || { echo "no $T"; exit 1; }
grep -q "hhro-daemon:6.0-$TAG" /home/user/hhro-daemon/deploy/manifest.yaml || { echo "manifest tag != $TAG"; exit 1; }
O="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR"
for h in 10.0.0.50 10.0.0.52; do
  sshpass -p "$SSH_PASS" scp $O $T user@$h:/tmp/hhro-$TAG.tar && sshpass -p "$SSH_PASS" ssh -n $O user@$h "echo "$SUDO_PASS" | sudo -S -p '' ctr -n k8s.io images import /tmp/hhro-$TAG.tar >/dev/null 2>&1; echo -n '$h imported: '; echo "$SUDO_PASS" | sudo -S -p '' ctr -n k8s.io images ls -q | grep -c 6.0-$TAG"
done
sshpass -p "$SSH_PASS" scp $O /home/user/hhro-daemon/deploy/manifest.yaml user@10.0.0.50:/tmp/hhro-manifest-$TAG.yaml
sshpass -p "$SSH_PASS" ssh -n $O user@10.0.0.50 "kubectl apply -f /tmp/hhro-manifest-$TAG.yaml 2>&1 | grep deployment; kubectl -n hhro-system rollout status deploy/hhro-daemon --timeout=180s | tail -1; sleep 8; kubectl -n hhro-system get pods -o custom-columns=IMG:.spec.containers[0].image,ST:.status.phase --no-headers; curl -s -m 5 http://10.102.132.80:8080/autoscale/status"; echo
