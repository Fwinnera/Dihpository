#!/usr/bin/env python3
"""Camp clears in the opening, from ladder summaries: openclears.py LIMIT FOLDER:TEAM ..."""
import json, statistics as st, sys
from collections import Counter
from pathlib import Path
B = Path("/Users/faeezaullyar/Claude/battlecode/ws/bench")
T = json.loads(Path(__file__).resolve().with_name("camps86.json").read_text())
limit = int(sys.argv[1])
for arg in sys.argv[2:]:
    folder, team = arg.split(":", 1)
    games = 0; clears = []; first = []
    for m in json.loads((B / folder / "matches.json").read_text()):
        me = next((t for t in m["teams"] if t["name"] == team), None)
        f = B / folder / "summaries" / f"{m['matchId']}.json"
        key = m["map"].replace("_", "-")
        if not me or not f.exists() or key not in T: continue
        side = "teamA" if me["side"] == "a" else "teamB"
        spawn = T[key]["spawn_a" if side == "teamA" else "spawn_b"]
        if not spawn: continue
        sx = st.mean(p[0] for p in spawn); sy = st.mean(p[1] for p in spawn)
        groups = {g["id"]: g for g in T[key]["groups"]}
        d = json.loads(f.read_text()); games += 1
        mine = []
        for e in d["events"]:
            if e["kind"] != "campClear" or (e.get("owner") or {}).get("team") != side: continue
            for x in e["entries"]:
                r = x["timestamp"]["round"]
                if r < limit:
                    g = groups.get(x["target"]["id"])
                    if g: mine.append((r, g, max(abs(g["x"] - sx), abs(g["y"] - sy))))
        mine.sort(key=lambda t: t[0])
        clears += mine
        if mine: first.append(mine[0][0])
    gem = [c[1]["gems"] for c in clears]; gold = [c[1]["gold"] for c in clears]; hp = [c[1]["hp"] for c in clears]
    dist = [c[2] for c in clears]; strn = [c[1]["strength"] for c in clears]
    print(f"{team}: {games} games, clears before round {limit}: {len(clears) / games:.1f} a game; per clear median "
          f"gems {st.median(gem):.0f} (mean {st.mean(gem):.1f}), gold {st.median(gold):.0f} (mean {st.mean(gold):.0f}), "
          f"hp {st.median(hp):.0f}, strength {st.median(strn):.0f}, spawn distance {st.median(dist):.0f}; "
          f"zero-gem share {sum(1 for g in gem if g == 0) / len(gem):.0%}; first clear {st.median(first):.0f}")
    print("   value mix:", Counter((c[1]['gems'], c[1]['gold']) for c in clears).most_common(8))
