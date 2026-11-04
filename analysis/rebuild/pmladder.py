#!/usr/bin/env python3
"""Ladder (lab and diag) games on party maps, with the pmsum mechanism counts for both sides.

    pmladder.py [MAP ...]

Index: ws/bench/lab/groups/*.json (match lists: map, sides, team names); summaries in
ws/bench/lab/summaries/<matchId>.json. Ours is "Milk and Potatoes".
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pmsum import facts, PARTY  # noqa: E402

LAB = Path(__file__).resolve().parents[2] / "ws/bench/lab"
US = "Milk and Potatoes"


def games(maps):
    seen = set()
    for g in sorted((LAB / "groups").glob("*.json")):
        d = json.loads(g.read_text())
        for m in d.get("matches", []):
            if m.get("map") not in maps or m["matchId"] in seen:
                continue
            f = LAB / "summaries" / f"{m['matchId']}.json"
            if not f.exists():
                continue
            seen.add(m["matchId"])
            us = next((t for t in m["teams"] if t["name"] == US), None)
            them = next((t for t in m["teams"] if t["name"] != US), None)
            if not us or not them:
                continue
            yield m, us, them, json.loads(f.read_text())


def main(argv):
    maps = argv or PARTY
    print(f"{'map':<14} side res opp                 | us sub/col/lost dc dh 1st nsub big | them sub/col/lost dc dh 1st nsub big | rounds  created")
    for m, us, them, d in sorted(games(maps), key=lambda z: (z[0]["map"], z[0]["createdAt"])):
        side = "teamA" if us["side"] == "a" else "teamB"
        other = "teamB" if side == "teamA" else "teamA"
        u, t = facts(d, side, m["map"]), facts(d, other, m["map"])
        print(f"{m['map']:<14} {us['side']}    {us.get('result', '?')[:4]:<4} {them['name'][:18]:<18} | "
              f"{u['sub']:>4}/{u['col']:>4}/{u['lost']:>4} {u['dc']:>2} {u['dh']:>2} {u['first']:>4} {u['nsub']:>3} {u['big']:>2} | "
              f"{t['sub']:>4}/{t['col']:>4}/{t['lost']:>4} {t['dc']:>2} {t['dh']:>2} {t['first']:>4} {t['nsub']:>3} {t['big']:>2} | "
              f"{d['match']['roundsCompleted']:>5}  {m['createdAt'][5:16]} {m['matchId'][:8]}")


if __name__ == "__main__":
    main(sys.argv[1:])
