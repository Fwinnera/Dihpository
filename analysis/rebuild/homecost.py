#!/usr/bin/env python3
"""What each trip home costs: rounds from the decision to go home until the champion
is next hitting, approaching or capturing a camp, by why it went home.

    homecost.py RUNDIR
"""
import statistics as st
import sys
from collections import Counter, defaultdict
from pathlib import Path

src = Path(__file__).with_name("profsum.py").read_text()
ns = {"__name__": "homecost"}
sys.argv = [sys.argv[0], sys.argv[1]]
exec(compile(src.split("labels = defaultdict(Counter)")[0], "profsum", "exec"), ns)

WORK = {"approach", "farm", "capture", "to-reward", "party-clear", "submitting"}
cost = defaultdict(list)
bank_from_spawn = []
n = 0
for opp, mp, side, ours, theirs, rows in ns["games"]():
    n += 1
    by = defaultdict(list)
    for r in rows:
        by[r[1]].append(r)
    for champ, rs in by.items():
        rs.sort()
        i = 0
        while i < len(rs):
            lab = rs[i][2]
            reason = None
            if lab == "dead" and (i == 0 or rs[i - 1][2] != "dead"):
                reason = "death"
            elif lab in ("heal", "shop-recall"):
                reason = lab
            elif lab == "recalling" and i > 0 and rs[i - 1][2] in ("retreat", "bank", "idle", "travel", "combat", "disengage", "capture"):
                reason = "recall from " + rs[i - 1][2]
            if reason is None:
                i += 1
                continue
            start = rs[i][0]
            j = i + 1
            while j < len(rs) and rs[j][2] not in WORK:
                j += 1
            if j < len(rs):
                cost[reason].append(rs[j][0] - start)
            # after death or recall, a bank walk started at spawn
            k = i + 1
            while k < len(rs) and rs[k][2] in ("dead", "recalling", "spawn-heal", "heal", "shop-recall", "none"):
                k += 1
            if k < len(rs) and rs[k][2] == "bank":
                m = k
                while m + 1 < len(rs) and rs[m + 1][2] == "bank":
                    m += 1
                bank_from_spawn.append((rs[m][0] - rs[k][0] + 1, rs[k][7]))
            i = j if j > i else i + 1
print(f"{n} games: rounds from going home to next camp work (count a game, median, mean, rounds a game)")
for k, v in sorted(cost.items(), key=lambda kv: -sum(kv[1])):
    print(f"  {k:<24} {len(v) / n:5.1f}  {st.median(v):5.0f}  {st.mean(v):6.1f}  {sum(v) / n:7.1f}")
if bank_from_spawn:
    w = [b[0] for b in bank_from_spawn]; g = [b[1] for b in bank_from_spawn]
    print(f"\nbank walks straight out of spawn: {len(w) / n:.1f} a game, median walk {st.median(w):.0f}, "
          f"median gems {st.median(g):.0f}, under 24 gems {sum(1 for x in g if x < 24) / n:.1f} a game, "
          f"{sum(w) / n:.0f} rounds a game")
