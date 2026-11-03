#!/usr/bin/env python3
"""Ladder performance rating of our recent versions against opponents' current ratings.

    ladderperf.py NAME=START,END [NAME=START,END ...]     (ISO times, e.g. v138=2026-11-03T01:29,2026-11-04)

Fetches our last 1,200 ranked matches and the ladder through cambc, then for each era
prints wins, games and the rating at which the expected score equals the wins.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

CAMBC = str(Path.home() / "Library/Python/3.9/bin/cambc")
WS = "/Users/faeezaullyar/Claude/battlecode/ws"
US = "246f9cef-b416-4864-964e-ebcafb97f7ad"


def cambc(*args):
    r = subprocess.run([CAMBC, *args], cwd=WS, capture_output=True, text=True, env=dict(os.environ))
    return json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else {}


def perf(games):
    w = sum(x for _, x in games)
    lo, hi = 800.0, 3000.0
    for _ in range(60):
        mid = (lo + hi) / 2
        e = sum(1 / (1 + 10 ** ((r - mid) / 400)) for r, _ in games)
        lo, hi = (mid, hi) if e < w else (lo, mid)
    return (lo + hi) / 2, w, len(games)


eras = [(a.split("=", 1)[0], *a.split("=", 1)[1].split(",")) for a in sys.argv[1:]]
first = min(e[1] for e in eras)
ratings = {}
for page in range(1, 10):
    d = cambc("ladder", "--page", str(page), "--limit", "100", "--json")
    teams = d.get("teams", [])
    for t in teams:
        ratings[t["teamId"]] = t["rating"]
        if t["teamId"] == US:
            print(f"now: rank {t['rank']}, rating {t['rating']:.0f}")
    if len(teams) < 100:
        break
matches, cursor = {}, None
while len(matches) < 1200:
    args = ["matches", "list", "--team", "me", "--kind", "ranked", "--limit", "100", "--json"]
    if cursor:
        args += ["--cursor", cursor]
    d = cambc(*args)
    batch = d.get("matches", [])
    for m in batch:
        matches[m["matchId"]] = m
    cursor = d.get("nextCursor")
    if not batch or not cursor or min(m["createdAt"] for m in batch) < first:
        break
for name, start, end in eras:
    games = []
    for m in matches.values():
        if m.get("status") != "finished" or not (start <= m["createdAt"] < end):
            continue
        t = {x["teamId"]: x for x in m["teams"]}
        if US not in t:
            continue
        opp = next(x for k, x in t.items() if k != US)
        if opp["teamId"] in ratings:
            games.append((ratings[opp["teamId"]], t[US].get("result") == "win"))
    if games:
        p, w, n = perf(games)
        mean = sum(r for r, _ in games) / n
        print(f"  {name:<8} {w:4d}/{n:<4d} ({100 * w / n:4.1f}%)  performance {p:5.0f}  mean opponent {mean:5.0f}")
    else:
        print(f"  {name:<8} no games")
