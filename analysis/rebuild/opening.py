#!/usr/bin/env python3
"""Label shares in the opening (rounds < LIMIT): opening.py RUNDIR [LIMIT]"""
import sys
from collections import Counter, defaultdict
from pathlib import Path
src = Path(__file__).with_name("profsum.py").read_text()
limit = int(sys.argv[2]) if len(sys.argv) > 2 else 100
ns = {"__name__": "opening"}
sys.argv = [sys.argv[0], sys.argv[1]]
exec(compile(src.split("labels = defaultdict(Counter)")[0], "profsum", "exec"), ns)
lab = defaultdict(Counter); n = 0
first_farm = defaultdict(list)
for opp, mp, side, ours, theirs, rows in ns["games"]():
    n += 1
    seen = set()
    for r in sorted(rows):
        if r[0] < limit:
            lab[r[1]][r[2]] += 1; lab["TEAM"][r[2]] += 1
        if r[2] == "farm" and r[1] not in seen:
            seen.add(r[1]); first_farm[r[1]].append(r[0])
order = [l for l, _ in lab["TEAM"].most_common(12)]
print(f"{n} games, rounds < {limit}")
print("  %-14s" % "" + "".join("%10s" % l[:9] for l in order))
for c in ["TEAM"] + sorted(k for k in lab if k != "TEAM"):
    t = sum(lab[c].values()) or 1
    print("  %-14s" % c + "".join("%9.1f%%" % (100 * lab[c][l] / t) for l in order))
import statistics as st
print("first farm round, median:", {c: st.median(v) for c, v in first_farm.items()})
