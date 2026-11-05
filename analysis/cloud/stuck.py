#!/usr/bin/env python3
"""Wasted turns in contact: alive, an enemy champion within 3 (true positions), and no move/attack/cast, not a
recall (11) or out-of-fuel (26) turn; by health band, per game, for the focus team and its opponents."""
import collections, json, sys
from pathlib import Path
US = "Milk and Potatoes"
def cheb(a, b): return max(abs(a[0]-b[0]), abs(a[1]-b[1]))
bdir, sdir, adir = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
arm = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] != "-" else None
meta = json.loads((bdir / "meta.json").read_text())
W = {"focus": collections.Counter(), "opp": collections.Counter()}; games = 0
for m in meta:
    if arm and not m.get("arm", "").startswith(arm): continue
    fs = sdir / f"{m['matchId']}.jsonl"; fa = adir / f"{m['matchId']}.jsonl"
    if not (fs.exists() and fa.exists()): continue
    focus = m.get("focus", US)
    me = next(t for t in m["teams"] if t["name"] == focus or t.get("teamId") == focus); ours = 0 if me["side"] == "a" else 1
    games += 1
    acts = collections.defaultdict(list)
    for l in fa.read_text().splitlines():
        r = json.loads(l)
        if isinstance(r, dict): continue
        if r[8] and r[1] >= 0: acts[(r[0], r[1])].append(r[2])
    rows = [json.loads(l) for l in fs.read_text().splitlines()]; rows = [r for r in rows if r["c"]]
    for st in rows:
        living = [c for c in st["c"] if c[7] and c[3] >= 0]
        for a in living:
            if not any(b[1] != a[1] and cheb((a[3], a[4]), (b[3], b[4])) <= 3 for b in living): continue
            side = "focus" if a[1] == ours else "opp"
            cs = acts.get((st["r"], a[0]), [])
            W[side]["contact turns"] += 1
            if any(k in cs for k in (4, 5, 6)): continue
            if 11 in cs: W[side]["recall"] += 1; continue
            if 26 in cs: W[side]["out of fuel"] += 1; continue
            f = a[5] / max(1, a[6])
            W[side]["wasted, health <45%" if f < 0.45 else "wasted, health >=45%"] += 1
for side in ("focus", "opp"):
    c = W[side]
    print(f"{side:<6} per game: contact turns {c['contact turns'] / games:.0f}; " + ", ".join(f"{k} {c[k] / games:.1f}" for k in ("wasted, health <45%", "wasted, health >=45%", "recall", "out of fuel")))
