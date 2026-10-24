#!/usr/bin/env python3
"""Per-champion totals for our side of a bench tag, a game average per champion.

    champs.py TAG [TAG ...]

Collected gems against submitted shows what a champion banks and what it loses:
a kill hands the killer everything carried, so collected - submitted - held at
the end is roughly what the enemy took from it.
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parent.parent / "ws/bench"
FIELDS = ("collectedGems", "submittedGems", "gems", "earnedGold", "monsterDamageDone",
          "championDamageDone", "shieldingDone", "deaths", "kills")


def main(tags: list[str]) -> None:
    for tag in tags:
        sums, games = collections.defaultdict(lambda: collections.Counter()), collections.Counter()
        for f in (BENCH / tag).glob("*__*__*.json"):
            side = "teamA" if f.stem.endswith("__A") else "teamB"
            d = json.loads(f.read_text())
            for c in d["champions"]:
                if c["team"] != side:
                    continue
                games[c["name"]] += 1
                for k in FIELDS:
                    sums[c["name"]][k] += float(c["metrics"][k])
                sums[c["name"]]["emblems"] += len(c["itemsBought"])
        print(f"{tag}: per game a champion played")
        print(f"  {'champion':14} {'games':>5} {'collect':>7} {'submit':>6} {'held':>5} {'lost':>5} "
              f"{'gold':>6} {'camp dmg':>8} {'champ dmg':>9} {'shield':>6} {'deaths':>6} {'kills':>5} {'items':>5}")
        for name in sorted(games, key=lambda n: -games[n]):
            n, s = games[name], sums[name]
            lost = s["collectedGems"] - s["submittedGems"] - s["gems"]
            print(f"  {name:14} {n:5d} {s['collectedGems']/n:7.1f} {s['submittedGems']/n:6.1f} {s['gems']/n:5.1f} "
                  f"{lost/n:5.1f} {s['earnedGold']/n:6.0f} {s['monsterDamageDone']/n:8.0f} "
                  f"{s['championDamageDone']/n:9.0f} {s['shieldingDone']/n:6.0f} {s['deaths']/n:6.2f} "
                  f"{s['kills']/n:5.2f} {s['emblems']/n:5.1f}")


if __name__ == "__main__":
    main(sys.argv[1:])
