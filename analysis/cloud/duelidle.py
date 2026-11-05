#!/usr/bin/env python3
"""Our idle duel turns (no move, attack or cast) in profiled games: the PF label of that turn (missing = the turn
ended in a replan or exception, i.e. no PF line), our champion type, and the codes it did emit."""
import collections, json, re, sys, zipfile
from pathlib import Path
US = "Milk and Potatoes"
T = ["ryth","vv","vend","cassi","issac","stel","prism","marc","willow","ren","varg","tavi","hor"]
PF = re.compile(r"PF (\d+) (\d+) ([a-z-]+) ")
def cheb(a, b): return max(abs(a[0]-b[0]), abs(a[1]-b[1]))
bdir, sdir, adir = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
meta = json.loads((bdir / "meta.json").read_text())
lab = collections.Counter(); typ = collections.Counter(); codes = collections.Counter(); alltyp = collections.Counter(); alllab = collections.Counter()
for m in meta:
    f = sdir / f"{m['matchId']}.jsonl"; fa = adir / f"{m['matchId']}.jsonl"
    if not (f.exists() and fa.exists()): continue
    me = next(t for t in m["teams"] if t["name"] == US); ours = 0 if me["side"] == "a" else 1
    out = zipfile.ZipFile(bdir / f"{m['matchId']}.repl26a").read(f"team-{me['side']}.stdout").decode("utf8", "replace").replace("\x00", "")
    pf = {}
    for p in PF.finditer(out): pf[(int(p[1]), int(p[2]))] = p[3]
    acts = collections.defaultdict(list)
    for l in fa.read_text().splitlines():
        r = json.loads(l)
        if r[8] and r[1] >= 0: acts[(r[0], r[1])].append(r[2])
    rows = [json.loads(l) for l in f.read_text().splitlines()]; rows = [r for r in rows if r["c"]]
    for st, nx in zip(rows, rows[1:]):
        living = [c for c in st["c"] if c[7] and c[3] >= 0]
        for a in living:
            if a[1] != ours: continue
            foes = [b for b in living if b[1] != ours and cheb((a[3], a[4]), (b[3], b[4])) <= 3]
            if len(foes) != 1: continue
            b = foes[0]
            if any(c[0] not in (a[0], b[0]) and (cheb((a[3], a[4]), (c[3], c[4])) <= 6 or cheb((b[3], b[4]), (c[3], c[4])) <= 6) for c in living): continue
            na = next(c for c in nx["c"] if c[0] == a[0]); nb = next(c for c in nx["c"] if c[0] == b[0])
            if not (na[7] and nb[7]): continue
            cs = acts.get((st["r"], a[0]), [])
            label = pf.get((st["r"], a[2]), "MISSING")
            alltyp[T[a[2]]] += 1; alllab[label] += 1
            if any(k in cs for k in (4, 5, 6)): continue
            lab[label] += 1; typ[T[a[2]]] += 1; codes[tuple(cs)] += 1
n = sum(lab.values())
print(f"idle duel turns: {n} of {sum(alltyp.values())}")
print("PF label on idle turns:", ", ".join(f"{k} {v} ({100 * v / max(1, alllab[k]):.0f}% of that label's duel turns)" for k, v in lab.most_common(12)))
print("by champion:", ", ".join(f"{k} {v}/{alltyp[k]}" for k, v in typ.most_common()))
print("codes emitted on idle turns:", codes.most_common(10))
