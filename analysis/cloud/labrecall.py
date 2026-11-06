#!/usr/bin/env python3
"""Recall attempts and restarts (a recall started on the turn after another: the previous one was interrupted)
per game for our team in lab arms, from action streams with a team header (actions.mjs / actions3.mjs)."""
import collections, json, sys
from pathlib import Path
US = "Milk and Potatoes"
bdir, adir = Path(sys.argv[1]), Path(sys.argv[2])
prefixes = sys.argv[3].split(",")
meta = json.loads((bdir / "meta.json").read_text())
for pre in prefixes:
    games = attempts = restarts = 0
    for m in meta:
        if not m.get("arm", "").startswith(pre): continue
        f = adir / f"{m['matchId']}.jsonl"
        if not f.exists(): continue
        me = next(t for t in m["teams"] if t["name"] == US); ours = 0 if me["side"] == "a" else 1
        team = None; rec = collections.defaultdict(set)
        for l in f.read_text().splitlines():
            r = json.loads(l)
            if isinstance(r, dict):
                team = {k: t for k, t, _ in r["teams"]}; continue
            if team and r[8] and r[1] >= 0 and r[2] == 11 and team.get(r[1]) == ours: rec[r[1]].add(r[0])
        if team is None: continue
        games += 1
        for k, rs in rec.items():
            attempts += len(rs); restarts += sum(1 for x in rs if x - 1 in rs)
    print(f"{pre}: games {games}, recall attempts {attempts / max(1, games):.1f} a game, restarted next turn {restarts / max(1, games):.2f} a game")
