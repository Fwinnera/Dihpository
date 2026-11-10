#!/usr/bin/env python3
"""deaths.py STATES_DIR META_JSON [--us TEAM_ID]: every death, with local numbers before it, depth, flight, gems."""
import json, sys, glob, collections
from pathlib import Path
a = sys.argv[1:]
us = "246f9cef-b416-4864-964e-ebcafb97f7ad"
if "--us" in a: i = a.index("--us"); us = a[i + 1]; del a[i:i + 2]
st_dir, meta_f = a[0], a[1]
meta = {m["matchId"]: m for m in json.load(open(meta_f))}
def dist(p, q): return max(abs(p[0] - q[0]), abs(p[1] - q[1]))
agg = {"us": collections.Counter(), "them": collections.Counter()}
num = {"us": collections.Counter(), "them": collections.Counter()}
games = 0
for f in sorted(glob.glob(st_dir + "/*.jsonl")):
    m = meta.get(Path(f).stem)
    if not m: continue
    me = next(t for t in m["teams"] if t["teamId"] == us); ours = 0 if me["side"] == "a" else 1
    rounds = []
    for line in open(f):
        d = json.loads(line)
        if "camps" in d or not d.get("c"): continue
        rounds.append(d)
    if not rounds: continue
    games += 1
    spawn = {}
    for c in rounds[0]["c"]: spawn.setdefault(c[1], (c[3], c[4]))
    idx = {d["r"]: d for d in rounds}
    prev = None
    for d in rounds:
        if prev is not None:
            was = {c[0]: c for c in prev["c"]}
            for c in d["c"]:
                p = was.get(c[0])
                if p is None or not p[7] or c[7]: continue
                # c died this round; p = last living state
                who = "us" if c[1] == ours else "them"
                A = agg[who]; A["deaths"] += 1
                r = d["r"]
                pos = (p[3], p[4])
                def counts(rr):
                    s = idx.get(rr)
                    if not s: return None
                    v = next((x for x in s["c"] if x[0] == c[0]), None)
                    if not v or not v[7]: return None
                    vp = (v[3], v[4])
                    al = sum(1 for x in s["c"] if x[1] == c[1] and x[0] != c[0] and x[7] and dist((x[3], x[4]), vp) <= 5)
                    en = sum(1 for x in s["c"] if x[1] != c[1] and x[7] and dist((x[3], x[4]), vp) <= 5)
                    na = min((dist((x[3], x[4]), vp) for x in s["c"] if x[1] == c[1] and x[0] != c[0] and x[7]), default=99)
                    return al, en, na, v[5] / max(1, v[6]), vp, v[9]
                c1, c5, c10 = counts(r - 1), counts(r - 5), counts(r - 10)
                if c1:
                    al, en = c1[0], c1[1]
                    num[who][(min(al, 3), min(en, 4))] += 1
                    if en > al + 1: A["outnumbered (enemies >= allies+2 incl. victim)"] += 1
                    if al == 0: A["no ally within 5 at death"] += 1
                    A["gems carried"] += c1[5]
                    if c1[5] >= 10: A["carrying 10+ gems"] += 1
                if c10:
                    A["with t-10"] += 1
                    if c10[1] == 0: A["no enemy within 5 ten rounds before"] += 1
                    A["hp at t-10"] += c10[3]
                    if c10[2] > 8: A["nearest ally > 8 ten rounds before"] += 1
                    home = spawn[c[1]]
                    if c1 and dist(c1[4], home) < dist(c10[4], home) - 2: A["moved 3+ toward home in last 10"] += 1
                    if c1 and dist(c1[4], c10[4]) <= 2: A["stayed within 2 tiles in last 10"] += 1
                home, away = spawn[c[1]], spawn[1 - c[1]]
                depth = dist(pos, home) / max(1, dist(pos, home) + dist(pos, away))
                A["depth<0.33" if depth < 0.33 else "depth<0.66" if depth < 0.66 else "depth>=0.66"] += 1
                A["r<300" if r < 300 else "r<700" if r < 700 else "r>=700"] += 1
        prev = d
print(games, "games")
for who in ("us", "them"):
    A = agg[who]; n = max(1, A["deaths"])
    print(f"== {who}: {A['deaths']/games:.1f} deaths a game")
    for k, v in sorted(A.items()):
        if k in ("deaths", "with t-10"): continue
        if k in ("gems carried",): print(f"   {k:<48}{v/n:6.1f} a death"); continue
        if k == "hp at t-10": print(f"   {'mean health ten rounds before':<48}{100*v/max(1,A['with t-10']):5.0f}%"); continue
        print(f"   {k:<48}{100*v/n:5.0f}%")
    print("   allies(within 5) v enemies at t-1:  " + "  ".join(f"{k[0]}v{k[1]}:{100*v/n:.0f}%" for k, v in sorted(num[who].items(), key=lambda kv: -kv[1])[:10]))
