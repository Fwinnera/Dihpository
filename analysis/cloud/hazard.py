#!/usr/bin/env python3
"""Death hazard by PF label and zone (deaths within 10 turns per 1,000 champion turns), from p_pm logs."""
import collections, json, re, sys, zipfile
from pathlib import Path
US = "Milk and Potatoes"
PF = re.compile(r"PF (\d+) (\d+) ([a-z-]+) (-?\d+) (-?\d+) (\d+(?:\.\d+)?) (\d+(?:\.\d+)?) (\d+) (\d+) (-?\d+)(?: (-?\d+) (-?\d+) (-?\d+) (-?\d+))?")
MAPINFO = {k.replace("-", "_"): v for k, v in json.loads(Path("/home/user/runs/mapinfo/mapinfo.json").read_text()).items()}
def cheb(a, b): return max(abs(a[0]-b[0]), abs(a[1]-b[1]))
d = Path(sys.argv[1]); meta = json.loads((d / "meta.json").read_text())
turns = collections.Counter(); haz = collections.Counter()
for m in meta:
    me = next(t for t in m["teams"] if t["name"] == US)
    mi = MAPINFO.get(m["map"].replace("-", "_"))
    if not mi: continue
    own, enemy = (mi["spawn_a"], mi["spawn_b"]) if me["side"] == "a" else (mi["spawn_b"], mi["spawn_a"])
    try:
        out = zipfile.ZipFile(d / f"{m['matchId']}.repl26a").read(f"team-{me['side']}.stdout").decode("utf8", "replace").replace("\x00", "")
    except Exception: continue
    seq = collections.defaultdict(list)
    for p in PF.finditer(out):
        seq[int(p[2])].append((int(p[1]), p[3], int(p[4]), int(p[5])))
    for t, rows in seq.items():
        rows.sort()
        deaths = [rows[i][0] for i in range(1, len(rows)) if rows[i][1] == "dead" and rows[i-1][1] != "dead"]
        for r, lab, x, y in rows:
            if lab == "dead" or x < 0: continue
            do = min(cheb((x, y), q) for q in own); de = min(cheb((x, y), q) for q in enemy)
            depth = do / max(1, do + de)
            z = "home" if depth < 0.45 else "mid" if depth < 0.55 else "away"
            turns[(lab, z)] += 1
            if any(0 < dr - r <= 10 for dr in deaths): haz[(lab, z)] += 1
labs = sorted({k[0] for k in turns}, key=lambda l: -sum(turns[(l, z)] for z in ("home", "mid", "away")))
tot = sum(turns.values())
print(f"{'label':<16}" + "".join(f"{z + ' share':>12}{z + ' haz':>10}" for z in ("home", "mid", "away")))
for l in labs[:16]:
    print(f"{l:<16}" + "".join(f"{100 * turns[(l, z)] / tot:>11.1f}%{1000 * haz[(l, z)] / max(1, turns[(l, z)]):>10.0f}" for z in ("home", "mid", "away")))
