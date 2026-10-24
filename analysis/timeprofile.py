#!/usr/bin/env python3
"""Where do our champion-turns go? Reads `mktimelog.py` loggers' TL lines.

    timeprofile.py TAG [TAG ...]       # bench folders under ws/bench

For every game it takes each champion's last cumulative TL line from our team's
stdout inside the replay bundle (NUL padding stripped), sums them, and prints
each label's share of all champion-turns, with the share of turns that landed a
hit on a camp or a champion. Labels are the branch of play_turn that ended the
turn; a `replan/` prefix means a fuel suspension cut it short.
"""
from __future__ import annotations

import collections
import sys
import zipfile
from pathlib import Path

BENCH = Path(__file__).resolve().parent.parent / "ws" / "bench"


def game_counts(bundle: Path, side: str) -> dict[str, int]:
    with zipfile.ZipFile(bundle) as z:
        name = f"team-{side.lower()}.stdout"
        if name not in z.namelist():
            return {}
        text = z.read(name).replace(b"\x00", b"").decode("utf-8", "replace")
    last = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0] == "TL":
            last[parts[2]] = parts[3:]
    total = collections.Counter()
    for fields in last.values():
        for f in fields:
            k, _, v = f.partition("=")
            total[k] += int(v)
    return total


def main(tags: list[str]) -> None:
    total, games = collections.Counter(), 0
    per_map = collections.defaultdict(collections.Counter)
    for tag in tags:
        for bundle in sorted((BENCH / tag).glob("*.repl26a")):
            opp, mapname, side = bundle.stem.split("__")
            c = game_counts(bundle, side)
            if not c:
                continue
            games += 1
            total.update(c)
            per_map[mapname].update(c)
    turns = total["turns"]
    if not turns:
        sys.exit("no TL lines found")
    print(f"{games} games, {turns} champion-turns\n")
    print(f"  {'hit a camp':<22}{100 * total['hit_camp'] / turns:6.1f}%")
    print(f"  {'hit a champion':<22}{100 * total['hit_champ'] / turns:6.1f}%\n")
    merged = collections.Counter()
    for k, v in total.items():
        if k in ("turns", "hit_camp", "hit_champ") or k.startswith(("ev_", "at/")):
            continue
        merged[k] += v
    print(f"  {'label':<22}{'share':>7}")
    for k, v in merged.most_common():
        print(f"  {k:<22}{100 * v / turns:6.1f}%")
    lost = sum(v for k, v in total.items() if k.startswith("replan/"))
    print(f"\n  {'cut short by fuel':<22}{100 * lost / turns:6.1f}%")
    events = {k: v for k, v in total.items() if k.startswith("ev_")}
    if events:
        print("\n  events per 1,000 champion-turns")
        for k, v in sorted(events.items()):
            if k != "ev_wasted_travel":
                print(f"  {k:<22}{1000 * v / turns:7.2f}")
        print(f"  travel wasted on dropped objectives: {100 * events.get('ev_wasted_travel', 0) / turns:.1f}% of turns")
    where = collections.Counter({k[3:]: v for k, v in total.items() if k.startswith("at/")})
    if where:
        print("\n  where fuel ran out (innermost frames)")
        for k, v in where.most_common(12):
            print(f"  {100 * v / turns:5.1f}%  {k}")
    print("\n  per map: travel / bank / hit camp shares")
    for m, c in sorted(per_map.items(), key=lambda kv: -kv[1]["travel"] / max(1, kv[1]["turns"])):
        t = max(1, c["turns"])
        print(f"    {m:24}{100 * c['travel'] / t:6.1f}%{100 * c['bank'] / t:7.1f}%{100 * c['hit_camp'] / t:7.1f}%")


if __name__ == "__main__":
    main(sys.argv[1:] or sys.exit(__doc__))
