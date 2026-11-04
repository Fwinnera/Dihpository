#!/usr/bin/env python3
"""Print the last N rounds before one of our deaths: every champion within 14 of the victim (team, type, pos, hp)."""
import json, sys
from pathlib import Path
US = "Milk and Potatoes"
T = ["ryth","vv","vend","cassi","issac","stel","prism","marc","willow","ren","varg","tavi","hor"]
bdir, sdir, mid, rnd, vtype = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5]
meta = {m["matchId"]: m for m in json.loads(Path(bdir, "meta.json").read_text())}
me = next(t for t in meta[mid]["teams"] if t["name"] == US); ours = 0 if me["side"] == "a" else 1
st = {json.loads(l)["r"]: json.loads(l) for l in Path(sdir, f"{mid}.jsonl").read_text().splitlines()}
def cheb(a, b): return max(abs(a[0]-b[0]), abs(a[1]-b[1]))
v = next(c for c in st[rnd - 1]["c"] if c[1] == ours and T[c[2]] == vtype)
for r in range(rnd - 16, rnd + 1):
    if r not in st: continue
    vc = next(c for c in st[r]["c"] if c[0] == v[0])
    vp = (vc[3], vc[4]) if vc[7] else (v[3], v[4])
    row = []
    for c in st[r]["c"]:
        if not c[7] or c[3] < 0: continue
        d = cheb(vp, (c[3], c[4]))
        if d <= 14:
            tag = ("U" if c[1] == ours else "E") + ":" + T[c[2]]
            row.append(f"{tag}@{d}({c[5]}/{c[6]})")
    print(f"r{r}: " + "  ".join(sorted(row, key=lambda s: (s[0], int(s.split('@')[1].split('(')[0])))))
