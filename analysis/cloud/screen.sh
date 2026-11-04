#!/bin/bash
# Cloud copy of analysis/rebuild/screen.sh: same games and log format, repo path and job count adapted.
set -u
prefix=$1; log=$2; cands=$3
opps=${4:-"gs_mix_camp b_tbd next_trial"}
jobs=${JOBS:-4}
cd /home/user/repo || exit 1
export SSL_CERT_FILE=/root/.ccr/ca-bundle.crt
for c in $cands; do
  for o in $opps; do
    tag="${prefix}_${c}_vs_${o}"
    python3 bench.py "$c" --opponents "$o" --tag "$tag" --jobs "$jobs" > /dev/null 2>&1
    echo "$(date +%H:%M) $c vs $o: $(python3 -I analysis/h2h.py "$tag" 2>&1 | grep 'games won' | head -1)" >> "$log"
    find "ws/bench/$tag" -type f -name "*__*.json" -print0 | xargs -0 -n 64 -P 4 gzip -q 2>/dev/null || true
  done
done
echo "$(date +%H:%M) done $cands" >> "$log"
