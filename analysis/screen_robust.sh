#!/bin/zsh
# screen_robust.sh "ARMS" "OPPONENTS": each arm, unperturbed (REROLL 0, as submitted),
# against each opponent build, all 80 map-sides. Tags h2h_o3_<arm>_0_<opp>.
root=/Users/faeezaullyar/Claude/battlecode
for arm in ${=1}; do
  name=o3_${arm}_0
  [ -f $root/ws/bots/$name/.cambc/build-release/bot-injected.wasm ] || $root/analysis/mkomni_arm.sh $arm 0 > /dev/null || continue
  for opp in ${=2}; do
    tag=h2h_${name}_${opp}
    if [ -d $root/ws/bench/$tag ] && [ $(ls $root/ws/bench/$tag/*.json 2>/dev/null | wc -l) -ge 80 ]; then continue; fi
    (cd $root && python3 bench.py $name --opponents $opp --tag $tag --jobs 11 > /dev/null 2>&1)
    echo "$(date +%H:%M:%S) $tag $(cd $root && python3 -I analysis/h2h.py $tag | sed -n 2p)"
  done
done
