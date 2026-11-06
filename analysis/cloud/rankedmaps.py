#!/usr/bin/env python3
"""Our ranked games on engine 3.0.0 from downloaded `cambc matches list` pages: overall, by controller mode
(party = Willow drafted) and roster size, by map; optionally only games played by given live versions'
time windows (start,end ISO prefixes)."""
import collections, glob, json, sys
pages = sys.argv[1]
since = sys.argv[2] if len(sys.argv) > 2 else ""
until = sys.argv[3] if len(sys.argv) > 3 else "9999"
games = {}
for f in sorted(glob.glob(pages + "/p*.json")):
    try: d = json.load(open(f))
    except Exception: continue
    for m in d.get("matches", []): games[m["matchId"]] = m
e3 = [m for m in games.values() if all(t.get("engineVersion") == "3.0.0" for t in m["teams"]) and m.get("status") == "finished"
      and since <= m["createdAt"] < until]
us = lambda m: next(t for t in m["teams"] if t["name"] == "Milk and Potatoes")
w = sum(us(m)["result"] == "win" for m in e3)
print(f"games {len(e3)} ({min(m['createdAt'] for m in e3)[:16]} to {max(m['createdAt'] for m in e3)[:16]}): win rate {w / len(e3):.3f}")
mode = collections.defaultdict(lambda: [0, 0])
bymap = collections.defaultdict(lambda: [0, 0, set()])
for m in e3:
    me = us(m); party = "7" in me["characters"]
    mode[("party" if party else "solo", len(me["characters"]))][0] += me["result"] == "win"
    mode[("party" if party else "solo", len(me["characters"]))][1] += 1
    b = bymap[m["map"]]; b[0] += me["result"] == "win"; b[1] += 1; b[2].add("party" if party else "solo")
for k, (a, n) in sorted(mode.items()): print(f"  {k}: {a}/{n} = {a / n:.2f}")
rows = sorted(((a / n, mp, a, n, "/".join(sorted(md))) for mp, (a, n, md) in bymap.items() if n >= 8), key=lambda t: t[0])
print("maps with >= 8 games, worst 25:")
for r, mp, a, n, md in rows[:25]: print(f"  {mp:<24} {a:>3}/{n:<3} {r:.2f}  {md}")
print("best 8:", ", ".join(f"{mp} {a}/{n}" for r, mp, a, n, md in rows[-8:]))
