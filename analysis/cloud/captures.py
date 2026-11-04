#!/usr/bin/env python3
"""Camp captures by gem value (from gemCollection campGroup events and campClear), first N rounds."""
import collections, json, sys
from pathlib import Path
US = "Milk and Potatoes"
d = Path(sys.argv[1]); meta = json.loads((d / "meta.json").read_text())
arms = set(sys.argv[2].split(",")) if len(sys.argv) > 2 and sys.argv[2] else None
upto = int(sys.argv[3]) if len(sys.argv) > 3 else 10**9
dist = collections.defaultdict(collections.Counter); n = 0
for m in meta:
    if arms and m.get("arm") not in arms: continue
    f = d / f"{m['matchId']}.json"
    if not f.exists(): continue
    focus = m.get("focus", US)
    me = next(t for t in m["teams"] if t["name"] == focus or t.get("teamId") == focus)
    side = "teamA" if me["side"] == "a" else "teamB"
    s = json.loads(f.read_text()); n += 1
    for e in s["events"]:
        if e["kind"] != "gemCollection": continue
        who = "focus" if e["owner"].get("team") == side else "opp"
        for x in e["entries"]:
            if x["timestamp"]["round"] > upto or x.get("context") != "campGroup": continue
            v = int(float(x.get("value") or 0))
            b = "0" if v == 0 else "1-9" if v < 10 else "10-19" if v < 20 else "20-39" if v < 40 else "40-99" if v < 100 else "100+"
            dist[who][b] += 1
order = ["0", "1-9", "10-19", "20-39", "40-99", "100+"]
print(f"{n} games, captures per game by gems, up to round {upto}")
for who in ("focus", "opp"):
    tot = sum(dist[who].values())
    print(f"  {who:<6} " + "  ".join(f"{b}: {dist[who][b] / n:4.1f}" for b in order) + f"   (zero-gem share {100 * dist[who]['0'] / max(1, tot):.0f}%)")
