#!/bin/bash
# queue.sh LOG "BOT|ARM|NOTE" ...: run arm.sh for each spec in turn; one RESULT line per arm in LOG.
log=$1; shift
for spec in "$@"; do
  IFS='|' read -r bot arm note <<< "$spec"
  echo "$(date -u +%H:%M:%SZ) start $arm" >> "$log"
  /home/user/tools/arm.sh "$bot" "$arm" "$note" 2>&1 | grep -E "RESULT|smoke:|failed|not live|exists|no version|won \(" >> "$log"
done
echo "$(date -u +%H:%M:%SZ) queue done" >> "$log"
