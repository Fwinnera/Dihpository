#!/usr/bin/env python3
"""For each of our deaths: where our other living champions were 10 rounds earlier (distance to the victim),
and the same for their deaths (their teammates). Needs skirm.py's fights.json and the states."""
import collections, json, sys
from pathlib import Path
US = "Milk and Potatoes"
fights = json.loads(Path("/home/user/runs/fights.json").read_text())
meta = {m["matchId"]: m for m in json.loads(Path(sys.argv[1], "meta.json").read_text())}
cache = {}
def states(mid):
    if mid not in cache:
        cache.clear()
        cache[mid] = {json.loads(l)["r"]: json.loads(l) for l in Path(sys.argv[2], f"{mid}.jsonl").read_text().splitlines()}
    return cache[mid]
def cheb(a, b): return max(abs(a[0]-b[0]), abs(a[1]-b[1]))
out = collections.defaultdict(list)
for x in sorted(fights, key=lambda x: x["match"]):
    st = states(x["match"])
    me = next(t for t in meta[x["match"]]["teams"] if t["name"] == US)
    ours = 0 if me["side"] == "a" else 1
    r0 = x["round"] - 10
    s0 = st.get(r0); s1 = st.get(x["round"] - 1)
    if not s0 or not s1: continue
    vteam = ours if x["victim"] == "us" else 1 - ours
    # victim = champion alive in s1 and dead at x["round"]
    dead_now = {c[0] for c in st[x["round"]]["c"] if not c[7]}
    cands = [c for c in s1["c"] if c[1] == vteam and c[7] and c[0] in dead_now]
    if not cands: continue
    v = cands[0]
    pos = (v[3], v[4])
    d = sorted(cheb(pos, (c[3], c[4])) for c in s0["c"] if c[1] == vteam and c[7] and c[0] != v[0] and c[3] >= 0)
    out[(x["victim"], x["zone"], x["allies"] <= 1 and x["foes"] >= 2)].append(d)
for k in sorted(out):
    rows = out[k]
    n = len(rows)
    w8 = sum(1 for d in rows if any(v <= 8 for v in d)) / n
    w12 = sum(1 for d in rows if any(v <= 12 for v in d)) / n
    two12 = sum(1 for d in rows if sum(v <= 12 for v in d) >= 2) / n
    print(f"{k[0]:<5}{k[1]:<12} outnumbered={str(k[2]):<5} n={n:<4} ally within 8: {100*w8:4.0f}%  within 12: {100*w12:4.0f}%  two within 12: {100*two12:4.0f}%")
