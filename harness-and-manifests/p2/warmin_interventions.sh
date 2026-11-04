#!/bin/bash
L=/home/user/experiment/p2/main_exp.log; B=${1:-t6}; LEDGER=/home/user/experiment/p2/main_exp_ledger.tsv
printf "%-6s %-10s %-6s %-5s %-6s %s\n" run arm slo ints ues "times (UE ids)"
awk -F'\t' -v b="$B" '$2==b {print $1, $3, $4}' $LEDGER | while read -r r arm slo; do
  lines=$(grep -E "PLATFORM:.*during ${r}w: ([0-9 ]+$|switch-off\+gNB-kill on \[)" $L); n=$(echo "$lines" | grep -c "PLATFORM" ); ues=0; det=""
  if [ "$n" != "0" ]; then while IFS= read -r l; do ids=$(echo "$l" | sed -E 's/.*during [a-z0-9]+w: //; s/switch-off\+gNB-kill on \[([0-9 ]*)\].*/\1/'); k=$(echo "$ids" | wc -w); ues=$((ues+k)); det="$det $(echo "$l" | cut -c13-17)[$k:$(echo $ids)]"; done <<< "$lines"; fi
  notes=$(grep -cE "PLATFORM:.*during ${r}w" $L); extra=$((notes-n)); [ $extra -gt 0 ] && det="$det (+$extra note line)"
  printf "%-6s %-10s %-6s %-5s %-6s %s\n" "$r" "$arm" "$slo" "$n" "$ues" "$det"
done
