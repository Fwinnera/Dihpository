#!/usr/bin/env python3
"""coattack.py DATA_DIR STATES_DIR ACT_DIR [--us TEAM_ID] [--upto N]: camp attack turns by number of teammates
attacking the same camp group (camps within 2 tiles count as one group) in the same round, and by camp type."""
import collections, json, sys
from pathlib import Path
a = sys.argv[1:]
us = None; upto = 400
if "--us" in a: i = a.index("--us"); us = a[i + 1]; del a[i:i + 2]
if "--upto" in a: i = a.index("--upto"); upto = int(a[i + 1]); del a[i:i + 2]
bdir, sdir, adir = Path(a[0]), Path(a[1]), Path(a[2])
meta = json.loads((bdir / "meta.json").read_text())
cnt = collections.defaultdict(collections.Counter)
def ctype(hp): return {1350: "wolf", 2400: "elk", 5000: "golem", 120: "cluster", 20000: "mono"}.get(hp, "?")
for m in meta:
    fa = adir / f"{m['matchId']}.jsonl"; fs = sdir / f"{m['matchId']}.jsonl"
    if not fa.exists() or not fs.exists(): continue
    team_of = {}; camps = {}
    for l in fs.open():
        s = json.loads(l)
        if "camps" in s:
            for c in s["camps"]: camps.setdefault((c[1], c[2]), c[3])
            continue
        if s["c"]:
            for c in s["c"]: team_of[c[0]] = c[1]
            if len(team_of) >= 6 and s["r"] > 3: break
    # group camps: union of camps within Chebyshev distance 1 (cardinal adjacency approximated)
    pos = list(camps); parent = {p: p for p in pos}
    def find(p):
        while parent[p] != p: parent[p] = parent[parent[p]]; p = parent[p]
        return p
    for i, p in enumerate(pos):
        for q in pos[i + 1:]:
            if abs(p[0] - q[0]) + abs(p[1] - q[1]) == 1: parent[find(p)] = find(q)
    gsize = collections.Counter(find(p) for p in pos)
    gstr = collections.Counter()
    for p in pos: gstr[find(p)] += {1350: 20, 2400: 60, 5000: 120, 20000: 200}.get(camps[p], 0)
    side_key = {}
    for t in m["teams"]:
        k = 0 if t["side"] == "a" else 1
        side_key[k] = ("us" if t["teamId"] == us else "them") if us else ("focus" if t["teamId"] == m.get("focus") else "opp")
    per = collections.defaultdict(set)  # (round, team, group) -> attackers
    typ = {}
    for l in fa.open():
        r = json.loads(l)
        if isinstance(r, dict) or r[1] < 0 or r[0] > upto or r[2] != 5: continue
        tgt = (r[5], r[6])
        if tgt not in camps: continue
        g = find(tgt)
        per[(r[0], team_of.get(r[1]), g)].add(r[1])
    for (rd, team, g), who in per.items():
        if team is None: continue
        c = cnt[side_key[team]]
        n = len(who)
        c["turns"] += n
        c[f"n{min(n,4)}"] += n
        s = gstr[g]
        band = "harmless" if s == 0 else "light<=40" if s <= 40 else "60-80" if s <= 80 else "100-180" if s <= 180 else "heavy>180"
        c["str_" + band] += n
        c[f"str_{band}_n{min(n,4)}"] += n
    cnt[side_key[0]]["games"] += 1; cnt[side_key[1]]["games"] += 1
for side, c in cnt.items():
    t = max(1, c["turns"])
    print(f"{side:<6} camp-attack turns a game {c['turns']/max(1,c['games']):.0f}; attackers on the group: " + "  ".join(f"{k[1:]}{'+' if k=='n4' else ''}: {100*c[k]/t:.0f}%" for k in ("n1", "n2", "n3", "n4")))
    for band in ("harmless", "light<=40", "60-80", "100-180", "heavy>180"):
        b = c["str_" + band]
        if not b: continue
        print(f"        group strength {band:<10} {100*b/t:5.1f}% of attack turns;  alone {100*c[f'str_{band}_n1']/b:.0f}%  2: {100*c[f'str_{band}_n2']/b:.0f}%  3: {100*c[f'str_{band}_n3']/b:.0f}%  4+: {100*c[f'str_{band}_n4']/b:.0f}%")
