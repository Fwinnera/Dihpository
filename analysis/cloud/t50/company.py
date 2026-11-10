#!/usr/bin/env python3
"""company.py STATES_DIR META_JSON [--us TEAM_ID] [--upto 400]: who farms what, in what company (rounds 1..N).
Groups team-games as focus/opp (meta 'focus') or us/them (--us)."""
import json, sys, glob, collections
from pathlib import Path
a = sys.argv[1:]
us = None; upto = 400
if "--us" in a: i = a.index("--us"); us = a[i + 1]; del a[i:i + 2]
if "--upto" in a: i = a.index("--upto"); upto = int(a[i + 1]); del a[i:i + 2]
st_dir, meta_f = a[0], a[1]
meta = {m["matchId"]: m for m in json.load(open(meta_f))}
NAMES = ["ryth", "vesper", "vendetta", "cassi", "issac", "stellar", "prism", "marcella", "willow", "ren", "varg", "tavi", "hor"]
def ctype(hp):
    return {1350: "wolf", 2400: "elk", 5000: "golem", 120: "cluster", 20000: "mono"}.get(hp, f"hp{hp}")
agg = collections.defaultdict(lambda: collections.defaultdict(float))
openings = collections.defaultdict(list)
for f in sorted(glob.glob(st_dir + "/*.jsonl")):
    mid = Path(f).stem
    m = meta.get(mid)
    if not m: continue
    side_team = {0: next(t for t in m["teams"] if t["side"] == "a"), 1: next(t for t in m["teams"] if t["side"] == "b")}
    camps = {}; spawn = {}
    first_hit = {}
    T = {0: collections.defaultdict(float), 1: collections.defaultdict(float)}
    for line in open(f):
        d = json.loads(line)
        if "camps" in d:
            for c in d["camps"]: camps.setdefault(c[0], (c[1], c[2], c[3]))
            continue
        r = d["r"]
        if r < 1 or r > upto or not d["c"]: continue
        ch = d["c"]
        for c in ch:
            if c[0] not in spawn: spawn[c[0]] = (c[3], c[4])
        alive = [c for c in ch if c[7]]
        for c in ch:
            t = T[c[1]]
            t["rounds"] += 1
            if not c[7]: t["dead"] += 1; continue
            if max(abs(c[3] - spawn[c[0]][0]), abs(c[4] - spawn[c[0]][1])) <= 3: t["home"] += 1
            mates = [o for o in alive if o[1] == c[1] and o[0] != c[0]]
            nd = min((max(abs(o[3] - c[3]), abs(o[4] - c[4])) for o in mates), default=99)
            t["alive"] += 1
            if nd <= 3: t["mate3"] += 1
            if nd > 5: t["alone5"] += 1
        farming = set()
        for k, x, y, lost in d.get("d", []):
            ct = ctype(camps.get(k, (0, 0, 0))[2])
            near = [c for c in alive if max(abs(c[3] - x), abs(c[4] - y)) <= 4]
            for team in (0, 1):
                mine = [c for c in near if c[1] == team]
                if not mine: continue
                if len({c[1] for c in near}) > 1:
                    # both teams near: credit the nearer team
                    other = [c for c in near if c[1] != team]
                    if min(max(abs(c[3] - x), abs(c[4] - y)) for c in mine) > min(max(abs(c[3] - x), abs(c[4] - y)) for c in other): continue
                t = T[team]
                t["dmg"] += lost; t["dmg_" + ct] += lost
                if len(mine) >= 2: t["dmg_grp"] += lost
                if len(mine) >= 3: t["dmg_grp3"] += lost
                for c in mine:
                    farming.add(c[0])
                    if c[0] not in first_hit:
                        first_hit[c[0]] = (r, ct, len(mine), NAMES[c[2]] if c[2] < len(NAMES) else str(c[2]), team)
        for c in alive:
            if c[0] in farming: T[c[1]]["farm_rounds"] += 1
    for team in (0, 1):
        tm = side_team[team]
        if us: key = "us" if tm["teamId"] == us else "them"
        else: key = "focus" if tm["teamId"] == m.get("focus") else "opp"
        g = agg[key]; g["n"] += 1
        for k, v in T[team].items(): g[k] += v
        fh = sorted(v for v in first_hit.values() if v[4] == team)
        openings[key].append((m.get("map"), tm["name"][:14], [(v[0], v[3], v[1], v[2]) for v in fh]))
for key, g in agg.items():
    n = g["n"]
    print(f"== {key}: {int(n)} team-games, rounds 1-{upto}")
    print(f"  camp damage a game {g['dmg']/n:8.0f}   by type: " + ", ".join(f"{k[4:]} {g[k]/n:.0f}" for k in sorted(g) if k.startswith('dmg_') and not k.startswith('dmg_grp')))
    print(f"  share of camp damage with 2+ teammates on the camp {100*g['dmg_grp']/max(1,g['dmg']):.0f}%, with 3+ {100*g['dmg_grp3']/max(1,g['dmg']):.0f}%")
    print(f"  champion-rounds: dead {100*g['dead']/g['rounds']:.1f}%, near spawn {100*g['home']/g['rounds']:.1f}%, farming {100*g['farm_rounds']/g['rounds']:.1f}%")
    print(f"  living rounds: teammate within 3: {100*g['mate3']/g['alive']:.0f}%, none within 5: {100*g['alone5']/g['alive']:.0f}%")
if "--openings" in sys.argv or True:
    for key, lst in openings.items():
        print(f"-- openings ({key}): first camp hit per champion (round, champion, camp, teammates on it)")
        for mp, name, fh in lst[:12]:
            print(f"  {mp:<22}{name:<15}" + "  ".join(f"{r}:{c}:{t}:{k}" for r, c, t, k in fh))
