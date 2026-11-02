#!/bin/bash
# screen.sh PREFIX LOG "CAND ..." ["OPP ..."]: every candidate against every panel opponent,
# both sides of every map; one h2h line per pairing appended to LOG.
set -u
prefix=$1; log=$2; cands=$3
opps=${4:-"b_tbd next_trial gs_stand_submit f_hor_h f_hor_n f_vv_h f_tavi_n f_cast_n"}
cd /Users/faeezaullyar/Claude/battlecode || exit 1
export PATH="$HOME/Library/Python/3.9/bin:$PATH"
for c in $cands; do
  for o in $opps; do
    tag="${prefix}_${c}_vs_${o}"
    python3 bench.py "$c" --opponents "$o" --tag "$tag" --jobs 11 > /dev/null 2>&1
    echo "$(date +%H:%M) $c vs $o: $(python3 -I analysis/h2h.py "$tag" 2>&1 | grep 'games won' | head -1)" >> "$log"
  done
done
echo "$(date +%H:%M) done $cands" >> "$log"
