#!/usr/bin/env python3
"""What champions were doing in the 8 rounds before each death: deaths.py RUNDIR"""
import statistics as st, sys
from collections import Counter, defaultdict
from pathlib import Path
src = Path(__file__).with_name("profsum.py").read_text()
ns = {"__name__": "deaths"}
sys.argv = [sys.argv[0], sys.argv[1]]
exec(compile(src.split("labels = defaultdict(Counter)")[0], "profsum", "exec"), ns)
first = Counter(); last = Counter(); gems = []; n = 0; when = []; champ = Counter(); hp_at = []
for opp, mp, side, ours, theirs, rows in ns["games"]():
    n += 1
    by = defaultdict(list)
    for r in rows: by[r[1]].append(r)
    for c, rs in by.items():
        rs.sort()
        for i in range(1, len(rs)):
            if rs[i][2] == "dead" and rs[i - 1][2] != "dead":
                window = [r for r in rs[max(0, i - 8):i] if r[0] >= rs[i][0] - 8]
                if not window: continue
                labs = [r[2] for r in window]
                last[labs[-1]] += 1
                # the first label of the run of fight-like labels before death
                k = len(labs) - 1
                while k > 0 and labs[k - 1] in ("combat", "retreat", "disengage", "no-action"):
                    k -= 1
                first[labs[k]] += 1
                gems.append(window[-1][7]); when.append(rs[i][0]); champ[c] += 1
                hp_at.append(window[0][5] / max(1, window[0][6]))
print(f"{n} games, {sum(last.values()) / n:.1f} deaths a game; median round {st.median(when):.0f}; "
      f"carrying gems: median {st.median(gems):.0f}, mean {st.mean(gems):.1f}; health 8 rounds before: median {st.median(hp_at):.2f}")
print("  last decision before death:", ", ".join(f"{k} {100 * v / sum(last.values()):.0f}%" for k, v in last.most_common(8)))
print("  what started it:          ", ", ".join(f"{k} {100 * v / sum(first.values()):.0f}%" for k, v in first.most_common(8)))
print("  by champion:", ", ".join(f"{k} {v / n:.1f}" for k, v in champ.most_common()))
q = sorted(when); print("  deaths by round quartile:", q[len(q) // 4], q[len(q) // 2], q[3 * len(q) // 4], " before round 200:", f"{sum(1 for w in q if w < 200) / n:.1f} a game")
