#!/usr/bin/env python3
"""How often a clear was shared: other champions on the team dealt monster damage in the
three rounds up to the clear and none in the two after it. Also where clears happen:
own-half share by spawn distance. shared.py LIMIT FOLDER:TEAM ..."""
import json, statistics as st, sys
from collections import defaultdict, Counter
from pathlib import Path
B = Path("/Users/faeezaullyar/Claude/battlecode/ws/bench")
T = json.loads(Path(__file__).resolve().with_name("camps86.json").read_text())
limit = int(sys.argv[1])
def expand(runs, n):
    out = []
    for r in runs:
        out += [float(r["value"])] * int(r["duration"])
        if len(out) > n: break
    return (out + [out[-1] if out else 0.0] * n)[:n]
for arg in sys.argv[2:]:
    folder, team = arg.split(":", 1)
    helpers = Counter(); own = Counter(); n = 0
    for m in json.loads((B / folder / "matches.json").read_text()):
        me = next((t for t in m["teams"] if t["name"] == team), None)
        f = B / folder / "summaries" / f"{m['matchId']}.json"
        key = m["map"].replace("_", "-")
        if not me or not f.exists() or key not in T or not T[key].get("spawn_b") or not T[key].get("spawn_a"): continue
        side = "teamA" if me["side"] == "a" else "teamB"
        sa, sb = T[key]["spawn_a"], T[key]["spawn_b"]
        mine, theirs = (sa, sb) if side == "teamA" else (sb, sa)
        cm = (st.mean(p[0] for p in mine), st.mean(p[1] for p in mine)); ct = (st.mean(p[0] for p in theirs), st.mean(p[1] for p in theirs))
        d = json.loads(f.read_text()); n += 1
        ids = {c["id"] for c in d["roster"]["champions"] if c["team"] == side}
        md = {}
        for x in d["championTimelines"]:
            if x["owner"]["id"] in ids and x["metric"] == "monsterDamageDone":
                md[x["owner"]["id"]] = expand(x["runs"], limit + 4)
        for e in d["events"]:
            if e["kind"] != "campClear" or (e.get("owner") or {}).get("team") != side: continue
            for x in e["entries"]:
                r = x["timestamp"]["round"]
                if r >= limit or r < 4: continue
                k = 0
                for cid, s in md.items():
                    if cid == e["owner"]["id"]: continue
                    if s[r] > s[r - 3] and s[r + 2] == s[r]:
                        k += 1
                helpers[min(k, 3)] += 1
                p = (x["x"], x["y"])
                dm = max(abs(p[0] - cm[0]), abs(p[1] - cm[1])); dt = max(abs(p[0] - ct[0]), abs(p[1] - ct[1]))
                own["own half" if dm < dt - 2 else "enemy half" if dt < dm - 2 else "middle"] += 1
    tot = sum(helpers.values())
    print(f"{team}: {n} games, {tot / n:.1f} clears a game before round {limit}; helpers per clear "
          + ", ".join(f"{k}: {100 * helpers[k] / tot:.0f}%" for k in range(4))
          + "; where: " + ", ".join(f"{k} {100 * v / tot:.0f}%" for k, v in own.most_common()))
