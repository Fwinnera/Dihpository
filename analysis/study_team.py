#!/usr/bin/env python3
"""Per-champion behaviour profile of one team from match summaries.

Summaries carry no position track, so behaviour is rebuilt from two sources:
per-round cumulative timelines for every champion (damage dealt and taken to
monsters and champions, gems carried, collected, submitted, deaths) and the
positioned event log (camp clears, pickups, deposits, purchases, wards, kills).

Each alive champion-round is classed by what changed that round, in priority:
fighting (champion damage dealt or taken), farming (monster damage dealt),
banking (gems submitted), collecting (gems picked up), else "nothing", which is
travel or wandering. Rounds from a death to the champion's next activity are
"dead / walking back".

    study_team.py prism                 # the #1 team's 60 summaries
    study_team.py us                    # our version 93 and greatsage ladder games
"""
from __future__ import annotations

import json
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

WS = Path(__file__).resolve().parent.parent / "ws"
US = "Milk and Potatoes"
METRICS = ("championDamageDone", "championDamageTaken", "monsterDamageDone",
           "submittedGems", "collectedGems", "deaths", "gems")


def expand(runs, n):
    out = []
    for r in runs:
        out += [float(r["value"])] * int(r["duration"])
    return (out + [out[-1] if out else 0.0] * n)[:n]


def sources(which):
    if which == "prism":
        listing = json.loads((WS / "bench/top1/matches.json").read_text())
        for m in listing:
            me = next(t for t in m["teams"] if t["name"] == "prism best girl")
            f = WS / "bench/top1/summaries" / f"{m['matchId']}.json"
            if f.exists():
                yield f, "teamA" if me["side"] == "a" else "teamB", me["result"] == "win"
    else:
        for tag in ("v93_live", "db_base"):
            for gf in sorted((WS / "bench/ladder" / tag).glob("group_*.json")):
                for m in json.loads(gf.read_text()).get("matches", []):
                    me = next((t for t in m["teams"] if t["name"] == US), None)
                    f = WS / "bench/ladder" / tag / "summaries" / f"{m['matchId'][:8]}.json"
                    if me and f.exists():
                        yield f, "teamA" if me["side"] == "a" else "teamB", me["result"] == "win"


