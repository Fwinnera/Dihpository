#!/usr/bin/env python3
"""Gem flow in ranked games from summaries: collected vs submitted for us and for opponents, deaths, and the
share of collected gems that never reached an altar; split by result."""
import collections, json, sys
from pathlib import Path
meta = json.loads(Path(sys.argv[1]).read_text()); sdir = Path(sys.argv[2])
acc = {"win": collections.Counter(), "loss": collections.Counter()}
for m in meta:
    f = sdir / f"{m['matchId']}.json"
    if not f.exists(): continue
    d = json.loads(f.read_text())
    me = next(t for t in m["teams"] if t["name"] == "Milk and Potatoes"); mine = "teamA" if me["side"] == "a" else "teamB"
    g = {t["team"]: int(t["submittedGems"]) for t in d["teams"]}
    s = lambda ours, k: sum(float(c["metrics"].get(k, 0)) for c in d["champions"] if (c["team"] == mine) == ours)
    a = acc["win" if me["result"] == "win" else "loss"]
    a["n"] += 1
    a["our_sub"] += g[mine]; a["their_sub"] += g["teamB" if mine == "teamA" else "teamA"]
    a["our_col"] += s(True, "collectedGems"); a["their_col"] += s(False, "collectedGems")
    a["our_deaths"] += s(True, "deaths"); a["their_deaths"] += s(False, "deaths")
    a["our_kills"] += s(True, "kills"); a["their_kills"] += s(False, "kills")
    a["rounds"] += d["match"]["roundsCompleted"]
    if not a.get("keys"): pass
print(f"{'':<6}{'games':>6}{'our sub':>9}{'our col':>9}{'kept':>6}{'their sub':>10}{'their col':>10}{'kept':>6}{'our d':>7}{'their d':>8}{'rounds':>8}")
for k in ("win", "loss"):
    a = acc[k]; n = max(1, a["n"])
    print(f"{k:<6}{a['n']:>6}{a['our_sub'] / n:>9.0f}{a['our_col'] / n:>9.0f}{a['our_sub'] / max(1, a['our_col']):>6.2f}"
          f"{a['their_sub'] / n:>10.0f}{a['their_col'] / n:>10.0f}{a['their_sub'] / max(1, a['their_col']):>6.2f}"
          f"{a['our_deaths'] / n:>7.1f}{a['their_deaths'] / n:>8.1f}{a['rounds'] / n:>8.0f}")
