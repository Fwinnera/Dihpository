#!/usr/bin/env python3
"""How a team's champions of one type move (decoded states): nearest teammate distance, share of living rounds
with an enemy within 3, dashes (2+ tile moves) per 100 living rounds, and who it stays closest to."""
import collections, json, statistics, sys
from pathlib import Path
US = "Milk and Potatoes"
T = ["ryth","vesper_vale","vendetta","cassi","issac","stellar","prism","marcella","willow","ren","varg","tavi","heart_of_ruin"]
def cheb(a, b): return max(abs(a[0]-b[0]), abs(a[1]-b[1]))
bdir, sdir, want = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
meta = json.loads((bdir / "meta.json").read_text())
near, close_enemy, alive, dashes, buddy = [], 0, 0, 0, collections.Counter()
for m in meta:
    f = sdir / f"{m['matchId']}.jsonl"
    if not f.exists(): continue
    focus = m.get("focus", US)
    me = next(t for t in m["teams"] if t["name"] == focus or t.get("teamId") == focus); ours = 0 if me["side"] == "a" else 1
    prev = None
    for line in f.read_text().splitlines():
        st = json.loads(line)
        h = next((c for c in st["c"] if c[1] == ours and c[2] == want), None)
        if not h: continue
        if h[7] and h[3] >= 0:
            alive += 1
            mates = [(cheb((h[3], h[4]), (c[3], c[4])), T[c[2]]) for c in st["c"] if c[1] == ours and c[0] != h[0] and c[7] and c[3] >= 0]
            if mates:
                d, who = min(mates); near.append(d); buddy[who] += 1
            if any(c[1] != ours and c[7] and c[3] >= 0 and cheb((h[3], h[4]), (c[3], c[4])) <= 3 for c in st["c"]): close_enemy += 1
            if prev and prev[7] and prev[3] >= 0 and cheb((h[3], h[4]), (prev[3], prev[4])) >= 2: dashes += 1
        prev = h
print(f"{T[want]}: {alive} living rounds; nearest teammate median {statistics.median(near) if near else 'n/a'}, "
      f"within 5 {100 * sum(1 for d in near if d <= 5) / max(1, len(near)):.0f}%; enemy within 3: {100 * close_enemy / max(1, alive):.1f}%; "
      f"dashes per 100 living rounds {100 * dashes / max(1, alive):.1f}")
tot = sum(buddy.values())
print("  nearest teammate is:", ", ".join(f"{k} {100 * v / tot:.0f}%" for k, v in buddy.most_common(5)))
