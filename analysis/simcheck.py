#!/usr/bin/env python3
"""How well does the fight simulator predict deaths, against the ratio rule?

    simcheck.py DIR      # bundles from a SIM_LOG build (PRED and DEATH lines)

Every PRED line is a turn with an enemy within the disengage radius. Its label
is whether that champion died within the next WINDOW rounds. Scores: the ratio
rule (local health x strength, ours over theirs; disengage below 0.5) and the
simulator (predicted death within its horizon; predicted health left).
"""
from __future__ import annotations

import re
import statistics
import sys
import zipfile
from pathlib import Path

WINDOW = 10
PRED = re.compile(r"PRED r=(\d+) s=(\d+) ratio=(\S+) die=(\d) at=(\d+) hp=(\S+) now=(\S+) gems=(\d+) kill=(\d+) lose=(\d+) fuel=(\d+)")
DEATH = re.compile(r"DEATH r=(\d+) s=(\d+)")


def auc(scores_pos: list[float], scores_neg: list[float]) -> float:
    """Probability a death turn scores higher than a survival turn (ties count half)."""
    allv = sorted([(s, 1) for s in scores_pos] + [(s, 0) for s in scores_neg])
    rank, i, pos_rank_sum = 1, 0, 0.0
    while i < len(allv):
        j = i
        while j < len(allv) and allv[j][0] == allv[i][0]:
            j += 1
        avg = (rank + rank + (j - i) - 1) / 2
        pos_rank_sum += avg * sum(1 for k in range(i, j) if allv[k][1])
        rank += j - i
        i = j
    n1, n0 = len(scores_pos), len(scores_neg)
    return (pos_rank_sum - n1 * (n1 + 1) / 2) / (n1 * n0) if n1 and n0 else float("nan")


def main(folder: Path) -> None:
    rows, fuels = [], []
    for b in sorted(folder.glob("*.repl26a")):
        side = "a"
        text = zipfile.ZipFile(b).read(f"team-{side}.stdout").replace(b"\x00", b"").decode("utf-8", "replace")
        deaths = {}
        for m in DEATH.finditer(text):
            deaths.setdefault(int(m.group(2)), []).append(int(m.group(1)))
        for m in PRED.finditer(text):
            r, s = int(m.group(1)), int(m.group(2))
            ratio = float("inf") if m.group(3) == "inf" else float(m.group(3))
            died = any(r < d <= r + WINDOW for d in deaths.get(s, []))
            rows.append(dict(died=died, ratio=ratio, die=m.group(4) == "1", hp=float(m.group(6)),
                             now=float(m.group(7)), gems=int(m.group(8))))
            fuels.append(int(m.group(11)))
    n = len(rows); pos = sum(r["died"] for r in rows)
    print(f"{n} turns with an enemy within 5 tiles; {pos} ({pos * 100 / n:.1f}%) followed by a death within {WINDOW} rounds")

    def rule(name, flag):
        tp = sum(1 for r in rows if flag(r) and r["died"]); fp = sum(1 for r in rows if flag(r) and not r["died"])
        fn = sum(1 for r in rows if not flag(r) and r["died"])
        prec = tp / (tp + fp) if tp + fp else 0; rec = tp / (tp + fn) if tp + fn else 0
        print(f"  {name:34} flags {tp + fp:6d}  precision {prec * 100:5.1f}%  recall {rec * 100:5.1f}%")
    rule("ratio < 0.5 (today's disengage)", lambda r: r["ratio"] < 0.5)
    rule("simulator: I die within horizon", lambda r: r["die"])
    rule("either", lambda r: r["die"] or r["ratio"] < 0.5)
    pos_rows = [r for r in rows if r["died"]]; neg_rows = [r for r in rows if not r["died"]]
    big = 1e9
    print(f"  AUC ratio (low = danger)          {auc([-min(r['ratio'], big) for r in pos_rows], [-min(r['ratio'], big) for r in neg_rows]):.3f}")
    print(f"  AUC simulated health left         {auc([-r['hp'] for r in pos_rows], [-r['hp'] for r in neg_rows]):.3f}")
    print(f"  AUC current health (baseline)     {auc([-r['now'] for r in pos_rows], [-r['now'] for r in neg_rows]):.3f}")
    if fuels:
        q = statistics.quantiles(fuels, n=20)
        print(f"  fuel left after the simulation: median {statistics.median(fuels):.0f}, 5th pct {q[0]:.0f}, min {min(fuels)}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
