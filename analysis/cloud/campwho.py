#!/usr/bin/env python3
"""Captures in the first N rounds by camp group: gems, gold, depth from the capturer's spawn; focus vs opp."""
import collections, json, sys
from pathlib import Path
US = "Milk and Potatoes"
T = json.loads(Path("/home/user/repo/analysis/rebuild/camps86.json").read_text())
T = {k.replace("-", "_"): v for k, v in T.items()}
MI = {k.replace("-", "_"): v for k, v in json.loads(Path("/home/user/runs/mapinfo/mapinfo.json").read_text()).items()}
def cheb(a, b): return max(abs(a[0]-b[0]), abs(a[1]-b[1]))
d = Path(sys.argv[1]); meta = json.loads((d / "meta.json").read_text())
arms = set(sys.argv[2].split(",")) if len(sys.argv) > 2 and sys.argv[2] else None
upto = int(sys.argv[3]) if len(sys.argv) > 3 else 600
acc = collections.Counter(); n = 0; missing = 0
for m in meta:
    if arms and m.get("arm") not in arms: continue
    f = d / f"{m['matchId']}.json"
    info = T.get(m["map"].replace("-", "_"))
    if not f.exists() or not info: missing += 1; continue
    focus = m.get("focus", US)
    me = next(t for t in m["teams"] if t["name"] == focus or t.get("teamId") == focus)
    side = "teamA" if me["side"] == "a" else "teamB"
    groups = {g["id"]: g for g in info["groups"]}
    s = json.loads(f.read_text()); n += 1
    for e in s["events"]:
        if e["kind"] != "gemCollection": continue
        who = "focus" if e["owner"].get("team") == side else "opp"
        mi = MI[m["map"].replace("-", "_")]
        mine_spawn = mi["spawn_a"] if (e["owner"].get("team") == "teamA") else mi["spawn_b"]
        their_spawn = mi["spawn_b"] if (e["owner"].get("team") == "teamA") else mi["spawn_a"]
        for x in e["entries"]:
            if x["timestamp"]["round"] > upto or x.get("context") != "campGroup": continue
            g = groups.get(x["target"]["id"])
            if not g: continue
            p = (g["x"], g["y"])
            do = min(cheb(p, q) for q in mine_spawn); de = min(cheb(p, q) for q in their_spawn)
            depth = do / max(1, do + de)
            z = "own half" if depth < 0.45 else "middle" if depth < 0.55 else "enemy half"
            kind = "gold-only" if g["gems"] == 0 else "gems<20" if g["gems"] < 20 else "gems 20+"
            acc[(who, z, kind)] += 1
            acc[(who, z, "gems")] += float(x.get("value") or 0)
print(f"{n} games (skipped {missing} without camp table), captures per game in the first {upto} rounds")
for who in ("focus", "opp"):
    for z in ("own half", "middle", "enemy half"):
        print(f"  {who:<6}{z:<11} gold-only {acc[(who, z, 'gold-only')] / n:4.1f}  gems<20 {acc[(who, z, 'gems<20')] / n:4.1f}  "
              f"gems 20+ {acc[(who, z, 'gems 20+')] / n:4.1f}   gems {acc[(who, z, 'gems')] / n:6.1f}")
