#!/usr/bin/env python3
"""Download our ranked games' summaries for named eras and compare them per game.

    fetcheras.py NAME=START,END [NAME=START,END ...]    (ISO times)

Summaries land in ws/bench/ladder_NAME/summaries/<matchId>.json with a matches.json
index; already-downloaded ones are reused. Prints medians per era: gold by rounds 100 and
300, camp damage by 300, kills, deaths, gems collected, gems submitted, and our win share.
"""
import json
import os
import statistics as st
import subprocess
import sys
import time
from pathlib import Path

CAMBC = str(Path.home() / "Library/Python/3.9/bin/cambc")
WS = Path("/Users/faeezaullyar/Claude/battlecode/ws")
US = "Milk and Potatoes"


def cambc(*args):
    r = subprocess.run([CAMBC, *args], cwd=WS, capture_output=True, text=True, env=dict(os.environ))
    return r


def expand(runs, n):
    out = []
    for r in runs:
        out += [float(r["value"])] * int(r["duration"])
        if len(out) > n:
            break
    return (out + [out[-1] if out else 0.0] * n)[:n]


eras = [(a.split("=", 1)[0], *a.split("=", 1)[1].split(",")) for a in sys.argv[1:]]
first = min(e[1] for e in eras)
matches, cursor = {}, None
while True:
    args = ["matches", "list", "--team", "me", "--kind", "ranked", "--limit", "100", "--json"]
    if cursor:
        args += ["--cursor", cursor]
    r = cambc(*args)
    d = json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else {}
    batch = d.get("matches", [])
    for m in batch:
        matches[m["matchId"]] = m
    cursor = d.get("nextCursor")
    if not batch or not cursor or min(m["createdAt"] for m in batch) < first:
        break
for name, start, end in eras:
    folder = WS / "bench" / f"ladder_{name}"
    (folder / "summaries").mkdir(parents=True, exist_ok=True)
    ms = [m for m in matches.values() if m.get("status") == "finished" and start <= m["createdAt"] < end]
    (folder / "matches.json").write_text(json.dumps(ms, indent=1))
    rows = []
    for m in ms:
        f = folder / "summaries" / f"{m['matchId']}.json"
        for attempt in range(4):
            if f.exists():
                break
            # Rapid calls get refused; a short pause and a retry fetch them.
            cambc("matches", "summary", m["matchId"], "--json", "-o", str(f))
            if not f.exists():
                time.sleep(2 + 3 * attempt)
        if not f.exists():
            continue
        d = json.loads(f.read_text())
        me = next(t for t in m["teams"] if t["name"] == US)
        side = "teamA" if me["side"] == "a" else "teamB"
        ids = {c["id"] for c in d["roster"]["champions"] if c["team"] == side}

        def tot(metric, at=None):
            s = 0.0
            for x in d["championTimelines"]:
                if x["owner"]["id"] in ids and x["metric"] == metric and x["runs"]:
                    s += expand(x["runs"], at + 1)[at] if at is not None else float(x["runs"][-1]["value"])
            return s
        rows.append(dict(win=me.get("result") == "win", g100=tot("earnedGold", 100), g300=tot("earnedGold", 300),
                         d300=tot("monsterDamageDone", 300), kills=tot("kills"), deaths=tot("deaths"),
                         coll=tot("collectedGems"), sub=tot("submittedGems"), rounds=d["match"]["roundsCompleted"]))
    if not rows:
        print(f"{name}: no games")
        continue
    med = lambda k: st.median(r[k] for r in rows)
    print(f"{name:<8} {len(rows):3d} games, won {sum(r['win'] for r in rows)}: gold@100 {med('g100'):5.0f} gold@300 {med('g300'):5.0f} "
          f"camp dmg@300 {med('d300'):6.0f} kills {med('kills'):4.1f} deaths {med('deaths'):4.1f} collected {med('coll'):5.0f} "
          f"submitted {med('sub'):5.0f} rounds {med('rounds'):5.0f}")
