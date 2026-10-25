#!/usr/bin/env python3
"""How early are head-to-head games decided? Kill timing against the result.

    snowball.py TAG      # an h2h bench tag (our bot vs one opponent)
"""
import collections
import json
import sys
from pathlib import Path


def main(tag: str) -> None:
    rows = []
    for f in Path(f"ws/bench/{tag}").glob("*__*__*.json"):
        o, m, s = f.stem.split("__"); us = "teamA" if s == "A" else "teamB"; them = "teamB" if us == "teamA" else "teamA"
        d = json.loads(f.read_text()); g = {k["team"]: int(k["submittedGems"]) for k in d["teams"]}
        deaths = []  # (round, team that died, killed by a champion?)
        for e in d["events"]:
            if e["kind"] != "death": continue
            for x in e["entries"]:
                deaths.append((x["timestamp"]["round"], e["owner"]["team"], x["context"] == "champion"))
        deaths.sort()
        pvp = [x for x in deaths if x[2]]
        first = pvp[0][1] if pvp else None
        def lead(r):  # our kills minus their kills by round r
            return sum(1 for t, team, _ in pvp if t <= r and team == them) - sum(1 for t, team, _ in pvp if t <= r and team == us)
        rows.append(dict(win=g[us] > g[them], first_us=(first == them), l300=lead(300), l600=lead(600), l1000=lead(1000),
                         camp_deaths=sum(1 for t, team, c in deaths if team == us and not c), map=m))
    n = len(rows)
    fb = [r for r in rows if r["first_us"]]
    print(f"{tag}: {n} games, won {sum(r['win'] for r in rows)}")
    print(f"  first blood ours in {len(fb)} games: won {sum(r['win'] for r in fb)}; theirs in {n - len(fb)}: won {sum(r['win'] for r in rows if not r['first_us'])}")
    for k in ("l300", "l600", "l1000"):
        ahead = [r for r in rows if r[k] > 0]; level = [r for r in rows if r[k] == 0]; behind = [r for r in rows if r[k] < 0]
        f = lambda xs: f"{sum(x['win'] for x in xs)}/{len(xs)}"
        print(f"  kill lead at round {k[1:]}: ahead {f(ahead)} won, level {f(level)}, behind {f(behind)}")
    print(f"  our deaths to camps: {sum(r['camp_deaths'] for r in rows) / n:.1f} a game")


if __name__ == "__main__":
    main(sys.argv[1])
