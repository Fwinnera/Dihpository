#!/usr/bin/env python3
"""Paired comparison of lab arms from downloaded summaries (fetchlab.py folders, meta records with `arm`).

    pairarms.py DIR BASE_ARMS CAND_ARMS      e.g. pairarms.py /home/user/plat/lab pm_best,pm_best_s2,pm_best_s3 as2,as2_s2,as2_s3

Games are paired by (opponent team id, map). For each side: wins, gem margin, our deaths and their deaths
(total and in our half / middle / their half, from death event positions), our kills.
"""
import collections
import json
import math
import sys
from pathlib import Path

US = "Milk and Potatoes"
MAPINFO = {k.replace("-", "_"): v for k, v in json.loads(Path("/home/user/runs/mapinfo/mapinfo.json").read_text()).items()}


def cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def game_stats(d, m):
    me = next(t for t in m["teams"] if t["name"] == US)
    opp = next(t for t in m["teams"] if t["name"] != US)
    side = "teamA" if me["side"] == "a" else "teamB"
    s = json.loads((d / f"{m['matchId']}.json").read_text())
    ours = sum(float(c["metrics"]["submittedGems"]) for c in s["champions"] if c["team"] == side)
    theirs = sum(float(c["metrics"]["submittedGems"]) for c in s["champions"] if c["team"] != side)
    mi = MAPINFO.get(m["map"].replace("-", "_"))
    own, enemy = (mi["spawn_a"], mi["spawn_b"]) if me["side"] == "a" else (mi["spawn_b"], mi["spawn_a"])
    team_of = {c["id"]: c["team"] for c in s["roster"]["champions"]}
    z = collections.Counter()
    for ev in s["events"]:
        if ev["kind"] != "death":
            continue
        who = "us" if team_of.get(ev["owner"]["id"]) == side else "them"
        for e in ev["entries"]:
            p = (e["x"], e["y"])
            do = min(cheb(p, q) for q in own)
            de = min(cheb(p, q) for q in enemy)
            depth = do / max(1, do + de)
            zone = "home" if depth < 0.45 else "mid" if depth < 0.55 else "away"
            z[(who, zone)] += 1
            z[(who, "all")] += 1
    return dict(key=(opp.get("teamId", opp["name"]), m["map"], me["side"]), win=me.get("result") == "win", margin=ours - theirs,
                **{f"{w}_{k}": z[(w, k)] for w in ("us", "them") for k in ("all", "home", "mid", "away")})


def load(d, arms):
    meta = json.loads((d / "meta.json").read_text())
    out = {}
    for m in meta:
        if m.get("arm") in arms and (d / f"{m['matchId']}.json").exists():
            g = game_stats(d, m)
            out[g["key"]] = g
    return out


def main(d, base, cand):
    d = Path(d)
    a, b = load(d, set(base.split(","))), load(d, set(cand.split(",")))
    keys = sorted(set(a) & set(b))
    print(f"{len(keys)} paired games ({len(a)} base, {len(b)} candidate)")
    fields = ["win", "margin", "us_all", "us_home", "us_mid", "us_away", "them_all", "them_home", "them_mid", "them_away"]
    print(f"{'':<12}{'base':>9}{'cand':>9}{'diff':>9}{'se':>8}")
    for f in fields:
        xa = [float(a[k][f]) for k in keys]
        xb = [float(b[k][f]) for k in keys]
        diffs = [y - x for x, y in zip(xa, xb)]
        n = len(diffs)
        mean = sum(diffs) / n
        se = math.sqrt(sum((v - mean) ** 2 for v in diffs) / max(1, n - 1) / n)
        if f == "win":
            print(f"{'wins':<12}{sum(xa):>9.0f}{sum(xb):>9.0f}{sum(xb) - sum(xa):>+9.0f}{se * n:>8.1f}")
        else:
            print(f"{f:<12}{sum(xa) / n:>9.2f}{sum(xb) / n:>9.2f}{mean:>+9.2f}{se:>8.2f}")
    same = sum(1 for k in keys if a[k]["win"] == b[k]["win"] and a[k]["margin"] == b[k]["margin"])
    print(f"identical results (same winner and margin): {same} of {len(keys)}")


if __name__ == "__main__":
    main(*sys.argv[1:4])
