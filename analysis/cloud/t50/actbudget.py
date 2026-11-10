#!/usr/bin/env python3
"""actbudget.py DATA_DIR STATES_DIR ACT_DIR [--us TEAM_ID] [--upto N]: per living champion-turn action shares."""
import collections, json, sys
from pathlib import Path
a = sys.argv[1:]
us = None; upto = 100000
if "--us" in a: i = a.index("--us"); us = a[i + 1]; del a[i:i + 2]
if "--upto" in a: i = a.index("--upto"); upto = int(a[i + 1]); del a[i:i + 2]
bdir, sdir, adir = Path(a[0]), Path(a[1]), Path(a[2])
meta = json.loads((bdir / "meta.json").read_text())
cnt = collections.defaultdict(collections.Counter)
for m in meta:
    fa = adir / f"{m['matchId']}.jsonl"; fs = sdir / f"{m['matchId']}.jsonl"
    if not fa.exists() or not fs.exists(): continue
    alive = {}; team_of = {}; camps = set()
    for l in fs.open():
        s = json.loads(l)
        if "camps" in s:
            camps = {(c[1], c[2]) for c in s["camps"]}; continue
        if s["c"] and s["r"] <= upto:
            for c in s["c"]:
                team_of[c[0]] = c[1]
                alive[(s["r"], c[0])] = c[7]
    turn = collections.defaultdict(list)
    for l in fa.open():
        r = json.loads(l)
        if isinstance(r, dict) or r[1] < 0 or r[0] > upto: continue
        turn[(r[0], r[1])].append(r)
    side_key = {}
    for t in m["teams"]:
        k = 0 if t["side"] == "a" else 1
        if us: side_key[k] = "us" if t["teamId"] == us else "them"
        else: side_key[k] = "focus" if t["teamId"] == m.get("focus") else "opp"
    for (rd, k), is_alive in alive.items():
        c = cnt[side_key[team_of[k]]]
        c["all"] += 1
        if not is_alive: c["dead"] += 1; continue
        c["alive"] += 1
        acts = turn.get((rd, k), [])
        codes = {x[2] for x in acts}
        if 5 in codes:
            on_camp = any(x[2] == 5 and (x[5], x[6]) in camps for x in acts)
            c["attack camp" if on_camp else "attack champ"] += 1
        if 6 in codes: c["cast"] += 1
        if 4 in codes: c["move"] += 1
        if 11 in codes: c["recall"] += 1
        if 26 in codes and not (codes & {4, 5, 6, 11}): c["fuel-out, no action"] += 1
        if not (codes & {4, 5, 6, 11}): c["no move/attack/cast/recall"] += 1
        if 4 in codes and not (codes & {5, 6}): c["move only"] += 1
        for code in codes: c[f"code{code}"] += 1
for side, c in cnt.items():
    print(f"{side:<6} champion-turns {c['all']:>7}, dead {100*c['dead']/max(1,c['all']):.1f}%; of living turns: " +
          "  ".join(f"{k} {100 * c[k] / max(1, c['alive']):.1f}%" for k in ("attack camp", "attack champ", "cast", "move", "move only", "recall", "no move/attack/cast/recall", "fuel-out, no action")))
    print("       codes: " + " ".join(f"{k[4:]}:{100*v/max(1,c['alive']):.1f}" for k, v in sorted(c.items()) if k.startswith("code")))
