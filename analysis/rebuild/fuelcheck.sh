#!/bin/bash
# fuelcheck.sh SINCE BOT [OTHER_BOT]: confirm which build is live. Takes our newest finished
# ranked game created at or after SINCE (ISO, e.g. 2026-11-03T01:30), downloads it into a
# fresh folder, runs BOT (and OTHER_BOT, for contrast) locally on the same map and side for
# 40 rounds, and compares the fuel figures after the first four (the draft budgets, which
# differ between the platform and any local run).
set -eu
since=$1; bot=$2; other=${3:-}
here=$(cd "$(dirname "$0")" && pwd)
export PATH="$HOME/Library/Python/3.9/bin:$PATH"
cd /Users/faeezaullyar/Claude/battlecode/ws
work=$(mktemp -d "${TMPDIR:-/tmp}/fuelcheck.XXXXXX")
read -r id map side opp < <(cambc matches list --team me --kind ranked --limit 50 --json | python3 -I -c '
import json, sys
since = sys.argv[1]
for m in json.load(sys.stdin).get("matches", []):
    if m.get("status") == "finished" and m["createdAt"] >= since:
        us = next(t for t in m["teams"] if t["name"] == "Milk and Potatoes")
        op = next(t for t in m["teams"] if t["name"] != "Milk and Potatoes")
        print(m["matchId"], m["map"].replace("_", "-"), us["side"], op["name"].replace(" ", "_")); break
' "$since")
if [ -z "${id:-}" ]; then echo "no finished ranked game since $since"; exit 2; fi
echo "match $id on $map, our side $side, against $opp"
mkdir -p "$work/dl"
cambc matches download "$id" --output "$work/dl/match.zip" > /dev/null
for b in "$bot" $other; do
  mkdir -p "$work/$b"
  if [ "$side" = a ]; then cambc run --release --rounds 40 --map "$map" -o "$work/$b" "bots/$b" bots/b_tbd > /dev/null 2>&1
  else cambc run --release --rounds 40 --map "$map" -o "$work/$b" bots/b_tbd "bots/$b" > /dev/null 2>&1; fi
done
python3 -I - "$work/dl/match.zip" "$side" "$work" "$bot" $other <<'EOF'
import struct, sys, zipfile
from pathlib import Path
def figures(bundle, side, n=124):
    data = zipfile.ZipFile(bundle).read(f"team-{side}.fuel")
    body = data[13:]
    return [struct.unpack_from("<Q", body, 8 * i)[0] for i in range(min(n, len(body) // 8))][4:]
target, side, work = sys.argv[1], sys.argv[2], Path(sys.argv[3])
t = figures(target, side)
for b in sys.argv[4:]:
    f = figures(str(next((work / b).glob("*.repl26a"))), side)
    n = min(len(t), len(f)); same = 0
    for x, y in zip(t[:n], f[:n]):
        if x != y: break
        same += 1
    print(f"  {b:<16} matches the first {same} of {n} figures after the draft")
EOF
rm -rf "${work:?}"
