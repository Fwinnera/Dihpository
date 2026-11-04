#!/usr/bin/env python3
"""Family-level mechanism counts on party maps (means per game over every build's games).

    pmfacts.py --opps a,b FAMILY=cand:tag[+tag],... ...
Columns: games, gems submitted / collected / lost, deaths to camps / champions, monolith rewards,
median first-bank round.
"""
import argparse
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pmsum import BENCH, PARTY, facts, load  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--opps", required=True)
    ap.add_argument("fams", nargs="+")
    a = ap.parse_args()
    opps = a.opps.split(",")
    print(f"{'family':<8}{'map':<15}{'n':>4}{'sub':>6}{'col':>6}{'lost':>5}{'dc':>5}{'dh':>5}{'big':>5}{'1st':>6}")
    for spec in a.fams:
        name, rest = spec.split("=", 1)
        members = [(c, tags.split("+")) for c, tags in (x.split(":") for x in rest.split(","))]
        for m in PARTY:
            rows = []
            for cand, tags in members:
                for tag in tags:
                    for o in opps:
                        for s in "AB":
                            p = BENCH / tag / f"{cand}__{o}__{m}__{s}.json"
                            if not p.exists():
                                continue
                            rows.append(facts(load(p), "teamA" if s == "A" else "teamB", m))
            if not rows:
                continue
            g = lambda k: sum(r[k] for r in rows) / len(rows)
            first = statistics.median(r["first"] for r in rows)
            print(f"{name:<8}{m[:14]:<15}{len(rows):>4}{g('sub'):>6.0f}{g('col'):>6.0f}{g('lost'):>5.0f}{g('dc'):>5.1f}{g('dh'):>5.1f}{g('big'):>5.1f}{first:>6.0f}")


if __name__ == "__main__":
    main()
