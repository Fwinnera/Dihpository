#!/usr/bin/env python3
"""meta.json for a bench tag folder (OPP__MAP__A|B.repl26a), so diag/skirm/groups tools can read it."""
import gzip, json, sys
from pathlib import Path
d = Path(sys.argv[1]); meta = []
for p in sorted(d.glob("*__*__*.repl26a")):
    opp, mp, side = p.stem.split("__"); s = side.lower()
    j = d / f"{p.stem}.json.gz"
    jj = d / f"{p.stem}.json"
    if not jj.exists() and j.exists():
        jj.write_bytes(gzip.open(j).read())
    if not jj.exists(): continue
    out = json.loads(jj.read_text())["match"]["outcome"]
    ours = "teamA" if s == "a" else "teamB"
    meta.append(dict(matchId=p.stem, map=mp, teams=[dict(name="Milk and Potatoes", side=s, result="win" if out == ours else "loss"),
                                                    dict(name=opp, side="b" if s == "a" else "a", result="loss" if out == ours else "win")]))
(d / "meta.json").write_text(json.dumps(meta)); print(len(meta), "games")
