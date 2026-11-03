#!/usr/bin/env python3
"""Retreats with their local odds (needs mkprofx.py's two extra fields): for every retreat
or disengage episode, whether the champion died within 15 rounds, by enemies within 6,
allies within 5, health fraction and distance from home at the start of the episode.

    deaths2.py RUNDIR
"""
import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

src = Path(__file__).with_name("profsum.py").read_text()
ns = {"__name__": "deaths2"}
sys.argv = [sys.argv[0], sys.argv[1]]
exec(compile(src.split("labels = defaultdict(Counter)")[0], "profsum", "exec"), ns)
T = json.loads(Path(__file__).with_name("camps86.json").read_text())

FLEE = {"retreat", "disengage"}
cells = defaultdict(lambda: [0, 0])     # key -> [episodes, deaths]
starts = []
n = 0
for opp, mp, side, ours, theirs, rows in ns["games"]():
    n += 1
    info = T.get(mp) or {}
    spawn = info.get("spawn_a" if side == "A" else "spawn_b") or []
    by = defaultdict(list)
    for r in rows:
        by[r[1]].append(r)
    for c, rs in by.items():
        rs.sort()
        i = 0
        while i < len(rs):
            r = rs[i]
            if r[2] not in FLEE or (i > 0 and rs[i - 1][2] in FLEE and rs[i - 1][0] >= r[0] - 2):
                i += 1
                continue
            extra = r[10] if len(r) > 10 else ()
            if len(extra) < 2:
                i += 1
                continue
            foes, friends = extra[0], extra[1]
            hp = r[5] / max(1.0, r[6])
            home = min((max(abs(r[3] - p[0]), abs(r[4] - p[1])) for p in spawn), default=-1)
            died = any(q[2] == "dead" and q[0] <= r[0] + 15 for q in rs[i + 1:i + 40])
            starts.append((died, foes, friends, hp, home, r[2], r[7]))
            key = (r[2], min(foes, 3), min(friends, 2))
            cells[key][0] += 1
            cells[key][1] += died
            i += 1
print(f"{n} games, {len(starts) / n:.1f} retreat/disengage episodes a game, "
      f"{sum(s[0] for s in starts) / n:.1f} of them end in death within 15 rounds")
print("\nby kind, enemies within 6 (3 = 3+), allies within 5 (2 = 2+): episodes a game, share that die")
for key in sorted(cells):
    e, d = cells[key]
    if e / n >= 0.2:
        print(f"  {key[0]:<10} enemies {key[1]}  allies {key[2]}   {e / n:5.1f} a game   {100 * d / e:4.0f}% die")
for kind in FLEE:
    for died in (True, False):
        s = [x for x in starts if x[5] == kind and x[0] == died]
        if s:
            print(f"  {kind:<10} {'died' if died else 'lived'}: health {st.median(x[3] for x in s):.2f}, "
                  f"home {st.median(x[4] for x in s):.0f} tiles, enemies {st.mean(x[1] for x in s):.1f}, "
                  f"allies {st.mean(x[2] for x in s):.1f}, gems {st.mean(x[6] for x in s):.1f}")
