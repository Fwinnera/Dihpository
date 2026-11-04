#!/usr/bin/env python3
"""Twin families on party maps: each candidate as the mean over decision-identical rebuilds.

    pmfam.py --opps a,b,c FAMILY=cand:tag[+tag],cand:tag ... [--base FAMILY]

A party-map game re-rolls with any change in fuel use (two decision-identical builds of ab3
won 7 and 1 of 10 on 01boss-battle), so one build's screen cannot rank changes. A family is a
candidate plus rebuilds that differ only by a dead loop (mkparty.py twin=K). Each game cell
(opponent, map, side) gets the family's win fraction and mean margin over its builds; families
are compared cell by cell against --base (paired; standard error across cells).
"""
import argparse
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pmsum import BENCH, PARTY, facts, load  # noqa: E402


def family_cells(members, opps):
    cells = defaultdict(list)  # (opp, map, side) -> [(win, margin, sub)]
    for cand, tags in members:
        for tag in tags:
            for o in opps:
                for m in PARTY:
                    for s in "AB":
                        p = BENCH / tag / f"{cand}__{o}__{m}__{s}.json"
                        if not p.exists():
                            p = Path(str(p) + ".gz")
                        if not p.exists():
                            continue
                        d = load(p)
                        me, them = ("teamA", "teamB") if s == "A" else ("teamB", "teamA")
                        g = {t["team"]: int(t["submittedGems"]) for t in d["teams"]}
                        cells[(o, m, s)].append((d["match"]["outcome"] == me, g.get(me, 0) - g.get(them, 0), g.get(me, 0)))
    return cells


def mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--opps", required=True)
    ap.add_argument("--base")
    ap.add_argument("fams", nargs="+")
    a = ap.parse_args()
    opps = a.opps.split(",")
    fams = {}
    for spec in a.fams:
        name, rest = spec.split("=", 1)
        members = []
        for item in rest.split(","):
            cand, tags = item.split(":")
            members.append((cand, tags.split("+")))
        fams[name] = family_cells(members, opps)
    names = list(fams)
    base = a.base or names[0]
    print("win % by map (games per family in brackets); paired difference against", base)
    print(f"{'map':<14}" + "".join(f"{n:>18}" for n in names))
    for scope, maps, oo in (("all", PARTY, opps), ("gs_mix", PARTY, [o for o in opps if "gsmix" in o])):
        if not oo:
            continue
        rows = maps + ["TOTAL"]
        print(f"-- opponents: {scope}")
        for m in rows:
            line = f"{m[:14]:<14}"
            keys = [(o, mm, s) for o in oo for mm in (maps if m == "TOTAL" else [m]) for s in "AB"]
            for n in names:
                c = fams[n]
                games = [g for k in keys for g in c.get(k, [])]
                if not games:
                    line += f"{'-':>18}"
                    continue
                w = 100 * mean([g[0] for g in games])
                mg = mean([g[1] for g in games])
                cellwins = [mean([g[0] for g in c[k]]) for k in keys if c.get(k)]
                if n != base:
                    b = fams[base]
                    diffs = [mean([g[0] for g in c[k]]) - mean([g[0] for g in b[k]]) for k in keys if c.get(k) and b.get(k)]
                    if len(diffs) > 1:
                        md = mean(diffs)
                        sd = math.sqrt(sum((x - md) ** 2 for x in diffs) / (len(diffs) - 1)) / math.sqrt(len(diffs))
                        line += f"{w:>6.0f}{100 * md:>+6.0f}({100 * sd:>2.0f}){'':>1}"
                        continue
                line += f"{w:>6.0f} m{mg:>+5.0f} [{len(games):>3}]"
            print(line)


if __name__ == "__main__":
    main()
