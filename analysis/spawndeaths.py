#!/usr/bin/env python3
"""Deaths to champions near our own spawn, from bench folders (local summaries).

    spawndeaths.py SPAWNS TAG [TAG ...]

SPAWNS is the probe_spawn output (`<map> SPAWN ally=x,y enemy=x,y altars=...`
per line, team A's view). For each tag prints per game: our deaths to champions,
those within 8 tiles of our spawn, kills, gems submitted and win rate.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parent.parent / "ws/bench"


def main(spawns: Path, tags: list[str]) -> None:
    spawn = {}
    for line in spawns.read_text().splitlines():
        m = re.match(r"(\S+) SPAWN ally=([\d.]+),([\d.]+) enemy=([\d.]+),([\d.]+)", line)
        if m:
            spawn[m.group(1)] = ((float(m.group(2)), float(m.group(3))), (float(m.group(4)), float(m.group(5))))
    for tag in tags:
        n = deaths = near = kills = gems = wins = 0
        for f in sorted((BENCH / tag).glob("*__*__*.json")):
            opp, mp, side = f.stem.split("__")
            if mp not in spawn:
                continue
            d = json.loads(f.read_text())
            mine = "teamA" if side == "A" else "teamB"
            sp = spawn[mp][0] if side == "A" else spawn[mp][1]
            n += 1
            wins += d["match"]["outcome"] == mine
            gems += next(int(t["submittedGems"]) for t in d["teams"] if t["team"] == mine)
            for e in d["events"]:
                o = e.get("owner") or {}
                if o.get("team") != mine:
                    continue
                for x in e["entries"]:
                    if e["kind"] == "death" and x.get("context") == "champion":
                        deaths += 1
                        near += max(abs(x["x"] - sp[0]), abs(x["y"] - sp[1])) <= 8
                    elif e["kind"] == "kill":
                        kills += 1
        if n:
            print(f"{tag:14} {n:4} games  deaths to champions {deaths/n:5.1f}  near our spawn {near/n:5.1f}"
                  f"  kills {kills/n:5.1f}  gems {gems/n:6.0f}  win {100*wins/n:4.0f}%")


if __name__ == "__main__":
    main(Path(sys.argv[1]), sys.argv[2:]) if len(sys.argv) > 2 else sys.exit(__doc__)
