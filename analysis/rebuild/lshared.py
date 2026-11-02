#!/usr/bin/env python3
"""Shared clears and farming profile for our side of local bench games.

    lshared.py LIMIT TAG ...      (TAG = folder under ws/bench, files <opp>__<map>__<A|B>.json)
"""
import json, statistics as st, sys
from collections import Counter
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
for tag in sys.argv[2:]:
    helpers = Counter(); own = Counter(); n = 0; md100 = []; gold100 = []; clears = 0; hit = []
    for f in sorted((B / tag).glob("*__*__*.json")):
        opp, mp, s = f.stem.split("__")
        side = "teamA" if s == "A" else "teamB"
        d = json.loads(f.read_text()); n += 1
        ids = {c["id"] for c in d["roster"]["champions"] if c["team"] == side}
        md = {}; tot_md = 0; tot_gold = 0
        for x in d["championTimelines"]:
            if x["owner"]["id"] in ids and x["metric"] == "monsterDamageDone":
                md[x["owner"]["id"]] = s_ = expand(x["runs"], max(limit, 100) + 4)
                tot_md += s_[100]
                hit.append(sum(1 for r in range(1, 101) if s_[r] > s_[r - 1]) / 100)
            if x["owner"]["id"] in ids and x["metric"] == "earnedGold":
                tot_gold += expand(x["runs"], 101)[100]
        md100.append(tot_md); gold100.append(tot_gold)
        info = T.get(mp)
        for e in d["events"]:
            if e["kind"] != "campClear" or (e.get("owner") or {}).get("team") != side: continue
            for x in e["entries"]:
                r = x["timestamp"]["round"]
                if r >= limit or r < 4: continue
                clears += 1
                k = sum(1 for cid, s_ in md.items() if cid != e["owner"]["id"] and s_[r] > s_[r - 3] and s_[r + 2] == s_[r])
                helpers[min(k, 3)] += 1
                if info and info.get("spawn_a") and info.get("spawn_b"):
                    mine, theirs = (info["spawn_a"], info["spawn_b"]) if side == "teamA" else (info["spawn_b"], info["spawn_a"])
                    cm = (st.mean(p[0] for p in mine), st.mean(p[1] for p in mine)); ct = (st.mean(p[0] for p in theirs), st.mean(p[1] for p in theirs))
                    p = (x["x"], x["y"])
                    dm = max(abs(p[0] - cm[0]), abs(p[1] - cm[1])); dt = max(abs(p[0] - ct[0]), abs(p[1] - ct[1]))
                    own["own" if dm < dt - 2 else "enemy" if dt < dm - 2 else "middle"] += 1
    tot = sum(helpers.values()) or 1; to = sum(own.values()) or 1
    print(f"{tag}: {n} games; by round 100 camp damage {st.median(md100):.0f}, gold {st.median(gold100):.0f}, "
          f"hit share {100 * st.mean(hit):.1f}%; clears before {limit} {clears / n:.1f}; helpers "
          + " ".join(f"{k}:{100 * helpers[k] / tot:.0f}%" for k in range(4)) + "; "
          + " ".join(f"{k} {100 * v / to:.0f}%" for k, v in own.most_common()))
