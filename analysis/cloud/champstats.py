#!/usr/bin/env python3
"""Per-champion averages from match summaries (deaths, kills, gems collected, monster and champion damage),
for the focus team and for its opponents, by champion name."""
import collections, json, sys
from pathlib import Path
US = "Milk and Potatoes"
bdir = Path(sys.argv[1]); pre = sys.argv[2] if len(sys.argv) > 2 else ""
meta = json.loads((bdir / "meta.json").read_text())
K = ["deaths", "kills", "collectedGems", "monsterDamageDone", "championDamageDone", "championDamageTaken", "earnedGold"]
S = {"focus": collections.defaultdict(lambda: collections.Counter()), "opp": collections.defaultdict(lambda: collections.Counter())}
for m in meta:
    if pre and not m.get("arm", "").startswith(pre): continue
    f = bdir / f"{m['matchId']}.json"
    if not f.exists(): continue
    d = json.loads(f.read_text())
    focus = m.get("focus", US)
    me = next(t for t in m["teams"] if t["name"] == focus or t.get("teamId") == focus)
    mine = "teamA" if me["side"] == "a" else "teamB"
    for c in d["champions"]:
        side = "focus" if c["team"] == mine else "opp"
        s = S[side][c["name"]]
        s["n"] += 1
        for k in K: s[k] += float(c["metrics"].get(k, 0))
for side in ("focus", "opp"):
    print(f"## {side}")
    print(f"{'champion':<16}{'games':>6}" + "".join(f"{k[:12]:>13}" for k in K))
    for name, s in sorted(S[side].items(), key=lambda kv: -kv[1]["n"]):
        if s["n"] < 20: continue
        print(f"{name:<16}{s['n']:>6}" + "".join(f"{s[k] / s['n']:>13.0f}" for k in K))
