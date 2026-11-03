#!/usr/bin/env python3
"""Score the danger-response episodes of an exploration run and write a response policy.

    drfit.py RUNDIR [--emit HEADER] [--z 2.0]

RUNDIR holds drrun.sh games of a mkdr.py MODE 1 bot (folders <opp>__<map>__<A|B> with the
bundle and stats.json). Each DR line is an episode: round, champion type, response (0 the
ordinary rule, 1 fall back to a teammate, 2 fight), state cell. Its value is what followed for
that champion: gold earned and gems collected over the next 40 rounds (gems x 2) minus 150 for
a death within 20 rounds. Prints the responses' mean value overall, by trigger and by state
cell; with --emit, writes dr_policy.h choosing, per coarse cell, the response whose mean beats
the ordinary rule's by more than z standard errors (else the ordinary rule).
"""
import collections
import json
import math
import statistics as st
import sys
import zipfile
from pathlib import Path

run = Path(sys.argv[1])
emit = sys.argv[sys.argv.index("--emit") + 1] if "--emit" in sys.argv else None
z_cut = float(sys.argv[sys.argv.index("--z") + 1]) if "--z" in sys.argv else 2.0
NAMES = {0: "Ryth", 1: "Vesper Vale", 2: "Vendetta", 3: "Cassi", 4: "Issac", 5: "Stellar", 6: "Prism",
         7: "Marcella", 8: "Willow", 9: "Ren", 10: "Varg", 11: "Tavi", 12: "Heart of Ruin"}
H_GOLD, H_DEATH = 40, 20


def expand(runs, n):
    out = []
    for r in runs:
        out += [float(r["value"])] * int(r["duration"])
        if len(out) > n:
            break
    return (out + [out[-1] if out else 0.0] * n)[:n]


episodes = []
games = 0
for d in sorted(run.iterdir()):
    if not d.is_dir() or d.name.startswith("_"):
        continue
    side = d.name.rsplit("__", 1)[-1]
    stats, bundle = d / "stats.json", next(d.glob("*.repl26a"), None)
    if not stats.exists() or bundle is None:
        continue
    try:
        sm = json.loads(stats.read_text())
        text = zipfile.ZipFile(bundle).read(f"team-{side.lower()}.stdout").decode("utf8", "replace")
    except (KeyError, ValueError, zipfile.BadZipFile):
        continue
    games += 1
    team = "teamA" if side == "A" else "teamB"
    R = int(sm["match"]["roundsCompleted"]) + 2
    series = collections.defaultdict(dict)
    for x in sm["championTimelines"]:
        if x["owner"].get("team") == team and x["metric"] in ("earnedGold", "deaths", "collectedGems", "kills") and x["runs"]:
            series[x["owner"]["name"]][x["metric"]] = expand(x["runs"], R + H_GOLD + 2)
    for raw in text.splitlines():
        f = raw.replace("\x00", "").split()
        if len(f) != 9 or f[0] != "DR":
            continue
        try:
            r, typ, act, idx, coarse = int(f[1]), int(f[2]), int(f[3]), int(f[4]), int(f[5])
            flags, p = f[6], float(f[7])
        except ValueError:
            continue
        s = series.get(NAMES.get(typ, "?"))
        if not s or "earnedGold" not in s or "deaths" not in s:
            continue
        g, dd, c = s["earnedGold"], s["deaths"], s.get("collectedGems", [0.0] * (R + H_GOLD + 2))
        e = min(r + H_GOLD, len(g) - 1)
        died = dd[min(r + H_DEATH, len(dd) - 1)] - dd[r] > 0
        value = (g[e] - g[r]) + 2 * (c[e] - c[r]) - 150 * died
        episodes.append(dict(act=act, coarse=coarse, idx=idx, flags=flags, p=p, value=value, died=died,
                             gold=g[e] - g[r], typ=typ))

print(f"{games} games, {len(episodes)} episodes")


def summary(eps):
    out = {}
    for a in (0, 1, 2):
        v = [e["value"] for e in eps if e["act"] == a]
        if len(v) >= 2:
            out[a] = (len(v), st.mean(v), st.stdev(v) / math.sqrt(len(v)), st.mean(e["died"] for e in eps if e["act"] == a))
    return out


LABEL = {0: "ordinary", 1: "fall back", 2: "fight"}
for name, sel in (("all", lambda e: True), ("retreat rule", lambda e: e["flags"][0] == "1"),
                  ("disengage rule", lambda e: e["flags"][1] == "1"), ("table only", lambda e: e["flags"] == "00")):
    s = summary([e for e in episodes if sel(e)])
    print(f"  {name:<15}" + "  ".join(f"{LABEL[a]}: n {n} value {m:+6.1f} (se {se:4.1f}) died {dd:.0%}" for a, (n, m, se, dd) in s.items()))

for typ in sorted({e["typ"] for e in episodes}):
    s = summary([e for e in episodes if e["typ"] == typ])
    if 0 in s:
        print(f"  {NAMES.get(typ, typ):<15}" + "  ".join(
            f"{LABEL[a]}: n {n} value {m:+6.1f} (se {se:4.1f}) died {dd:.0%}" for a, (n, m, se, dd) in s.items()))

by = collections.defaultdict(list)
for e in episodes:
    by[e["coarse"]].append(e)
policy = [0] * 120
changed = []
for cell, eps in sorted(by.items()):
    s = summary(eps)
    if 0 not in s:
        continue
    best, gain = 0, 0.0
    for a in (1, 2):
        if a not in s or s[a][0] < 40 or s[0][0] < 40:
            continue
        diff = s[a][1] - s[0][1]
        se = math.sqrt(s[a][2] ** 2 + s[0][2] ** 2)
        if diff > z_cut * se and diff > gain:
            best, gain = a, diff
    policy[cell] = best
    if best:
        hb, rest = divmod(cell, 24)
        ob, nb = divmod(rest, 4)
        changed.append((cell, hb, ob, nb, LABEL[best], round(gain, 1), s[0][0], s[best][0]))
print(f"cells where a response beats the ordinary rule by more than {z_cut} se: {len(changed)}")
for c in changed:
    print("   cell", c[0], "health band", c[1], "odds band", c[2], "enemies", c[3], "->", c[4], "gain", c[5], "n", c[6], c[7])
if emit:
    Path(emit).write_text(
        "// Generated by analysis/rebuild/drfit.py: danger response per coarse cell\n"
        "// (health band x 6 + odds band) x 4 + enemies; 0 ordinary rule, 1 fall back, 2 fight.\n"
        f"// From {games} exploration games, {len(episodes)} episodes, z > {z_cut}.\n"
        "#pragma once\nnamespace dr {\ninline constexpr int policy[120] = {"
        + ", ".join(str(x) for x in policy) + "};\n}\n")
    print("wrote", emit)
