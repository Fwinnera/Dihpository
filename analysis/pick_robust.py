#!/usr/bin/env python3
"""Choose omni arms per map-side for robustness to small changes in the opponent.

    pick_robust.py OPP[,OPP...] [--own 0.25] [--write FILE] [--show]

Reads h2h_o3_<arm>_0_<opp> (screen_robust.sh: our build unperturbed, as
submitted, against each opponent build). An arm's score on a map-side is its
wins over those opponents, plus --own times its wins over our own re-rolled
seeds 1-4 (h2h_o3_<arm>_<seed>_eq) as a tie-break; then its overall record.
Leave-one-opponent-out estimates what the choice is worth on an opponent build
it was not chosen on. --write saves "map side arm" lines for mktable.py --picks.
"""
from __future__ import annotations

import collections
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pick_arms  # noqa: E402

BENCH = pick_arms.BENCH


def load(opps):
    data = collections.defaultdict(dict)  # arm -> opp -> {mapside: win}
    for p in BENCH.iterdir():
        m = re.match(r"^h2h_o3_(\d+)_0_(\w+)$", p.name)
        if m and m.group(2) in opps:
            games = pick_arms.load_tag(p.name)
            if len(games) == 80:
                data[int(m.group(1))][m.group(2)] = games
    return data


def choose(data, own, opps, arms, own_weight):
    keys = sorted({k for a in arms for o in opps for k in data[a][o]})
    overall = {a: sum(sum(data[a][o].values()) for o in opps) for a in arms}
    pick = {}
    for k in keys:
        def score(a):
            s = sum(data[a][o][k] for o in opps)
            s += own_weight * sum(own[a][x][k] for x in own.get(a, {}))
            return (s, overall[a], -a)
        pick[k] = max(arms, key=score)
    return pick


def main(argv):
    opps = argv[0].split(",")
    own_weight = float(argv[argv.index("--own") + 1]) if "--own" in argv else 0.25
    data = load(opps)
    arms = sorted(a for a in data if all(o in data[a] for o in opps))
    own = {a: s for a, s in pick_arms.load("o3").items() if a in arms}
    print(f"{len(arms)} arms against {opps}")
    rates = {a: sum(sum(data[a][o].values()) for o in opps) / len(opps) for a in arms}
    print("  mean wins of 80: " + "  ".join(f"{a}:{rates[a]:.1f}" for a in sorted(arms, key=lambda a: -rates[a])[:15]))
    if len(opps) > 1:
        cv = []
        for h in opps:
            rest = [o for o in opps if o != h]
            pick = choose(data, own, rest, arms, own_weight)
            cv.append(sum(data[pick[k]][h][k] for k in pick))
        print(f"leave-one-opponent-out wins of 80: {cv}  mean {sum(cv) / len(cv):.1f}"
              f"   arm 0 alone: {[sum(data[0][o].values()) for o in opps]}")
    pick = choose(data, own, opps, arms, own_weight)
    insample = sum(sum(data[pick[k]][o][k] for o in opps) for k in pick) / len(opps)
    print(f"in-sample (flattering) wins of 80: {insample:.1f}")
    if "--show" in argv:
        for k in sorted(pick):
            print(f"  {k[0]:24} {k[1]} arm {pick[k]:2}  {sum(data[pick[k]][o][k] for o in opps)}/{len(opps)}")
    if "--write" in argv:
        Path(argv[argv.index("--write") + 1]).write_text("".join(f"{m} {s} {a}\n" for (m, s), a in sorted(pick.items())))


if __name__ == "__main__":
    main(sys.argv[1:])
