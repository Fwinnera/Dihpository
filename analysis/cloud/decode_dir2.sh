#!/bin/bash
# decode_dir2.sh SRC DST [LIMIT]: like decode_dir.sh, with camp damage per round (read2.mjs ... camps).
src=$1; dst=$2; lim=${3:-100000}; mkdir -p "$dst"
ls "$src"/*.repl26a | head -n "$lim" | xargs -P "${JOBS:-4}" -I{} bash -c '
  f="{}"; id=$(basename "$f" .repl26a); out="'"$dst"'/$id.jsonl"
  [ -s "$out" ] && exit 0
  tmp=$(mktemp -d)
  python3 -I -c "import zipfile,sys; open(sys.argv[2],\"wb\").write(zipfile.ZipFile(sys.argv[1]).read(\"replay.repl26a\"))" "$f" "$tmp/r.bin" &&
  node /home/user/tools/replay/read2.mjs "$tmp/r.bin" seek cp camps > "$out.part" 2>/dev/null && mv "$out.part" "$out"
  rm -rf "$tmp"
'
