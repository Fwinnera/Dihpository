#!/usr/bin/env python3
"""One-line mechanism summary of a set of decoded games (meta.json + states), from the focus team's view:
wins, deaths a game (ours/theirs) by zone, share of time alone (no teammate within 5), death hazard alone.

    labmech.py BUNDLE_DIR STATES_DIR [ARM ...]    (ARM filters meta records by their `arm` field)
"""
import collections
import json
import sys
from pathlib import Path

US = "Milk and Potatoes"
MAPINFO = {k.replace("-", "_"): v for k, v in json.loads(Path("/home/user/runs/mapinfo/mapinfo.json").read_text()).items()}


def cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def main(bdir, sdir, arms):
    meta = json.loads(Path(bdir, "meta.json").read_text())
    if arms:
        meta = [m for m in meta if m.get("arm") in arms]
    games = wins = 0
    deaths = collections.Counter()
    alone = total = alone_d = 0
    per_game = []
    for m in meta:
        f = Path(sdir, f"{m['matchId']}.jsonl")
        if not f.exists():
            continue
        focus = m.get("focus", US)
        me = next(t for t in m["teams"] if t["name"] == focus or t.get("teamId") == focus)
        ours = 0 if me["side"] == "a" else 1
        mi = MAPINFO.get(m["map"].replace("-", "_"))
        own, enemy = (mi["spawn_a"], mi["spawn_b"]) if ours == 0 else (mi["spawn_b"], mi["spawn_a"])
        rows = [json.loads(l) for l in f.read_text().splitlines()]
        rows = [r for r in rows if r["c"]]
        games += 1
        wins += me.get("result") == "win"
        prev = {}
        died = collections.defaultdict(list)
        g = collections.Counter()
        for st in rows:
            for c in st["c"]:
                p = prev.get(c[0])
                if p and p[7] and not c[7] and p[3] >= 0:
                    pos = (p[3], p[4])
                    do = min(cheb(pos, q) for q in own)
                    de = min(cheb(pos, q) for q in enemy)
                    depth = do / max(1, do + de)
                    z = "home" if depth < 0.45 else "mid" if depth < 0.55 else "away"
                    who = "us" if c[1] == ours else "them"
                    deaths[(who, z)] += 1
                    g[who] += 1
                    died[c[0]].append(st["r"])
            prev = {c[0]: c for c in st["c"]}
        for st in rows:
            living = [c for c in st["c"] if c[7] and c[3] >= 0 and c[1] == ours]
            for c in living:
                total += 1
                if all(cheb((c[3], c[4]), (o[3], o[4])) > 5 for o in living if o[0] != c[0]):
                    alone += 1
                    if any(0 < d - st["r"] <= 10 for d in died[c[0]]):
                        alone_d += 1
        per_game.append((g["us"], g["them"]))
    n = max(1, games)
    us = sum(v for (w, z), v in deaths.items() if w == "us") / n
    them = sum(v for (w, z), v in deaths.items() if w == "them") / n
    sd = (sum((a - us) ** 2 for a, b in per_game) / max(1, n - 1)) ** 0.5
    print(f"{games} games, {wins} won | our deaths {us:.2f} (se {sd / n ** 0.5:.2f}; home {deaths[('us', 'home')] / n:.2f}, "
          f"mid {deaths[('us', 'mid')] / n:.2f}, away {deaths[('us', 'away')] / n:.2f}) | their deaths {them:.2f} "
          f"(our home {deaths[('them', 'home')] / n:.2f}) | alone {100 * alone / max(1, total):.1f}%, "
          f"hazard alone {1000 * alone_d / max(1, alone):.1f}/1k")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3:])
