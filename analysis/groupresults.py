#!/usr/bin/env python3
"""Score queued unranked groups, paging through the match list with --cursor.

    groupresults.py GROUPS_JSON [SINCE_ISO]

GROUPS_JSON: a list of {rank, rating, name, groupId}. Pages back until SINCE_ISO
(default: the earliest queuedAt is not known, so 3 hours). Writes each finished
group's wins back into the file.
"""
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

WS = Path(__file__).resolve().parent.parent / "ws"
CAMBC = str(Path.home() / "Library/Python/3.9/bin/cambc")
US = "Milk and Potatoes"


def matches(since: str) -> list:
    out, cursor = [], None
    while True:
        cmd = [CAMBC, "matches", "list", "--team", "me", "--kind", "unranked", "--limit", "100", "--json"]
        if cursor:
            cmd += ["--cursor", cursor]
        d = json.loads(subprocess.run(cmd, cwd=WS, capture_output=True, text=True).stdout)
        out += d["matches"]
        cursor = d.get("nextCursor")
        if not cursor or not d["matches"] or d["matches"][-1]["createdAt"] < since:
            return out


def main() -> None:
    path = Path(sys.argv[1]); groups = json.loads(path.read_text())
    since = sys.argv[2] if len(sys.argv) > 2 else (dt.datetime.utcnow() - dt.timedelta(hours=3)).isoformat()
    by = {}
    for m in matches(since):
        by.setdefault(m["groupId"], []).append(m)
    w_tot = n_tot = series = done = 0
    above = [0, 0, 0]; below = [0, 0, 0]
    for g in groups:
        ms = by.get(g["groupId"], []); fin = [m for m in ms if m["status"] == "finished"]
        if len(fin) == 5:
            g["wins"] = sum(1 for m in fin for t in m["teams"] if t["name"] == US and t.get("result") == "win")
        if "wins" in g:
            w = g["wins"]; w_tot += w; n_tot += 5; done += 1; series += w >= 3
            side = above if g.get("above") else below
            side[0] += w; side[1] += 5; side[2] += w >= 3
            state = f"{w}-{5 - w}" + ("  won" if w >= 3 else "")
        else:
            state = f"{len(fin)}/5 finished" if ms else "not listed"
        print(f"  rank {g['rank']:3d} {g['rating']:6.0f}  {g['name'][:28]:28} {state}")
    path.write_text(json.dumps(groups, indent=1))
    if n_tot:
        print(f"finished {done} groups: series won {series}; games {w_tot}/{n_tot} ({w_tot * 100 / n_tot:.0f}%)")
        for label, s in (("rated above us", above), ("rated below us", below)):
            if s[1]:
                print(f"  {label}: series {s[2]}/{s[1] // 5}, games {s[0]}/{s[1]} ({s[0] * 100 / s[1]:.0f}%)")


if __name__ == "__main__":
    main()
