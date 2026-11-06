#!/usr/bin/env python3
"""p_fuel bail-outs (RP lines): the last checkpoint reached and the fuel spent between checkpoints, for bail-outs
that did nothing (could still move and attack)."""
import collections, sys, zipfile
from pathlib import Path
d = Path("/home/user/repo/ws/bench") / sys.argv[1]
last = collections.Counter(); spent = collections.defaultdict(list); games = 0; n = 0; start = []
for f in sorted(d.glob("*__*__*.repl26a")):
    side = f.stem.rsplit("__", 1)[-1]
    out = zipfile.ZipFile(f).read(f"team-{'a' if side == 'A' else 'b'}.stdout").decode("utf8", "replace").replace("\x00", "")
    games += 1
    for l in out.splitlines():
        p = l.split()
        if len(p) < 9 or p[0] != "RP" or int(p[1]) <= 5: continue
        if p[4] != "1" or p[5] != "1" or p[6] != "1": continue   # alive, could move, could attack
        n += 1
        marks = sorted(((int(k), int(v)) for k, v in (x.split(":") for x in p[8:])), key=lambda kv: -kv[1])   # chronological: fuel only falls
        last[marks[-1][0]] += 1
        start.append(marks[0][1])
        for (k0, v0), (k1, v1) in zip(marks, marks[1:]):
            spent[(k0, k1)].append(v0 - v1)
        # fuel spent after the last mark until the bail-out (remaining < 10,000)
        spent[(marks[-1][0], "bail")].append(marks[-1][1] - 10000)
print(f"games {games}: bail-outs that did nothing {n / games:.1f} a game")
start.sort()
print(f"fuel at turn start: median {start[len(start) // 2]}, 10th pct {start[len(start) // 10]}")
print("last checkpoint reached:", ", ".join(f"{k}: {v / games:.1f}" for k, v in sorted(last.items())))
print("fuel spent between checkpoints in those turns (count, median):")
for k, v in sorted(spent.items(), key=lambda kv: -sum(kv[1])):
    v.sort()
    if len(v) >= 5: print(f"  {str(k):<14} n {len(v):>6}  median {v[len(v) // 2]:>7}  total share {sum(v) / max(1, sum(sum(x) for x in spent.values())):.0%}")
