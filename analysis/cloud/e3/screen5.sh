#!/bin/bash
# screen5.sh PREFIX LOG "CANDS" ["OPPS"]: the local screen on engine 3.0.0 (cambc 5.0.0, /home/user/ws5, 128 maps).
set -u
prefix=$1; log=$2; cands=$3
opps=${4:-"gs_mix_camp b_tbd next_trial"}
jobs=${JOBS:-4}
cd /home/user/bench5 || exit 1
export SSL_CERT_FILE=/root/.ccr/ca-bundle.crt
for c in $cands; do
  for o in $opps; do
    tag="${prefix}_${c}_vs_${o}"
    python3 bench5.py "$c" --opponents "$o" --tag "$tag" --jobs "$jobs" > /dev/null 2>&1
    echo "$(date +%H:%M) $c vs $o: $(python3 -I h2h5.py "$tag" 2>&1 | grep 'games won' | head -1)" >> "$log"
  done
done
echo "$(date +%H:%M) done $cands" >> "$log"
