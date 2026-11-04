#!/bin/bash
# labrun.sh BOT ARM "NOTE": the whole ladder-lab cycle for one candidate (take the README ladder
# lock first). Uploads ws/bots/BOT (an untagged, smoke-tested _submit copy), waits for the new
# version to go live, pins it, queues lab sets 1-3 against the pinned opponents (ARM --from v140,
# ARM_s2 --from rl_s2, ARM_s3 --from ab3_s3), waits for all 150 games, then prints the results and
# the paired gem margins against v155 (ab3, ab3_s2, ab3_s3). It does not re-pin anything: keep the
# candidate or re-activate 155 by hand.
set -u
bot=$1; arm=$2; note=$3
root=/Users/faeezaullyar/Claude/battlecode
cambc="$HOME/Library/Python/3.9/bin/cambc"
cd "$root/ws" || exit 1
[ -e "$root/ws/bench/lab/$arm.json" ] && { echo "arm $arm exists"; exit 1; }
before=$("$cambc" submissions list 2>&1 | awk '/^v[0-9]+ /{print substr($1,2); exit}')
out=""
for i in 1 2 3 4; do
  out=$("$cambc" submit "bots/$bot" -n "$note" 2>&1)
  echo "$out" | tail -1
  echo "$out" | grep -q 'Submitted bot version' && break
  echo "$out" | grep -qi 'frozen' && exit 2
  sleep 10
done
ver=$(echo "$out" | sed -n 's/.*Submitted bot version \([0-9]*\).*/\1/p')
[ -n "$ver" ] || { echo "no version (latest before: v$before)"; exit 1; }
for i in $(seq 1 90); do
  st=$("$cambc" submissions list 2>&1)
  echo "$st" | grep -q "Live: $ver" && break
  echo "$st" | grep -E "^v$ver " | grep -qi 'fail\|error\|cancel' && { echo "v$ver failed to build"; exit 1; }
  sleep 20
done
echo "$st" | grep -q "Live: $ver" || { echo "v$ver not live after 30 min"; exit 1; }
"$cambc" submissions activate "$ver" > /dev/null 2>&1
"$cambc" submissions list 2>&1 | sed -n '1,2p'
cd "$root" || exit 1
# The team may start 50 groups an hour: retry (resuming the arm) until each has its ten groups.
groups() { python3 -I -c "import json,sys; print(len(json.load(open(sys.argv[1]))['groups']))" "$root/ws/bench/lab/$1.json" 2>/dev/null || echo 0; }
for spec in "$arm v140 1" "${arm}_s2 rl_s2 2" "${arm}_s3 ab3_s3 3"; do
  set -- $spec
  for i in $(seq 1 40); do
    [ "$(groups "$1")" -ge 10 ] && break
    python3 -I analysis/rebuild/lab.py queue "$1" --from "$2" --set "$3" 2>&1 | tail -1
    [ "$(groups "$1")" -ge 10 ] || sleep 120
  done
done
for i in $(seq 1 60); do
  s=$(python3 -I analysis/rebuild/lab.py show "$arm" "${arm}_s2" "${arm}_s3" 2>&1 | grep -E '^[^ ]+: version')
  [ "$(echo "$s" | grep -c '(0 pending)')" -ge 3 ] && break
  sleep 60
done
echo "$s"
python3 -I analysis/rebuild/labmargin.py fetch "$arm" "${arm}_s2" "${arm}_s3" > /dev/null 2>&1
python3 -I analysis/rebuild/labmargin.py ab3 "$arm" ab3_s2 "${arm}_s2" ab3_s3 "${arm}_s3" 2>&1 | tail -3
