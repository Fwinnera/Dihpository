#!/usr/bin/env python3
"""Reconstruct the fight behind every champion death from ladder match summaries.

A summary has no positions or health, but it has a per-round timeline of every
champion's cumulative champion damage dealt and taken, gems carried and gold
spent, and an event log naming each kill's killer and assisters. That is enough
to rebuild a fight:

    window      the run of rounds before the death in which the victim kept
                taking champion damage (gaps of up to GAP rounds allowed)
    opener      whichever came first in that window: the victim dealing champion
                damage (we engaged) or taking it (we were engaged)
    enemies     the killer and the assisters, which the engine names exactly
    allies      the victim's teammates whose champion damage rose in the window
                -- an upper bound, since they may be fighting elsewhere
    item edge   gold spent by the enemy participants against the victim and the
                allies, per champion, at the round the fight began

Their deaths are rebuilt the same way, as the control: if the fights we lose look
like the fights they lose, the gap is how often we fight, not how.

    analysis/fights.py [--glob PATTERN]
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "ws/bench/ladder"
US = "Milk and Potatoes"
GAP = 3
METRICS = ("championDamageTaken", "championDamageDone", "gems", "spentGold")


def expand(runs: list[dict], length: int) -> list[float]:
    out = []
    for r in runs:
        out += [float(r["value"])] * int(r["duration"])
    out += [out[-1] if out else 0.0] * (length - len(out))
    return out[:length]


def games(pattern: str | None):
    for tag in sorted(d.name for d in ROOT.iterdir() if (d / "summaries").exists()):
        for gf in sorted(ROOT.glob(f"{tag}/group_*.json")):
            for m in json.loads(gf.read_text()).get("matches", []):
                us = next((t for t in m["teams"] if t["name"] == US), None)
                sm = ROOT / tag / "summaries" / f"{m['matchId'][:8]}.json"
                if us and sm.exists():
                    yield m, json.loads(sm.read_text()), "teamA" if us["side"] == "a" else "teamB"


def fights(d: dict, ours: str) -> list[dict]:
    length = d["match"]["roundsCompleted"] + 2
    team = {c["id"]: c["team"] for c in d["roster"]["champions"]}
    tl = defaultdict(dict)
    for x in d["championTimelines"]:
        if x["metric"] in METRICS:
            tl[x["owner"]["id"]][x["metric"]] = expand(x["runs"], length)
    kills, assists = {}, defaultdict(list)
    for e in d["events"]:
        if e["kind"] not in ("kill", "assist"):
            continue
        who = e["owner"]["id"]
        for x in e["entries"]:
            key = (x["target"]["id"], x["timestamp"]["round"])
            if e["kind"] == "kill":
                kills[key] = who
            else:
                assists[key].append(who)
    out = []
    for (victim, rnd), killer in kills.items():
        if victim not in tl or "championDamageTaken" not in tl[victim]:
            continue
        taken = tl[victim]["championDamageTaken"]
        dealt = tl[victim]["championDamageDone"]
        hit = lambda s, t: s[t] > s[t - 1] if t > 0 else False
        start, quiet, t = rnd, 0, rnd
        while t > 1 and quiet <= GAP:
            if hit(taken, t):
                start, quiet = t, 0
            else:
                quiet += 1
            t -= 1
        first_dealt = next((t for t in range(max(1, start - GAP), rnd + 1) if hit(dealt, t)), None)
        first_taken = next((t for t in range(max(1, start - GAP), rnd + 1) if hit(taken, t)), None)
        if first_dealt is not None and (first_taken is None or first_dealt < first_taken):
            opener = "victim opened"
        elif first_dealt is not None and first_dealt == first_taken:
            opener = "same round"
        else:
            opener = "victim was hit first"
        side = team[victim]
        enemies = {killer, *assists[(victim, rnd)]}
        allies = {c for c in tl if team.get(c) == side and c != victim
                  and "championDamageDone" in tl[c]
                  and tl[c]["championDamageDone"][rnd] > tl[c]["championDamageDone"][max(0, start - 1)]}
        spent = lambda c: tl[c]["spentGold"][start] if "spentGold" in tl[c] else 0.0
        mine = [spent(victim)] + [spent(c) for c in allies]
        theirs = [spent(c) for c in enemies if c in tl]
        out.append({
            "ours": side == ours, "round": rnd, "length": rnd - start + 1,
            "opener": opener, "enemies": len(enemies), "allies": len(allies),
            "edge": (sum(theirs) / max(1, len(theirs))) - (sum(mine) / len(mine)),
            "carrying": tl[victim]["gems"][start] if "gems" in tl[victim] else 0.0,
            "dealt": dealt[rnd] - dealt[max(0, start - 1)],
            "taken": taken[rnd] - taken[max(0, start - 1)],
        })
    return out


def report(rows: list[dict], label: str, n_games: int) -> None:
    n = len(rows)
    print(f"=== {label}: {n} deaths, {n / n_games:.1f} a game ===")
    op = Counter(r["opener"] for r in rows)
    for k in ("victim opened", "same round", "victim was hit first"):
        print(f"  {k:<24}{100 * op[k] / n:5.0f}%")
    num = Counter("outnumbered" if r["enemies"] > r["allies"] + 1 else
                  "even" if r["enemies"] == r["allies"] + 1 else "outnumbering" for r in rows)
    alone = sum(r["allies"] == 0 for r in rows)
    print(f"  {'alone (no ally engaged)':<24}{100 * alone / n:5.0f}%")
    for k in ("outnumbered", "even", "outnumbering"):
        print(f"  {k:<24}{100 * num[k] / n:5.0f}%   (enemy participants vs victim + allies)")
    edge = sorted(r["edge"] for r in rows)
    behind = sum(e > 150 for e in edge)
    print(f"  {'enemy item edge':<24} median {edge[n // 2]:+.0f} gold a champion; "
          f"{100 * behind / n:.0f}% of deaths a full emblem or more behind")
    carry = [r["carrying"] for r in rows]
    print(f"  {'carrying gems':<24}{100 * sum(c > 0 for c in carry) / n:5.0f}%  "
          f"(mean {sum(carry) / n:.1f} when the fight began)")
    ratio = sum(r["dealt"] for r in rows) / max(1, sum(r["taken"] for r in rows))
    print(f"  {'victim dealt / took':<24}{ratio:7.2f}   in the fight it died in")
    ln = sorted(r["length"] for r in rows)
    print(f"  {'fight length':<24} median {ln[n // 2]} rounds, 90th {ln[int(n * .9)]}\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--glob")
    ap.parse_args()
    ours, theirs, n = [], [], 0
    by_edge = defaultdict(lambda: [0, 0])
    for _, d, side in games(None):
        n += 1
        for r in fights(d, side):
            (ours if r["ours"] else theirs).append(r)
    report(ours, "OUR DEATHS", n)
    report(theirs, "THEIR DEATHS (control)", n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
