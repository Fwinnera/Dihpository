#!/usr/bin/env python3
"""Economy and deaths per game for our team in lab arms (from match summaries): gems submitted and
collected, gold, deaths, kills, monster and champion damage, rounds; by arm prefix."""
import collections, json, sys
from pathlib import Path
US = "Milk and Potatoes"
bdir = Path(sys.argv[1]); prefixes = sys.argv[2].split(",")
meta = json.loads((bdir / "meta.json").read_text())
K = ["collectedGems", "earnedGold", "deaths", "kills", "monsterDamageDone", "championDamageDone", "championDamageTaken"]
print(f"{'arm':<8}{'games':>6}{'subm':>7}{'opp':>7}" + "".join(f"{k[:10]:>11}" for k in K) + f"{'rounds':>8}")
for pre in prefixes:
    n = 0; acc = collections.Counter()
    for m in meta:
        if not m.get("arm", "").startswith(pre): continue
        f = bdir / f"{m['matchId']}.json"
        if not f.exists(): continue
        d = json.loads(f.read_text())
        me = next(t for t in m["teams"] if t["name"] == US); mine = "teamA" if me["side"] == "a" else "teamB"
        g = {t["team"]: int(t["submittedGems"]) for t in d["teams"]}
        n += 1
        acc["subm"] += g[mine]; acc["opp"] += g["teamB" if mine == "teamA" else "teamA"]; acc["rounds"] += d["match"]["roundsCompleted"]
        for c in d["champions"]:
            if c["team"] == mine:
                for k in K: acc[k] += float(c["metrics"].get(k, 0))
    if n: print(f"{pre:<8}{n:>6}{acc['subm'] / n:>7.0f}{acc['opp'] / n:>7.0f}" + "".join(f"{acc[k] / n:>11.0f}" for k in K) + f"{acc['rounds'] / n:>8.0f}")
