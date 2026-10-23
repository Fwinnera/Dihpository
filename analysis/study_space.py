#!/usr/bin/env python3
"""Where a team operates, the true order it buys emblems in, and how its
carriers bank.

Bases: each team shops at its own spawn, so the median position of its
purchases marks its base, and the opponent's purchases mark theirs. Every
positioned event is then placed on the line between them: 0 at home, 1 at the
enemy base. Emblem order comes from the timestamped `buyItem` events (the
summary's `itemsBought` list is in catalogue order, not purchase order).

    study_space.py prism | us
"""
from __future__ import annotations

import json
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from study_team import sources, expand  # noqa: E402


def depth(p, home, away):
    hx, hy = home; ax, ay = away
    vx, vy = ax - hx, ay - hy
    L = vx * vx + vy * vy
    if L == 0:
        return None
    return ((p[0] - hx) * vx + (p[1] - hy) * vy) / L


def main(which):
    games = 0
    where = defaultdict(lambda: defaultdict(list))     # kind -> champion -> depths
    order = defaultdict(Counter)
    dep_rounds = defaultdict(list)
    carry_peak = defaultdict(list)
    deposit_share = defaultdict(list)
    end_gap = defaultdict(list)
    for path, side, win in sources(which):
        d = json.loads(path.read_text())
        other = "teamB" if side == "teamA" else "teamA"
        n = d["match"]["roundsCompleted"]
        buys = defaultdict(list)
        for e in d["events"]:
            if e["kind"] == "buyItem":
                t = (e.get("owner") or {}).get("team")
                buys[t] += [(x["x"], x["y"]) for x in e["entries"] if "x" in x]
        if not buys[side] or not buys[other]:
            continue
        home = (st.median(p[0] for p in buys[side]), st.median(p[1] for p in buys[side]))
        away = (st.median(p[0] for p in buys[other]), st.median(p[1] for p in buys[other]))
        games += 1
        shards = defaultdict(Counter)
        seq = defaultdict(list)
        team_sub = 0.0
        sub_by = Counter()
        for e in sorted(d["events"], key=lambda e: 0):
            o = e.get("owner") or {}
            if o.get("team") != side:
                continue
            name = o.get("name")
            for x in e.get("entries", []):
                if e["kind"] in ("campClear", "kill", "death", "gemSubmission", "wardPlacement") and "x" in x:
                    dp = depth((x["x"], x["y"]), home, away)
                    if dp is not None:
                        where[e["kind"]][name].append(dp)
                if e["kind"] == "buyItem":
                    item = (x.get("target") or {}).get("name", "")
                    if "Shard" in item:
                        shards[name][item] += int(x.get("value", 1) or 1)
                        if shards[name][item] >= 5:
                            shards[name][item] -= 5
                            seq[name].append((x["timestamp"]["round"], item.replace(" Shard of ", ":")))
                    elif "Emblem" in item:
                        seq[name].append((x["timestamp"]["round"], item.replace(" Emblem of ", ":")))
                if e["kind"] == "gemSubmission":
                    v = float(x.get("value", 0) or 0)
                    dep_rounds[name].append((x["timestamp"]["round"], v, n))
                    sub_by[name] += v; team_sub += v
        for name, s in seq.items():
            order[name][tuple(i for _, i in sorted(s)[:4])] += 1
        for name, v in sub_by.items():
            deposit_share[name].append(v / team_sub if team_sub else 0)
        for x in d["championTimelines"]:
            if x["owner"]["team"] == side and x["metric"] == "gems":
                carry_peak[x["owner"]["name"]].append(max(expand(x["runs"], n + 1)))

    print(f"### {which}: {games} games with both bases located\n")
    print("WHERE THEY OPERATE: median depth, 0 = own base, 1 = enemy base; % of events past halfway")
    print("  %-14s" % "" + "".join("%20s" % k for k in ("campClear", "gemSubmission", "kill", "death", "wardPlacement")))
    names = sorted({n for k in where.values() for n in k}, key=lambda n: -len(where["campClear"][n]))
    for name in names:
        row = ""
        for k in ("campClear", "gemSubmission", "kill", "death", "wardPlacement"):
            v = where[k][name]
            row += ("%11.2f %6.0f%%  " % (st.median(v), 100 * sum(1 for z in v if z > 0.5) / len(v))) if len(v) >= 5 else "%20s" % "-"
        print("  %-14s" % name + row)
    print("\nEMBLEM ORDER (from purchase events): most common first four completed")
    for name in names:
        for t, c in order[name].most_common(2):
            print(f"  {name:<14} {' > '.join(t)}  (x{c})")
    print("\nBANKING: share of the team's submitted gems, peak gems carried, deposit timing")
    for name in names:
        sh = deposit_share[name]; pk = carry_peak[name]; dr = dep_rounds[name]
        if not sh:
            continue
        last = [n - r for r, v, n in dr]
        big = [v for r, v, n in dr if v >= 100]
        print(f"  {name:<14} share {100 * st.mean(sh):5.1f}%   peak carried median {st.median(pk) if pk else 0:5.0f}"
              f"   deposits of 100+ gems: {len(big)}   median rounds before game end {st.median(last) if last else 0:.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "prism"))
