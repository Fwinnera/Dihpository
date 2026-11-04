#!/usr/bin/env python3
"""How a team farms (decoded states with camp damage, read2.mjs): share of living rounds farming (a camp in reach
lost health), co-farming (teammates on the same camp), fighting (enemy within 4), and spacing in each state."""
import collections, json, statistics, sys
from pathlib import Path
US = "Milk and Potatoes"
RANGED = {1, 3, 5, 6, 8, 11}
def cheb(a, b): return max(abs(a[0]-b[0]), abs(a[1]-b[1]))
bdir, sdir = Path(sys.argv[1]), Path(sys.argv[2])
arms = set(sys.argv[3].split(",")) if len(sys.argv) > 3 and sys.argv[3] else None
meta = json.loads((bdir / "meta.json").read_text())
acc = {w: collections.Counter() for w in ("focus", "opp")}
mates = {w: collections.defaultdict(list) for w in ("focus", "opp")}
mdmg = collections.Counter(); games = 0
for m in meta:
    if arms and m.get("arm") not in arms: continue
    f = sdir / f"{m['matchId']}.jsonl"
    if not f.exists(): continue
    focus = m.get("focus", US)
    me = next(t for t in m["teams"] if t["name"] == focus or t.get("teamId") == focus); ours = 0 if me["side"] == "a" else 1
    s = json.loads((bdir / f"{m['matchId']}.json").read_text()); side = "teamA" if ours == 0 else "teamB"
    for c in s["champions"]: mdmg["focus" if c["team"] == side else "opp"] += float(c["metrics"]["monsterDamageDone"])
    games += 1
    for line in f.read_text().splitlines():
        st = json.loads(line)
        if not st["c"]: continue
        dmg = st.get("d", [])
        living = [c for c in st["c"] if c[7] and c[3] >= 0]
        for c in living:
            who = "focus" if c[1] == ours else "opp"
            reach = (3 if c[2] in RANGED else 1) + 1
            pos = (c[3], c[4])
            on = [d for d in dmg if cheb(pos, (d[1], d[2])) <= reach]
            team = [o for o in living if o[1] == c[1] and o[0] != c[0]]
            near = min((cheb(pos, (o[3], o[4])) for o in team), default=99)
            fighting = any(o[1] != c[1] and cheb(pos, (o[3], o[4])) <= 4 for o in living)
            a = acc[who]; a["alive"] += 1
            if on:
                a["farm"] += 1
                d0 = on[0]
                co = sum(1 for o in team if cheb((o[3], o[4]), (d0[1], d0[2])) <= (3 if o[2] in RANGED else 1) + 1)
                a["farm_co" if co else "farm_solo"] += 1
                mates[who]["farm"].append(near)
            elif fighting:
                a["fight"] += 1; mates[who]["fight"].append(near)
            else:
                a["other"] += 1; mates[who]["other"].append(near)
for who in ("focus", "opp"):
    a = acc[who]; n = max(1, a["alive"])
    print(f"{who:<6} farming {100 * a['farm'] / n:4.1f}% (with a teammate on the camp {100 * a['farm_co'] / max(1, a['farm']):4.1f}%), "
          f"fighting {100 * a['fight'] / n:4.1f}%, other {100 * a['other'] / n:4.1f}% | nearest teammate median: farming "
          f"{statistics.median(mates[who]['farm']) if mates[who]['farm'] else 'n/a'}, other {statistics.median(mates[who]['other']) if mates[who]['other'] else 'n/a'} | "
          f"monster damage per farming round {mdmg[who] / max(1, a['farm']):.0f} ({games} games)")
