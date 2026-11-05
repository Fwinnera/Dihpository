#!/usr/bin/env python3
"""Damage race in isolated duels (as duels.py): health each side loses per round while both are alive and
within 3 tiles, by our champion type, for the focus team and its opponents."""
import collections, json, sys
from pathlib import Path
US = "Milk and Potatoes"
T = ["ryth","vv","vend","cassi","issac","stel","prism","marc","willow","ren","varg","tavi","hor"]
def cheb(a, b): return max(abs(a[0]-b[0]), abs(a[1]-b[1]))
bdir, sdir = Path(sys.argv[1]), Path(sys.argv[2])
meta = json.loads((bdir / "meta.json").read_text())
dealt = collections.Counter(); taken = collections.Counter(); rounds = collections.Counter(); maxhp = collections.defaultdict(list)
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
            key = T[a[2]]
            # health lost this round (ignore heals): a's loss is damage taken, b's loss is damage dealt
            dealt[key] += max(0, b[5] - nb[5]); taken[key] += max(0, a[5] - na[5]); rounds[key] += 1
            maxhp[key].append(a[6]); maxhp["opp_" + key].append(b[6])
print(f"{'our champion':<12}{'duel rounds':>12}{'dealt/round':>13}{'taken/round':>13}{'ratio':>7}")
for k in sorted(rounds, key=lambda k: -rounds[k]):
    if rounds[k] < 30: continue
    print(f"{k:<12}{rounds[k]:>12}{dealt[k] / rounds[k]:>13.0f}{taken[k] / rounds[k]:>13.0f}{dealt[k] / max(1, taken[k]):>7.2f}")
tr = sum(rounds.values())
print(f"{'all':<12}{tr:>12}{sum(dealt.values()) / tr:>13.0f}{sum(taken.values()) / tr:>13.0f}{sum(dealt.values()) / max(1, sum(taken.values())):>7.2f}")
