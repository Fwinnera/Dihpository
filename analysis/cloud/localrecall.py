#!/usr/bin/env python3
"""Local bench runs: recalls restarted straight after a hit (the hidden-attacker pattern), per game, for the
candidate (side named in the file: OPP__MAP__A means the candidate played side A)."""
import collections, json, sys
from pathlib import Path
adir = Path(sys.argv[1])
games = 0; restarts = 0; attempts = 0
for f in sorted(adir.glob("*.jsonl")):
    side = f.stem.rsplit("__", 1)[-1]
    ours = 0 if side == "A" else 1
    lines = f.read_text().splitlines()
    if not lines: continue
    team = None
    rec = collections.defaultdict(set)
    rows = []
    for l in lines:
        r = json.loads(l)
        if isinstance(r, dict):
            team = {k: t for k, t, _ in r["teams"]}
            continue
        rows.append(r)
    if team is None: continue
    games += 1
    for r in rows:
        if r[8] and r[1] >= 0 and r[2] == 11 and team.get(r[1]) == ours: rec[r[1]].add(r[0])
    for k, rs in rec.items():
        attempts += len(rs); restarts += sum(1 for x in rs if x - 1 in rs)
print(f"{adir.name}: games {games}, recall attempts {attempts / max(1, games):.1f} a game, restarted next turn {restarts / max(1, games):.2f} a game")