def main(which):
    games = 0
    budget = defaultdict(Counter)          # name -> class -> rounds
    fielded, picks = Counter(), defaultdict(list)
    emblem_order = defaultdict(Counter)    # name -> (1st, 2nd, 3rd emblem) tuple counts
    first_emblem_round = defaultdict(list)
    final_families = defaultdict(Counter)
    clears, deposits, dep_gems, kills, deaths, wards, carrier_kills = (defaultdict(int) for _ in range(7))
    clear_gaps = defaultdict(list)
    kill_rounds, death_rounds, rounds_played, wins = [], [], [], 0
    for path, side, win in sources(which):
        d = json.loads(path.read_text())
        games += 1; wins += win
        n = d["match"]["roundsCompleted"]; rounds_played.append(n)
        names = {c["id"]: c["name"] for c in d["roster"]["champions"] if c["team"] == side}
        for c in d["roster"]["champions"]:
            if c["team"] == side:
                fielded[c["name"]] += 1; picks[c["name"]].append(c["draftPick"])
        tl = defaultdict(dict)
        for x in d["championTimelines"]:
            if x["owner"]["id"] in names and x["metric"] in METRICS:
                tl[x["owner"]["id"]][x["metric"]] = expand(x["runs"], n + 1)
        for cid, name in names.items():
            s = tl[cid]
            if len(s) < len(METRICS):
                continue
            dead = False
            for r in range(1, n + 1):
                up = lambda k: s[k][r] > s[k][r - 1]
                if up("deaths"):
                    dead = True
                if up("championDamageDone") or up("championDamageTaken"):
                    cls = "fighting"
                elif up("monsterDamageDone"):
                    cls = "farming camps"
                elif up("submittedGems"):
                    cls = "banking"
                elif up("collectedGems"):
                    cls = "collecting"
                else:
                    cls = "dead / walking back" if dead else "nothing (travel, wandering)"
                if cls != "dead / walking back" and cls != "nothing (travel, wandering)":
                    dead = False
                budget[name][cls] += 1
        # items: emblems in purchase order, and the round the first one completed
        for c in d["champions"]:
            if c["team"] != side:
                continue
            ems = [i["item"] for i in (c.get("itemsBought") or []) if "Emblem" in i["item"]]
            emblem_order[c["name"]][tuple(e.replace(" Emblem of ", ":") for e in ems[:3])] += 1
            for i in c.get("items") or []:
                if "Emblem" in i["item"]:
                    final_families[c["name"]][i["item"].split()[0]] += int(i.get("quantity", 1))
        last_clear = {}
        shards = defaultdict(int)
        for e in d["events"]:
            o = e.get("owner") or {}
            if o.get("team") != side:
                continue
            name = o.get("name")
            for x in e.get("entries", []):
                r = x["timestamp"]["round"]
                if e["kind"] == "campClear":
                    clears[name] += 1
                    if name in last_clear:
                        clear_gaps[name].append(r - last_clear[name])
                    last_clear[name] = r
                elif e["kind"] == "gemSubmission":
                    deposits[name] += 1; dep_gems[name] += float(x.get("value", 0) or 0)
                elif e["kind"] == "kill":
                    kills[name] += 1; kill_rounds.append(r)
                elif e["kind"] == "death":
                    deaths[name] += 1; death_rounds.append(r)
                elif e["kind"] == "wardPlacement":
                    wards[name] += 1
                elif e["kind"] == "buyItem" and "Shard" in (x.get("target") or {}).get("name", ""):
                    shards[name] += int(x.get("value", 1) or 1)
                    if shards[name] >= 5 and name not in [k for k, _ in first_emblem_round.get("_seen", [])]:
                        first_emblem_round[name].append(r)
                        first_emblem_round.setdefault("_seen", []).append((name, r))
        first_emblem_round.pop("_seen", None)
        # kills of carriers: our victims' gem losses at the kill round
        losses = {}
        for e in d["events"]:
            if e["kind"] == "gemLoss" and (e.get("owner") or {}).get("team") != side:
                for x in e["entries"]:
                    losses[(e["owner"]["id"], x["timestamp"]["round"])] = float(x.get("value", 0) or 0)
        for e in d["events"]:
            if e["kind"] == "kill" and (e.get("owner") or {}).get("team") == side:
                for x in e["entries"]:
                    if losses.get((x["target"]["id"], x["timestamp"]["round"]), 0) > 0:
                        carrier_kills[e["owner"]["name"]] += 1

    print(f"### {which}: {games} games, {wins}-{games - wins}, "
          f"median {st.median(rounds_played):.0f} rounds a game\n")
    print("DRAFT (games fielded, median pick slot)")
    for name, k in fielded.most_common():
        print(f"  {name:<14} {k:3d} / {games}   pick {st.median(picks[name]):.0f}")
    order = ("fighting", "farming camps", "banking", "collecting",
             "nothing (travel, wandering)", "dead / walking back")
    print("\nTIME BUDGET, % of each champion's rounds")
    print("  %-14s" % "" + "".join("%11s" % h.split()[0] for h in order))
    allc = Counter()
    for name in fielded:
        b = budget[name]; tot = sum(b.values()) or 1; allc.update(b)
        print("  %-14s" % name + "".join("%10.1f%%" % (100 * b[h] / tot) for h in order))
    tot = sum(allc.values()) or 1
    print("  %-14s" % "TEAM" + "".join("%10.1f%%" % (100 * allc[h] / tot) for h in order))
    print("\nPER CHAMPION, per game fielded")
    print("  %-14s%8s%11s%9s%10s%7s%8s%8s%9s" % ("", "clears", "clear gap", "deposits", "gems/dep", "kills", "deaths", "wards", "carrier k"))
    for name, k in fielded.most_common():
        gap = st.median(clear_gaps[name]) if clear_gaps[name] else 0
        print("  %-14s%8.1f%11.0f%9.1f%10.1f%7.1f%8.1f%8.1f%9.1f" % (
            name, clears[name] / k, gap, deposits[name] / k,
            dep_gems[name] / max(1, deposits[name]), kills[name] / k, deaths[name] / k,
            wards[name] / k, carrier_kills[name] / k))
    print("\nEMBLEMS: most common first three, in purchase order")
    for name, _ in fielded.most_common():
        top = emblem_order[name].most_common(2)
        print(f"  {name:<14} " + "  |  ".join(f"{' > '.join(t) or '-'} (x{c})" for t, c in top))
        fam = final_families[name]
        print(f"  {'':<14} held at the end, per game: " + ", ".join(
            f"{f} {v / fielded[name]:.1f}" for f, v in fam.most_common()))
        if first_emblem_round[name]:
            print(f"  {'':<14} first emblem by round {st.median(first_emblem_round[name]):.0f} (median)")
    if kill_rounds:
        q = sorted(kill_rounds)
        print(f"\nKILL TIMING: median round {q[len(q)//2]}, quartiles {q[len(q)//4]}-{q[3*len(q)//4]}; "
              f"{len(q) / games:.1f} kills a game")
    if death_rounds:
        q = sorted(death_rounds)
        print(f"DEATH TIMING: median round {q[len(q)//2]}; {len(q) / games:.1f} deaths a game")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "prism"))
