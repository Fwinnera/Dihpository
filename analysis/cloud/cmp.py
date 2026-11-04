#!/usr/bin/env python3
"""Per-game means for bench tags (subject's view): wins, gems, deaths, kills, gold, monster damage, champion damage."""
import gzip, json, sys
from pathlib import Path
B = Path("/home/user/repo/ws/bench")
def load(p):
    return json.loads(gzip.open(p).read() if p.suffix == ".gz" else p.read_text())
for tag in sys.argv[1:]:
    rows = []
    for p in sorted((B / tag).glob("*__*__*.json*")):
        opp, mp, side = p.name.split(".")[0].split("__")
        d = load(p)
        me = "teamA" if side == "A" else "teamB"
        g = {t["team"]: int(t["submittedGems"]) for t in d["teams"]}
        mine = [c for c in d["champions"] if c["team"] == me]
        theirs = [c for c in d["champions"] if c["team"] != me]
        s = lambda cs, k: sum(float(c["metrics"][k]) for c in cs)
        rows.append(dict(win=g[me] > g["teamB" if me == "teamA" else "teamA"], gems=g[me], deaths=s(mine, "deaths"), kills=s(mine, "kills"),
                         odeaths=s(theirs, "deaths"), gold=s(mine, "earnedGold"), mon=s(mine, "monsterDamageDone"), cdmg=s(mine, "championDamageDone"),
                         ctaken=s(mine, "championDamageTaken"), rounds=d["match"]["roundsCompleted"]))
    n = len(rows)
    m = lambda k: sum(r[k] for r in rows) / n
    print(f"{tag:<40} n={n} win {sum(r['win'] for r in rows)}  gems {m('gems'):.0f}  deaths {m('deaths'):.1f}  their deaths {m('odeaths'):.1f}  "
          f"gold {m('gold'):.0f}  monster dmg {m('mon'):.0f}  champ dmg {m('cdmg'):.0f}/{m('ctaken'):.0f}  rounds {m('rounds'):.0f}")
