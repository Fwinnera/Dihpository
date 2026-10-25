#!/usr/bin/env python3
"""Choose one omni arm per map-side, and estimate honestly what the choice is worth.

    pick_arms.py PREFIX [--seeds 1,2,3,4] [--prior K] [--top N] [--table]

Reads ws/bench/h2h_<PREFIX>_<arm>_<seed>_eq (screen_omni.sh). For every map-side
each arm's record is shrunk toward that arm's overall rate with K pseudo-games,
and the best shrunk rate wins (ties: arm 0, then the lower arm). --top keeps only
the N arms with the best overall records.

Picking the best of many arms on a few games each flatters the pick, so the
honest number is leave-one-seed-out: choose on the other seeds, score on the
held-out one. --table prints rows for policy_table.h, chosen on every seed.
"""
from __future__ import annotations

import collections
import json
import re
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parent.parent / "ws/bench"


def load_tag(tag: str):
    cache = BENCH / tag / "_wins.txt"
    if cache.exists():
        rows = [line.split() for line in cache.read_text().splitlines()]
        if len(rows) == 80:
            return {(m, s): w == "1" for m, s, w in rows}
    out = {}
    for f in (BENCH / tag).glob("*__*__*.json"):
        _, m, s = f.stem.split("__")
        us = "teamA" if s == "A" else "teamB"
        d = json.loads(f.read_text())
        g = {k["team"]: int(k["submittedGems"]) for k in d["teams"]}
        them = "teamB" if us == "teamA" else "teamA"
        out[(m, s)] = g[us] > g[them]
    if len(out) == 80:
        cache.write_text("".join(f"{m} {s} {int(w)}\n" for (m, s), w in sorted(out.items())))
    return out


def load(prefix: str):
    data = collections.defaultdict(dict)  # arm -> seed -> {mapside: win}
    pat = re.compile(rf"^h2h_{re.escape(prefix)}_(\d+)_(\d+)_eq$")
    for p in BENCH.iterdir():
        m = pat.match(p.name)
        if not m or not p.is_dir():
            continue
        games = load_tag(p.name)
        if len(games) == 80:
            data[int(m.group(1))][int(m.group(2))] = games
    return data


def choose(data, seeds, prior, arms):
    keys = sorted({k for a in arms for s in seeds if s in data[a] for k in data[a][s]})
    overall = {}
    for a in arms:
        w = sum(v for s in seeds if s in data[a] for v in data[a][s].values())
        n = sum(len(data[a][s]) for s in seeds if s in data[a])
        overall[a] = w / n if n else 0
    pick = {}
    for k in keys:
        best, best_score = None, -1.0
        for a in arms:
            res = [data[a][s][k] for s in seeds if s in data[a] and k in data[a][s]]
            if not res:
                continue
            score = (sum(res) + prior * overall[a]) / (len(res) + prior)
            if score > best_score + 1e-12:
                best, best_score = a, score
        pick[k] = best
    return pick, overall


def main(argv):
    prefix = argv[0]
    seeds = [1, 2, 3, 4]
    prior, top = 2.0, None
    if "--seeds" in argv:
        seeds = [int(x) for x in argv[argv.index("--seeds") + 1].split(",")]
    if "--prior" in argv:
        prior = float(argv[argv.index("--prior") + 1])
    if "--top" in argv:
        top = int(argv[argv.index("--top") + 1])
    data = load(prefix)
    complete = sorted(a for a in data if all(s in data[a] for s in seeds))
    if not complete:
        print("no arm has every seed yet")
        return
    rates = {a: sum(sum(data[a][s].values()) for s in seeds) / len(seeds) for a in complete}
    arms = sorted(complete, key=lambda a: -rates[a])
    if top:
        arms = arms[:top]
    print(f"{len(complete)} arms with seeds {seeds}; mean wins of 80 per arm:")
    print("  " + "  ".join(f"{a}:{rates[a]:.1f}" for a in sorted(complete, key=lambda a: -rates[a])))
    # leave-one-seed-out
    cv = []
    for h in seeds:
        rest = [s for s in seeds if s != h]
        pick, _ = choose(data, rest, prior, arms)
        cv.append(sum(data[pick[k]][h][k] for k in pick))
    base = [sum(data[0][s].values()) for s in seeds] if 0 in data else []
    print(f"leave-one-seed-out wins of 80 (prior {prior}, {len(arms)} arms): {cv}  mean {sum(cv) / len(cv):.1f}"
          + (f"   arm 0 alone: {base} mean {sum(base) / len(base):.1f}" if base else ""))
    pick, overall = choose(data, seeds, prior, arms)
    insample = sum(sum(data[pick[k]][s][k] for s in seeds) for k in pick) / len(seeds)
    print(f"in-sample (flattering) wins of 80 with all seeds: {insample:.1f}")
    if "--table" in argv:
        by_map = collections.defaultdict(dict)
        for (m, s), a in pick.items():
            by_map[m][s] = a
        for m in sorted(by_map):
            rec = {s: sum(data[by_map[m][s]][x][(m, s)] for x in seeds) for s in "AB"}
            print(f"  {m:24} A arm {by_map[m]['A']:2} ({rec['A']}/{len(seeds)})   B arm {by_map[m]['B']:2} ({rec['B']}/{len(seeds)})")


if __name__ == "__main__":
    main(sys.argv[1:])
