#!/bin/bash
n=0
for p in /proc/[0-9]*; do
  pid=${p#/proc/}
  c=$(cat $p/comm 2>/dev/null) || continue
  case "$c" in vpp|vpp_main|vpp_wk*) continue;; esac
  al=$(grep -m1 Cpus_allowed_list $p/status 2>/dev/null | cut -f2)
  [ "$al" = "0" ] && continue
  taskset -a -pc 0 $pid >/dev/null 2>&1 && n=$((n+1))
done
for d in /proc/irq/[0-9]*; do
  l=$(cat $d/smp_affinity_list 2>/dev/null) || continue
  [ "$l" = "0" ] && continue
  echo 0 > $d/smp_affinity_list 2>/dev/null
done
echo "vyos-guest-isolate: moved=$n"
