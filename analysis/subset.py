#!/usr/bin/env python3
"""Paired comparison restricted to a set of maps.

    subset.py BASE TAG [TAG ...] --maps a,b,c      (or --mono 0.5: maps whose
                                                   monolith gem share >= 0.5)
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
        out[(o, m.replace("-", "_"), s)] = (g[side], int(g[side] > g[other]))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base"); ap.add_argument("tags", nargs="+")
    ap.add_argument("--maps"); ap.add_argument("--mono", type=float)
    a = ap.parse_args()
    if a.mono is not None:
        T = json.loads((BENCH / "camptable.json").read_text())
        maps = {m for m, gs in T.items()
                if sum(g["gems"] for g in gs if g["monolith"]) >= a.mono * max(1, sum(g["gems"] for g in gs))}
    else:
        maps = {m.replace("-", "_") for m in a.maps.split(",")}
    base = {k: v for k, v in load(a.base).items() if k[1] in maps}
    print(f"{len(maps)} maps; baseline {a.base}: {len(base)} games")
    print("%-26s%7s%9s%7s%10s" % ("candidate", "games", "gems", "z", "win rate"))
    for tag in a.tags:
        c = {k: v for k, v in load(tag).items() if k in base}
        d = [c[k][0] - base[k][0] for k in c]; w = [c[k][1] - base[k][1] for k in c]
        if len(d) < 2:
            print(f"{tag:<26} not enough games"); continue
        mean = sum(d) / len(d); se = (sum((x - mean) ** 2 for x in d) / (len(d) - 1)) ** 0.5 / len(d) ** 0.5
        print("%-26s%7d%+9.1f%+7.1f%+9.1f" % (tag, len(d), mean, mean / se if se else 0, 100 * sum(w) / len(w)))


if __name__ == "__main__":
    main()
