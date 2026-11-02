#!/usr/bin/env python3
"""Per champion, per game: healing done/received, shielding, camp and champion damage taken,
deaths, by the end. sustain.py FOLDER:TEAM ..."""
import json, statistics as st, sys
from collections import defaultdict
from pathlib import Path
B = Path("/Users/faeezaullyar/Claude/battlecode/ws/bench")
M = ["healingDone", "healingReceived", "shieldingDone", "monsterDamageTaken", "championDamageTaken", "deaths", "monsterDamageDone"]
for arg in sys.argv[1:]:
    folder, team = arg.split(":", 1)
    acc = defaultdict(lambda: defaultdict(list)); rounds = []
    for m in json.loads((B / folder / "matches.json").read_text()):
        me = next((t for t in m["teams"] if t["name"] == team), None)
        f = B / folder / "summaries" / f"{m['matchId']}.json"
        if not me or not f.exists(): continue
        side = "teamA" if me["side"] == "a" else "teamB"
        d = json.loads(f.read_text()); rounds.append(d["match"]["roundsCompleted"])
        names = {c["id"]: c["name"] for c in d["roster"]["champions"] if c["team"] == side}
        for x in d["championTimelines"]:
            if x["owner"]["id"] in names and x["metric"] in M:
                acc[names[x["owner"]["id"]]][x["metric"]].append(float(x["runs"][-1]["value"]) if x["runs"] else 0)
    print(f"{team}: median {st.median(rounds):.0f} rounds; per game (mean)")
    print("  %-14s" % "" + "".join("%13s" % k[:12] for k in M))
    for nm in sorted(acc, key=lambda k: -len(acc[k]["deaths"])):
        print("  %-14s" % nm + "".join("%13.0f" % (st.mean(acc[nm][k]) if acc[nm][k] else 0) for k in M))
