#!/usr/bin/env python3
"""Team totals by round from downloaded summaries: curve.py FOLDER:TEAM ..."""
import json, statistics as st, sys
from pathlib import Path
B = Path("/Users/faeezaullyar/Claude/battlecode/ws/bench")
MET = ["earnedGold", "spentGold", "monsterDamageDone", "collectedGems", "submittedGems", "deaths", "kills", "healingReceived", "shieldingDone"]
AT = [100, 200, 300, 400, 600, 800]
def val(runs, r):
    t = 0; v = 0.0
    for x in runs:
        if t > r: break
        v = float(x["value"]); t += int(x["duration"])
    return v
for arg in sys.argv[1:]:
    folder, team = arg.split(":", 1)
    acc = {m: {a: [] for a in AT} for m in MET}
    for m in json.loads((B / folder / "matches.json").read_text()):
        me = next((t for t in m["teams"] if t["name"] == team), None)
        f = B / folder / "summaries" / f"{m['matchId']}.json"
        if not me or not f.exists(): continue
        side = "teamA" if me["side"] == "a" else "teamB"
        d = json.loads(f.read_text())
        ids = {c["id"] for c in d["roster"]["champions"] if c["team"] == side}
        tot = {m_: {a: 0.0 for a in AT} for m_ in MET}
        for x in d["championTimelines"]:
            if x["owner"]["id"] in ids and x["metric"] in MET:
                for a in AT: tot[x["metric"]][a] += val(x["runs"], a)
        for m_ in MET:
            for a in AT: acc[m_][a].append(tot[m_][a])
    print(f"{team} ({len(acc['deaths'][100])} games), median team totals at round " + " ".join(f"{a:>7d}" for a in AT))
    for m_ in MET:
        print(f"  {m_:<20}" + " ".join(f"{st.median(acc[m_][a]):7.0f}" for a in AT))
