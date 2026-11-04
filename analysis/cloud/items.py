#!/usr/bin/env python3
"""Final items per champion type for the focus team (or us) and their opponents, from summaries."""
import collections, json, sys
from pathlib import Path
US = "Milk and Potatoes"
d = Path(sys.argv[1]); meta = json.loads((d / "meta.json").read_text())
items = collections.defaultdict(collections.Counter); n = collections.Counter()
drafts = collections.Counter()
for m in meta:
    focus = m.get("focus", US)
    me = next(t for t in m["teams"] if t["name"] == focus or t.get("teamId") == focus)
    side = "teamA" if me["side"] == "a" else "teamB"
    s = json.loads((d / f"{m['matchId']}.json").read_text())
    names = {c["id"]: c["name"] for c in s["roster"]["champions"]}
    for who in ("focus", "opp"):
        team = side if who == "focus" else ("teamB" if side == "teamA" else "teamA")
        roster = sorted(c["name"] for c in s["roster"]["champions"] if c["team"] == team)
        drafts[(who, tuple(roster))] += 1
        for c in s["champions"]:
            if c["team"] != team: continue
            nm = names.get(c["id"], "?")
            n[(who, nm)] += 1
            for it in c.get("items", []):
                items[(who, nm)][it["item"]] += int(it["quantity"])
for who in ("focus", "opp"):
    print(f"== {who}: most common rosters")
    for (w, r), k in drafts.most_common():
        if w == who: print(f"   {k:>3}  {', '.join(r)}")
    for (w, nm) in sorted(k for k in n if k[0] == who):
        top = items[(w, nm)].most_common(5)
        print(f"   {nm:<14}({n[(w, nm)]:>2}) " + ", ".join(f"{it} {q / n[(w, nm)]:.1f}" for it, q in top))
