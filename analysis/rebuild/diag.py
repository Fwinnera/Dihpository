#!/usr/bin/env python3
"""Unranked diagnostics with the live version on chosen maps against teams near our rating.

    diag.py queue NAME RANK_FROM RANK_TO TEAMS MAP,MAP,...   (maps in groups of five)
    diag.py show NAME

Unlike lab.py (fixed opponents, set maps, for comparing versions), this aims the live bot
at its weakest maps against the band it meets in ranked games, to collect losses to read.
Groups are stored in ws/bench/diag/NAME.json; summaries go to ws/bench/lab/summaries.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

CAMBC = str(Path.home() / "Library/Python/3.9/bin/cambc")
WS = Path("/Users/faeezaullyar/Claude/battlecode/ws")
DIAG = WS / "bench" / "diag"
SUMS = WS / "bench" / "lab" / "summaries"
US = "Milk and Potatoes"


def cambc(*args):
    for attempt in range(6):
        r = subprocess.run([CAMBC, *args], cwd=WS, capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip().startswith("{"):
            return json.loads(r.stdout)
        time.sleep(3 + 4 * attempt)
    sys.exit(f"cambc {' '.join(args)} failed: {r.stderr.strip()[-300:]}")


def queue(name, lo, hi, nteams, maps):
    DIAG.mkdir(parents=True, exist_ok=True)
    teams = []
    for page in (2, 3):
        teams += cambc("ladder", "--page", str(page), "--limit", "100", "--json")["teams"]
    pool = [t for t in teams if lo <= t["rank"] <= hi and t["name"] != US]
    step = max(1, len(pool) // nteams)
    chosen = pool[::step][:nteams]
    blocks = [maps[i:i + 5] for i in range(0, len(maps), 5)]
    out = dict(name=name, live=cambc("submissions", "list", "--json")["active"]["version"], groups=[])
    for k, t in enumerate(chosen):
        for j, block in enumerate(blocks):
            sides = ["a", "b"] * 3
            if (k + j) % 2:
                sides = ["b", "a"] * 3
            d = cambc("match-groups", "create", t["teamId"], "--maps", ",".join(block), "--sides", ",".join(sides[:len(block)]), "--json")
            out["groups"].append(dict(team=t["teamId"], name=t["name"], rank=t["rank"], rating=t["rating"], maps=block, group=d["groupId"]))
            (DIAG / f"{name}.json").write_text(json.dumps(out, indent=1))
            print(f"{t['rank']:>4} {t['name'][:22]:<22} {d['groupId']}  {' '.join(block)}")
            time.sleep(2)


def show(name):
    d = json.loads((DIAG / f"{name}.json").read_text())
    rows, pending = [], 0
    for g in d["groups"]:
        s = cambc("match-groups", "show", g["group"], "--json")
        for m in s["matches"]:
            if m.get("status") != "finished":
                pending += 1
                continue
            me = next(t for t in m["teams"] if t["name"] == US)
            f = SUMS / f"{m['matchId']}.json"
            for attempt in range(4):
                if f.exists():
                    break
                subprocess.run([CAMBC, "matches", "summary", m["matchId"], "--json", "-o", str(f)], cwd=WS, capture_output=True, text=True)
                if not f.exists():
                    time.sleep(2 + 3 * attempt)
            line = (m["map"], me["side"], me.get("result"), g["rank"], g["name"][:16], m["matchId"])
            if f.exists():
                sm = json.loads(f.read_text())
                side = "teamA" if me["side"] == "a" else "teamB"
                tot = lambda who, k: sum(float(c["metrics"][k]) for c in sm["champions"] if (c["team"] == side) == (who == "us"))
                line += (sm["match"]["roundsCompleted"], f"{tot('us', 'submittedGems'):.0f}-{tot('them', 'submittedGems'):.0f}",
                         f"camp {tot('us', 'monsterDamageDone') / 1000:.0f}k-{tot('them', 'monsterDamageDone') / 1000:.0f}k",
                         f"K{tot('us', 'kills'):.0f}-{tot('them', 'kills'):.0f}")
            rows.append(line)
        time.sleep(1)
    by = {}
    for r in rows:
        by.setdefault(r[0], []).append(r)
    for mp in sorted(by):
        w = sum(1 for r in by[mp] if r[2] == "win")
        print(f"{mp:<20} {w}/{len(by[mp])}")
        for r in by[mp]:
            print("    ", r[1], r[2], r[3], r[4], *r[6:])
    print(f"{sum(1 for r in rows if r[2] == 'win')} of {len(rows)} won, {pending} pending; live version {d['live']}")


if __name__ == "__main__":
    if sys.argv[1] == "queue":
        queue(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), sys.argv[6].split(","))
    else:
        show(sys.argv[2])
