#!/usr/bin/env python3
"""pair.py BASE CAND: paired comparison of two lab arms (three sets each: X, X_s2, X_s3) on wins, gem margin,
deaths and economy, from summaries fetched into /home/user/data/lab_<arm> (fetchlab.py runs if missing)."""
import json, math, subprocess, sys
from pathlib import Path
US = "246f9cef-b416-4864-964e-ebcafb97f7ad"
def load(arm):
    d = Path(f"/home/user/data/lab_{arm}")
    if not (d / "meta.json").exists() or len(list(d.glob("*.json"))) < 150:
        subprocess.run(["python3", "-I", "/home/user/tools/fetchlab.py", str(d), arm, arm + "_s2", arm + "_s3"], capture_output=True)
    out = {}
    for m in json.loads((d / "meta.json").read_text()):
        f = d / f"{m['matchId']}.json"
        if not f.exists(): continue
        s = json.loads(f.read_text())
        me = next(t for t in m["teams"] if t["teamId"] == US)
        side = "teamA" if me["side"] == "a" else "teamB"; other = "teamB" if side == "teamA" else "teamA"
        g = {t["team"]: int(t["submittedGems"]) for t in s["teams"]}
        row = dict(win=me.get("result") == "win", margin=g[side] - g[other], rounds=int(s["match"]["roundsCompleted"]),
                   bodies=sum(1 for c in s["champions"] if c["team"] == side))
        for key in ("deaths", "kills", "collectedGems", "earnedGold", "monsterDamageDone", "championDamageDone", "championDamageTaken"):
            row[key] = sum(float(c["metrics"][key]) for c in s["champions"] if c["team"] == side)
            row["opp_" + key] = sum(float(c["metrics"][key]) for c in s["champions"] if c["team"] == other)
        out[(m["arm"].replace(arm, "", 1), m["oppName"], m["map"])] = row
    return out
def main():
    base, cand = sys.argv[1], sys.argv[2]
    A, B = load(base), load(cand)
    keys = sorted(set(A) & set(B))
    n = len(keys)
    print(f"{base} vs {cand}: {n} paired games; wins {sum(A[k]['win'] for k in keys)} -> {sum(B[k]['win'] for k in keys)}"
          f" (flipped to win {sum(1 for k in keys if B[k]['win'] and not A[k]['win'])}, to loss {sum(1 for k in keys if A[k]['win'] and not B[k]['win'])})")
    def stat(key):
        d = [B[k][key] - A[k][key] for k in keys]
        mean = sum(d) / n; se = math.sqrt(sum((x - mean) ** 2 for x in d) / (n - 1) / n)
        return sum(A[k][key] for k in keys) / n, sum(B[k][key] for k in keys) / n, mean, se
    for key in ("margin", "deaths", "opp_deaths", "collectedGems", "opp_collectedGems", "earnedGold", "opp_earnedGold", "monsterDamageDone", "championDamageDone", "championDamageTaken", "rounds"):
        a, b, m, se = stat(key)
        print(f"  {key:<22}{a:>10.1f} -> {b:>10.1f}   diff {m:>+9.1f} (se {se:.1f}, {m/se if se else 0:+.1f} se)")
    for nb in (3, 4, 5, 6):
        ks = [k for k in keys if A[k]["bodies"] == nb]
        if ks: print(f"  bodies {nb}: {len(ks)} games, wins {sum(A[k]['win'] for k in ks)} -> {sum(B[k]['win'] for k in ks)}")
main()
