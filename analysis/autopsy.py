#!/usr/bin/env python3
"""Loss autopsy: in each game, our team against the opponent on every measure.

Both teams' records are in every summary, so a lost game shows directly what
the winner did that we did not, on the same map at the same time.

    autopsy.py DIR [DIR ...] [--since ISO]     # folders written by fetch_team.py
"""
from __future__ import annotations

import argparse
import json
import statistics as st
from collections import defaultdict
from pathlib import Path

WS = Path(__file__).resolve().parent.parent / "ws"
US = "Milk and Potatoes"
TABLE = json.loads((WS / "bench/camptable.json").read_text())
KEYS = ["gems", "farm%", "fight%", "dead%", "travel/other%", "deaths", "kills", "carrier kills",
        "gems lost", "clears", "gems/pickup", "zero-gem %", "deposits", "gems/deposit",
        "monolith gems", "lock hits", "gold", "emblems"]


def expand(runs, n):
    out = []
    for r in runs:
        out += [float(r["value"])] * int(r["duration"])
    return (out + [out[-1] if out else 0.0] * n)[:n]


def team_stats(d, side, mono):
    other = "teamB" if side == "teamA" else "teamA"
    R = d["match"]["roundsCompleted"]
    ids = {c["id"] for c in d["roster"]["champions"] if c["team"] == side}
    s = defaultdict(float)
    tl = defaultdict(dict)
    for x in d["championTimelines"]:
        if x["owner"]["id"] in ids and x["metric"] in ("championDamageDone", "championDamageTaken",
                                                       "monsterDamageDone", "deaths"):
            tl[x["owner"]["id"]][x["metric"]] = expand(x["runs"], R + 1)
    budget = defaultdict(int)
    for t in tl.values():
        if len(t) < 4:
            continue
        dead = False
        for r in range(1, R + 1):
            up = lambda k: t[k][r] > t[k][r - 1]
            if up("deaths"):
                dead = True
            if up("championDamageDone") or up("championDamageTaken"):
                budget["fight"] += 1; dead = False
            elif up("monsterDamageDone"):
                budget["farm"] += 1; dead = False
            elif dead:
                budget["dead"] += 1
            else:
                budget["other"] += 1
    tot = sum(budget.values()) or 1
    s["farm%"], s["fight%"] = 100 * budget["farm"] / tot, 100 * budget["fight"] / tot
    s["dead%"], s["travel/other%"] = 100 * budget["dead"] / tot, 100 * budget["other"] / tot
    losses = {}
    for e in d["events"]:
        if e["kind"] == "gemLoss" and (e.get("owner") or {}).get("team") == other:
            for x in e["entries"]:
                losses[(e["owner"]["id"], x["timestamp"]["round"])] = float(x.get("value", 0) or 0)
    pick = []
    for e in d["events"]:
        if (e.get("owner") or {}).get("team") != side:
            continue
        for x in e.get("entries", []):
            k = e["kind"]; tg = x.get("target") or {}
            if k == "death": s["deaths"] += 1
            elif k == "kill":
                s["kills"] += 1
                if losses.get((tg.get("id"), x["timestamp"]["round"]), 0) > 0:
                    s["carrier kills"] += 1
            elif k == "gemLoss": s["gems lost"] += float(x.get("value", 0) or 0)
            elif k == "campClear": s["clears"] += 1
            elif k == "gemCollection" and tg.get("kind") == "campGroup":
                v = float(x.get("value", 0) or 0); pick.append(v)
                if tg.get("id") in mono: s["monolith gems"] += v
            elif k == "gemSubmission":
                s["deposits"] += 1; s["dep_g"] += float(x.get("value", 0) or 0)
            elif k == "lockHit" or k == "altarLockHit":
                s["lock hits"] += 1
    s["gems/pickup"] = st.mean(pick) if pick else 0
    s["zero-gem %"] = 100 * sum(1 for v in pick if v == 0) / max(1, len(pick))
    s["gems/deposit"] = s["dep_g"] / max(1, s["deposits"])
    for c in d["champions"]:
        if c["team"] == side:
            s["gold"] += int(c["metrics"]["earnedGold"])
            s["emblems"] += sum(int(i.get("quantity", 1)) for i in (c.get("items") or []) if "Emblem" in i["item"])
    s["gems"] = {t["team"]: int(t["submittedGems"]) for t in d["teams"]}[side]
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+"); ap.add_argument("--since")
    a = ap.parse_args()
    lost, won, rows = [], [], []
    for folder in a.dirs:
        for m in json.loads((WS / "bench" / folder / "matches.json").read_text()):
            if a.since and m["createdAt"] < a.since:
                continue
            me = next((t for t in m["teams"] if t["name"] == US), None)
            them = next((t for t in m["teams"] if t["name"] != US), None)
            f = WS / "bench" / folder / "summaries" / f"{m['matchId']}.json"
            if not me or not them or not f.exists():
                continue
            d = json.loads(f.read_text())
            side = "teamA" if me["side"] == "a" else "teamB"; other = "teamB" if side == "teamA" else "teamA"
            mono = {g["id"] for g in TABLE.get(m["map"].replace("-", "_"), []) if g["monolith"]}
            u, o = team_stats(d, side, mono), team_stats(d, other, mono)
            rec = (m["map"], them["name"], me["result"], d["match"]["roundsCompleted"], u, o, m["kind"])
            (won if me["result"] == "win" else lost).append(rec); rows.append(rec)
    print(f"{len(rows)} games: {len(won)} won, {len(lost)} lost\n")
    for label, group in (("LOST GAMES: us against the winner, per game", lost), ("WON GAMES: us against the loser", won)):
        if not group:
            continue
        print(f"=== {label} ({len(group)}) ===")
        print("  %-16s%10s%10s%10s" % ("", "us", "them", "gap"))
        for k in KEYS:
            u = st.mean(r[4][k] for r in group); o = st.mean(r[5][k] for r in group)
            print("  %-16s%10.1f%10.1f%+10.1f" % (k, u, o, u - o))
        print()
    print("=== every lost game ===")
    for mp, opp, res, R, u, o, kind in sorted(lost, key=lambda r: r[4]["gems"] - r[5]["gems"]):
        print(f"  {mp:<22} vs {opp[:20]:<20} {kind[:4]} {int(u['gems']):4d}-{int(o['gems']):4d} in {R:4d}  "
              f"farm {u['farm%']:4.1f}/{o['farm%']:4.1f}  deaths {int(u['deaths']):2d}/{int(o['deaths']):2d}  "
              f"lost gems {int(u['gems lost']):3d}  zero-gem {u['zero-gem %']:3.0f}%")


if __name__ == "__main__":
    main()
