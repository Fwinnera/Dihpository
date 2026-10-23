#!/usr/bin/env python3
"""Head to head by map pair: each map played once from each side.

A map counts as won only if the bot won it from both sides, which cancels the
pool's side advantage. Gem margins are averaged per map pair, so the standard
error and bootstrap interval are over maps, the unit that varies.

    h2h.py TAG [TAG ...]       # bench tags run with --opponents OTHER
"""
from __future__ import annotations

import glob
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

BENCH = Path(__file__).resolve().parent.parent / "ws/bench"


def main(tags):
    for tag in tags:
        by_map, stats, opp = defaultdict(dict), defaultdict(float), None
        for f in glob.glob(str(BENCH / tag / "*__*__*.json")):
            o, m, side = Path(f).stem.split("__")
            opp = o
            s = "teamA" if side == "A" else "teamB"; t = "teamB" if s == "teamA" else "teamA"
            d = json.loads(Path(f).read_text())
            g = {k["team"]: int(k["submittedGems"]) for k in d["teams"]}
            by_map[m][side] = (g[s] - g[t], g[s] > g[t])
            for c in d["champions"]:
                k = "us" if c["team"] == s else "them"
                stats[k + "_deaths"] += int(c["metrics"]["deaths"])
                stats[k + "_gold"] += int(c["metrics"]["earnedGold"])
            stats["n"] += 1; stats["wins"] += g[s] > g[t]
        pairs = [v for v in by_map.values() if len(v) == 2]
        if len(pairs) < 2:
            print(f"{tag}: not enough map pairs yet ({len(pairs)})"); continue
        both = sum(1 for v in pairs if v["A"][1] and v["B"][1])
        none = sum(1 for v in pairs if not v["A"][1] and not v["B"][1])
        margins = [(v["A"][0] + v["B"][0]) / 2 for v in pairs]
        mean = sum(margins) / len(margins)
        se = (sum((x - mean) ** 2 for x in margins) / (len(margins) - 1)) ** 0.5 / len(margins) ** 0.5
        random.seed(3)
        boot = sorted(sum(random.choice(margins) for _ in margins) / len(margins) for _ in range(10000))
        n = stats["n"]
        print(f"=== {tag}: {len(pairs)} maps from both sides, against {opp} ===")
        print(f"  games won {int(stats['wins'])} of {int(n)};  maps won from both sides {both}, "
              f"split {len(pairs) - both - none}, lost from both sides {none}")
        print(f"  gem margin per game {mean:+.0f}, se {se:.0f}, 95% {boot[250]:+.0f} to {boot[9750]:+.0f}")
        print(f"  deaths a game {stats['us_deaths'] / n:.1f} against {stats['them_deaths'] / n:.1f};  "
              f"gold {stats['us_gold'] / n:.0f} against {stats['them_gold'] / n:.0f}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
