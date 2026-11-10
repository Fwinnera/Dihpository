#!/usr/bin/env python3
"""deathact.py STATES_DIR ACT_DIR META: what each champion did in the eight rounds before it died (ours v theirs)."""
import json, sys, glob, collections
from pathlib import Path
US = "246f9cef-b416-4864-964e-ebcafb97f7ad"
st_dir, act_dir, meta_f = sys.argv[1:4]
meta = {m["matchId"]: m for m in json.load(open(meta_f))}
cat = {"us": collections.Counter(), "them": collections.Counter()}
detail = {"us": collections.Counter(), "them": collections.Counter()}
for f in sorted(glob.glob(st_dir + "/*.jsonl")):
    mid = Path(f).stem; m = meta.get(mid); fa = Path(act_dir) / f"{mid}.jsonl"
    if not m or not fa.exists(): continue
    me = next(t for t in m["teams"] if t["teamId"] == US); ours = 0 if me["side"] == "a" else 1
    camps = set(); rounds = []
    for line in open(f):
        d = json.loads(line)
        if "camps" in d: camps = {(c[1], c[2]) for c in d["camps"]}; continue
        if d.get("c"): rounds.append(d)
    turn = collections.defaultdict(list)
    for l in fa.open():
        r = json.loads(l)
        if isinstance(r, dict) or r[1] < 0: continue
        turn[(r[0], r[1])].append(r)
    prev = None
    for d in rounds:
        if prev is not None:
            was = {c[0]: c for c in prev["c"]}
            for c in d["c"]:
                p = was.get(c[0])
                if p is None or not p[7] or c[7]: continue
                who = "us" if c[1] == ours else "them"
                r = d["r"]; k = c[0]
                ac = collections.Counter()
                for rr in range(r - 8, r):
                    acts = turn.get((rr, k), [])
                    codes = {x[2] for x in acts}
                    if 5 in codes:
                        ac["atk_camp" if any(x[2] == 5 and (x[5], x[6]) in camps for x in acts) else "atk_champ"] += 1
                    elif 6 in codes: ac["cast"] += 1
                    elif 4 in codes: ac["move"] += 1
                    else: ac["none"] += 1
                C = cat[who]; C["n"] += 1
                if ac["atk_champ"] >= 3: C["fighting champions (3+ of last 8 turns)"] += 1
                elif ac["atk_camp"] >= 3: C["hitting a camp (3+)"] += 1
                elif ac["move"] >= 5: C["moving (5+)"] += 1
                elif ac["none"] >= 4: C["no action (4+): channel, stun or fuel"] += 1
                else: C["mixed"] += 1
                for kk, v in ac.items(): detail[who][kk] += v
        prev = d
for who in ("us", "them"):
    C = cat[who]; n = max(1, C["n"])
    print(f"== {who}: {C['n']} deaths; last eight turns: " + ", ".join(f"{k} {100*v/n:.0f}%" for k, v in C.most_common() if k != "n"))
    t = sum(detail[who].values())
    print("   turn mix: " + ", ".join(f"{k} {100*v/t:.0f}%" for k, v in detail[who].most_common()))
