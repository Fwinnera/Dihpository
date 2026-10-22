#!/usr/bin/env python3
"""Queue unranked games in bulk against real teams and build a dataset from them.

No submission happens here. `greatsage` is already the live bot, so games against
it need no submit/restore cycle, no safe-window wait, and put the ranked rating at
no risk at all. That is what makes volume possible: the only limits are the team's
shared match-group quota and the public API's rate limiting.

The quota is not readable -- `cambc match-groups quota` prints the map list, which
looks like a CLI bug -- so this discovers the ceiling instead of assuming one: it
paces itself, retries transient failures, and stops cleanly on a quota refusal
while keeping everything collected so far.

Note that the quota is shared with the rest of the team. Queuing hundreds of games
spends something a teammate may also want.

    collect.py --plan                     # what it would queue, no API calls
    collect.py --groups 20                # queue, wait, download, append
    collect.py --analyse                  # report over everything collected

Each group is five matches on five maps against one opponent from one side.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import subprocess
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WS = ROOT / "ws"
CAMBC = Path.home() / "Library" / "Python" / "3.9" / "bin" / "cambc"
OUR_TEAM = "Milk and Potatoes"
DATA = WS / "bench" / "collected"
PACE = 6.0          # seconds between queueing calls; 429s start below about 3


def cambc(*args: str, retries: int = 5) -> tuple[int, str]:
    env = dict(os.environ)
    env["PATH"] = f"{CAMBC.parent}:{env.get('PATH','')}"
    for attempt in range(retries + 1):
        r = subprocess.run([str(CAMBC), *args], capture_output=True, text=True,
                           env=env, cwd=WS)
        blob = (r.stdout or "") + (r.stderr or "")
        if r.returncode == 0:
            return 0, r.stdout
        low = blob.lower()
        if "quota" in low or "limit reached" in low:
            return 2, blob                      # a real ceiling, not a hiccup
        transient = ("429" in blob or "busy" in low or "invalid response" in low
                     or "timed out" in low or "connection" in low)
        if transient and attempt < retries:
            time.sleep(4 * (attempt + 1))
            continue
        return 1, blob
    return 1, ""


def ladder() -> list[dict]:
    teams, page = [], 1
    while page <= 12:
        code, out = cambc("ladder", "--page", str(page), "--limit", "100", "--json")
        if code:
            break
        d = json.loads(out)
        teams += d.get("teams", [])
        if len(teams) >= d.get("total", 0) or not d.get("teams"):
            break
        page += 1
    return teams


def map_names() -> list[str]:
    # The platform spells maps with underscores; local files use hyphens.
    return sorted(p.stem.replace("-", "_") for p in WS.glob("maps/*.map26a"))


def opponents(teams: list[dict], n: int) -> list[dict]:
    """A spread across the ladder, not just the top: we need games we can win."""
    ours = next((t for t in teams if t["name"] == OUR_TEAM), None)
    rank = ours["rank"] if ours else 180
    bands = [(1, 10), (max(1, rank - 120), max(2, rank - 60)),
             (max(1, rank - 30), rank - 1), (rank + 1, rank + 30),
             (rank + 60, rank + 150)]
    picked, seen = [], {OUR_TEAM}
    for lo, hi in bands:
        pool = [t for t in teams if lo <= t["rank"] <= hi and t["name"] not in seen]
        random.shuffle(pool)
        for t in pool[: max(1, n // len(bands))]:
            picked.append(t)
            seen.add(t["name"])
    return picked[:n]


def plan(groups: int) -> list[tuple[dict, list[str], str]]:
    teams = ladder()
    if not teams:
        sys.exit("could not read the ladder")
    maps = map_names()
    opps = opponents(teams, max(4, groups // 4))
    # The engine is deterministic, so an identical (opponent, maps, side) triple
    # returns a byte-identical result and buys nothing. Walk the opponents and the
    # map chunks on co-prime strides and flip the side each full cycle, so every
    # group is a pairing we have not already played.
    chunks = [maps[i:i + 5] for i in range(0, len(maps), 5)]
    chunks = [c for c in chunks if len(c) == 5] or [maps[:5]]
    jobs, seen, i = [], set(), 0
    while len(jobs) < groups and i < groups * 20:
        opp = opps[i % len(opps)]
        chunk = chunks[(i // len(opps)) % len(chunks)]
        # Checkerboard the side across opponent and map-chunk so each opponent is
        # met from both seats within a short run, not only after a full cycle. The
        # rules break gem ties in team B's favour, so a one-sided sample measures a
        # seat as much as a bot.
        cycle = i // (len(opps) * len(chunks))
        side = "a" if (i % len(opps) + i // len(opps) + cycle) % 2 == 0 else "b"
        key = (opp["teamId"], tuple(chunk), side)
        if key not in seen:
            seen.add(key)
            jobs.append((opp, chunk, side))
        i += 1
    return jobs


def queue(jobs) -> list[dict]:
    DATA.mkdir(parents=True, exist_ok=True)
    queued, stop = [], None
    for idx, (opp, maps, side) in enumerate(jobs, 1):
        code, out = cambc("match-groups", "create", opp["teamId"],
                          "--maps", ",".join(maps), "--side", side, "--json")
        if code == 2:
            stop = out.strip().splitlines()[-1] if out.strip() else "quota reached"
            print(f"  stopped at group {idx}: {stop}")
            break
        if code:
            print(f"  group {idx} vs {opp['name']} failed: "
                  f"{out.strip().splitlines()[-1] if out.strip() else '?'}")
            continue
        g = json.loads(out)
        queued.append({"groupId": g["groupId"], "opponent": opp["name"],
                       "rank": opp["rank"], "teamId": opp["teamId"],
                       "maps": maps, "side": side})
        print(f"  {idx:>3}/{len(jobs)}  {opp['name'][:24]:<24} rank {opp['rank']:>4} "
              f"side {side}  {', '.join(m[:14] for m in maps[:2])}...")
        time.sleep(PACE)
    return queued


def harvest(queued: list[dict]) -> int:
    """Wait for the groups, then pull per-match summaries into the dataset."""
    print(f"  waiting for {len(queued) * 5} matches")
    deadline = time.time() + 600
    while time.time() < deadline:
        pending = 0
        for q in queued:
            code, out = cambc("match-groups", "show", q["groupId"], "--json")
            if code:
                continue
            pending += sum(1 for m in json.loads(out).get("matches", [])
                           if m.get("status") != "finished")
        if not pending:
            break
        time.sleep(15)

    saved = 0
    for q in queued:
        code, out = cambc("match-groups", "show", q["groupId"], "--json")
        if code:
            continue
        for m in json.loads(out).get("matches", []):
            dest = DATA / f"{m['matchId'][:12]}.json"
            if dest.exists():
                saved += 1
                continue
            code, _ = cambc("matches", "summary", m["matchId"], "--json",
                            "-o", str(dest))
            if code == 0 and dest.exists():
                us = next((t for t in m["teams"] if t["name"] == OUR_TEAM), None)
                meta = DATA / f"{m['matchId'][:12]}.meta.json"
                meta.write_text(json.dumps({
                    "map": m["map"], "opponent": q["opponent"], "rank": q["rank"],
                    "side": us["side"] if us else q["side"],
                    "result": us["result"] if us else None}))
                saved += 1
            time.sleep(1.5)
    return saved


def rows() -> list[dict]:
    out = []
    for meta in sorted(DATA.glob("*.meta.json")):
        summary = DATA / meta.name.replace(".meta.json", ".json")
        if not summary.exists():
            continue
        m = json.loads(meta.read_text())
        d = json.loads(summary.read_text())
        me = "teamA" if m["side"] == "a" else "teamB"
        them = "teamB" if me == "teamA" else "teamA"
        gems = {t["team"]: int(t["submittedGems"]) for t in d["teams"]}
        mine = [c for c in d["champions"] if c["team"] == me]
        if not mine:
            continue
        s = lambda k: sum(float(c["metrics"][k]) for c in mine)
        out.append(dict(
            m, gems=gems[me], theirs=gems[them],
            rounds=d["match"]["roundsCompleted"], win=gems[me] > gems[them],
            collected=s("collectedGems"), deaths=s("deaths"), gold=s("earnedGold"),
            kills=s("kills"), assists=s("assists"),
            chDmgTaken=s("championDamageTaken"), chDmgDone=s("championDamageDone"),
            monsterDmg=s("monsterDamageDone"), healRecv=s("healingReceived"),
            champs=len(mine),
            roster=tuple(sorted(c["name"] for c in
                                d.get("roster", {}).get("champions", [])
                                if c["team"] == me))))
    return out


def analyse() -> int:
    r = rows()
    if not r:
        print(f"nothing collected yet under {DATA}")
        return 1
    n = len(r)
    w = sum(1 for x in r if x["result"] == "win")
    f = lambda k: sum(x[k] for x in r) / n
    print(f"\n{n} unranked games collected, record {w}-{n - w} ({100*w/n:.0f}%)")
    print("  gems %.0f vs %.0f | collected %.0f | deaths %.1f | gold %.0f "
          "| kills %.1f | rounds %.0f"
          % (f("gems"), f("theirs"), f("collected"), f("deaths"), f("gold"),
             f("kills"), f("rounds")))

    def table(key, label, minimum=4):
        g = defaultdict(list)
        for x in r:
            g[x[key]].append(x)
        cand = [(k, v) for k, v in g.items() if len(v) >= minimum]
        if not cand:
            return
        print(f"\n  by {label} (min {minimum} games), worst first:")
        print("    %-26s%7s%8s%8s%9s%8s" % (label, "games", "win%", "gems",
                                            "theirs", "deaths"))
        for k, v in sorted(cand, key=lambda kv: sum(
                1 for x in kv[1] if x["result"] == "win") / len(kv[1])):
            ww = sum(1 for x in v if x["result"] == "win")
            print("    %-26s%7d%7.0f%%%8.0f%9.0f%8.1f"
                  % (str(k)[:25], len(v), 100 * ww / len(v),
                     sum(x["gems"] for x in v) / len(v),
                     sum(x["theirs"] for x in v) / len(v),
                     sum(x["deaths"] for x in v) / len(v)))

    table("map", "map")
    table("side", "side", 10)
    table("champs", "team size", 10)

    # What separates a win from a loss, in the bot's own terms.
    wins = [x for x in r if x["result"] == "win"]
    loss = [x for x in r if x["result"] != "win"]
    if wins and loss:
        print("\n  wins against losses (the mechanism, not the scoreline):")
        print("    %-26s%12s%12s%10s" % ("metric", "wins", "losses", "ratio"))
        for k in ("collected", "deaths", "gold", "kills", "chDmgTaken",
                  "monsterDmg", "healRecv", "rounds"):
            a = sum(x[k] for x in wins) / len(wins)
            b = sum(x[k] for x in loss) / len(loss)
            print("    %-26s%12.0f%12.0f%9.2fx"
                  % (k, a, b, (a / b) if b else 0))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--groups", type=int, default=0,
                    help="how many five-match groups to queue")
    ap.add_argument("--plan", action="store_true", help="show the plan, queue nothing")
    ap.add_argument("--analyse", action="store_true")
    ap.add_argument("--seed", type=int, default=None)
    a = ap.parse_args()
    if a.seed is not None:
        random.seed(a.seed)
    if a.analyse:
        return analyse()
    if a.plan or a.groups:
        jobs = plan(a.groups or 8)
        if a.plan:
            print(f"would queue {len(jobs)} groups = {len(jobs)*5} matches")
            for opp, maps, side in jobs:
                print(f"   {opp['name'][:26]:<26} rank {opp['rank']:>4} side {side}"
                      f"  {', '.join(m[:16] for m in maps)}")
            return 0
        print(f"queueing {len(jobs)} groups = {len(jobs)*5} matches "
              f"(no submission; greatsage is already live)")
        queued = queue(jobs)
        if not queued:
            return 1
        saved = harvest(queued)
        print(f"  dataset now holds {saved} summaries from this batch")
        return analyse()
    ap.error("give --plan, --groups N, or --analyse")


if __name__ == "__main__":
    sys.exit(main())
