#!/usr/bin/env python3
"""Outcome of every camp trip in profiler output: a run of travel rounds toward one group.

    trips.py RUNDIR
"""
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.argv = [sys.argv[0], sys.argv[1]]
src = Path(__file__).with_name("profsum.py").read_text()
# Reuse the parser: run profsum's definitions up to the aggregation loop.
head = src.split("labels = defaultdict(Counter)")[0]
ns = {"__name__": "trips"}
exec(compile(head, "profsum", "exec"), ns)

outcome = Counter()
wasted = Counter()
lengths = defaultdict(list)
deaths_with_gems = []
n = 0
for opp, mp, side, ours, theirs, rows in ns["games"]():
    n += 1
    by = defaultdict(list)
    for r in rows:
        by[r[1]].append(r)
    for champ, rs in by.items():
        rs.sort()
        i = 0
        while i < len(rs):
            r = rs[i]
            if r[2] != "travel":
                i += 1
                continue
            g, j = r[9], i
            while j + 1 < len(rs) and rs[j + 1][2] == "travel" and rs[j + 1][9] == g and rs[j + 1][0] == rs[j][0] + 1:
                j += 1
            length = j - i + 1
            nxt = rs[j + 1] if j + 1 < len(rs) else None
            if nxt is None:
                kind = "game over"
            elif nxt[2] in ("approach", "farm", "to-reward") and nxt[9] == g:
                kind = "arrived"
            elif nxt[2] == "travel":
                kind = "switched camp"
            else:
                kind = "interrupted: " + nxt[2]
            outcome[kind] += 1
            wasted[kind] += length
            lengths[kind].append(length)
            i = j + 1
print(f"{n} games: camp trips by how they ended (trips a game, rounds a game, median length)")
for k, c in outcome.most_common():
    print(f"  {k:<28} {c / n:6.1f}  {wasted[k] / n:7.1f}  {st.median(lengths[k]):5.0f}")
