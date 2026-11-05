#!/usr/bin/env python3
"""Deaths after repeated recall attempts (action code 11 on 2+ of the last 8 turns: a recall restarted because
the previous one was interrupted), focus team only; plus how many recall attempts were repeats overall."""
import collections, json, sys
from pathlib import Path
US = "Milk and Potatoes"
bdir, sdir, adir = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
arm = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] != "-" else None
meta = json.loads((bdir / "meta.json").read_text())
games = 0; deaths = 0; futile = 0; attempts = 0; repeats = 0; byhp = collections.Counter()
for m in meta:
    if arm and m.get("arm") != arm: continue
    fs = sdir / f"{m['matchId']}.jsonl"; fa = adir / f"{m['matchId']}.jsonl"
    if not (fs.exists() and fa.exists()): continue
    focus = m.get("focus", US)
    me = next(t for t in m["teams"] if t["name"] == focus or t.get("teamId") == focus); ours = 0 if me["side"] == "a" else 1
    games += 1
    rows = [json.loads(l) for l in fs.read_text().splitlines()]; rows = [r for r in rows if r["c"]]
    team = {c[0]: c[1] for c in rows[0]["c"]}
    rec = collections.defaultdict(set)
    for l in fa.read_text().splitlines():
        r = json.loads(l)
        if r[8] and r[1] >= 0 and r[2] == 11 and team.get(r[1]) == ours: rec[r[1]].add(r[0])
    for k, rs in rec.items():
        attempts += len(rs); repeats += sum(1 for x in rs if x - 1 in rs)
    for i in range(1, len(rows)):
        for c in rows[i]["c"]:
            if c[1] != ours: continue
            prev = next((x for x in rows[i - 1]["c"] if x[0] == c[0]), None)
            if not prev or not prev[7] or c[7]: continue
            deaths += 1
            n = sum(1 for x in range(rows[i]["r"] - 8, rows[i]["r"]) if x in rec[c[0]])
            if n >= 2: futile += 1
print(f"games {games}: our deaths {deaths / games:.1f} a game, after 2+ recall attempts in the last 8 turns {futile / games:.2f} a game ({100 * futile / max(1, deaths):.0f}%)")
print(f"recall attempts {attempts / games:.1f} a game, of which repeats of the previous turn's {repeats / games:.1f}")
