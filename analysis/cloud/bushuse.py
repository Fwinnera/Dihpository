#!/usr/bin/env python3
"""How often champions near an enemy stand hidden in a bush (on a bush tile with no enemy champion within 1;
an approximation of bush vision), for the focus team and its opponents; and at each of our deaths, how many
enemies within 6 were hidden that way in the 5 rounds before."""
import collections, json, sys
from pathlib import Path
US = "Milk and Potatoes"
CL = Path("/home/user/dihpository/analysis/cloud")
BU = {k.replace("-", "_"): {tuple(t) for t in v} for k, v in json.loads((CL / "bushes.json").read_text()).items()}
def cheb(a, b): return max(abs(a[0]-b[0]), abs(a[1]-b[1]))
bdir, sdir = Path(sys.argv[1]), Path(sys.argv[2])
arm = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] != "-" else None
meta = json.loads((bdir / "meta.json").read_text())
near = collections.Counter(); hid = collections.Counter(); games = 0
death_hidden = collections.Counter()
for m in meta:
    if arm and not m.get("arm", "").startswith(arm): continue
    fs = sdir / f"{m['matchId']}.jsonl"
    if not fs.exists(): continue
    bush = BU.get(m["map"].replace("-", "_"), set())
    focus = m.get("focus", US)
    me = next(t for t in m["teams"] if t["name"] == focus or t.get("teamId") == focus); ours = 0 if me["side"] == "a" else 1
    games += 1
    rows = [json.loads(l) for l in fs.read_text().splitlines()]; rows = [r for r in rows if r["c"]]
    hidden_near = {}   # (round, our index) -> hidden enemies within 6
    for st in rows:
        living = [c for c in st["c"] if c[7] and c[3] >= 0]
        for b in living:
            others = [a for a in living if a[1] != b[1]]
            close = [a for a in others if cheb((a[3], a[4]), (b[3], b[4])) <= 6]
            if not close: continue
            side = "focus" if b[1] == ours else "opp"
            near[side] += 1
            hidden = (b[3], b[4]) in bush and not any(cheb((a[3], a[4]), (b[3], b[4])) <= 1 for a in others)
            if hidden:
                hid[side] += 1
                if side == "opp":
                    for a in close: hidden_near[(st["r"], a[0])] = hidden_near.get((st["r"], a[0]), 0) + 1
    for i in range(1, len(rows)):
        for c in rows[i]["c"]:
            if c[1] != ours: continue
            prev = next((x for x in rows[i - 1]["c"] if x[0] == c[0]), None)
            if not prev or not prev[7] or c[7]: continue
            h = max((hidden_near.get((r, c[0]), 0) for r in range(rows[i]["r"] - 5, rows[i]["r"])), default=0)
            death_hidden[min(h, 2)] += 1
print(f"games {games}")
for side in ("focus", "opp"):
    print(f"  {side}: champion-rounds near an enemy {near[side] / games:.0f} a game, hidden in a bush {100 * hid[side] / max(1, near[side]):.1f}%")
n = sum(death_hidden.values())
print(f"  our deaths: a hidden enemy within 6 in the 5 rounds before: 0 {100 * death_hidden[0] / n:.0f}%, 1 {100 * death_hidden[1] / n:.0f}%, 2+ {100 * death_hidden[2] / n:.0f}%")
