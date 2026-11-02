#!/usr/bin/env python3
"""Each champion's first camp: firstcamp.py RUNDIR"""
import json, statistics as st, sys
from collections import defaultdict
from pathlib import Path
src = Path(__file__).with_name("profsum.py").read_text()
ns = {"__name__": "firstcamp"}
sys.argv = [sys.argv[0], sys.argv[1]]
exec(compile(src.split("labels = defaultdict(Counter)")[0], "profsum", "exec"), ns)
T = json.loads(Path(__file__).resolve().with_name("camps86.json").read_text())
dist = defaultdict(list); first_hit = defaultdict(list); val = defaultdict(list); same = []
for opp, mp, side, ours, theirs, rows in ns["games"]():
    info = T.get(mp)
    if not info or not info.get("spawn_a") or not info.get("spawn_b"): continue
    spawn = info["spawn_a"] if side == "A" else info["spawn_b"]
    sx = st.mean(p[0] for p in spawn); sy = st.mean(p[1] for p in spawn)
    groups = {g["id"]: g for g in info["groups"]}
    by = defaultdict(list)
    for r in rows: by[r[1]].append(r)
    firsts = []
    for c, rs in by.items():
        rs.sort()
        g = next((r[9] for r in rs if r[2] in ("travel", "approach", "farm") and r[9] >= 0), None)
        h = next((r[0] for r in rs if r[2] == "farm"), None)
        if g is None or g not in groups: continue
        G = groups[g]
        dist[c].append(max(abs(G["x"] - sx), abs(G["y"] - sy))); val[c].append(G["gems"] + 0.3 * G["gold"])
        if h is not None: first_hit[c].append(h)
        firsts.append(g)
    if firsts: same.append(len(firsts) - len(set(firsts)))
for c in sorted(dist):
    print(f"  {c:<12} first camp: spawn distance median {st.median(dist[c]):4.0f}, value {st.median(val[c]):5.0f}; first farm round {st.median(first_hit[c]) if first_hit[c] else -1:4.0f}")
print(f"  champions sharing a first camp with a teammate: {st.mean(same):.2f} a game")
