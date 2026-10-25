#!/bin/zsh
# screen_omni.sh "SEEDS" "ARMS": every arm at every seed against gs_eq, all 80 map-sides.
root=/Users/faeezaullyar/Claude/battlecode
for seed in ${=1}; do
  for arm in ${=2}; do
    name=o3_${arm}_${seed}
    if [ -d $root/ws/bench/h2h_${name}_eq ] && [ $(ls $root/ws/bench/h2h_${name}_eq/*.json 2>/dev/null | wc -l) -ge 80 ]; then continue; fi
    $root/analysis/mkomni_arm.sh $arm $seed > /dev/null || continue
    (cd $root && python3 bench.py $name --opponents gs_eq --tag h2h_${name}_eq --jobs 11 > /dev/null 2>&1)
    echo "$(date +%H:%M:%S) $name $(cd $root && python3 -I analysis/h2h.py h2h_${name}_eq | sed -n 2p)"
  done
done
