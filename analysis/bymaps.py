#!/usr/bin/env python3
"""Paired comparison split by map groups: where does a change gain or lose?

    bymaps.py BASE,BASE2 CAND,CAND2 --group stall=01the-farm,01big-world --group party=00contest,00stampede

Each comma list is pooled game for game (same opponent, map and side), as
pooled.py does; every map not named in a --group falls in "other". Prints gems
and win rate per group with paired standard errors, then the ten maps that move
most.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
from pathlib import Path

BENCH = Path(__file__).resolve().parent.parent / "ws/bench"


def load(tag: str) -> dict:
    out = {}
    for f in (BENCH / tag).glob("*__*__*.json"):
        o, m, s = f.stem.split("__")
        d = json.loads(f.read_text())
        side, other = ("teamA", "teamB") if s == "A" else ("teamB", "teamA")
        g = {t["team"]: t for t in d["teams"]}
        out[(o, m, s)] = (float(g[side]["submittedGems"]), float(d["match"]["outcome"] == side))
    return out


def pooled(tags: str) -> dict:
    arms = [load(t) for t in tags.split(",")]
    keys = set.intersection(*(set(a) for a in arms))
    return {k: tuple(sum(a[k][i] for a in arms) / len(arms) for i in range(2)) for k in keys}


def mean_se(xs: list[float]) -> tuple[float, float]:
    n = len(xs)
    m = sum(xs) / n
    return m, math.sqrt(sum((x - m) ** 2 for x in xs) / max(1, n - 1) / n)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("base"); ap.add_argument("cand")
    ap.add_argument("--group", action="append", default=[], help="name=map,map")
    a = ap.parse_args()
    base, cand = pooled(a.base), pooled(a.cand)
    groups = {}
    for spec in a.group:
        name, maps = spec.split("=", 1)
        for m in maps.split(","):
            groups[m] = name
    diffs = collections.defaultdict(list)
    per_map = collections.defaultdict(list)
    for k in base.keys() & cand.keys():
        d = (cand[k][0] - base[k][0], 100 * (cand[k][1] - base[k][1]))
        diffs[groups.get(k[1], "other")].append(d)
        diffs["all"].append(d)
        per_map[k[1]].append(d[0])
    print(f"{'group':10}{'games':>6}{'gems':>9}{'se':>7}{'z':>6}{'win %':>8}{'se':>6}")
    for name in sorted(diffs, key=lambda n: (n == "all", n)):
        g, w = zip(*diffs[name])
        gm, gs = mean_se(list(g)); wm, ws = mean_se(list(w))
        print(f"{name:10}{len(g):6}{gm:+9.1f}{gs:7.1f}{gm / gs if gs else 0:+6.2f}{wm:+8.1f}{ws:6.1f}")
    print("\nmaps that move most (mean gems change):")
    for m, v in sorted(per_map.items(), key=lambda kv: -abs(sum(kv[1]) / len(kv[1])))[:10]:
        print(f"  {m:24}{len(v):4}{sum(v) / len(v):+9.1f}  [{groups.get(m, 'other')}]")


if __name__ == "__main__":
    main()
