#!/usr/bin/env python3
"""Between consecutive camp captures of the same champion (gemCollection campGroup events): distance (Chebyshev)
and rounds elapsed, focus vs opponents; plus captures per champion per 1,000 living rounds."""
import collections, json, statistics, sys
from pathlib import Path
US = "Milk and Potatoes"
def cheb(a, b): return max(abs(a[0]-b[0]), abs(a[1]-b[1]))
bdir = Path(sys.argv[1]); arms = set(sys.argv[2].split(",")) if len(sys.argv) > 2 and sys.argv[2] else None
meta = json.loads((bdir / "meta.json").read_text())
dist = collections.defaultdict(list); gap = collections.defaultdict(list); caps = collections.Counter(); deaths = collections.Counter()
for m in meta:
    if arms and m.get("arm") not in arms: continue
    f = bdir / f"{m['matchId']}.json"
    if not f.exists(): continue
    focus = m.get("focus", US)
    me = next(t for t in m["teams"] if t["name"] == focus or t.get("teamId") == focus); side = "teamA" if me["side"] == "a" else "teamB"
    s = json.loads(f.read_text())
    seq = collections.defaultdict(list)
    for e in s["events"]:
        who = "focus" if e["owner"].get("team") == side else "opp"
        if e["kind"] == "gemCollection":
            for x in e["entries"]:
                if x.get("context") == "campGroup": seq[(who, e["owner"]["id"])].append((x["timestamp"]["round"], x["x"], x["y"]))
        if e["kind"] == "death": deaths[who] += len(e["entries"])
    for (who, cid), rows in seq.items():
        rows.sort(); caps[who] += len(rows)
        for a, b in zip(rows, rows[1:]):
            dist[who].append(cheb((a[1], a[2]), (b[1], b[2]))); gap[who].append(b[0] - a[0])
for who in ("focus", "opp"):
    d = dist[who]; g = gap[who]
    print(f"{who:<6} captures {caps[who]}, hops: median distance {statistics.median(d):.0f} (mean {statistics.mean(d):.1f}), median rounds between {statistics.median(g):.0f} (mean {statistics.mean(g):.1f})")
