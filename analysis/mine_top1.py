#!/usr/bin/env python3
"""Every behavioural cue about the #1 team, per champion, from its summaries.

    mine_top1.py [FOLDER] [TEAM]     # default top1, "prism best girl"
"""
from __future__ import annotations

import json
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

WS = Path(__file__).resolve().parent.parent / "ws"
folder = sys.argv[1] if len(sys.argv) > 1 else "top1"
TEAM = sys.argv[2] if len(sys.argv) > 2 else "prism best girl"
TABLE = json.loads((WS / "bench/camptable.json").read_text())


def expand(runs, n):
    out = []
    for r in runs:
        out += [float(r["value"])] * int(r["duration"])
    return (out + [out[-1] if out else 0.0] * n)[:n]


def depth(p, home, away):
    vx, vy = away[0] - home[0], away[1] - home[1]
    L = vx * vx + vy * vy
    return None if not L else ((p[0] - home[0]) * vx + (p[1] - home[1]) * vy) / L


orders = Counter(); sizes = Counter(); games = 0
per = defaultdict(lambda: defaultdict(list))
shop_round = defaultdict(list); emblem_seq = defaultdict(Counter); shard_first = defaultdict(list)
dep_sizes = defaultdict(list); dep_rounds_to_end = defaultdict(list)
mono_part = Counter(); mono_events = 0
ability_like = defaultdict(lambda: defaultdict(float))
for m in json.loads((WS / "bench" / folder / "matches.json").read_text()):
    me = next((t for t in m["teams"] if t["name"] == TEAM), None)
    f = WS / "bench" / folder / "summaries" / f"{m['matchId']}.json"
    if not me or not f.exists():
        continue
    d = json.loads(f.read_text()); games += 1
    side = "teamA" if me["side"] == "a" else "teamB"; other = "teamB" if side == "teamA" else "teamA"
    R = d["match"]["roundsCompleted"]
    mine = sorted((c for c in d["roster"]["champions"] if c["team"] == side), key=lambda c: c["draftPick"])
    orders[tuple(c["name"] for c in mine)] += 1; sizes[len(mine)] += 1
    names = {c["id"]: c["name"] for c in mine}
    mono = {g["id"] for g in TABLE.get(m["map"].replace("-", "_"), []) if g["monolith"]}
    buys = defaultdict(list)
    for e in d["events"]:
        if e["kind"] == "buyItem":
            buys[(e.get("owner") or {}).get("team")] += [(x["x"], x["y"]) for x in e["entries"] if "x" in x]
    home = away = None
    if buys[side] and buys[other]:
        home = (st.median(p[0] for p in buys[side]), st.median(p[1] for p in buys[side]))
        away = (st.median(p[0] for p in buys[other]), st.median(p[1] for p in buys[other]))
    tl = defaultdict(dict)
    for x in d["championTimelines"]:
        if x["owner"]["id"] in names:
            tl[x["owner"]["id"]][x["metric"]] = expand(x["runs"], R + 1)
    for cid, nm in names.items():
        s = tl[cid]
        if "gems" in s:
            per[nm]["peak carried"].append(max(s["gems"]))
            per[nm]["mean carried"].append(st.mean(s["gems"]))
        for k in ("healingDone", "shieldingDone", "healingReceived", "championDamageDone", "monsterDamageDone",
                  "championDamageTaken", "monsterDamageTaken", "earnedGold", "spentGold"):
            if k in s:
                ability_like[nm][k] += s[k][-1]
    shards = defaultdict(Counter); seq = defaultdict(list); first = {}
    clears_by = defaultdict(list)
    for e in d["events"]:
        o = e.get("owner") or {}
        if o.get("team") != side:
            continue
        nm = o.get("name")
        for x in e.get("entries", []):
            r = x["timestamp"]["round"]; tg = x.get("target") or {}
            if e["kind"] == "buyItem":
                it = tg.get("name", "")
                if nm not in first:
                    first[nm] = r
                if "Shard" in it:
                    shards[nm][it] += int(x.get("value", 1) or 1)
                    if shards[nm][it] >= 5:
                        shards[nm][it] -= 5; seq[nm].append((r, it.replace(" Shard of ", ":")))
                elif "Emblem" in it:
                    seq[nm].append((r, it.replace(" Emblem of ", ":")))
            elif e["kind"] == "campClear":
                clears_by[nm].append(r)
                if home and "x" in x:
                    dp = depth((x["x"], x["y"]), home, away)
                    ph = "early" if r < 300 else "mid" if r < 700 else "late"
                    if dp is not None:
                        per[nm][f"clear depth {ph}"].append(dp)
                if tg.get("id") in mono:
                    mono_part[nm] += 1; mono_events += 1
            elif e["kind"] == "gemSubmission":
                v = float(x.get("value", 0) or 0); dep_sizes[nm].append(v); dep_rounds_to_end[nm].append(R - r)
            elif e["kind"] == "wardPlacement" and home and "x" in x:
                dp = depth((x["x"], x["y"]), home, away)
                if dp is not None:
                    per[nm]["ward depth"].append(dp)
    for nm, s in seq.items():
        emblem_seq[nm][tuple(i for _, i in sorted(s)[:5])] += 1
        for k, (r, it) in enumerate(sorted(s)[:3]):
            per[nm][f"emblem {k + 1} round"].append(r)
    for nm, r in first.items():
        shop_round[nm].append(r)
    for nm, rs in clears_by.items():
        per[nm]["first clear round"].append(min(rs))
        per[nm]["clears"].append(len(rs))

