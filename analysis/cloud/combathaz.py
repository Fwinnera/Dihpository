#!/usr/bin/env python3
"""Combat turns by local numbers (allies within 5 vs visible enemies within 5): share, death hazard within 10
turns, and kill rate (an enemy champion death within 10 rounds credited to our team)."""
import collections, json, re, sys, zipfile
from pathlib import Path
US = "Milk and Potatoes"
PF = re.compile(r"PF (\d+) (\d+) ([a-z-]+) (-?\d+) (-?\d+) (\d+(?:\.\d+)?) (\d+(?:\.\d+)?) (\d+) (\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+) (-?\d+)")
d = Path(sys.argv[1]); meta = json.loads((d / "meta.json").read_text())
turns = collections.Counter(); haz = collections.Counter(); kill = collections.Counter()
labels = set(sys.argv[2].split(",")) if len(sys.argv) > 2 else {"combat"}
for m in meta:
    me = next(t for t in m["teams"] if t["name"] == US); side = "teamA" if me["side"] == "a" else "teamB"
    try:
        out = zipfile.ZipFile(d / f"{m['matchId']}.repl26a").read(f"team-{me['side']}.stdout").decode("utf8", "replace").replace("\x00", "")
        s = json.loads((d / f"{m['matchId']}.json").read_text())
    except Exception: continue
    names = {c["id"]: c["team"] for c in s["roster"]["champions"]}
    kills = [e["timestamp"]["round"] for ev in s["events"] if ev["kind"] == "death" and names.get(ev["owner"]["id"]) != side for e in ev["entries"]]
    seq = collections.defaultdict(list)
    for p in PF.finditer(out):
        seq[int(p[2])].append((int(p[1]), p[3], int(p[11]), int(p[13])))
    for t, rows in seq.items():
        rows.sort()
        deaths = [rows[i][0] for i in range(1, len(rows)) if rows[i][1] == "dead" and rows[i-1][1] != "dead"]
        for r, lab, ne5, na5 in rows:
            if lab not in labels or ne5 < 0: continue
            k = (min(na5, 3), min(ne5, 3))
            turns[k] += 1
            if any(0 < dr - r <= 10 for dr in deaths): haz[k] += 1
            if any(0 < kr - r <= 10 for kr in kills): kill[k] += 1
tot = sum(turns.values())
print(f"{','.join(sorted(labels))} turns: {tot}")
print(f"{'allies v enemies (within 5)':<28}{'share':>8}{'death<=10':>11}{'team kill<=10':>15}")
for k in sorted(turns, key=lambda k: -turns[k])[:14]:
    print(f"{str(k[0]) + 'v' + str(k[1]):<28}{100 * turns[k] / tot:>7.1f}%{1000 * haz[k] / turns[k]:>10.0f}{1000 * kill[k] / turns[k]:>14.0f}")
