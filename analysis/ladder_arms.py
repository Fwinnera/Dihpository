#!/usr/bin/env python3
"""Compare two ladder arms game by game, from the platform's own summaries and replays.

`ladderbench.py` reports means. This asks where a difference came from: per game,
paired by opponent and map, with the mechanism counts the summaries carry (monster
damage, camp clears, deposits, rounds alive, rounds farming) and a BOTTAG audit of
every replay, so a contaminated arm is caught rather than averaged in.

    ladder_arms.py fetch DIR ARM=GROUP,GROUP... ARM=GROUP,...   # group-id prefixes
    ladder_arms.py compare DIR BASE_ARM CANDIDATE_ARM

`fetch` reads `cambc matches list --team me --kind unranked`, so it needs the CLI
login and spends no match quota. Downloads are rate-limited and retried.
"""
from __future__ import annotations

import collections
import json
import math
import os
import statistics
import subprocess
import sys
import time
import zipfile
from pathlib import Path

US = "Milk and Potatoes"
CAMBC = os.environ.get("CAMBC", "cambc")


def cambc(args: list[str]) -> subprocess.CompletedProcess:
    for attempt in range(8):
        r = subprocess.run([CAMBC] + args, capture_output=True, text=True)
        if r.returncode == 0:
            return r
        time.sleep(3 * (attempt + 1))
    sys.exit(f"cambc {' '.join(args)} failed: {r.stderr[-300:]}")


def fetch(out: Path, specs: list[str]) -> None:
    arms = {}
    for spec in specs:
        name, groups = spec.split("=", 1)
        arms[name] = groups.split(",")
    out.mkdir(parents=True, exist_ok=True)
    listing = json.loads(cambc(["matches", "list", "--team", "me", "--kind", "unranked",
                                "--limit", "100", "--json"]).stdout)
    index = []
    for arm, prefixes in arms.items():
        for m in listing["matches"]:
            if not any(m["groupId"].startswith(p) for p in prefixes):
                continue
            mid = m["matchId"]
            base = out / f"{arm}__{mid}"
            if not base.with_suffix(".json").exists():
                cambc(["matches", "summary", mid, "--json", "-o", str(base.with_suffix(".json"))])
            if not base.with_suffix(".zip").exists():
                cambc(["matches", "download", mid, "-o", str(base.with_suffix(".zip"))])
            us = next(t for t in m["teams"] if t["name"] == US)
            them = next(t for t in m["teams"] if t is not us)
            index.append({"arm": arm, "match": mid, "map": m["map"], "opp": them["name"], "side": us["side"]})
            time.sleep(1)
    (out / "index.json").write_text(json.dumps(index, indent=1))
    print(f"{len(index)} games in {out}")


def increases(runs: list[dict]) -> int:
    """Rounds on which a cumulative timeline went up."""
    n, prev = 0, None
    for r in runs:
        v = float(r["value"])
        if prev is not None and v > prev:
            n += 1
        prev = v
    return n


def bottag(path: Path) -> str:
    tags = set()
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if name.endswith(".stdout"):
                text = z.read(name).replace(b"\x00", b"").decode("utf-8", "replace")
                tags |= {line.strip() for line in text.splitlines() if "BOTTAG" in line}
    return ", ".join(sorted(tags)) or "untagged (greatsage)"


