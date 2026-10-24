#!/usr/bin/env python3
"""Mine the platform's match summaries for why we lose: us against the opponent,
in losses against wins.

    lossmine.py fetch DIR [N]       # last N ranked matches (default 200), summaries only
    lossmine.py report DIR [--since ISO] [--until ISO]

`fetch` pages `cambc matches list --team me --kind ranked` and downloads each
finished match's summary (`cambc matches summary <id> --json`), skipping ones
already on disk; it spends no match quota. `report` reads every summary and, per
game and per side, counts: gems submitted; gems collected from camps and from
kills; gems lost to champions and to camps; deaths by champions and by camps;
kills; deposits and their size; camp clears; fuel exhaustions and bot faults;
and the round each side reached 250 and 500 submitted gems. It prints the means
for us and the opponent in losses and in wins, and the gap that differs most.
"""
from __future__ import annotations

import collections
import json
import os
import subprocess
import sys
import time
from pathlib import Path

US = "Milk and Potatoes"
CAMBC = os.environ.get("CAMBC", "cambc")


def cambc(args: list[str]) -> subprocess.CompletedProcess:
    for attempt in range(6):
        r = subprocess.run([CAMBC, *args], capture_output=True, text=True)
        if r.returncode == 0:
            return r
        time.sleep(2 ** attempt)
    raise RuntimeError(f"cambc {' '.join(args)} failed: {r.stderr[-300:]}")


def fetch(out: Path, n: int) -> None:
    out.mkdir(parents=True, exist_ok=True)
    rows, cursor = [], None
    while len(rows) < n:
        args = ["matches", "list", "--team", "me", "--kind", "ranked", "--limit", "100", "--json"]
        if cursor:
            args += ["--cursor", cursor]
        page = json.loads(cambc(args).stdout)
        rows += page["matches"]
        cursor = page.get("nextCursor") or page.get("cursor")
        if not cursor or not page["matches"]:
            break
    rows = [r for r in rows[:n] if r["status"] == "finished"]
    (out / "listing.json").write_text(json.dumps(rows, indent=1))
    got = 0
    for r in rows:
        f = out / f"{r['matchId']}.json"
        if not f.exists():
            cambc(["matches", "summary", r["matchId"], "--json", "-o", str(f)])
            got += 1
            time.sleep(0.5)
    print(f"{len(rows)} finished ranked matches in {out}; {got} summaries downloaded now")


def side_stats(d: dict, team: str) -> dict:
    """Counts for one team ('teamA' or 'teamB') from a summary."""
    s = collections.Counter()
    for t in d["teams"]:
        if t["team"] == team:
            s["gems"] = int(t["submittedGems"])
    for e in d["events"]:
        owner = e.get("owner") or {}
        if owner.get("team") != team:
            continue
        k = e["kind"]
        for x in e["entries"]:
            v = float(x.get("value") or 0)
            ctx = x.get("context")
            if k == "gemCollection":
                s["got_from_kills" if ctx == "champion" else "got_from_camps"] += v
            elif k == "gemLoss":
                s["lost_to_champs" if ctx == "champion" else "lost_to_camps"] += v
            elif k == "death":
                s["deaths_to_champs" if ctx == "champion" else "deaths_to_camps"] += 1
            elif k == "kill":
                s["kills"] += 1
            elif k == "gemSubmission":
                s["deposits"] += 1
                s["deposited"] += v
            elif k == "campClear":
                s["camp_clears"] += 1
            elif k == "fuelExhausted":
                s["fuel_exhausted"] += 1
            elif k == "botFault":
                s["bot_faults"] += 1
    for tl in d["teamTimelines"]:
        if tl["owner"] == team and tl["metric"] == "submittedGems":
            r = 0
            for run in tl["runs"]:
                for mark in (250, 500):
                    if f"to{mark}" not in s and int(run["value"]) >= mark:
                        s[f"to{mark}"] = r
                r += run["duration"]
    return s


def report(out: Path, since: str = "", until: str = "~") -> None:
    rows = json.loads((out / "listing.json").read_text())
    games = []
    for r in rows:
        if not (since <= r["createdAt"] < until):
            continue
        f = out / f"{r['matchId']}.json"
        if not f.exists():
            continue
        d = json.loads(f.read_text())
        us = next(t for t in r["teams"] if t["name"] == US)
        them = next(t for t in r["teams"] if t is not us)
        mine, theirs = ("teamA", "teamB") if us["side"] == "a" else ("teamB", "teamA")
        champs = {c["team"]: [] for c in d["roster"]["champions"]}
        for c in d["roster"]["champions"]:
            champs[c["team"]].append(c["name"])
        games.append({"win": us["result"] == "win", "map": r["map"], "opp": them["name"],
                      "rounds": d["match"]["roundsCompleted"], "us": side_stats(d, mine),
                      "them": side_stats(d, theirs), "their_champs": champs.get(theirs, [])})
    keys = ["gems", "got_from_camps", "got_from_kills", "lost_to_champs", "lost_to_camps",
            "deaths_to_champs", "deaths_to_camps", "kills", "deposits", "deposited",
            "camp_clears", "fuel_exhausted", "bot_faults", "to250", "to500"]
    print(f"{len(games)} games: {sum(g['win'] for g in games)} wins, {sum(not g['win'] for g in games)} losses\n")
    for label, sel in (("losses", lambda g: not g["win"]), ("wins", lambda g: g["win"])):
        gs = [g for g in games if sel(g)]
        if not gs:
            continue
        print(f"{label} ({len(gs)} games, mean rounds {sum(g['rounds'] for g in gs) / len(gs):.0f})")
        print(f"  {'':18}{'us':>9}{'them':>9}{'gap':>9}")
        for k in keys:
            def mean(side):
                vals = [g[side][k] for g in gs if k in g[side] or not k.startswith("to")]
                return sum(vals) / len(vals) if vals else float("nan")
            a, b = mean("us"), mean("them")
            print(f"  {k:18}{a:9.1f}{b:9.1f}{a - b:+9.1f}")
        print()
    losses = [g for g in games if not g["win"]]
    by_map = collections.Counter(g["map"] for g in losses)
    by_opp = collections.Counter(g["opp"] for g in losses)
    champs = collections.Counter(c for g in losses for c in g["their_champs"])
    print("losses by map:", by_map.most_common(10))
    print("losses by opponent:", by_opp.most_common(8))
    print("opponent champions in losses:", champs.most_common(13))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    if sys.argv[1] == "fetch":
        fetch(Path(sys.argv[2]), int(sys.argv[3]) if len(sys.argv) > 3 else 200)
    else:
        a = sys.argv[3:]
        since = a[a.index("--since") + 1] if "--since" in a else ""
        until = a[a.index("--until") + 1] if "--until" in a else "~"
        report(Path(sys.argv[2]), since, until)
