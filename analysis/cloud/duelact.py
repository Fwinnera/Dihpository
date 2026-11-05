#!/usr/bin/env python3
"""What each side does on its turns during isolated duels (as duels.py): attack the duel opponent, attack
something else (a camp), cast, move, from the replay's action stream (actions.mjs: code 4 move, 5 attack,
6 cast, 8 end of turn)."""
import collections, json, sys
from pathlib import Path
US = "Milk and Potatoes"
T = ["ryth","vv","vend","cassi","issac","stel","prism","marc","willow","ren","varg","tavi","hor"]
def cheb(a, b): return max(abs(a[0]-b[0]), abs(a[1]-b[1]))
bdir, sdir, adir = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
bytype = len(sys.argv) > 4
meta = json.loads((bdir / "meta.json").read_text())
K = ["turns", "hit foe", "hit other", "cast", "moved", "no action", "dist1", "dist2", "dist3"]
S = {side: collections.defaultdict(collections.Counter) for side in ("focus", "opp")}
for m in meta:
    f = sdir / f"{m['matchId']}.jsonl"; fa = adir / f"{m['matchId']}.jsonl"
    if not (f.exists() and fa.exists()): continue
    focus = m.get("focus", US)
    me = next(t for t in m["teams"] if t["name"] == focus or t.get("teamId") == focus); ours = 0 if me["side"] == "a" else 1
    acts = collections.defaultdict(list)
    for l in fa.read_text().splitlines():
        r = json.loads(l)
        if r[8] and r[1] >= 0: acts[(r[0], r[1])].append(r)
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
            for side, x, y, nyy in (("focus", a, b, nb), ("opp", b, a, na)):
                key = T[x[2]] if bytype else "all"
                c = S[side][key]
                c["turns"] += 1
                c[f"dist{cheb((x[3], x[4]), (y[3], y[4]))}"] += 1
                spots = {(y[3], y[4]), (nyy[3], nyy[4])}
                for r in acts.get((st["r"], y[0]), []):
                    if r[2] == 4: spots.add((r[5], r[6]))
                mine = acts.get((st["r"], x[0]), [])
                codes = [r[2] for r in mine]
                hit_foe = any(r[2] == 5 and (r[5], r[6]) in spots for r in mine)
                hit_other = any(r[2] == 5 and (r[5], r[6]) not in spots for r in mine)
                if hit_foe: c["hit foe"] += 1
                if hit_other: c["hit other"] += 1
                if 6 in codes: c["cast"] += 1
                if 4 in codes: c["moved"] += 1
                if not any(k in codes for k in (4, 5, 6)): c["no action"] += 1
for side in ("focus", "opp"):
    print(f"## {side} side")
    print(f"{'':<10}" + "".join(f"{k:>10}" for k in K))
    for key, c in sorted(S[side].items(), key=lambda kv: -kv[1]["turns"]):
        if c["turns"] < 30: continue
        print(f"{key:<10}{c['turns']:>10}" + "".join(f"{100 * c[k] / c['turns']:>9.0f}%" for k in K[1:]))
