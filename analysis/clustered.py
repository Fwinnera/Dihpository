#!/usr/bin/env python3
"""Paired comparison with an honest standard error: games clustered by map and side.

Three of the four default opponents (greatsage, base, boss_focus) are near
clones: on 52 of 80 map-sides they produce games with identical gem totals, for
v97 and for v98 alike. A paired SE over all games counts those copies as
independent and understates the uncertainty. This averages each (map, side)
over the opponents of one bench tag before taking the SE, which treats the
opponents within a tag as one draw: conservative where they differ.

    clustered.py BASE CAND [BASE2 CAND2 ...]      # pairs of bench tags

Prints the plain paired result and the clustered one, for gems and win rate.
"""
from __future__ import annotations

import collections
import json
import math
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parent.parent / "ws/bench"


def load(tag: str) -> dict:
    out = {}
    for f in (BENCH / tag).glob("*__*__*.json"):
        o, m, s = f.stem.split("__")
        d = json.loads(f.read_text())
        side = "teamA" if s == "A" else "teamB"
        gems = {t["team"]: float(t["submittedGems"]) for t in d["teams"]}
        out[(o, m, s)] = (gems[side], 100.0 * (d["match"]["outcome"] == side))
    return out


def mean_se(xs: list[float]) -> tuple[float, float]:
    m = sum(xs) / len(xs)
    return m, math.sqrt(sum((x - m) ** 2 for x in xs) / max(1, len(xs) - 1) / len(xs))


def main(tags: list[str]) -> None:
    if len(tags) < 2 or len(tags) % 2:
        sys.exit(__doc__)
    plain = ([], [])
    clusters = collections.defaultdict(lambda: ([], []))
    for base, cand in zip(tags[::2], tags[1::2]):
        b, c = load(base), load(cand)
        for k in b.keys() & c.keys():
            for i in (0, 1):
                d = c[k][i] - b[k][i]
                plain[i].append(d)
                clusters[(base, k[1], k[2])][i].append(d)
    print(f"{len(plain[0])} paired games, {len(clusters)} map-side clusters")
    for i, label in ((0, "gems submitted"), (1, "win rate %")):
        m, se = mean_se(plain[i])
        cm, cse = mean_se([sum(v[i]) / len(v[i]) for v in clusters.values()])
        print(f"  {label:15} {m:+8.1f}   plain se {se:5.1f} (z {m / se if se else 0:+.2f})"
              f"   clustered se {cse:5.1f} (z {cm / cse if cse else 0:+.2f})")


if __name__ == "__main__":
    main(sys.argv[1:])
