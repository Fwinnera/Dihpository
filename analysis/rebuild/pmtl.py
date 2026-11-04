#!/usr/bin/env python3
"""One game's gem story from its match summary: collections, submissions, losses, deaths, clears.

    pmtl.py GAME.json[.gz] [--side A|B] [--full]

Without --full prints per-team totals and the first few hundred rounds condensed into
50-round buckets: gems collected, submitted and lost, deaths (by camps / champions), and
monolith clears. Positions of deaths near an altar are listed. Side is only a label.
"""
from __future__ import annotations

import gzip
import json
import sys
from collections import defaultdict
from pathlib import Path


def load(p: Path) -> dict:
    return json.loads(gzip.open(p).read() if p.suffix == ".gz" else p.read_text())


def main(argv) -> int:
    path = Path(argv[0])
    full = "--full" in argv
    d = load(path)
    ev = defaultdict(list)  # kind -> (round, team, champ, entry)
    for e in d["events"]:
        o = e["owner"]
        for x in e["entries"]:
            ev[e["kind"]].append((x["timestamp"]["round"], o.get("team"), o.get("name"), x))
    rounds = d["match"]["roundsCompleted"]
    out = {t["team"]: int(t["submittedGems"]) for t in d["teams"]}
    print(f"{path.name}: rounds {rounds}, outcome {d['match']['outcome']}, submitted {out}")
    names = {c["id"]: (c["name"], c["team"]) for c in d["roster"]["champions"]}
    for team in ("teamA", "teamB"):
        col = sum(int(x["value"]) for r, t, n, x in ev["gemCollection"] if t == team)
        sub = sum(int(x["value"]) for r, t, n, x in ev["gemSubmission"] if t == team)
        lost = sum(int(x["value"]) for r, t, n, x in ev["gemLoss"] if t == team)
        deaths = [(r, n, x["context"], x["x"], x["y"]) for r, t, n, x in ev["death"] if t == team]
        bycamp = sum(1 for z in deaths if z[2] == "camp")
        subs = sorted((r, n, int(x["value"])) for r, t, n, x in ev["gemSubmission"] if t == team)
        print(f"  {team}: collected {col}, submitted {sub}, lost {lost}; deaths {len(deaths)} "
              f"({bycamp} to camps); submissions {len(subs)}, first at r{subs[0][0] if subs else '-'}")
    buckets = defaultdict(lambda: defaultdict(int))
    step = 50 if not full else 25
    for kind, label in (("gemCollection", "col"), ("gemSubmission", "sub"), ("gemLoss", "lost")):
        for r, t, n, x in ev[kind]:
            buckets[(r // step) * step][f"{t[-1]}{label}"] += int(x["value"])
    for r, t, n, x in ev["death"]:
        buckets[(r // step) * step][f"{t[-1]}d{'c' if x['context'] == 'camp' else 'h'}"] += 1
    for r, t, n, x in ev["campClear"]:
        if x["target"].get("kind") == "campGroup":
            buckets[(r // step) * step][f"{t[-1]}clr"] += 1
    print("  round   A:col sub lost dc dh clr | B:col sub lost dc dh clr")
    for r in sorted(buckets):
        b = buckets[r]
        f = lambda s: f"{b[s + 'col']:>4} {b[s + 'sub']:>4} {b[s + 'lost']:>4} {b[s + 'dc']:>2} {b[s + 'dh']:>2} {b[s + 'clr']:>3}"
        print(f"  {r:>5}   {f('A')} | {f('B')}")
    if full:
        for kind in ("gemSubmission", "death", "kill"):
            print(f"  -- {kind}")
            for r, t, n, x in sorted(ev[kind], key=lambda z: z[0]):
                tgt = x.get("target")
                tn = tgt.get("name") if isinstance(tgt, dict) else tgt
                print(f"    r{r:>4} {t} {n:<12} v={x['value']:>4} at {x['x']},{x['y']} ctx={x['context']} tgt={tn}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
