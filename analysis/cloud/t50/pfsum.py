#!/usr/bin/env python3
"""pfsum.py DIR [SIDE=a] [UPTO]: state time budget from PF lines (profiled bot's stdout in replay bundles)."""
import sys, zipfile, glob, collections, json
d = sys.argv[1]; side = sys.argv[2] if len(sys.argv) > 2 else "a"; upto = int(sys.argv[3]) if len(sys.argv) > 3 else 100000
NAMES = ["ryth", "vesper", "vendetta", "cassi", "issac", "stellar", "prism", "marcella", "willow", "ren", "varg", "tavi", "hor"]
tot = collections.Counter(); by = collections.defaultdict(collections.Counter); games = 0
trans = collections.Counter(); heal_hp = []; spawn_runs = []; trips = collections.Counter()
for f in sorted(glob.glob(d + "/*.repl26a")):
    z = zipfile.ZipFile(f)
    try: out = z.read(f"team-{side}.stdout").replace(b"\x00", b"").decode("utf8", "replace")
    except KeyError: continue
    games += 1
    last = {}
    run = {}
    for line in out.splitlines():
        p = line.split()
        if len(p) < 9 or p[0] != "PF": continue
        r = int(p[1]); ch = int(p[2]); st = p[3]
        if r > upto: continue
        tot[st] += 1; by[NAMES[ch]][st] += 1
        prev = last.get(ch)
        if prev != st:
            trans[(prev, st)] += 1
            if st == "heal": heal_hp.append(int(p[6]) / max(1, int(p[7])))
            if st in ("heal", "shoprecall", "retreat"): trips[st] += 1
        last[ch] = st
n = sum(tot.values())
print(f"{games} games, {n} champion-turns (rounds <= {upto})")
for st, c in tot.most_common(): print(f"  {st:<12}{100*c/n:6.1f}%")
print("recall trips a game: " + ", ".join(f"{k} {v/games:.1f}" for k, v in trips.items()), "| mean health at heal-recall start:", round(sum(heal_hp)/max(1,len(heal_hp)), 2))
print("by champion (% of its turns):")
keys = [k for k, _ in tot.most_common(12)]
print(f"  {'':<10}" + "".join(f"{k[:9]:>10}" for k in keys))
for ch, c in by.items():
    t = sum(c.values())
    print(f"  {ch:<10}" + "".join(f"{100*c[k]/t:>10.1f}" for k in keys))
