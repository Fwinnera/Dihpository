"""Pool every matched pair of gold-weight games, selection and held-out alike.

A pair counts only when the two arms actually diverged: the engine is
deterministic, so a bit-identical game carries no information about the change
and inflates the sample without moving the estimate. The bootstrap is over
games, which is the unit that varies.
"""
import json, glob, random, sys
from pathlib import Path
from collections import defaultdict

ROOT = Path("/Users/faeezaullyar/Claude/battlecode/ws/bench/ladder")
US = "Milk and Potatoes"

def arm(tag):
    """(opponent, map, side) -> (our gems, their gems, deaths, rounds) per game."""
    out = {}
    for gf in sorted(ROOT.glob(f"{tag}/group_*.json")):
        g = json.loads(gf.read_text())
        for m in g.get("matches", []):
            us = next((t for t in m["teams"] if t["name"] == US), None)
            them = next((t for t in m["teams"] if t["name"] != US), None)
            if not us or not them:
                continue
            sm = ROOT / tag / "summaries" / f"{m[chr(39)+chr(39)] if False else m['matchId'][:8]}.json"
            if not sm.exists():
                continue
            d = json.loads(sm.read_text())
            side = "teamA" if us["side"] == "a" else "teamB"
            other = "teamB" if side == "teamA" else "teamA"
            gems = {t["team"]: int(t["submittedGems"]) for t in d["teams"]}
            ch = [c for c in d["champions"] if c["team"] == side]
            out[(them["name"], m["map"], us["side"])] = (
                gems[side], gems[other],
                sum(int(c["metrics"]["deaths"]) for c in ch),
                d["match"]["roundsCompleted"])
    return out

PAIRS = [("gold_base", "gold_030", "selection"),
         ("gw_base", "gw_030", "selection"),
         ("ho_base", "ho_gold", "HELD OUT")]

rows = []
for a, b, kind in PAIRS:
    A, B = arm(a), arm(b)
    for k in sorted(set(A) & set(B)):
        if A[k] == B[k]:
            continue                      # bit-identical: no information
        rows.append((kind, k, A[k], B[k]))

print(f"{len(rows)} matched games where the arms actually diverged\n")
by = defaultdict(list)
for kind, k, x, y in rows:
    by[kind].append((k, x, y))
    by["POOLED"].append((k, x, y))

print("%-11s%7s%10s%10s%9s%9s%8s" % ("set", "games", "base", "gold.3", "delta", "deaths", "record"))
for kind in ("selection", "HELD OUT", "POOLED"):
    r = by[kind]
    if not r:
        continue
    n = len(r)
    ga = sum(x[0] for _, x, _ in r) / n
    gb = sum(y[0] for _, _, y in r) / n
    da = sum(x[2] for _, x, _ in r) / n
    db = sum(y[2] for _, _, y in r) / n
    wb = sum(y[0] > y[1] for _, _, y in r)
    print("%-11s%7d%10.0f%10.0f%+9.0f%+9.1f%8s"
          % (kind, n, ga, gb, gb - ga, db - da, f"{wb}-{n-wb}"))

r = by["POOLED"]
d = [y[0] - x[0] for _, x, y in r]
random.seed(7)
boot = sorted(sum(random.choice(d) for _ in d) / len(d) for _ in range(20000))
lo, hi = boot[int(.025 * len(boot))], boot[int(.975 * len(boot))]
print(f"\npooled gem delta {sum(d)/len(d):+.0f} per game, "
      f"95% bootstrap interval {lo:+.0f} to {hi:+.0f}")
print(f"  games better {sum(x>0 for x in d)}, worse {sum(x<0 for x in d)}, "
      f"tied {sum(x==0 for x in d)}")
print(f"  interval {'EXCLUDES' if lo > 0 or hi < 0 else 'INCLUDES'} zero")

print("\nper opponent, pooled over maps and sides:")
op = defaultdict(lambda: [0, 0, 0])
for _, k, x, y in rows:
    e = op[k[0][:26]]
    e[0] += 1; e[1] += x[0]; e[2] += y[0]
for name, (n, a, b) in sorted(op.items(), key=lambda kv: kv[1][2] - kv[1][1]):
    print("  %-28s%3d games  %5.0f -> %5.0f  %+6.0f" % (name, n, a/n, b/n, (b-a)/n))

print("\nthe five largest single-game swings:")
for kind, k, x, y in sorted(rows, key=lambda r: -abs(r[3][0] - r[2][0]))[:5]:
    print("  %-9s %-26s %-20s %s  %4d -> %4d  %+5d"
          % (kind, k[0][:26], k[1], k[2], x[0], y[0], y[0] - x[0]))
