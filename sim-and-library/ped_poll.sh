#!/bin/bash
OUT=${1:-$HOME/ped2026}; mkdir -p "$OUT"
URL='https://data.melbourne.vic.gov.au/api/explore/v2.1/catalog/datasets/pedestrian-counting-system-past-hour-counts-per-minute/exports/csv?delimiter=%2C&timezone=Australia%2FMelbourne&use_labels=false'
T0=$(date -u +%FT%TZ); L0=$(date '+%F %T')
F="$OUT/snap_$(date -u +%Y%m%dT%H%M%SZ).csv"
if curl -sS -m 180 -A 'ped-poll/1.0' -o "$F.part" "$URL" && [ -s "$F.part" ] && head -n 1 "$F.part" | grep -q location_id; then
  mv "$F.part" "$F"; echo "[$T0 .. $(date -u +%FT%TZ)] (local $L0 .. $(date '+%T')) ok $(wc -l < "$F") rows cpu=$(cat /proc/self/stat | awk '{print $14+$15+$16+$17}') ticks -> $F" >> "$OUT/poll.log"
else
  rm -f "$F.part"; echo "[$T0 .. $(date -u +%FT%TZ)] (local $L0 .. $(date '+%T')) FAIL" >> "$OUT/poll.log"; exit 1
fi
