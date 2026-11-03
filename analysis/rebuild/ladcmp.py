#!/usr/bin/env python3
"""Us against our ladder opponents, game by game, from downloaded ranked summaries.

    ladcmp.py FOLDER [MIN_RATING]     (FOLDER = ws/bench/ladder_NAME, from fetcheras.py)

For both sides of every game: camp damage and gold earned by rounds 100 and 300, gold
spent on items, gems collected and submitted, kills, deaths, healing received, and gold
spent on consumables. Prints medians for won and lost games, the opponents' drafts and
item families in the games we lost, and the same split by opponent rating when the
ladder listing in the scratch folder is passed as a third argument.
"""
import collections
import json
import statistics as st
import sys
from pathlib import Path

US = "Milk and Potatoes"
folder = Path(sys.argv[1])
min_rating = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
ratings = {}
for p in sys.argv[3:]:
    for t in json.loads(Path(p).read_text())["teams"]:
        ratings[t["name"]] = t["rating"]
ms = json.loads((folder / "matches.json").read_text())


def expand(runs, n):
    out = []
    for r in runs:
        out += [float(r["value"])] * int(r["duration"])
        if len(out) > n:
            break
    return (out + [out[-1] if out else 0.0] * n)[:n]


def side_stats(d, side):
    ids = {c["id"] for c in d["roster"]["champions"] if c["team"] == side}

    def at(metric, rnd):
        s = 0.0
        for x in d["championTimelines"]:
            if x["owner"]["id"] in ids and x["metric"] == metric and x["runs"]:
                s += expand(x["runs"], rnd + 1)[rnd]
        return s

    champs = [c for c in d["champions"] if c["team"] == side]
    tot = lambda k: sum(float(c["metrics"][k]) for c in champs)
    fam = collections.Counter()
    for c in champs:
        for it in c["itemsBought"]:
            words = it["item"].split()
            if "Emblem" in words:
                fam[words[0]] += int(it["quantity"])
    cons = collections.Counter()
    for c in champs:
        for it in c["consumablesBought"]:
            cons[it["consumable"]] += int(it["quantity"])
    return dict(d100=at("monsterDamageDone", 100), d300=at("monsterDamageDone", 300),
                g100=at("earnedGold", 100), g300=at("earnedGold", 300), g600=at("earnedGold", 600),
                gold=tot("earnedGold"), spent=tot("spentGold"), coll=tot("collectedGems"),
                sub=tot("submittedGems"), kills=tot("kills"), deaths=tot("deaths"),
                heal=tot("healingReceived"), dmg=tot("monsterDamageDone"),
                names=[c["name"] for c in champs], fam=fam, cons=cons)


rows = []
for m in ms:
    f = folder / "summaries" / f"{m['matchId']}.json"
    if not f.exists():
        continue
    d = json.loads(f.read_text())
    me = next(t for t in m["teams"] if t["name"] == US)
    op = next(t for t in m["teams"] if t["name"] != US)
    if ratings and ratings.get(op["name"], 0) < min_rating:
        continue
    a, b = ("teamA", "teamB") if me["side"] == "a" else ("teamB", "teamA")
    rows.append(dict(win=me.get("result") == "win", map=m["map"], opp=op["name"], rating=ratings.get(op["name"]),
                     rounds=d["match"]["roundsCompleted"], us=side_stats(d, a), them=side_stats(d, b)))

keys = ["d100", "d300", "g100", "g300", "g600", "gold", "spent", "coll", "sub", "kills", "deaths", "heal", "dmg"]
print(f"{len(rows)} games, won {sum(r['win'] for r in rows)}")
for label, sel in (("won", True), ("lost", False)):
    rs = [r for r in rows if r["win"] == sel]
    if not rs:
        continue
    print(f"\n{label} ({len(rs)}), median rounds {st.median(r['rounds'] for r in rs):.0f}")
    print(f"  {'':8}" + "".join(f"{k:>8}" for k in keys))
    for who in ("us", "them"):
        print(f"  {who:8}" + "".join(f"{st.median(r[who][k] for r in rs):8.0f}" for k in keys))

lost = [r for r in rows if not r["win"]]
print("\nopponent champions in games we lost:", collections.Counter(n for r in lost for n in r["them"]["names"]).most_common())
print("our champions:", collections.Counter(n for r in rows for n in r["us"]["names"]).most_common())
for who in ("us", "them"):
    fam = collections.Counter()
    cons = collections.Counter()
    for r in lost:
        fam.update(r[who]["fam"])
        cons.update(r[who]["cons"])
    n = max(1, len(lost))
    print(f"{who} emblems a lost game:", {k: round(v / n, 1) for k, v in fam.most_common()})
    print(f"{who} consumables a lost game:", {k: round(v / n, 1) for k, v in cons.most_common()})
