"""What kills us on the maps where we score nothing, against the maps where we win.

Final gem totals say we fail; they do not say why. The event log names the killer's
context for each death, so a bot that walks into an uncleanable camp fifty times is
distinguishable from one that loses fights to champions.
"""
import json
from pathlib import Path
from collections import Counter, defaultdict

ROOT = Path("/Users/faeezaullyar/Claude/battlecode/ws/bench/ladder")
US = "Milk and Potatoes"
BAD = {("01elk_arena", "a"), ("00swirl", "b"), ("00stampede", "a"), ("00eight", "b")}
GOOD = {("00quadrants", "b"), ("01big_world", "b"), ("00collision", "b"), ("00corners", "a")}

bucket = defaultdict(lambda: {"n": 0, "ctx": Counter(), "rounds": [], "who": Counter(),
                              "clears": 0, "picks": 0, "subs": 0, "lost": 0.0,
                              "got": 0.0, "fuel": 0, "faults": 0})

for tag in sorted(d.name for d in ROOT.iterdir() if d.is_dir() and (d / "summaries").exists()):
    for gf in sorted(ROOT.glob(tag + "/group_*.json")):
        g = json.loads(gf.read_text())
        for m in g.get("matches", []):
            us = next((t for t in m["teams"] if t["name"] == US), None)
            sm = ROOT / tag / "summaries" / (m["matchId"][:8] + ".json")
            if not us or not sm.exists():
                continue
            key = (m["map"], us["side"])
            lab = "FAILING" if key in BAD else "WINNING" if key in GOOD else None
            if lab is None:
                continue
            d = json.loads(sm.read_text())
            side = "teamA" if us["side"] == "a" else "teamB"
            b = bucket[lab]
            b["n"] += 1
            for e in d.get("events", []):
                if (e.get("owner") or {}).get("team") != side:
                    continue
                k, ents = e.get("kind"), e.get("entries", [])
                if k == "death":
                    for x in ents:
                        b["ctx"][x.get("context", "?")] += 1
                        b["rounds"].append(x.get("timestamp", {}).get("round", 0))
                        b["who"][(e.get("owner") or {}).get("character", "?")] += 1
                elif k == "campClear":
                    b["clears"] += len(ents)
                elif k == "gemCollection":
                    b["picks"] += len(ents)
                    b["got"] += sum(float(x.get("value", 0) or 0) for x in ents)
                elif k == "gemSubmission":
                    b["subs"] += len(ents)
                elif k == "gemLoss":
                    b["lost"] += sum(float(x.get("value", 0) or 0) for x in ents)
                elif k in ("fuelExhausted", "botFault"):
                    b["faults"] += len(ents)

for lab in ("FAILING", "WINNING"):
    b = bucket[lab]
    n = max(1, b["n"])
    tot = sum(b["ctx"].values())
    print(f"=== {lab}: {b['n']} games ===")
    print(f"  deaths per game            {tot/n:7.1f}")
    for k, v in b["ctx"].most_common(6):
        print(f"    by {k:<24}{v/n:7.1f}   ({100*v/max(1,tot):.0f}%)")
    if b["rounds"]:
        r = sorted(b["rounds"])
        q = lambda p: r[int(len(r) * p)]
        print(f"  death rounds               {q(.1)} / {q(.5)} / {q(.9)}  (10th/median/90th)")
    print(f"  camp clears per game       {b['clears']/n:7.1f}")
    print(f"  gem pickups per game       {b['picks']/n:7.1f}")
    print(f"  deposits per game          {b['subs']/n:7.1f}")
    print(f"  collected / lost to death  {b['got']/n:7.0f} / {b['lost']/n:.0f}")
    print(f"  fuel exhaustion + faults   {b['faults']/n:7.2f}")
    print(f"  deaths per camp clear      {tot/max(1,b['clears']):7.2f}\n")
