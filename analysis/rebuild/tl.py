#!/usr/bin/env python3
"""One champion's game as label runs: tl.py GAMEDIR SIDE CHAMP [MAXROUND]"""
import re, sys, zipfile
from pathlib import Path
TYPES = ["ryth", "vesper_vale", "vendetta", "cassi", "issac", "stellar", "prism", "marcella",
         "willow", "ren", "varg", "tavi", "heart_of_ruin"]
PF = re.compile(r"PF (\d+) (\d+) ([a-z-]+) (-?\d+) (-?\d+) (\d+(?:\.\d+)?) (\d+(?:\.\d+)?) (\d+) (\d+) (-?\d+)(?=\n|PF|$)")
d, side, champ = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
mx = int(sys.argv[4]) if len(sys.argv) > 4 else 10**9
out = zipfile.ZipFile(next(d.glob("*.repl26a"))).read(f"team-{side.lower()}.stdout").decode("utf8", "replace").replace("\x00", "")
rows = sorted((int(m[1]), m[3], int(m[4]), int(m[5]), float(m[6]), int(m[8]), int(m[9]), int(m[10]))
              for m in PF.finditer(out) if TYPES[int(m[2])] == champ and int(m[1]) <= mx)
runs = []
for r in rows:
    if runs and runs[-1][1] == r[1] and runs[-1][7] == r[7] and runs[-1][-1] == r[0] - 1:
        runs[-1][-1] = r[0]
    else:
        runs.append(list(r) + [r[0]])
for r in runs:
    print(f"{r[0]:5d}-{r[-1]:<5d} {r[-1]-r[0]+1:4d} {r[1]:<14} g{r[7]:<3d} at ({r[2]},{r[3]}) hp {r[4]:.0f} gems {r[5]} gold {r[6]}")
