#!/usr/bin/env python3
"""Where gems come from: gemCollection events by source (camp group capture vs champion kill), gem losses on
death, submissions; per game, focus team vs opponents, over the first N rounds and the whole game."""
import collections, json, sys
from pathlib import Path
US = "Milk and Potatoes"
d = Path(sys.argv[1]); meta = json.loads((d / "meta.json").read_text())
arms = set(sys.argv[2].split(",")) if len(sys.argv) > 2 and sys.argv[2] else None
upto = int(sys.argv[3]) if len(sys.argv) > 3 else 10**9
acc = collections.Counter(); n = 0; clears = collections.Counter()
for m in meta:
    if arms and m.get("arm") not in arms: continue
    f = d / f"{m['matchId']}.json"
    if not f.exists(): continue
    focus = m.get("focus", US)
    me = next(t for t in m["teams"] if t["name"] == focus or t.get("teamId") == focus)
    side = "teamA" if me["side"] == "a" else "teamB"
    s = json.loads(f.read_text()); n += 1
    for e in s["events"]:
        who = "focus" if e["owner"].get("team") == side else "opp"
        for x in e["entries"]:
            if x["timestamp"]["round"] > upto: continue
            v = float(x.get("value") or 0)
            if e["kind"] == "gemCollection":
                acc[(who, "from " + str(x.get("context")))] += v
                acc[(who, "pickups " + str(x.get("context")))] += 1
            elif e["kind"] == "gemLoss": acc[(who, "lost on death")] += v
            elif e["kind"] == "gemSubmission": acc[(who, "submitted")] += v; acc[(who, "deposits")] += 1
            elif e["kind"] == "campClear": acc[(who, "camp clears")] += 1
keys = ["from campGroup", "pickups campGroup", "from champion", "pickups champion", "lost on death", "submitted", "deposits", "camp clears"]
print(f"{n} games, events up to round {upto if upto < 10**9 else 'end'}")
print(f"  {'':<20}{'focus':>10}{'opp':>10}")
for k in keys:
    print(f"  {k:<20}{acc[('focus', k)] / max(1, n):>10.1f}{acc[('opp', k)] / max(1, n):>10.1f}")
