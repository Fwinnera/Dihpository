#!/usr/bin/env python3
"""Deaths deep in enemy territory, from profiled games (an mkprof.py / mkprof2.py bot run by
drrun.sh or profrun.sh; folders <opp>__<map>__<A|B>, the profiled bot on that side).

    deepwhy.py RUNDIR [--maps a,b]

Depth of a tile: our distance to our nearest spawn tile over the sum of that and the distance to
the enemy's nearest spawn tile (Chebyshev; spawns from camps86.json) -- 0 at our spawn, 1 at
theirs. For our side of every game it prints:
  - deaths per game by the depth of the last living turn;
  - for deaths past the middle (depth >= 0.55): the label of the turn that carried the champion
    across the middle (the first turn of the deep run that ended in the death), the last label
    before the death, how long the champion had been deep, and its health when it crossed;
  - the hazard of each label (deaths in the next 10 turns per 1,000 champion turns) in our half
    and in theirs, which says which activities are deadly over there.
"""
import collections
import json
import re
import sys
import zipfile
from pathlib import Path

TYPES = ["ryth", "vesper_vale", "vendetta", "cassi", "issac", "stellar", "prism", "marcella",
         "willow", "ren", "varg", "tavi", "heart_of_ruin"]
PF = re.compile(r"PF (\d+) (\d+) ([a-z-]+) (-?\d+) (-?\d+) (\d+(?:\.\d+)?) (\d+(?:\.\d+)?) (\d+) (\d+) (-?\d+)")
T = json.loads(Path(__file__).with_name("camps86.json").read_text())
args = [a for a in sys.argv[1:] if not a.startswith("--")]
run = Path(args[0])
maps = set(sys.argv[sys.argv.index("--maps") + 1].split(",")) if "--maps" in sys.argv else None


def cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


games = 0
deaths_by_depth = collections.Counter()
entry = collections.Counter()
last = collections.Counter()
entry_by_champ = collections.defaultdict(collections.Counter)
dwell = []
cross_hp = []
turns = collections.Counter()      # (label, region) -> champion turns
hazard = collections.Counter()     # (label, region) -> deaths within 10 turns
deep_maps = collections.Counter()
for d in sorted(run.iterdir()):
    if not d.is_dir() or d.name.startswith("_"):
        continue
    opp, mp, side = d.name.rsplit("__", 2)
    if maps and mp not in maps:
        continue
    info = T.get(mp) or {}
    if not info.get("spawn_a") or not info.get("spawn_b"):
        continue
    bundle = next(d.glob("*.repl26a"), None)
    if bundle is None:
        continue
    try:
        out = zipfile.ZipFile(bundle).read(f"team-{side.lower()}.stdout").decode("utf8", "replace").replace("\x00", "")
    except (KeyError, zipfile.BadZipFile):
        continue
    games += 1
    own, enemy = (info["spawn_a"], info["spawn_b"]) if side == "A" else (info["spawn_b"], info["spawn_a"])
    seq = collections.defaultdict(list)
    for m in PF.finditer(out):
        r, t, lab, x, y, hp, mx = int(m[1]), int(m[2]), m[3], int(m[4]), int(m[5]), float(m[6]), float(m[7])
        if t >= len(TYPES):
            continue
        if x >= 0:
            do = min(cheb((x, y), q) for q in own)
            de = min(cheb((x, y), q) for q in enemy)
            depth = do / max(1, do + de)
        else:
            depth = None
        seq[TYPES[t]].append((r, lab, depth, hp / max(1.0, mx)))
    for champ, rows in seq.items():
        rows.sort()
        died_at = []
        for i in range(1, len(rows)):
            if rows[i][1] == "dead" and rows[i - 1][1] != "dead" and rows[i - 1][2] is not None:
                died_at.append(i)
        dset = set(died_at)
        # hazard: for every living turn, a death within the next 10 turns
        nxt = [None] * len(rows)
        j = None
        for i in range(len(rows) - 1, -1, -1):
            if i in dset:
                j = i
            nxt[i] = j
        for i, (r, lab, depth, hpf) in enumerate(rows):
            if depth is None or lab == "dead":
                continue
            region = "theirs" if depth >= 0.55 else "middle" if depth >= 0.45 else "ours"
            turns[(lab, region)] += 1
            if nxt[i] is not None and rows[nxt[i]][0] - r <= 10:
                hazard[(lab, region)] += 1
        for i in died_at:
            r, lab, depth, hpf = rows[i - 1]
            b = "0-0.25" if depth < 0.25 else "0.25-0.45" if depth < 0.45 else "0.45-0.55" if depth < 0.55 else "0.55-0.75" if depth < 0.75 else "0.75-1"
            deaths_by_depth[b] += 1
            if depth < 0.55:
                continue
            deep_maps[mp] += 1
            k = i - 1
            while k > 0 and rows[k - 1][2] is not None and rows[k - 1][2] >= 0.5 and rows[k - 1][1] != "dead":
                k -= 1
            entry[rows[k][1]] += 1
            entry_by_champ[champ][rows[k][1]] += 1
            last[lab] += 1
            dwell.append(rows[i][0] - rows[k][0])
            cross_hp.append(rows[k][3])

n = max(1, games)
print(f"{games} games; our deaths a game by depth:",
      ", ".join(f"{b} {deaths_by_depth[b] / n:.2f}" for b in ("0-0.25", "0.25-0.45", "0.45-0.55", "0.55-0.75", "0.75-1")))
deep = sum(entry.values())
if deep:
    print(f"deep deaths {deep} ({deep / n:.2f} a game); median rounds deep before dying {sorted(dwell)[len(dwell) // 2]}, "
          f"median health when crossing {sorted(cross_hp)[len(cross_hp) // 2]:.0%}")
    print("  label that carried them across the middle:", ", ".join(f"{k} {v / deep:.0%}" for k, v in entry.most_common(10)))
    print("  last label before death:", ", ".join(f"{k} {v / deep:.0%}" for k, v in last.most_common(10)))
    for champ, c in sorted(entry_by_champ.items(), key=lambda kv: -sum(kv[1].values())):
        tot = sum(c.values())
        print(f"    {champ:<12} {tot:>4}: " + ", ".join(f"{k} {v / tot:.0%}" for k, v in c.most_common(5)))
    print("  maps:", ", ".join(f"{k} {v}" for k, v in deep_maps.most_common(12)))
print("hazard (deaths within 10 turns per 1,000 turns) and share of turns, by label: ours | theirs")
labs = sorted({k[0] for k in turns}, key=lambda l: -(turns[(l, "theirs")]))
tot_ours = sum(v for k, v in turns.items() if k[1] == "ours")
tot_theirs = sum(v for k, v in turns.items() if k[1] == "theirs")
for lab in labs:
    a, b = turns[(lab, "ours")], turns[(lab, "theirs")]
    if a + b < 500:
        continue
    print(f"  {lab:<16} ours {1000 * hazard[(lab, 'ours')] / max(1, a):6.1f} ({a / max(1, tot_ours):5.1%})   "
          f"theirs {1000 * hazard[(lab, 'theirs')] / max(1, b):6.1f} ({b / max(1, tot_theirs):5.1%})")
