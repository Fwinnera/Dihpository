#!/bin/zsh
# mkomni_arm.sh ARM SEED: build ws/bots/om_<ARM>_<SEED> from omni, forcing one arm, re-rolled by SEED.
set -e
arm=$1; seed=$2; name=o3_${arm}_${seed}
root=/Users/faeezaullyar/Claude/battlecode
python3 -I $root/analysis/mkgs.py omni $name "policy_table.h:inline constexpr int FORCE = -1;=>inline constexpr int FORCE = $arm;" "policy_table.h:inline constexpr int REROLL = 0;=>inline constexpr int REROLL = $(( seed * 37 ));" > /dev/null
cd $root/ws && ~/Library/Python/3.9/bin/cambc build --release bots/$name > /dev/null 2>&1 || { echo "build failed $name"; exit 1; }
echo $name
