#!/usr/bin/env python3
"""Game-by-game comparison of lab runs from the lab's cached group results (ws/bench/lab/ARM.json and
groups/*.json): each run is ARM (sets 1-3: ARM, ARM_s2, ARM_s3). Prints wins, pairwise agreement, and
how many games each run won alone."""
import itertools, json, sys
from pathlib import Path
LAB = Path("/home/user/repo/ws/bench/lab"); US = "Milk and Potatoes"
def games(arm):
    out = {}
    for k, suffix in enumerate(("", "_s2", "_s3")):
        f = LAB / f"{arm}{suffix}.json"
        if not f.exists(): continue
        for g in json.loads(f.read_text())["groups"]:
            c = LAB / "groups" / f"{g['group']}.json"
            if not c.exists(): continue
            for m in json.loads(c.read_text())["matches"]:
                me = next(t for t in m["teams"] if t["name"] == US); opp = next(t for t in m["teams"] if t["name"] != US)
                out[(k, opp["name"], m["map"], me["side"])] = (me["result"] == "win", m.get("endReason"))
    return out
runs = sys.argv[1:]
G = {r: games(r) for r in runs}
keys = set.intersection(*(set(G[r]) for r in runs))
print(f"{len(keys)} games common to {', '.join(runs)}")
for r in runs: print(f"  {r:<8} wins {sum(G[r][k][0] for k in keys)}")
for a, b in itertools.combinations(runs, 2):
    print(f"  {a} vs {b}: same result {sum(G[a][k][0] == G[b][k][0] for k in keys)} of {len(keys)}")
