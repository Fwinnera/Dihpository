#!/bin/bash
# profrun.sh BOT OUTDIR OPP... : every map, both sides; bundles land in OUTDIR/<opp>__<map>__<A|B>/
set -u
bot=$1; out=$2; shift 2
cd /Users/faeezaullyar/Claude/battlecode/ws || exit 1
export PATH="$HOME/Library/Python/3.9/bin:$PATH"
mkdir -p "$out"
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
  cambc run --release --log-limit 8000000 --map "$map" -o "$d" "$a" "$b" > "$d/run.txt" 2>&1
'
echo done
