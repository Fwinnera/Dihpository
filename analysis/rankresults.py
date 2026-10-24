#!/usr/bin/env python3
"""Results of the groups queued by rankgroups.py, by opponent rank.

    rankresults.py GROUPS_JSON
"""
import json
import subprocess
import sys
from pathlib import Path

WS = Path(__file__).resolve().parent.parent / "ws"
CAMBC = str(Path.home() / "Library/Python/3.9/bin/cambc")
US = "Milk and Potatoes"


def main() -> None:
    groups = json.loads(Path(sys.argv[1]).read_text())
    r = subprocess.run([CAMBC, "matches", "list", "--team", "me", "--kind", "unranked", "--limit", "100", "--json"],
                       cwd=WS, capture_output=True, text=True)
    d = json.loads(r.stdout); rows = d if isinstance(d, list) else d.get("matches", d.get("items", []))
    by = {}
    for m in rows:
        by.setdefault(m["groupId"], []).append(m)
    tot_w = tot_n = series = done = 0
    for g in groups:
        ms = by.get(g["groupId"], [])
        fin = [m for m in ms if m["status"] == "finished"]
        w = sum(1 for m in fin for t in m["teams"] if t["name"] == US and t.get("result") == "win")
        if len(fin) == 5:
            g["wins"] = w  # kept: the platform lists only the latest 100 games
        if "wins" in g:
            w = g["wins"]
            state = f"{w}-{5 - w}"
            tot_w += w; tot_n += 5; done += 1; series += w >= 3
        else:
            state = f"{len(fin)}/5 finished" if ms else "not listed yet"
        print(f"  rank {g['rank']:3d} {g['rating']:6.0f}  {g['name'][:28]:28} {state}")
    Path(sys.argv[1]).write_text(json.dumps(groups, indent=1))
    if tot_n:
        print(f"finished groups {done}: series won {series}; games {tot_w}/{tot_n} ({tot_w * 100 / tot_n:.0f}%)")


if __name__ == "__main__":
    main()
