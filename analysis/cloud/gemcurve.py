#!/usr/bin/env python3
"""Submitted gems by round (team timelines in summaries) for the focus team and its opponents."""
import collections, json, sys
from pathlib import Path
US = "Milk and Potatoes"
marks = [100, 200, 300, 400, 600, 800, 1000, 1200]
d = Path(sys.argv[1]); meta = json.loads((d / "meta.json").read_text())
arms = set(sys.argv[2].split(",")) if len(sys.argv) > 2 else None
acc = collections.defaultdict(list)
for m in meta:
    if arms and m.get("arm") not in arms: continue
    f = d / f"{m['matchId']}.json"
    if not f.exists(): continue
    focus = m.get("focus", US)
    me = next(t for t in m["teams"] if t["name"] == focus or t.get("teamId") == focus)
    side = "teamA" if me["side"] == "a" else "teamB"
    s = json.loads(f.read_text())
    for tl in s["teamTimelines"]:
        if tl["metric"] != "submittedGems": continue
        who = "focus" if tl["owner"] == side else "opp"
        r = 0; vals = {}
        for run in tl["runs"]:
            for mk in marks:
                if r <= mk < r + run["duration"]: vals[mk] = float(run["value"])
            r += run["duration"]
        last = float(tl["runs"][-1]["value"]) if tl["runs"] else 0
        for mk in marks: acc[(who, mk)].append(vals.get(mk, last))
print("mean submitted gems by round " + "".join(f"{mk:>7}" for mk in marks))
for who in ("focus", "opp"):
    print(f"  {who:<26}" + "".join(f"{sum(acc[(who, mk)]) / max(1, len(acc[(who, mk)])):>7.0f}" for mk in marks))