def load(out: Path) -> dict:
    rows = {}
    for r in json.loads((out / "index.json").read_text()):
        d = json.loads((out / f"{r['arm']}__{r['match']}.json").read_text())
        side = "team" + r["side"].upper()
        other = "teamB" if side == "teamA" else "teamA"
        rounds = d["match"]["roundsCompleted"]
        gems = {t["team"]: int(t["submittedGems"]) for t in d["teams"]}
        ours = [c for c in d["champions"] if c["team"] == side]
        total = lambda f: sum(float(c["metrics"][f]) for c in ours)
        timelines = collections.defaultdict(dict)
        for t in d["championTimelines"]:
            if t["owner"].get("team") == side:
                timelines[t["owner"]["id"]][t["metric"]] = t["runs"]
        events = collections.Counter()
        for e in d["events"]:
            if e["owner"].get("team") == side:
                events[e["kind"]] += len(e["entries"])
        deaths = total("deaths")
        rows[(r["arm"], r["opp"], r["map"])] = {
            "rounds": rounds, "won": d["match"]["outcome"] == side,
            "gems": gems[side], "opp_gems": gems[other],
            "collected": total("collectedGems"), "gold": total("earnedGold"),
            "monster_dmg": total("monsterDamageDone"), "deaths": deaths, "kills": total("kills"),
            "camp_clears": events["campClear"], "deposits": events["gemSubmission"],
            "farm_rounds": sum(increases(v.get("monsterDamageDone", [])) for v in timelines.values()),
            "hit_rounds": sum(increases(v.get("championDamageTaken", [])) for v in timelines.values()),
            "alive_rounds": 5 * rounds - 60 * deaths,
            "tag": bottag(out / f"{r['arm']}__{r['match']}.zip"),
        }
    return rows


def compare(out: Path, base: str, cand: str) -> None:
    rows = load(out)
    print("BOTTAG audit:")
    audit = collections.Counter((arm, row["tag"]) for (arm, _, _), row in rows.items())
    for (arm, tag), n in sorted(audit.items()):
        print(f"  {arm:<12} {tag:<28} {n} games")
    keys = sorted({(o, mp) for (_, o, mp) in rows if (base, o, mp) in rows and (cand, o, mp) in rows})
    pairs = [(rows[(base, o, mp)], rows[(cand, o, mp)]) for o, mp in keys]
    print(f"\n{len(pairs)} paired games\n")
    print(f"{'per game':<14}{base:>10}{cand:>10}{'change':>10}")
    for f in ["rounds", "gems", "opp_gems", "collected", "gold", "monster_dmg", "camp_clears", "deposits",
              "deaths", "kills", "alive_rounds", "farm_rounds", "hit_rounds"]:
        a = sum(p[0][f] for p in pairs) / len(pairs)
        b = sum(p[1][f] for p in pairs) / len(pairs)
        print(f"{f:<14}{a:>10.1f}{b:>10.1f}{b - a:>+10.1f}")
    diffs = [b["gems"] - a["gems"] for a, b in pairs]
    if len(diffs) > 1:
        se = statistics.stdev(diffs) / math.sqrt(len(diffs))
        print(f"\ngem change {statistics.mean(diffs):+.1f}, paired se {se:.1f}; "
              f"{sum(x > 0 for x in diffs)} better, {sum(x < 0 for x in diffs)} worse, {sum(x == 0 for x in diffs)} same")
    for label, num, den in [("monster dmg per alive round", "monster_dmg", "alive_rounds"),
                            ("farming share of alive rounds", "farm_rounds", "alive_rounds")]:
        a = sum(p[0][num] for p in pairs) / sum(p[0][den] for p in pairs)
        b = sum(p[1][num] for p in pairs) / sum(p[1][den] for p in pairs)
        print(f"{label:<30}{a:>9.3f}{b:>9.3f}")
    print(f"\nper game ({base} -> {cand}):")
    for (o, mp), (a, b) in zip(keys, pairs):
        print(f"  {o[:16]:<16} {mp:<20} gems {a['gems']:4} -> {b['gems']:4} ({b['gems'] - a['gems']:+5})"
              f"  opp {a['opp_gems']:4} -> {b['opp_gems']:4}  deaths {a['deaths']:3.0f} -> {b['deaths']:3.0f}"
              f"  dmg {a['monster_dmg'] / 1000:5.1f}k -> {b['monster_dmg'] / 1000:5.1f}k")


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "fetch":
        fetch(Path(sys.argv[2]), sys.argv[3:])
    elif len(sys.argv) == 5 and sys.argv[1] == "compare":
        compare(Path(sys.argv[2]), sys.argv[3], sys.argv[4])
    else:
        sys.exit(__doc__)
