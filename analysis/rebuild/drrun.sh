#!/bin/bash
# drrun.sh BOT OUTDIR OPP... : every map, both sides, keeping each game's bundle (stdout) and
# summary (stats.json) in OUTDIR/<opp>__<map>__<A|B>/ for drfit.py.
set -u
bot=$1; out=$2; shift 2
cd /Users/faeezaullyar/Claude/battlecode/ws || exit 1
export PATH="$HOME/Library/Python/3.9/bin:$PATH"
mkdir -p "$out"
# Build once before the parallel games (parallel first builds collide in cmake configure).
cambc run --release --rounds 2 --map 00oasis -o "$out/_build" "bots/$bot" "bots/$1" > /dev/null 2>&1
for opp in "$@"; do cambc run --release --rounds 2 --map 00oasis -o "$out/_build" "bots/$opp" "bots/$bot" > /dev/null 2>&1; done
jobs=()
for opp in "$@"; do
  for m in maps/*.map26a; do
    name=$(basename "$m" .map26a)
    jobs+=("$opp $name A" "$opp $name B")
  done
done
printf '%s\n' "${jobs[@]}" | xargs -P 11 -L 1 bash -c '
  opp=$0; map=$1; side=$2; d="'"$out"'/${opp}__${map}__${side}"
  mkdir -p "$d"
  if [ "$side" = A ]; then a="bots/'"$bot"'"; b="bots/$opp"; else a="bots/$opp"; b="bots/'"$bot"'"; fi
  cambc run --release --log-limit 8000000 --map "$map" -o "$d" --statistics "$d/stats.json" --json "$a" "$b" > "$d/run.txt" 2>&1
'
echo done
