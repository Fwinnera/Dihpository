#!/usr/bin/env python3
"""Per map-side record of many bench tags against one opponent.

    permap.py OPP_SUFFIX [--only TAG,TAG] [--show]

Reads every ws/bench/h2h_*<suffix> tag (e.g. _eq). Prints, per map-side, how
many tags won it and the best tags. The 'oracle' line is what picking the
best tag per map-side would score in these same games: an upper bound that
is biased upwards by selection, not an estimate.
"""
import collections
import json
import sys
from pathlib import Path

BENCH = Path(__file__).resolve().parent.parent / "ws/bench"


def load(tag):
    out = {}
    for f in (BENCH / tag).glob("*__*__*.json"):
        o, m, s = f.stem.split("__")
        us = "teamA" if s == "A" else "teamB"
        d = json.loads(f.read_text())
        g = {k["team"]: int(k["submittedGems"]) for k in d["teams"]}
        them = "teamB" if us == "teamA" else "teamA"
        out[(m, s)] = (g[us] > g[them], g[us] - g[them])
    return out


def main(argv):
    suffix = argv[0]
    only = None
    if "--only" in argv:
        only = argv[argv.index("--only") + 1].split(",")
    tags = sorted(p.name for p in BENCH.glob(f"h2h_*{suffix}") if p.is_dir())
    if only:
        tags = [t for t in tags if t in only]
    data = {t: load(t) for t in tags}
    data = {t: d for t, d in data.items() if len(d) == 80}
    keys = sorted({k for d in data.values() for k in d})
    oracle = 0
    for k in keys:
        wins = [t for t, d in data.items() if d.get(k, (False,))[0]]
        oracle += bool(wins)
        if "--show" in argv:
            print(f"{k[0]:24} {k[1]}  won by {len(wins):2}/{len(data)}  {' '.join(w.replace('h2h_', '').replace(suffix, '') for w in wins[:8])}")
    print(f"{len(data)} tags with all 80 games; oracle {oracle}/80")
    for t, d in sorted(data.items(), key=lambda x: -sum(v[0] for v in x[1].values())):
        print(f"  {t:28} {sum(v[0] for v in d.values())}/80")


if __name__ == "__main__":
    main(sys.argv[1:])
