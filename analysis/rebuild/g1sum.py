"""Summarise the held-out screen: wins per candidate per opponent, faults and engine codes."""
import json, sys
from pathlib import Path

BENCH = Path("/Users/faeezaullyar/Claude/battlecode/ws/bench")
CANDS = sys.argv[1].split(",")
OPPS = sys.argv[2].split(",")
prefix = sys.argv[3] if len(sys.argv) > 3 else "g1"
OUTCOME = len(sys.argv) > 4 and sys.argv[4] == "outcome"
tot = {c: [0, 0, 0] for c in CANDS}  # wins, games, gem margin sum
faults = {c: 0 for c in CANDS}; codes = {c: 0 for c in CANDS}
print(f"{'opponent':12}" + "".join(f"{c:>16}" for c in CANDS))
for o in OPPS:
    cells = []
    for c in CANDS:
        fs = list((BENCH / f"{prefix}_{c}_vs_{o}").glob("*__*__*.json"))
        w = gm = 0
        for f in fs:
            s = f.stem.split("__")[2]
            us, them = ("teamA", "teamB") if s == "A" else ("teamB", "teamA")
            d = json.loads(f.read_text())
            g = {k["team"]: int(k["submittedGems"]) for k in d["teams"]}
            w += (d["match"].get("outcome") == us) if OUTCOME else (g[us] > g[them]); gm += g[us] - g[them]
            faults[c] += d["diagnostics"]["botFaults"][us]
            codes[c] += len(d["diagnostics"].get("codes") or [])
        tot[c][0] += w; tot[c][1] += len(fs); tot[c][2] += gm
        cells.append(f"{w:4}/{len(fs):3} {gm / max(1, len(fs)):+5.0f}" if fs else f"{'-':>14}")
    print(f"{o:12}" + "".join(f"{x:>16}" for x in cells))
print(f"{'TOTAL':12}" + "".join(f"{tot[c][0]:5}/{tot[c][1]:4} {100 * tot[c][0] / max(1, tot[c][1]):3.0f}%" .rjust(16) for c in CANDS))
print("faults", faults, "engine codes", codes)
