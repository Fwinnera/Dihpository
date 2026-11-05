#!/usr/bin/env python3
"""Isolated duels from decoded states: one champion of each team within 3 tiles, no other living champion within
6 of either, at the start; the duel ends when one of the two dies within 15 rounds. Who wins, by matchup type,
and health at the start."""
import collections, json, sys
from pathlib import Path
US = "Milk and Potatoes"
T = ["ryth","vv","vend","cassi","issac","stel","prism","marc","willow","ren","varg","tavi","hor"]
def cheb(a, b): return max(abs(a[0]-b[0]), abs(a[1]-b[1]))
bdir, sdir = Path(sys.argv[1]), Path(sys.argv[2])
meta = json.loads((bdir / "meta.json").read_text())
res = collections.Counter(); byt = collections.defaultdict(lambda: [0, 0]); hpdiff = []
for m in meta:
    f = sdir / f"{m['matchId']}.jsonl"
    if not f.exists(): continue
    focus = m.get("focus", US)
    me = next(t for t in m["teams"] if t["name"] == focus or t.get("teamId") == focus); ours = 0 if me["side"] == "a" else 1
    rows = [json.loads(l) for l in f.read_text().splitlines()]
    rows = [r for r in rows if r["c"]]
    busy_until = {}
    for i, st in enumerate(rows):
        living = [c for c in st["c"] if c[7] and c[3] >= 0]
        for a in living:
            if a[1] != ours or busy_until.get(a[0], -1) >= st["r"]: continue
            foes = [b for b in living if b[1] != ours and cheb((a[3], a[4]), (b[3], b[4])) <= 3]
            if len(foes) != 1: continue
            b = foes[0]
            if busy_until.get(b[0], -1) >= st["r"]: continue
            others = [c for c in living if c[0] not in (a[0], b[0]) and (cheb((a[3], a[4]), (c[3], c[4])) <= 6 or cheb((b[3], b[4]), (c[3], c[4])) <= 6)]
            if others: continue
            winner = None
            for st2 in rows[i + 1:i + 16]:
                ca = next(c for c in st2["c"] if c[0] == a[0]); cb = next(c for c in st2["c"] if c[0] == b[0])
                if not ca[7] and cb[7]: winner = "them"; break
                if not cb[7] and ca[7]: winner = "us"; break
                if not ca[7] and not cb[7]: winner = "both"; break
            if winner is None: continue
            res[winner] += 1
            key = (T[a[2]], T[b[2]])
            byt[key][0] += winner == "us"; byt[key][1] += 1
            hpdiff.append((a[5] / max(1, a[6]) - b[5] / max(1, b[6]), winner))
            busy_until[a[0]] = busy_until[b[0]] = st["r"] + 15
n = sum(res.values())
print(f"{n} duels: focus wins {res['us']} ({100 * res['us'] / max(1, n):.0f}%), loses {res['them']}, both die {res['both']}")
even = [w for d, w in hpdiff if abs(d) < 0.15]
print(f"  at similar health (within 15%): {len(even)} duels, focus wins {100 * sum(1 for w in even if w == 'us') / max(1, len(even)):.0f}%")
print("  most common matchups (ours v theirs: wins/duels):", ", ".join(f"{a}v{b} {w}/{k}" for (a, b), (w, k) in sorted(byt.items(), key=lambda kv: -kv[1][1])[:10]))
