#!/bin/bash
# decode_dir.sh SRC DST: per-round champion states (JSONL) for every bundle in SRC.
src=$1; dst=$2; mkdir -p "$dst"
ls "$src"/*.repl26a | xargs -P "${JOBS:-4}" -I{} bash -c '
  f="{}"; id=$(basename "$f" .repl26a); out="'"$dst"'/$id.jsonl"
  [ -s "$out" ] && exit 0
  tmp=$(mktemp -d)
  python3 -I -c "import zipfile,sys; open(sys.argv[2],\"wb\").write(zipfile.ZipFile(sys.argv[1]).read(\"replay.repl26a\"))" "$f" "$tmp/r.bin" &&
  node /home/user/tools/replay/read.mjs "$tmp/r.bin" seek cp > "$out.part" 2>/dev/null && mv "$out.part" "$out"
  rm -rf "$tmp"
'
