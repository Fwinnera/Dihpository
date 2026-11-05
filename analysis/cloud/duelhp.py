#!/usr/bin/env python3
"""Duel damage race split by max-health ratio (a proxy for how many shards each side has bought)."""
import collections, json, sys
from pathlib import Path
US = "Milk and Potatoes"
T = ["ryth","vv","vend","cassi","issac","stel","prism","marc","willow","ren","varg","tavi","hor"]
def cheb(a, b): return max(abs(a[0]-b[0]), abs(a[1]-b[1]))
bdir, sdir = Path(sys.argv[1]), Path(sys.argv[2])
meta = json.loads((bdir / "meta.json").read_text())
B = collections.defaultdict(lambda: [0, 0, 0])   # bucket -> dealt, taken, rounds
same = collections.defaultdict(lambda: [0, 0, 0])  # same champion type, same max hp within 5%
gold = collections.defaultdict(list)
for m in meta:
    f = sdir / f"{m['matchId']}.jsonl"
    if not f.exists(): continue
    focus = m.get("focus", US)
    me = next(t for t in m["teams"] if t["name"] == focus or t.get("teamId") == focus); ours = 0 if me["side"] == "a" else 1
    rows = [json.loads(l) for l in f.read_text().splitlines()]; rows = [r for r in rows if r["c"]]
    for st, nx in zip(rows, rows[1:]):
        living = [c for c in st["c"] if c[7] and c[3] >= 0]
        for a in living:
            if a[1] != ours: continue
            foes = [b for b in living if b[1] != ours and cheb((a[3], a[4]), (b[3], b[4])) <= 3]
            if len(foes) != 1: continue
            b = foes[0]
            if any(c[0] not in (a[0], b[0]) and (cheb((a[3], a[4]), (c[3], c[4])) <= 6 or cheb((b[3], b[4]), (c[3], c[4])) <= 6) for c in living): continue
            na = next(c for c in nx["c"] if c[0] == a[0]); nb = next(c for c in nx["c"] if c[0] == b[0])
            if not (na[7] and nb[7]): continue
            r = a[6] / b[6]
            k = "<0.85" if r < 0.85 else "0.85-0.95" if r < 0.95 else "0.95-1.05" if r <= 1.05 else "1.05-1.15" if r <= 1.15 else ">1.15"
            d, t = max(0, b[5] - nb[5]), max(0, a[5] - na[5])
            B[k][0] += d; B[k][1] += t; B[k][2] += 1
            if a[2] == b[2] and 0.95 <= r <= 1.05:
                same[T[a[2]]][0] += d; same[T[a[2]]][1] += t; same[T[a[2]]][2] += 1
print(f"{'maxhp ours/theirs':<18}{'rounds':>8}{'dealt':>8}{'taken':>8}{'ratio':>7}")
for k in ["<0.85", "0.85-0.95", "0.95-1.05", "1.05-1.15", ">1.15"]:
    d, t, n = B[k]
    if n: print(f"{k:<18}{n:>8}{d / n:>8.0f}{t / n:>8.0f}{d / max(1, t):>7.2f}")
print("same champion type, max health within 5%:")
for k, (d, t, n) in sorted(same.items(), key=lambda kv: -kv[1][2]):
    if n >= 10: print(f"  {k:<16}{n:>8}{d / n:>8.0f}{t / n:>8.0f}{d / max(1, t):>7.2f}")
