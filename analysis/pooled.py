#!/usr/bin/env python3
"""Pooled paired test: several independent re-rolls of a candidate against
several independent re-rolls of the baseline, game by game.

Each arm is one realisation of the pool's trajectory luck. Averaging arms per
game shrinks that luck, and comparing unselected arms removes the winner's
curse. The standard error is over the 320 games of per-game differences.

    pooled.py --base A,B,C --cand X,Y [--metric gems|win]
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

BENCH = Path(__file__).resolve().parent.parent / "ws/bench"


def load(tag):
    out = {}
    for f in (BENCH / tag).glob("*__*__*.json"):
        o, m, s = f.stem.split("__")
        side = "teamA" if s == "A" else "teamB"; other = "teamB" if side == "teamA" else "teamA"
        d = json.loads(f.read_text())
        g = {t["team"]: int(t["submittedGems"]) for t in d["teams"]}
        dt = sum(int(c["metrics"]["deaths"]) for c in d["champions"] if c["team"] == side)
        out[(o, m, s)] = (g[side], int(g[side] > g[other]), dt)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True); ap.add_argument("--cand", required=True)
    a = ap.parse_args()
    B = [load(t) for t in a.base.split(",")]; C = [load(t) for t in a.cand.split(",")]
    # A game counts if at least one baseline arm and one candidate arm played it;
    # each side is averaged over the arms that did.
    keys = set.union(*[set(x) for x in B]) & set.union(*[set(x) for x in C])
    print(f"{len(keys)} distinct games with at least one arm on each side "
          f"({len(B)} baseline arms, {len(C)} candidate arms)")
    def avg(arms, k, i):
        v = [x[k][i] for x in arms if k in x]
        return sum(v) / len(v)
    for idx, label in ((0, "gems submitted"), (1, "win rate %"), (2, "deaths")):
        d = [avg(C, k, idx) - avg(B, k, idx) for k in keys]
        n = len(d); mean = sum(d) / n
        se = (sum((x - mean) ** 2 for x in d) / (n - 1)) ** 0.5 / n ** 0.5
        scale = 100 if idx == 1 else 1
        print(f"  {label:<16} change {mean * scale:+8.2f}   se {se * scale:6.2f}   z {mean / se if se else 0:+5.2f}")
        if idx == 0:
            random.seed(5)
            boot = sorted(sum(random.choice(d) for _ in d) / n for _ in range(10000))
            print(f"  {'':<16} one-sided 90% lower bound {boot[1000]:+.1f};  95% interval {boot[250]:+.1f} to {boot[9750]:+.1f}")


if __name__ == "__main__":
    main()
