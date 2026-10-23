#!/usr/bin/env python3
"""Paired comparison of bench tags: the standard error of the change, not of an arm.

`bench.py --compare` prints the subject arm's own standard error beside each
change. That is the spread of one mean, not of a difference between two, so a
change read against it is overstated by about root two when the arms are
independent. The pool is matched game for game -- same opponent, map and side --
so the honest error is the one of the per-game differences, which this computes.

    paired.py BASE TAG [TAG ...]        # tags are folders under ws/bench

For each candidate: per-metric mean change with its paired standard error, the
gem change's 95% bootstrap interval and sign test over the games that diverged,
and the per-opponent split. Games present in only one arm are dropped and
counted; bit-identical games are kept in the means (they are real zeros) but
reported, since a pool where most games did not move is a red flag for the rig.
"""
from __future__ import annotations

import math
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from bench import RESULTS, read  # noqa: E402

FIELDS = [("submittedGems", "gems submitted"), ("oppGems", "opponent gems"),
          ("margin", "gem margin"), ("win", "win rate %"),
          ("collectedGems", "gems collected"), ("deaths", "deaths"),
          ("kills", "kills"), ("earnedGold", "gold earned")]


def games(tag: str) -> dict:
    folder = RESULTS / tag
    if not folder.exists():
        sys.exit(f"no results for {tag} under {RESULTS}")
    out = {}
    for g in read(folder)["games"]:
        g = dict(g, margin=g["submittedGems"] - g["oppGems"], win=100.0 * g["win"])
        out[(g["opp"], g["map"], g["side"])] = g
    return out


def mean_se(values: list[float]) -> tuple[float, float]:
    n = len(values)
    mean = sum(values) / n
    if n < 2:
        return mean, float("nan")
    var = sum((v - mean) ** 2 for v in values) / (n - 1)
    return mean, math.sqrt(var / n)


def sign_p(better: int, worse: int) -> float:
    """Two-sided exact sign test on the games that moved."""
    n = better + worse
    if not n:
        return 1.0
    k = min(better, worse)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def compare(base: dict, tag: str) -> None:
    cand = games(tag)
    keys = sorted(set(base) & set(cand))
    unmatched = len(set(base) ^ set(cand))
    if not keys:
        print(f"{tag}: no games in common with the baseline")
        return
    same = sum(all(base[k][f] == cand[k][f] for f, _ in FIELDS) for k in keys)
    print(f"\n{tag} against the baseline: {len(keys)} paired games, "
          f"{same} bit-identical, {unmatched} unmatched\n")
    print(f"  {'metric':<16}{'base':>9}{'cand':>9}{'change':>9}{'paired se':>11}{'z':>7}")
    for f, label in FIELDS:
        d = [cand[k][f] - base[k][f] for k in keys]
        b = sum(base[k][f] for k in keys) / len(keys)
        m, se = mean_se(d)
        z = m / se if se else float("nan")
        print(f"  {label:<16}{b:>9.1f}{b + m:>9.1f}{m:>+9.2f}{se:>11.2f}{z:>+7.1f}")

    d = [cand[k]["submittedGems"] - base[k]["submittedGems"] for k in keys]
    rng = random.Random(7)
    boot = sorted(sum(rng.choice(d) for _ in d) / len(d) for _ in range(10000))
    lo, hi = boot[250], boot[9749]
    better, worse = sum(x > 0 for x in d), sum(x < 0 for x in d)
    flips_up = sum(base[k]["win"] < cand[k]["win"] for k in keys)
    flips_down = sum(base[k]["win"] > cand[k]["win"] for k in keys)
    print(f"\n  gems: 95% bootstrap {lo:+.1f} to {hi:+.1f}, "
          f"{better} better / {worse} worse / {len(d) - better - worse} same, "
          f"sign test p = {sign_p(better, worse):.3f}")
    print(f"  results flipped: {flips_up} to a win, {flips_down} to a loss, "
          f"sign test p = {sign_p(flips_up, flips_down):.3f}")

    print("\n  by opponent (gem change, paired se, games):")
    by = defaultdict(list)
    for k in keys:
        by[k[0]].append(cand[k]["submittedGems"] - base[k]["submittedGems"])
    for opp, values in sorted(by.items()):
        m, se = mean_se(values)
        print(f"    {opp:<22}{m:>+9.1f}{se:>9.1f}{len(values):>6}")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        sys.exit(__doc__)
    base = games(argv[0])
    for tag in argv[1:]:
        compare(base, tag)
    if len(argv) > 2:
        print(f"\n  {len(argv) - 1} candidates against one baseline: the best of them is "
              "selected, so read its z against a stricter bar than 2.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
