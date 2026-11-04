#!/usr/bin/env python3
"""Group structure: distribution of teammates within 5 per living champion-round, and deaths within the next
10 rounds per 1,000 champion-rounds by that count; focus team vs opponents."""
import collections, json, sys
from pathlib import Path
US = "Milk and Potatoes"
def cheb(a, b): return max(abs(a[0]-b[0]), abs(a[1]-b[1]))
meta = json.loads(Path(sys.argv[1], "meta.json").read_text())
cnt = collections.Counter(); dth = collections.Counter()
for m in meta:
    f = Path(sys.argv[2], f"{m['matchId']}.jsonl")
    if not f.exists(): continue
    focus = m.get("focus", US)
    me = next(t for t in m["teams"] if t["name"] == focus or t.get("teamId") == focus)
    ours = 0 if me["side"] == "a" else 1
    rows = [json.loads(l) for l in f.read_text().splitlines()]
    rows = [r for r in rows if r["c"]]
    # death rounds per champion index
    deaths = collections.defaultdict(list)
    prev = {}
    for st in rows:
        for c in st["c"]:
            if prev.get(c[0]) and not c[7]: deaths[c[0]].append(st["r"])
        prev = {c[0]: c[7] for c in st["c"]}
    for st in rows:
        living = [c for c in st["c"] if c[7] and c[3] >= 0]
        for c in living:
            k = sum(1 for o in living if o[1] == c[1] and o[0] != c[0] and cheb((c[3], c[4]), (o[3], o[4])) <= 5)
            side = "focus" if c[1] == ours else "opp"
            k = min(k, 3)
            cnt[(side, k)] += 1
            if any(0 < d - st["r"] <= 10 for d in deaths[c[0]]): dth[(side, k)] += 1
for side in ("focus", "opp"):
    tot = sum(cnt[(side, k)] for k in range(4))
    print(f"{side:<6} " + "  ".join(f"{k}{'+' if k == 3 else ''} mates: {100 * cnt[(side, k)] / tot:4.1f}% of time, "
          f"death<=10r {1000 * dth[(side, k)] / max(1, cnt[(side, k)]):5.1f}/1k" for k in range(4)))
