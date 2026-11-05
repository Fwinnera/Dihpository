#!/usr/bin/env python3
"""Duels (as duels.py) in profiled games: our champion's PF labels during each duel, and the enemy's health
fraction at the end, for duels we won and lost."""
import collections, json, re, sys, zipfile
from pathlib import Path
US = "Milk and Potatoes"
T = ["ryth","vv","vend","cassi","issac","stel","prism","marc","willow","ren","varg","tavi","hor"]
PF = re.compile(r"PF (\d+) (\d+) ([a-z-]+) ")
def cheb(a, b): return max(abs(a[0]-b[0]), abs(a[1]-b[1]))
bdir, sdir = Path(sys.argv[1]), Path(sys.argv[2])
meta = json.loads((bdir / "meta.json").read_text())
at_leave = []; labs = {"us": collections.Counter(), "them": collections.Counter()}; endhp = {"us": [], "them": []}; first_leave = collections.Counter(); n = collections.Counter()
for m in meta:
    f = sdir / f"{m['matchId']}.jsonl"
    if not f.exists(): continue
    me = next(t for t in m["teams"] if t["name"] == US); ours = 0 if me["side"] == "a" else 1
    out = zipfile.ZipFile(bdir / f"{m['matchId']}.repl26a").read(f"team-{me['side']}.stdout").decode("utf8", "replace").replace("\x00", "")
    pf = {}
    for p in PF.finditer(out): pf[(int(p[1]), int(p[2]))] = p[3]
    rows = [json.loads(l) for l in f.read_text().splitlines()]; rows = [r for r in rows if r["c"]]
    busy = {}
    for i, st in enumerate(rows):
        living = [c for c in st["c"] if c[7] and c[3] >= 0]
        for a in living:
            if a[1] != ours or busy.get(a[0], -1) >= st["r"]: continue
            foes = [b for b in living if b[1] != ours and cheb((a[3], a[4]), (b[3], b[4])) <= 3]
            if len(foes) != 1: continue
            b = foes[0]
            if busy.get(b[0], -1) >= st["r"]: continue
            if any(c[0] not in (a[0], b[0]) and (cheb((a[3], a[4]), (c[3], c[4])) <= 6 or cheb((b[3], b[4]), (c[3], c[4])) <= 6) for c in living): continue
            if abs(a[5] / max(1, a[6]) - b[5] / max(1, b[6])) >= 0.15: continue   # similar health only
            winner = None; end = None; seq = []
            for st2 in rows[i:i + 16]:
                ca = next(c for c in st2["c"] if c[0] == a[0]); cb = next(c for c in st2["c"] if c[0] == b[0])
                if ca[7]: seq.append(pf.get((st2["r"], a[2]), "?"))
                if not ca[7] and cb[7]: winner = "them"; end = cb[5] / max(1, cb[6]); break
                if not cb[7] and ca[7]: winner = "us"; end = ca[5] / max(1, ca[6]); break
            if winner is None: continue
            n[winner] += 1
            for s in seq: labs[winner][s] += 1
            endhp[winner].append(end)
            fl = next((k for k, s in enumerate(seq) if s in ("retreat", "disengage", "recalling")), None)
            if fl is not None:
                stl = rows[i + fl]
                ca = next(c for c in stl["c"] if c[0] == a[0]); cb = next(c for c in stl["c"] if c[0] == b[0])
                at_leave.append((winner, seq[fl], ca[5] / max(1, ca[6]), cb[5] / max(1, cb[6]) if cb[7] else 0.0))
            first_leave[(winner, "left" if fl is not None else "stayed")] += 1
            busy[a[0]] = busy[b[0]] = st["r"] + 15
for w in ("us", "them"):
    tot = sum(labs[w].values())
    e = sorted(endhp[w])
    print(f"duels at similar health that {'we won' if w == 'us' else 'we lost'}: {n[w]}; our labels during them: " +
          ", ".join(f"{k} {100 * v / max(1, tot):.0f}%" for k, v in labs[w].most_common(6)) +
          f" | we left (retreat/disengage/recall) in {first_leave[(w, 'left')]} of {n[w]} | winner's health at the end: median {e[len(e) // 2]:.2f}" if e else "")

print("\nat the moment we first left a duel (our health, enemy health):")
for kind in ("retreat", "disengage", "recalling"):
    xs = [x for x in at_leave if x[1] == kind]
    if not xs: continue
    ours = sorted(x[2] for x in xs); theirs = sorted(x[3] for x in xs)
    ahead = sum(1 for x in xs if x[2] >= x[3])
    print(f"  {kind:<10} {len(xs):>3} times: our health median {ours[len(ours)//2]:.2f}, enemy {theirs[len(theirs)//2]:.2f}; we were level or ahead in {ahead}")
