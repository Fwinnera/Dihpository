#!/bin/bash
# labrun.sh BOT ARM "NOTE": cloud copy of analysis/rebuild/labrun.sh. Take the README ladder lock first.
# Uploads ws/bots/BOT, waits for it to go live, pins it, queues lab sets 1-3 against the opponents pinned by
# v166's recovered arms (ARM --from pm_best, ARM_s2 --from pm_best_s2, ARM_s3 --from pm_best_s3), waits for
# all 150 games and prints the results next to pm_best's (73 of 150). It does not re-pin anything.
set -u
bot=$1; arm=$2; note=$3
root=/home/user/repo
cambc=/home/user/.venv-cambc/bin/cambc
export SSL_CERT_FILE=/root/.ccr/ca-bundle.crt
cd "$root/ws" || exit 1
[ -e "$root/ws/bench/lab/$arm.json" ] && { echo "arm $arm exists"; exit 1; }
[ ${#note} -le 80 ] || { echo "note longer than 80 characters"; exit 1; }
out=""
for i in 1 2 3 4; do
  out=$("$cambc" submit "bots/$bot" -n "$note" 2>&1)
  echo "$out" | tail -1
  echo "$out" | grep -q 'Submitted bot version' && break
  echo "$out" | grep -qi 'frozen' && exit 2
  sleep 10
done
ver=$(echo "$out" | sed -n 's/.*Submitted bot version \([0-9]*\).*/\1/p')
[ -n "$ver" ] || { echo "no version"; exit 1; }
echo "$(date -u +%H:%M:%SZ) submitted v$ver"
for i in $(seq 1 120); do
  st=$("$cambc" submissions list 2>&1)
  echo "$st" | grep -q "Live: $ver " && break
  echo "$st" | grep -E "^v$ver " | grep -qi 'fail\|error\|cancel' && { echo "v$ver failed to build"; exit 1; }
  sleep 20
done
echo "$st" | grep -q "Live: $ver " || { echo "v$ver not live after 40 min"; exit 1; }
"$cambc" submissions activate "$ver" > /dev/null 2>&1
echo "$(date -u +%H:%M:%SZ) v$ver live and pinned"
"$cambc" submissions list 2>&1 | sed -n '1,2p'
cd "$root" || exit 1
groups() { python3 -I -c "import json,sys; print(len(json.load(open(sys.argv[1]))['groups']))" "$root/ws/bench/lab/$1.json" 2>/dev/null || echo 0; }
for spec in "$arm pm_best 1" "${arm}_s2 pm_best_s2 2" "${arm}_s3 pm_best_s3 3"; do
  set -- $spec
  for i in $(seq 1 40); do
    [ "$(groups "$1")" -ge 10 ] && break
    python3 -I /home/user/tools/lab.py queue "$1" --from "$2" --set "$3" 2>&1 | tail -1
    [ "$(groups "$1")" -ge 10 ] || sleep 120
  done
done
for i in $(seq 1 90); do
  s=$(python3 -I /home/user/tools/lab.py show "$arm" "${arm}_s2" "${arm}_s3" 2>&1 | grep -E '^[^ ]+: version')
  [ "$(echo "$s" | grep -c '(0 pending)')" -ge 3 ] && break
  sleep 60
done
echo "$s"
echo "$(date -u +%H:%M:%SZ) baseline pm_best 23 + 24 + 26 = 73 of 150"
