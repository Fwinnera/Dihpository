#!/usr/bin/env python3
"""trace.py STATES.jsonl SIDE(0|1) [FROM TO STEP]: compact timeline of one team: position, hp%, gold, gems; camps hit."""
import json, sys
NAMES = ["ryth", "vesp", "vend", "cass", "issa", "stel", "pris", "marc", "will", "ren", "varg", "tavi", "hor"]
f, side = sys.argv[1], int(sys.argv[2])
lo, hi, step = (int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])) if len(sys.argv) > 5 else (1, 300, 5)
camps = {}
acc = {}
def ctype(hp): return {1350: "W", 2400: "E", 5000: "G", 120: "c", 20000: "M"}.get(hp, "?")
for line in open(f):
    d = json.loads(line)
    if "camps" in d:
        for c in d["camps"]: camps.setdefault(c[0], (c[1], c[2], c[3]))
        continue
    r = d["r"]
    if r < lo or r > hi or not d["c"]: continue
    mine = [c for c in d["c"] if c[1] == side]
    for k, x, y, lost in d.get("d", []):
        near = [c for c in mine if c[7] and max(abs(c[3] - x), abs(c[4] - y)) <= 4]
        if near:
            key = f"{ctype(camps.get(k, (0,0,0))[2])}@{x},{y}"
            acc[key] = acc.get(key, 0) + lost
    if (r - lo) % step == 0:
        cells = []
        for c in mine:
            nm = NAMES[c[2]] if c[2] < len(NAMES) else str(c[2])
            cells.append(f"{nm}({c[3]:>2},{c[4]:>2}) {('%3d%%' % round(100*c[5]/max(1,c[6]))) if c[7] else 'DEAD'} g{c[8]:<4} m{c[9]:<3}")
        print(f"r{r:<4} " + " | ".join(cells) + "  || " + " ".join(f"{k}:{v}" for k, v in sorted(acc.items())))
        acc = {}
