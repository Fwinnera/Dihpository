#!/usr/bin/env python3
"""Summarise per-round profiler lines (PF ...) from profrun.sh output.

    profsum.py RUNDIR [BOTNAME] [--maps a,b] [--by-map]

Prints, for our side of every game: the share of champion-rounds per decision label,
per champion type and for the team, then episode statistics for the labels that
look like waste (spawn-heal, travel, recalls, idle, dead).
"""
import re
import statistics as st
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

TYPES = ["ryth", "vesper_vale", "vendetta", "cassi", "issac", "stellar", "prism", "marcella",
         "willow", "ren", "varg", "tavi", "heart_of_ruin"]

PF = re.compile(r"PF (\d+) (\d+) ([a-z-]+) (-?\d+) (-?\d+) (\d+(?:\.\d+)?) (\d+(?:\.\d+)?) (\d+) (\d+) (-?\d+)((?: \d+)*)(?=\n|PF|$)")
args = [a for a in sys.argv[1:] if not a.startswith("--")]
run = Path(args[0])
bot = args[1] if len(args) > 1 else "p_hjt"
by_map = "--by-map" in sys.argv


def games():
    for d in sorted(run.iterdir()):
        if not d.is_dir():
            continue
        opp, mp, side = d.name.split("__")
        bundles = list(d.glob("*.repl26a"))
        if not bundles:
            continue
        txt = (d / "run.txt").read_text()
        gems = {}
        for m in re.finditer(r"^\s+([AB])\s+(\S+)\s+(\d+)\s", txt, re.M):
            gems[m.group(1)] = int(m.group(3))
        z = zipfile.ZipFile(bundles[0])
        out = z.read(f"team-{side.lower()}.stdout").decode("utf8", "replace").replace("\x00", "")
        rows = []
        # Champions share the team's stdout, so a record can be split by another's.
        for m in PF.finditer(out):
            p = m.groups()
            if int(p[1]) >= len(TYPES):
                continue
            rows.append((int(p[0]), TYPES[int(p[1])], p[2], int(p[3]), int(p[4]), float(p[5]), float(p[6]),
                         int(p[7]), int(p[8]), int(p[9]), tuple(int(x) for x in p[10].split())))
        other = "B" if side == "A" else "A"
        yield opp, mp, side, gems.get(side, 0), gems.get(other, 0), rows


labels = defaultdict(Counter)       # champ -> label -> rounds
early = defaultdict(Counter)        # champ -> label -> rounds, rounds < 400
episodes = defaultdict(list)        # label -> run lengths
per_map = {}
n = 0
wins = 0
rounds_total = []
gold_at_shop = []
for opp, mp, side, ours, theirs, rows in games():
    n += 1
    wins += ours > theirs
    last = max((r[0] for r in rows), default=0)
    rounds_total.append(last)
    by_champ = defaultdict(list)
    for r in rows:
        by_champ[r[1]].append(r)
    mp_lab = Counter()
    for champ, rs in by_champ.items():
        rs.sort()
        prev_label, prev_round, length = None, None, 0
        for r in rs:
            labels[champ][r[2]] += 1
            labels["TEAM"][r[2]] += 1
            mp_lab[r[2]] += 1
            if r[0] < 400:
                early[champ][r[2]] += 1
                early["TEAM"][r[2]] += 1
            if r[2] == "shop-recall":
                gold_at_shop.append(r[8])
            if r[2] == prev_label and prev_round == r[0] - 1:
                length += 1
            else:
                if prev_label is not None:
                    episodes[prev_label].append(length)
                length = 1
            prev_label, prev_round = r[2], r[0]
        if prev_label is not None:
            episodes[prev_label].append(length)
    per_map[(mp, side, opp)] = (ours, theirs, last, mp_lab)

print(f"{n} games, {wins} won, median {st.median(rounds_total):.0f} rounds\n")
order = [l for l, _ in labels["TEAM"].most_common()]


def table(src, title):
    print(title)
    print("  %-14s" % "" + "".join("%10s" % l[:9] for l in order))
    for champ in ["TEAM"] + sorted(c for c in src if c != "TEAM"):
        tot = sum(src[champ].values()) or 1
        print("  %-14s" % champ + "".join("%9.1f%%" % (100 * src[champ][l] / tot) for l in order))
    print()


table(labels, "SHARE OF CHAMPION-ROUNDS BY DECISION, whole game")
table(early, "SHARE OF CHAMPION-ROUNDS BY DECISION, rounds before 400")
print("EPISODES: count per game, median and mean length, rounds per game")
for l in order:
    e = episodes[l]
    if e:
        print("  %-15s %6.1f a game   median %4.0f   mean %6.1f   %7.1f rounds a game" % (
            l, len(e) / n, st.median(e), st.mean(e), sum(e) / n))
if gold_at_shop:
    print(f"\nshop recalls: {len(gold_at_shop) / n:.1f} a game, median gold {st.median(gold_at_shop):.0f}")
if by_map:
    print("\nPER MAP (our gems, theirs, rounds; farm share)")
    for k, (o, t, last, lab) in sorted(per_map.items()):
        tot = sum(lab.values()) or 1
        print(f"  {k[0]:<24}{k[1]} {k[2]:<8} {o:5d} {t:5d} {last:5d}  farm {100 * lab['farm'] / tot:4.1f}%"
              f"  travel {100 * lab['travel'] / tot:4.1f}%  spawn-heal {100 * lab['spawn-heal'] / tot:4.1f}%"
              f"  idle {100 * (lab['idle'] + lab['idle-bank']) / tot:4.1f}%")
