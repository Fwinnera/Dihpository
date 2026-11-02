#!/usr/bin/env python3
"""Trips home per champion from ladder summaries. A round in which healingReceived jumps by
at least 25% of max health is a spawn heal (spawn heals 100% a round); a jump within 70
rounds after a death is that death's respawn. visits.py FOLDER:TEAM ..."""
import json, statistics as st, sys
from collections import defaultdict
from pathlib import Path
B = Path("/Users/faeezaullyar/Claude/battlecode/ws/bench")
def expand(runs, n):
    out = []
    for r in runs: out += [float(r["value"])] * int(r["duration"])
    return (out + [out[-1] if out else 0.0] * n)[:n]
for arg in sys.argv[1:]:
    folder, team = arg.split(":", 1)
    per = defaultdict(list); deaths = defaultdict(list); rounds = []
    for m in json.loads((B / folder / "matches.json").read_text()):
        me = next((t for t in m["teams"] if t["name"] == team), None)
        f = B / folder / "summaries" / f"{m['matchId']}.json"
        if not me or not f.exists(): continue
        side = "teamA" if me["side"] == "a" else "teamB"
        d = json.loads(f.read_text()); n = d["match"]["roundsCompleted"]; rounds.append(n)
        champs = {c["id"]: c for c in d["roster"]["champions"] if c["team"] == side}
        if any(c["name"] == "Willow" for c in champs.values()): continue
        tl = defaultdict(dict)
        for x in d["championTimelines"]:
            if x["owner"]["id"] in champs and x["metric"] in ("healingReceived", "deaths"):
                tl[x["owner"]["id"]][x["metric"]] = expand(x["runs"], n + 1)
        maxhp = {}
        for c in d["champions"]:
            if c["team"] == side: maxhp[c["id"]] = float(c.get("maxHealth") or c.get("stats", {}).get("maxHealth") or 1000)
        for cid, c in champs.items():
            s = tl[cid]
            if len(s) < 2: continue
            h, dd = s["healingReceived"], s["deaths"]
            last_death = -1000; visits = 0
            for r in range(1, n + 1):
                if dd[r] > dd[r - 1]: last_death = r
                if h[r] - h[r - 1] >= 250 and r - last_death > 70:
                    visits += 1
            per[c["name"]].append(visits * 1000 / n); deaths[c["name"]].append(dd[n] * 1000 / n)
    print(f"{team}: games without Willow; per 1,000 rounds: trips home that were not deaths, and deaths")
    for nm in sorted(per, key=lambda k: -len(per[k])):
        print(f"  {nm:<14} n={len(per[nm]):3d}  trips {st.mean(per[nm]):5.1f}   deaths {st.mean(deaths[nm]):4.1f}")
    allv = [v for k in per for v in per[k]]; alld = [v for k in deaths for v in deaths[k]]
    print(f"  {'mean':<14}        trips {st.mean(allv):5.1f}   deaths {st.mean(alld):4.1f}")
