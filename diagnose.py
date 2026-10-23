#!/usr/bin/env python3
"""Where the score actually goes, from match event logs rather than final totals.

A summary carries an event log per champion: deaths with the killer's context and
position, gem collections, gem submissions, gem losses, camp clears, purchases,
fuel exhaustion and bot faults. Final gem totals cannot distinguish a bot that
farms badly from one that farms well and dies carrying the proceeds; the event log
can.

    diagnose.py                     # every summary on disk
    diagnose.py --glob 'ws/bench/ladder/wide_*/summaries/*.json'
    diagnose.py --min-rank 60       # only strong opponents, where rank is known
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUR_TEAM = "Milk and Potatoes"


def our_side(d: dict, meta: dict | None) -> str | None:
    """Which team label is ours. Summaries do not name teams, so use the meta."""
    if meta and meta.get("side"):
        return "teamA" if meta["side"] == "a" else "teamB"
    # Fall back on the roster: our drafts are recorded in the sibling group file.
    return None


def load(pattern: str) -> list[dict]:
    out = []
    for p in sorted(glob.glob(pattern)):
        path = Path(p)
        try:
            d = json.loads(path.read_text())
        except Exception:
            continue
        side = None
        metap = path.with_name(path.name.replace(".json", ".meta.json"))
        if metap.exists():
            side = our_side(d, json.loads(metap.read_text()))
        if side is None:
            # Group files sit two directories up and carry the side per match id.
            gid = path.stem
            for gf in path.parent.parent.glob("group_*.json"):
                try:
                    g = json.loads(gf.read_text())
                except Exception:
                    continue
                for m in g.get("matches", []):
                    if m["matchId"].startswith(gid):
                        us = next((t for t in m["teams"]
                                   if t["name"] == OUR_TEAM), None)
                        if us:
                            side = "teamA" if us["side"] == "a" else "teamB"
                        break
                if side:
                    break
        if side:
            out.append({"path": p, "d": d, "side": side})
    return out


def events_for(d: dict, team: str, kind: str) -> list[dict]:
    rows = []
    for e in d.get("events", []):
        if e.get("kind") != kind:
            continue
        owner = e.get("owner") or {}
        if owner.get("team") != team:
            continue
        rows.extend(e.get("entries", []))
    return rows


def analyse(records: list[dict]) -> None:
    n = len(records)
    if not n:
        print("no matches matched")
        return
    agg = Counter()
    death_ctx = Counter()
    death_round = []
    loss_amounts = []
    buy_rounds = []
    per_match = []
    rounds_total = 0

    for r in records:
        d, me = r["d"], r["side"]
        them = "teamB" if me == "teamA" else "teamA"
        gems = {t["team"]: int(t["submittedGems"]) for t in d["teams"]}
        rnds = d["match"]["roundsCompleted"]
        rounds_total += rnds
        deaths = events_for(d, me, "death")
        losses = events_for(d, me, "gemLoss")
        subs = events_for(d, me, "gemSubmission")
        colls = events_for(d, me, "gemCollection")
        buys = events_for(d, me, "buyItem")
        clears = events_for(d, me, "campClear")
        faults = events_for(d, me, "botFault") + events_for(d, me, "fuelExhausted")

        lost = sum(float(x.get("value", 0) or 0) for x in losses)
        got = sum(float(x.get("value", 0) or 0) for x in colls)
        put = sum(float(x.get("value", 0) or 0) for x in subs)
        agg["deaths"] += len(deaths)
        agg["gem_loss_events"] += len(losses)
        agg["gems_lost"] += lost
        agg["gems_collected"] += got
        agg["gems_submitted"] += put
        agg["submissions"] += len(subs)
        agg["collections"] += len(colls)
        agg["camp_clears"] += len(clears)
        agg["buys"] += len(buys)
        agg["faults"] += len(faults)
        agg["gems_final"] += gems[me]
        agg["opp_final"] += gems[them]
        agg["wins"] += int(gems[me] > gems[them])
        for x in deaths:
            death_ctx[x.get("context", "?")] += 1
            death_round.append(x.get("timestamp", {}).get("round", 0))
        loss_amounts += [float(x.get("value", 0) or 0) for x in losses]
        buy_rounds += [x.get("timestamp", {}).get("round", 0) for x in buys]
        per_match.append({"gems": gems[me], "theirs": gems[them], "rounds": rnds,
                          "deaths": len(deaths), "lost": lost, "put": put, "got": got,
                          "win": gems[me] > gems[them], "path": r["path"]})

    f = lambda k: agg[k] / n
    print(f"{n} matches, record {agg['wins']}-{n - agg['wins']}, "
          f"{rounds_total / n:.0f} rounds average\n")

    print("SCORING")
    print(f"  gems collected per game          {f('gems_collected'):8.0f}")
    print(f"  gems submitted per game          {f('gems_submitted'):8.0f}")
    print(f"  gems LOST per game               {f('gems_lost'):8.0f}"
          f"   ({100 * agg['gems_lost'] / max(1, agg['gems_collected']):.0f}% of collected)")
    unaccounted = f('gems_collected') - f('gems_submitted') - f('gems_lost')
    print(f"  still carried at the end         {unaccounted:8.0f}")
    print(f"  final team total                 {f('gems_final'):8.0f}"
          f"   opponent {f('opp_final'):.0f}")

    print("\nDEATHS")
    print(f"  deaths per game                  {f('deaths'):8.1f}")
    for k, v in death_ctx.most_common():
        print(f"    killed by {k:<22}{v / n:8.1f}  ({100 * v / max(1, agg['deaths']):.0f}%)")
    if death_round:
        death_round.sort()
        q = lambda p: death_round[int(len(death_round) * p)]
        print(f"  death rounds: median {q(0.5)}, quartiles {q(0.25)}-{q(0.75)}")
    if loss_amounts:
        carried = [x for x in loss_amounts if x > 0]
        print(f"  deaths while carrying gems       "
              f"{len(carried) / n:8.1f}  of {f('deaths'):.1f}"
              f"   ({100 * len(carried) / max(1, agg['deaths']):.0f}%)")
        if carried:
            carried.sort()
            print(f"  gems per losing death: mean {sum(carried)/len(carried):.0f}, "
                  f"median {carried[len(carried)//2]:.0f}, max {carried[-1]:.0f}")

    print("\nECONOMY AND ACTIVITY")
    print(f"  camp clears per game             {f('camp_clears'):8.1f}")
    print(f"  gem pickups per game             {f('collections'):8.1f}")
    print(f"  deposits per game                {f('submissions'):8.1f}")
    if agg["submissions"]:
        print(f"  gems per deposit                 "
              f"{agg['gems_submitted'] / agg['submissions']:8.1f}")
    print(f"  items bought per game            {f('buys'):8.1f}")
    if buy_rounds:
        buy_rounds.sort()
        q = lambda p: buy_rounds[int(len(buy_rounds) * p)]
        print(f"  purchase rounds: median {q(0.5)}, quartiles {q(0.25)}-{q(0.75)}")
    print(f"  bot faults / fuel exhaustion     {f('faults'):8.2f}")

    wins = [m for m in per_match if m["win"]]
    loss = [m for m in per_match if not m["win"]]
    if wins and loss:
        print("\nWINS AGAINST LOSSES")
        print("  %-26s%10s%10s%9s" % ("", "wins", "losses", "ratio"))
        for key, label in (("got", "gems collected"), ("put", "gems submitted"),
                           ("lost", "gems lost to deaths"), ("deaths", "deaths"),
                           ("rounds", "rounds")):
            a = sum(m[key] for m in wins) / len(wins)
            b = sum(m[key] for m in loss) / len(loss)
            print("  %-26s%10.0f%10.0f%8.2fx" % (label, a, b, (a / b) if b else 0))

    print("\nWORST LOSSES BY GEMS LOST TO DEATHS")
    for m in sorted(per_match, key=lambda m: -m["lost"])[:6]:
        print("  %-30s %4.0f-%4.0f  lost %4.0f of %4.0f collected, %2d deaths"
              % (Path(m["path"]).stem, m["gems"], m["theirs"], m["lost"], m["got"],
                 m["deaths"]))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--glob", default=str(ROOT / "ws/bench/ladder/*/summaries/*.json"))
    a = ap.parse_args()
    analyse(load(a.glob))
    return 0


if __name__ == "__main__":
    sys.exit(main())
