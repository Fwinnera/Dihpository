#!/bin/bash
# localprof.sh BOT OUTDIR "OPP ..." [MAPS_GLOB]: BOT against each OPP on every map from both sides, laid out
# like a ladder download (OUTDIR/<id>.repl26a, <id>.json, meta.json) for diag.py.
bot=$1; out=$2; opps=$3
mkdir -p "$out"
cd /home/user/repo/ws || exit 1
export SSL_CERT_FILE=/root/.ccr/ca-bundle.crt
: > "$out/manifest.txt"
for o in $opps; do
  for m in maps/*.map26a; do
    s=$(basename "$m" .map26a)
    echo "/home/user/repo/ws/bots/$bot /home/user/repo/ws/bots/$o /home/user/repo/ws/$m $out/${o}__${s}__a.repl26a --statistics $out/${o}__${s}__a.json" >> "$out/manifest.txt"
    echo "/home/user/repo/ws/bots/$o /home/user/repo/ws/bots/$bot /home/user/repo/ws/$m $out/${o}__${s}__b.repl26a --statistics $out/${o}__${s}__b.json" >> "$out/manifest.txt"
  done
done
/home/user/.venv-cambc/bin/cambc run-batch --release --json --jobs "${JOBS:-4}" --timeout 300 "$out/manifest.txt" > "$out/run.log" 2>&1
python3 -I - "$out" <<'PY'
import json, sys
from pathlib import Path
out = Path(sys.argv[1])
meta = []
for j in sorted(out.glob("*__*__*.json")):
    opp, mp, side = j.stem.split("__")
    d = json.loads(j.read_text())
    ours = "teamA" if side == "a" else "teamB"
    won = d["match"]["outcome"] == ours
    meta.append(dict(matchId=j.stem, map=mp, teams=[
        dict(name="Milk and Potatoes", side=side, result="win" if won else "loss"),
        dict(name=opp, side="b" if side == "a" else "a", result="loss" if won else "win")]))
(out / "meta.json").write_text(json.dumps(meta))
print(len(meta), "games")
PY
echo done >> "$out/run.log"
