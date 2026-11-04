#!/usr/bin/env python3
"""Farming rate: monster damage per living champion-round (summary totals over decoded alive counts), and the
share of champion-rounds dead, for the focus team and its opponents."""
import collections, json, sys
from pathlib import Path
US = "Milk and Potatoes"
bdir, sdir = Path(sys.argv[1]), Path(sys.argv[2])
arms = set(sys.argv[3].split(",")) if len(sys.argv) > 3 and sys.argv[3] else None
meta = json.loads((bdir / "meta.json").read_text())
acc = collections.Counter(); n = 0
for m in meta:
    if arms and m.get("arm") not in arms: continue
    f = sdir / f"{m['matchId']}.jsonl"
    if not f.exists(): continue
    focus = m.get("focus", US)
    me = next(t for t in m["teams"] if t["name"] == focus or t.get("teamId") == focus)
    ours = 0 if me["side"] == "a" else 1; side = "teamA" if ours == 0 else "teamB"
    s = json.loads((bdir / f"{m['matchId']}.json").read_text())
    for c in s["champions"]:
        who = "focus" if c["team"] == side else "opp"
        acc[(who, "mdmg")] += float(c["metrics"]["monsterDamageDone"])
    for line in f.read_text().splitlines():
        st = json.loads(line)
        for c in st["c"]:
            who = "focus" if c[1] == ours else "opp"
            acc[(who, "rounds")] += 1
            if c[7]: acc[(who, "alive")] += 1
    n += 1
for who in ("focus", "opp"):
    print(f"{who:<6} monster damage per living champion-round {acc[(who, 'mdmg')] / max(1, acc[(who, 'alive')]):6.1f}   "
          f"dead share {100 * (1 - acc[(who, 'alive')] / max(1, acc[(who, 'rounds')])):5.1f}%   ({n} games)")
