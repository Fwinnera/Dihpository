#!/usr/bin/env python3
"""Party-map mechanism counts per game, ours against theirs, from pmscreen tags.

    pmsum.py TAG [--cand C] [--map M] [--opp O]

One line a game: result, gems submitted, collected, lost to deaths, deaths (camp / champion),
first submission round, number of submissions, monolith (big-group) rewards collected, and
gems banked by rounds 300 / 600 / 1000. Totals per map at the end.
"""
from __future__ import annotations

import argparse
import gzip
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / "ws/bench"
PARTY = ["01boss-battle", "00anvil", "02guardians", "03showdown", "00stampede", "00contest", "03homonoliths"]
# Group ids (camp_groups() order) of each map's big groups: monoliths, and 00stampede's elk herd.
BIG = {"01boss-battle": {16}, "00anvil": {10}, "02guardians": {20, 21}, "03showdown": {22, 23},
       "00contest": {0, 1}, "03homonoliths": {2, 3}, "00stampede": {10}}


def load(p: Path) -> dict:
    return json.loads(gzip.open(p).read() if p.suffix == ".gz" else p.read_text())


def facts(d: dict, team: str, m: str) -> dict:
    f = defaultdict(int)
    subs = []
    big = BIG.get(m, set())
    for e in d["events"]:
        if e["owner"].get("team") != team:
            continue
        k = e["kind"]
        for x in e["entries"]:
            r = x["timestamp"]["round"]
            v = int(x["value"]) if str(x["value"]).lstrip("-").isdigit() else 0
            if k == "gemCollection":
                f["col"] += v
                tgt = x.get("target")
                if isinstance(tgt, dict) and tgt.get("kind") == "campGroup" and tgt.get("id") in big:
                    f["big"] += 1
                    f["big_gems"] += v
            elif k == "gemSubmission":
                f["sub"] += v
                subs.append((r, v))
            elif k == "gemLoss":
                f["lost"] += v
            elif k == "death":
                f["dc" if x["context"] == "camp" else "dh"] += 1
            elif k == "kill":
                f["kills"] += 1
    subs.sort()
    f["first"] = subs[0][0] if subs else 9999
    f["nsub"] = len(subs)
    for cut in (300, 600, 1000):
        f[f"by{cut}"] = sum(v for r, v in subs if r < cut)
    return f


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("tags", nargs="+")
    ap.add_argument("--cand")
    ap.add_argument("--map")
    ap.add_argument("--opp")
    a = ap.parse_args()
    per_map = defaultdict(lambda: defaultdict(float))
    n_map = defaultdict(int)
    print(f"{'game':<44} res  sub/col/lost  dc dh  1st nsub big | them: sub/col/lost dc dh 1st big | by300/600/1000 us-them")
    for tag in a.tags:
        for p in sorted((BENCH / tag).glob("*__*__*__*.json*")):
            c, o, m, side = p.name.split(".json")[0].split("__")
            if (a.cand and c != a.cand) or (a.map and m != a.map) or (a.opp and o != a.opp):
                continue
            d = load(p)
            me, them = ("teamA", "teamB") if side == "A" else ("teamB", "teamA")
            u, t = facts(d, me, m), facts(d, them, m)
            win = d["match"]["outcome"] == me
            name = f"{c[:10]}/{o.replace('pm_o_', '')[:6]}/{m[:12]}/{side}"
            print(f"{name:<44} {'W' if win else 'l'}  {u['sub']:>4}/{u['col']:>4}/{u['lost']:>4} {u['dc']:>3}{u['dh']:>3} "
                  f"{u['first']:>4} {u['nsub']:>3} {u['big']:>2} | {t['sub']:>4}/{t['col']:>4}/{t['lost']:>4} {t['dc']:>2}{t['dh']:>3} "
                  f"{t['first']:>4} {t['big']:>2} | {u['by300']}/{u['by600']}/{u['by1000']} - {t['by300']}/{t['by600']}/{t['by1000']}")
            key = (c, m)
            n_map[key] += 1
            pm = per_map[key]
            pm["win"] += win
            for k in ("sub", "col", "lost", "dc", "dh", "big", "kills"):
                pm[k] += u[k]
                pm["t" + k] += t[k]
    print()
    print(f"{'cand/map':<34} n  wins  sub   col  lost  dc   dh  big kills | them sub col lost dc dh big")
    for (c, m), n in sorted(n_map.items(), key=lambda z: (z[0][0], PARTY.index(z[0][1]) if z[0][1] in PARTY else 99)):
        pm = per_map[(c, m)]
        g = lambda k: pm[k] / n
        print(f"{c[:16] + '/' + m:<34} {n:<2} {int(pm['win']):>3}  {g('sub'):>4.0f} {g('col'):>5.0f} {g('lost'):>5.0f} {g('dc'):>4.1f} {g('dh'):>4.1f} {g('big'):>4.1f} {g('kills'):>4.1f} | "
              f"{g('tsub'):>4.0f} {g('tcol'):>4.0f} {g('tlost'):>4.0f} {g('tdc'):>4.1f} {g('tdh'):>4.1f} {g('tbig'):>3.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
