#!/usr/bin/env python3
"""Candidates against the mean of several decision-identical baselines.

    vsbase.py BASE1,BASE2[,...] CAND [CAND ...]      # bench tags

One twin is one draw of the baseline's luck, and every candidate judged against
it shares that luck (two v101 twins differed by +14.9 gems). This averages the
baselines game by game, then clusters each candidate's difference by (map,
side) over the opponents, as clustered.py does. It also prints how far each
baseline sits from the others' mean, the size of a do-nothing change.
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
        us = "teamA" if s == "A" else "teamB"
        them = "teamB" if us == "teamA" else "teamA"
        g = {k["team"]: int(k["submittedGems"]) for k in d["teams"]}
        deaths = sum(int(c["metrics"]["deaths"]) for c in d["champions"] if c["team"] == us)
        out[(o, m, s)] = (g[us], float(g[us] > g[them]), deaths)
    return out


def mean_of(runs: list[dict]) -> dict:
    keys = set.intersection(*(set(r) for r in runs))
    return {k: tuple(sum(r[k][i] for r in runs) / len(runs) for i in range(3)) for k in keys}


def compare(cand: dict, base: dict, label: str) -> None:
    clusters = collections.defaultdict(list)
    for k, v in cand.items():
        if k in base:
            clusters[(k[1], k[2])].append(tuple(v[i] - base[k][i] for i in range(3)))
    cols = []
    for i in range(3):
        vals = [sum(x[i] for x in c) / len(c) for c in clusters.values()]
        mu = sum(vals) / len(vals)
        se = math.sqrt(sum((x - mu) ** 2 for x in vals) / (len(vals) - 1) / len(vals))
        cols.append((mu, se))
    (g, gs), (w, ws), (d, ds) = cols
    print(f"  {label:28} gems {g:+7.1f} (z {g / gs if gs else 0:+.2f})   win {w * 100:+5.1f} (z {w / ws if ws else 0:+.2f})"
          f"   deaths {d:+5.2f} (z {d / ds if ds else 0:+.2f})")


def main() -> None:
    base_tags, cands = sys.argv[1].split(","), sys.argv[2:]
    bases = [load(t) for t in base_tags]
    print(f"against the mean of {', '.join(base_tags)}")
    if len(bases) > 1:
        for i, t in enumerate(base_tags):
            compare(bases[i], mean_of([b for j, b in enumerate(bases) if j != i]), f"{t} (a baseline)")
    base = mean_of(bases)
    for t in cands:
        compare(load(t), base, t)


if __name__ == "__main__":
    main()
