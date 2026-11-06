#!/usr/bin/env python3
"""Game-by-game outcomes of several lab runs on the same pinned pairings (opponent team, map, side, set):
pairwise agreement, and games won by one run but lost by all others."""
import collections, itertools, json, sys
from pathlib import Path
US = "Milk and Potatoes"
bdir = Path(sys.argv[1]); runs = sys.argv[2:]   # each run: comma-separated arm names (sets 1-3)
meta = json.loads((bdir / "meta.json").read_text())
res = collections.defaultdict(dict)
for run in runs:
    arms = run.split(",")
    for m in meta:
        if m.get("arm") not in arms: continue
        me = next(t for t in m["teams"] if t["name"] == US); opp = next(t for t in m["teams"] if t["name"] != US)
        key = (arms.index(m["arm"]), opp["name"], m["map"], me["side"])
        res[key][run] = me["result"] == "win"
keys = [k for k, v in res.items() if len(v) == len(runs)]
print(f"{len(keys)} games present in all {len(runs)} runs")
names = [r.split(",")[0] for r in runs]
for r, n in zip(runs, names):
    print(f"  {n:<8} wins {sum(res[k][r] for k in keys)}")
for (r1, n1), (r2, n2) in itertools.combinations(zip(runs, names), 2):
    agree = sum(res[k][r1] == res[k][r2] for k in keys)
    print(f"  {n1} vs {n2}: same result in {agree} of {len(keys)}")
for r, n in zip(runs, names):
    solo = [k for k in keys if res[k][r] and not any(res[k][o] for o in runs if o != r)]
    print(f"  only {n} won: {len(solo)}")
always = sum(1 for k in keys if all(res[k][r] for r in runs)); never = sum(1 for k in keys if not any(res[k][r] for r in runs))
print(f"  won by all: {always}; lost by all: {never}; mixed: {len(keys) - always - never}")
