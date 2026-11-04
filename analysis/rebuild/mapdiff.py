#!/usr/bin/env python3
"""Map by map, a candidate's screen games against a base's, opponent by opponent.

    mapdiff.py CAND_PREFIX BASE_PREFIX OPP [OPP ...] [--top N]

Tags are CAND_PREFIX_vs_OPP and BASE_PREFIX_vs_OPP (e.g. s43_fc and s31_ab3_submit). The engine is
deterministic, so maps where the candidate's change never fires replay identically; the rest
shows where the change wins and loses. Per map: games won by each (both sides, all opponents)
and the summed gem margin difference.
"""
import glob
import gzip
import json
import sys
from collections import defaultdict
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2] / "ws/bench"
args = [a for a in sys.argv[1:] if not a.startswith("--")]
top = int(sys.argv[sys.argv.index("--top") + 1]) if "--top" in sys.argv else 25
cand, base, opps = args[0], args[1], args[2:]


def load(tag):
    out = {}
    for f in glob.glob(str(BENCH / tag / "*__*__*.json*")):
        name = Path(f).name.replace(".gz", "")
        o, m, side = Path(name).stem.split("__")
        raw = gzip.open(f).read() if f.endswith(".gz") else Path(f).read_bytes()
        d = json.loads(raw)
        s = "teamA" if side == "A" else "teamB"
        g = {k["team"]: int(k["submittedGems"]) for k in d["teams"]}
        t = "teamB" if s == "teamA" else "teamA"
        out[(m, side)] = (g[s] - g[t], g[s] > g[t])
    return out


per = defaultdict(lambda: [0, 0, 0, 0.0, 0])  # map -> [cand wins, base wins, games, margin diff, identical]
for o in opps:
    a, b = load(f"{cand}_vs_{o}"), load(f"{base}_vs_{o}")
    for k in set(a) & set(b):
        p = per[k[0]]
        p[0] += a[k][1]
        p[1] += b[k][1]
        p[2] += 1
        p[3] += a[k][0] - b[k][0]
        p[4] += a[k][0] == b[k][0]
tot = [sum(p[i] for p in per.values()) for i in range(5)]
print(f"{len(per)} maps, {tot[2]} paired games: {cand} {tot[0]} wins, {base} {tot[1]}; identical {tot[4]}; margin diff {tot[3] / max(1, tot[2]):+.0f} a game")
rows = sorted(per.items(), key=lambda kv: kv[1][0] - kv[1][1])
print("worst maps for the candidate:")
for m, p in rows[:top]:
    if p[0] == p[1] and p[4] == p[2]:
        continue
    print(f"  {m:<24} {p[0]:>3} vs {p[1]:>3} of {p[2]:>3}  margin {p[3] / p[2]:+6.0f}  identical {p[4]}")
print("best maps for the candidate:")
for m, p in rows[::-1][:top]:
    if p[0] == p[1] and p[4] == p[2]:
        continue
    print(f"  {m:<24} {p[0]:>3} vs {p[1]:>3} of {p[2]:>3}  margin {p[3] / p[2]:+6.0f}  identical {p[4]}")
