#!/usr/bin/env python3
"""Lab arms compared game by game on gem margin, not only on wins.

    labmargin.py fetch ARM [ARM ...]      download the arms' match summaries (no quota)
    labmargin.py BASE CAND [BASE CAND ...]  paired comparison of each pair

Margin = our submitted gems minus theirs at the end of the game (a win is about +1,000 at
most, a blowout loss about -1,000). Paired by team and map, the mean difference and its
standard error say more than the win count alone, which flips on a quarter of the games
between near-identical versions.
"""
import json
import math
import statistics as st
import subprocess
import sys
import time
from pathlib import Path

CAMBC = str(Path.home() / "Library/Python/3.9/bin/cambc")
LAB = Path("/Users/faeezaullyar/Claude/battlecode/ws/bench/lab")
US = "Milk and Potatoes"


def games(arm):
    d = json.loads((LAB / f"{arm}.json").read_text())
    for g in d["groups"]:
        s = json.loads((LAB / "groups" / f"{g['group']}.json").read_text())
        for m in s["matches"]:
            yield g, m


def fetch(arm):
    for g, m in games(arm):
        f = LAB / "summaries" / f"{m['matchId']}.json"
        for attempt in range(4):
            if f.exists():
                break
            subprocess.run([CAMBC, "matches", "summary", m["matchId"], "--json", "-o", str(f)], cwd=LAB.parent.parent,
                           capture_output=True, text=True)
            if not f.exists():
                time.sleep(2 + 3 * attempt)


def margins(arm):
    out = {}
    for g, m in games(arm):
        f = LAB / "summaries" / f"{m['matchId']}.json"
        if not f.exists():
            continue
        me = next(t for t in m["teams"] if t["name"] == US)
        side = "teamA" if me["side"] == "a" else "teamB"
        sm = json.loads(f.read_text())
        ours = sum(float(c["metrics"]["submittedGems"]) for c in sm["champions"] if c["team"] == side)
        theirs = sum(float(c["metrics"]["submittedGems"]) for c in sm["champions"] if c["team"] != side)
        out[(g["name"], m["map"])] = (ours - theirs, me.get("result") == "win")
    return out


if __name__ == "__main__":
    if sys.argv[1] == "fetch":
        for arm in sys.argv[2:]:
            fetch(arm)
            print("fetched", arm, len(margins(arm)))
        sys.exit()
    args = sys.argv[1:]
    for base, cand in zip(args[::2], args[1::2]):
        A, B = margins(base), margins(cand)
        keys = [k for k in A if k in B]
        diffs = [B[k][0] - A[k][0] for k in keys]
        if len(diffs) < 2:
            print(base, cand, "too few games")
            continue
        mean = st.mean(diffs)
        se = st.stdev(diffs) / math.sqrt(len(diffs))
        wins = sum(B[k][1] for k in keys) - sum(A[k][1] for k in keys)
        print(f"{cand:>10} - {base:<10} {len(keys):3d} games: margin {mean:+7.1f} (se {se:5.1f}, z {mean / se:+.2f}); wins {wins:+d}")
