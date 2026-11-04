#!/usr/bin/env python3
"""Team strength over time from decoded states: mean max health of living champions and team gold+gems carried,
at fixed rounds; plus summary totals (earned gold, kills, deaths)."""
import collections, json, sys
from pathlib import Path
US = "Milk and Potatoes"
meta = json.loads(Path(sys.argv[1], "meta.json").read_text())
marks = [100, 200, 300, 500, 800, 1100, 1400]
acc = collections.defaultdict(list)
eg = collections.defaultdict(list)
for m in meta:
    f = Path(sys.argv[2], f"{m['matchId']}.jsonl")
    if not f.exists(): continue
    focus = m.get("focus", US); me = next(t for t in m["teams"] if t["name"] == focus or t.get("teamId") == focus); ours = 0 if me["side"] == "a" else 1
    st = {}
    for l in f.read_text().splitlines():
        d = json.loads(l); st[d["r"]] = d
    for r in marks:
        if r not in st or not st[r]["c"]: continue
        for team, lab in ((ours, "us"), (1 - ours, "them")):
            cs = [c for c in st[r]["c"] if c[1] == team]
            if not cs: continue
            acc[(lab, r, "maxhp")].append(sum(c[6] for c in cs) / len(cs))
    s = json.loads(Path(sys.argv[1], f"{m['matchId']}.json").read_text())
    side = "teamA" if ours == 0 else "teamB"
    for team, lab in ((side, "us"), ("teamB" if side == "teamA" else "teamA", "them")):
        cs = [c for c in s["champions"] if c["team"] == team]
        for k in ("earnedGold", "spentGold", "kills", "deaths", "collectedGems", "submittedGems", "monsterDamageDone", "championDamageDone", "championDamageTaken", "healingReceived", "shieldingDone"):
            eg[(lab, k)].append(sum(float(c["metrics"].get(k, 0)) for c in cs))
print("mean max health per champion (all champions, alive or not):")
print("  round " + "".join(f"{r:>7}" for r in marks))
for lab in ("us", "them"):
    print(f"  {lab:<5} " + "".join(f"{sum(acc[(lab, r, 'maxhp')]) / max(1, len(acc[(lab, r, 'maxhp')])):>7.0f}" for r in marks))
print("\nper game totals (mean):")
for k in ("earnedGold", "spentGold", "kills", "deaths", "collectedGems", "submittedGems", "monsterDamageDone", "championDamageDone", "championDamageTaken", "healingReceived", "shieldingDone"):
    a = eg[("us", k)]; b = eg[("them", k)]
    print(f"  {k:<22}{sum(a) / len(a):>10.0f}{sum(b) / len(b):>10.0f}")
