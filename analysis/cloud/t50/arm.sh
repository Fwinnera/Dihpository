#!/bin/bash
# arm.sh BOT ARM "NOTE": smoke-test ws5/bots/BOT, upload it, wait until it is live, pin it, queue lab sets 1-3
# (ARM, ARM_s2, ARM_s3 --from pm_best*), wait for the 150 games, print the result. Hold the README ladder lock.
# It does not re-pin anything afterwards.
set -u
bot=$1; arm=$2; note=$3
ws=/home/user/ws5
cambc=/home/user/.venv-cambc5/bin/cambc
export SSL_CERT_FILE=/root/.ccr/ca-bundle.crt
cd "$ws" || exit 1
[ -e "$ws/bench/lab/$arm.json" ] && { echo "arm $arm exists"; exit 1; }
[ ${#note} -le 80 ] || { echo "note longer than 80 characters"; exit 1; }
grep -q "DEBUG = false" "bots/$bot/src/config.h" || { echo "DEBUG is not false"; exit 1; }
# smoke test, both sides
sm=$(mktemp -d)
for pair in "bots/$bot bots/v183_submit 00lanes" "bots/v183_submit bots/$bot 03riverbed" "bots/$bot bots/v183_submit 00anvil"; do
  set -- $pair
  out=$("$cambc" run --release "$1" "$2" --map "$3" -o "$sm" 2>&1); rc=$?
  [ $rc -eq 0 ] || { echo "smoke: exit $rc on $3"; echo "$out" | tail -5; exit 1; }
done
bad=$(python3 -I - "$sm" "$bot" <<'PY'
import sys, zipfile, glob
bad = 0
for f in glob.glob(sys.argv[1] + "/*.repl26a"):
    z = zipfile.ZipFile(f)
    name = f.split("/")[-1]
    a, b = name.split("-vs-")[0], name.split("-vs-")[1].rsplit("-", 1)[0]
    for side, bot in (("a", a), ("b", b)):
        if bot != sys.argv[2]: continue
        out = z.read(f"team-{side}.stdout")
        if out.strip(): bad += 1; print("stdout not empty:", name, out[:200], file=sys.stderr)
print(bad)
PY
)
[ "$bad" = "0" ] || { echo "smoke: stdout not empty ($bad)"; exit 1; }
rm -rf "${sm:?}"
echo "$(date -u +%H:%M:%SZ) smoke ok: $bot"
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
st=""
for i in $(seq 1 120); do
  st=$("$cambc" submissions list 2>&1)
  echo "$st" | grep -q "Live: $ver " && break
  echo "$st" | grep -E "^v$ver " | grep -qi 'fail\|error\|cancel' && { echo "v$ver failed to build"; exit 1; }
  sleep 15
done
echo "$st" | grep -q "Live: $ver " || { echo "v$ver not live after 30 min"; exit 1; }
"$cambc" submissions activate "$ver" > /dev/null 2>&1
echo "$(date -u +%H:%M:%SZ) v$ver live and pinned"
"$cambc" submissions list 2>&1 | sed -n '1,2p'
groups() { python3 -I -c "import json,sys; print(len(json.load(open(sys.argv[1]))['groups']))" "$ws/bench/lab/$1.json" 2>/dev/null || echo 0; }
for spec in "$arm pm_best 1" "${arm}_s2 pm_best_s2 2" "${arm}_s3 pm_best_s3 3"; do
  set -- $spec
  for i in $(seq 1 40); do
    [ "$(groups "$1")" -ge 10 ] && break
    python3 -I /home/user/tools/lab.py queue "$1" --from "$2" --set "$3" 2>&1 | tail -1
    [ "$(groups "$1")" -ge 10 ] || sleep 120
  done
done
s=""
for i in $(seq 1 90); do
  s=$(python3 -I /home/user/tools/lab.py show "$arm" "${arm}_s2" "${arm}_s3" 2>&1 | grep -E '^[^ ]+: version')
  [ "$(echo "$s" | grep -c '(0 pending)')" -ge 3 ] && break
  sleep 30
done
echo "$s"
tot=$(echo "$s" | sed -n 's/.*, \([0-9]*\) of \([0-9]*\) won.*/\1/p' | paste -sd+ | bc)
echo "$(date -u +%H:%M:%SZ) RESULT $arm (v$ver, $bot): $tot of 150; baseline v183 28 + 25 + 19 = 72"
