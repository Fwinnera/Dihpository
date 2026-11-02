#!/bin/bash
# mkvariant.sh NAME DMG_COST [rush] [half] [draft=mite|ci5] : a j_hjt copy with group-aware
# camp choice at the given damage cost, plus the named extras; built in release mode.
set -eu
name=$1; dmg=$2; shift 2
here=$(cd "$(dirname "$0")" && pwd)
cd /Users/faeezaullyar/Claude/battlecode/ws/bots
rm -rf "./${name:?}"
mkdir "$name"
cp -R j_hjt/src "$name/src"
rm -f "$name/src/bot.h.orig"
python3 "$here/mkjoin.py" "$name" "DMG_COST=$dmg" > /dev/null
for extra in "$@"; do
  case "$extra" in
    rush) python3 "$here/mkrush.py" "$name" > /dev/null ;;
    half) python3 "$here/mkhalf.py" "$name" > /dev/null ;;
    draft=*)
      python3 - "$name" "${extra#draft=}" <<'EOF'
import sys
from pathlib import Path
name, which = sys.argv[1], sys.argv[2]
old = ("        order = {D::varg, D::vendetta, D::vesper_vale, D::ryth, D::marcella, D::willow, D::tavi, "
       "D::cassi_and_issac, D::ren, D::stellar, D::prism, D::heart_of_ruin};")
orders = {
    "mite": "D::vesper_vale, D::vendetta, D::heart_of_ruin, D::marcella, D::cassi_and_issac, D::ryth, D::varg, D::willow, D::tavi, D::stellar, D::ren, D::prism",
    "ci5": "D::varg, D::vendetta, D::vesper_vale, D::ryth, D::cassi_and_issac, D::marcella, D::willow, D::tavi, D::ren, D::stellar, D::prism, D::heart_of_ruin",
}
p = Path(name) / "src/draft.h"
t = p.read_text()
assert t.count(old) == 1, "ordinary draft line not found"
p.write_text(t.replace(old, "        order = {" + orders[which] + "};"))
EOF
      ;;
    *) echo "unknown extra $extra" >&2; exit 1 ;;
  esac
done
cd ..
export PATH="$HOME/Library/Python/3.9/bin:$PATH"
cambc build --release "bots/$name" 2>&1 | grep -E "error|built" | sed "s|.*bots/||"
