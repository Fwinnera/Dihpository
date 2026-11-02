#!/usr/bin/env python3
"""Per champion, rounds < LIMIT: share with monster damage dealt, champion damage, deaths, first hit.

    early.py LIMIT FOLDER:TEAM ...
"""
import json, statistics as st, sys
from collections import defaultdict
from pathlib import Path
B = Path("/Users/faeezaullyar/Claude/battlecode/ws/bench")
limit = int(sys.argv[1])
def expand(runs, n):
    out = []
    for r in runs:
        out += [float(r["value"])] * int(r["duration"])
        if len(out) > n: break
    return (out + [out[-1] if out else 0.0] * n)[:n]
for arg in sys.argv[2:]:
    folder, team = arg.split(":", 1)
    hit = defaultdict(list); first = defaultdict(list); dmg = defaultdict(list); fights = defaultdict(list)
    for m in json.loads((B / folder / "matches.json").read_text()):
        me = next((t for t in m["teams"] if t["name"] == team), None)
        f = B / folder / "summaries" / f"{m['matchId']}.json"
        if not me or not f.exists(): continue
        side = "teamA" if me["side"] == "a" else "teamB"
        d = json.loads(f.read_text())
        names = {c["id"]: c["name"] for c in d["roster"]["champions"] if c["team"] == side}
        tl = defaultdict(dict)
        for x in d["championTimelines"]:
            if x["owner"]["id"] in names and x["metric"] in ("monsterDamageDone", "championDamageDone", "championDamageTaken"):
                tl[x["owner"]["id"]][x["metric"]] = expand(x["runs"], limit + 1)
        for cid, nm in names.items():
            s = tl[cid]
            if len(s) < 3: continue
            md = s["monsterDamageDone"]
            h = [r for r in range(1, limit + 1) if md[r] > md[r - 1]]
            hit[nm].append(len(h) / limit); dmg[nm].append(md[limit])
            first[nm].append(h[0] if h else limit)
            cd = s["championDamageDone"]; ct = s["championDamageTaken"]
            fights[nm].append(sum(1 for r in range(1, limit + 1) if cd[r] > cd[r - 1] or ct[r] > ct[r - 1]) / limit)
    print(f"{team}: rounds 1-{limit}   hitting camps / fighting share, camp damage, first camp hit (medians)")
    for nm in sorted(hit, key=lambda k: -len(hit[k])):
        print(f"  {nm:<14} n={len(hit[nm]):3d}  hit {100 * st.mean(hit[nm]):5.1f}%  fight {100 * st.mean(fights[nm]):5.1f}%"
              f"  dmg {st.median(dmg[nm]):6.0f}  first {st.median(first[nm]):4.0f}")
