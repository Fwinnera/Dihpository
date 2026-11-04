#!/usr/bin/env python3
"""Candidates side by side on party maps, over the same opponents (pmscreen tags).

    pmcmp.py --opps a,b,c CAND:TAG[+TAG] ...
Per map: wins, mean gems submitted / collected / lost, deaths to camps / champions,
monolith (big-group) rewards; then totals.
"""
import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pmsum import BENCH, PARTY, facts, load  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--opps", required=True)
    ap.add_argument("cands", nargs="+")
    a = ap.parse_args()
    opps = a.opps.split(",")
    print(f"{'map':<14} " + " | ".join(f"{c.split(':')[0][:10]:<36}" for c in a.cands))
    print(f"{'':<14} " + " | ".join(f"{'win':>4} {'sub':>5} {'col':>5} {'lost':>4} {'dc':>4} {'dh':>4} {'big':>4}" for _ in a.cands))
    tot = defaultdict(lambda: defaultdict(float))
    for m in PARTY:
        cells = []
        for spec in a.cands:
            cand, tags = spec.split(":")
            agg, n = defaultdict(float), 0
            for tag in tags.split("+"):
                for o in opps:
                    for s in "AB":
                        p = BENCH / tag / f"{cand}__{o}__{m}__{s}.json"
                        if not p.exists():
                            p = p.with_suffix(".json.gz")
                        if not p.exists():
                            continue
                        d = load(p)
                        me = "teamA" if s == "A" else "teamB"
                        f = facts(d, me, m)
                        agg["win"] += d["match"]["outcome"] == me
                        for k in ("sub", "col", "lost", "dc", "dh", "big"):
                            agg[k] += f[k]
                        n += 1
            for k, v in agg.items():
                tot[spec][k] += v
            tot[spec]["n"] += n
            cells.append(f"{int(agg['win']):>2}/{n:<2}{agg['sub'] / max(1, n):>5.0f} {agg['col'] / max(1, n):>5.0f} {agg['lost'] / max(1, n):>4.0f} "
                         f"{agg['dc'] / max(1, n):>4.1f} {agg['dh'] / max(1, n):>4.1f} {agg['big'] / max(1, n):>4.1f}")
        print(f"{m[:14]:<14} " + " | ".join(cells))
    print(f"{'total':<14} " + " | ".join(f"{int(tot[c]['win']):>3}/{int(tot[c]['n']):<3} sub {tot[c]['sub'] / max(1, tot[c]['n']):.0f}{'':<19}" for c in a.cands))


if __name__ == "__main__":
    main()