print(f"### {TEAM}: {games} games\n")
print("DRAFT ORDER (their picks in pick order), most common:")
for o, k in orders.most_common(6):
    print(f"  {k:3d}  {' > '.join(o)}")
print("  roster sizes:", dict(sizes))
names = [n for n, _ in Counter(n for o in orders.elements() for n in o).most_common()]
print("\nPER CHAMPION")
keys = ["clears", "first clear round", "clear depth early", "clear depth mid", "clear depth late",
        "ward depth", "peak carried", "mean carried", "emblem 1 round", "emblem 2 round", "emblem 3 round"]
print("  %-14s" % "" + "".join("%15s" % k[:14] for k in keys))
for nm in names:
    row = ""
    for k in keys:
        v = per[nm][k]
        row += "%15.2f" % st.median(v) if v and "depth" in k else ("%15.0f" % st.median(v) if v else "%15s" % "-")
    print("  %-14s" % nm + row)
print("\nBANKING per champion: deposits a game, median size, share of deposits in the last 50 rounds")
for nm in names:
    ds = dep_sizes[nm]; n = sum(1 for o in orders.elements() for x in o if x == nm) / max(1, sum(orders.values())) * games
    late = sum(1 for r in dep_rounds_to_end[nm] if r <= 50)
    print(f"  {nm:<14} {len(ds) / max(1, n):5.1f} a game   median {st.median(ds) if ds else 0:5.0f} gems   "
          f"last-50-rounds {100 * late / max(1, len(ds)):3.0f}%   biggest {max(ds) if ds else 0:4.0f}")
print("\nDAMAGE AND SUPPORT per champion, per game fielded")
for nm in names:
    a = ability_like[nm]; n = max(1, sum(1 for o in orders.elements() for x in o if x == nm))
    print(f"  {nm:<14} monster dmg {a['monsterDamageDone'] / n:7.0f}   champion dmg {a['championDamageDone'] / n:6.0f}   "
          f"taken {a['championDamageTaken'] / n + a['monsterDamageTaken'] / n:7.0f}   shield {a['shieldingDone'] / n:5.0f}   "
          f"heal {a['healingDone'] / n:5.0f}   gold {a['earnedGold'] / n:5.0f}")
print("\nMONOLITH CLEARS by champion:", dict(mono_part.most_common()))
print("\nEMBLEM SEQUENCE (first five, purchase order)")
for nm in names:
    for s, k in emblem_seq[nm].most_common(2):
        print(f"  {nm:<14} x{k:2d}  {' > '.join(s)}")
