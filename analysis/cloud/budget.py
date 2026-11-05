#!/usr/bin/env python3
"""Time budget per champion-round from states + action streams: dead, attacking a champion, attacking a camp,
casting only, moving only, idle (alive, no move/attack/cast); split by side and by game phase."""
import collections, json, sys
from pathlib import Path
US = "Milk and Potatoes"
bdir, sdir, adir = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
arm = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] != "-" else None
meta = json.loads((bdir / "meta.json").read_text())
K = ["dead", "hit champ", "hit camp", "cast only", "move only", "idle"]
B = collections.defaultdict(collections.Counter)
games = collections.Counter()
for m in meta:
    if arm and m.get("arm") != arm: continue
    fs = sdir / f"{m['matchId']}.jsonl"; fa = adir / f"{m['matchId']}.jsonl"
    if not (fs.exists() and fa.exists()): continue
    focus = m.get("focus", US)
    me = next(t for t in m["teams"] if t["name"] == focus or t.get("teamId") == focus); ours = 0 if me["side"] == "a" else 1
    acts = collections.defaultdict(list)
    for l in fa.read_text().splitlines():
        r = json.loads(l)
        if r[8] and r[1] >= 0: acts[(r[0], r[1])].append(r)
    rows = [json.loads(l) for l in fs.read_text().splitlines()]; rows = [r for r in rows if r["c"]]
    games["n"] += 1
    for st, nx in zip(rows, rows[1:]):
        pos = {}
        for c in st["c"]:
            if c[7] and c[3] >= 0: pos.setdefault((c[3], c[4]), c[0])
        for c in nx["c"]:
            if c[7] and c[3] >= 0: pos.setdefault((c[3], c[4]), c[0])
        moved_to = {}
        for (rd, k), rs in acts.items():
            pass
        phase = "early" if st["r"] < 600 else "mid" if st["r"] < 1300 else "late"
        for c in st["c"]:
            side = "focus" if c[1] == ours else "opp"
            for key in (side, f"{side} {phase}"):
                b = B[key]
                b["n"] += 1
                if not c[7] or c[3] < 0:
                    b["dead"] += 1; continue
                rs = acts.get((st["r"], c[0]), [])
                codes = [r[2] for r in rs]
                champ_spots = set()
                for r in rs: pass
                hit_champ = hit_camp = False
                for r in rs:
                    if r[2] != 5: continue
                    tgt = (r[5], r[6])
                    # a champion of the other team stands there at the start or end of the round
                    t = pos.get(tgt)
                    if t is not None and next((x for x in st["c"] if x[0] == t), [0, c[1]])[1] != c[1]: hit_champ = True
                    else: hit_camp = True
                if hit_champ: b["hit champ"] += 1
                elif hit_camp: b["hit camp"] += 1
                elif 6 in codes: b["cast only"] += 1
                elif 4 in codes: b["move only"] += 1
                else: b["idle"] += 1
print(f"games {games['n']}")
print(f"{'':<12}" + "".join(f"{k:>11}" for k in K))
for key in ["focus", "opp", "focus early", "opp early", "focus mid", "opp mid", "focus late", "opp late"]:
    b = B[key]
    if b["n"]: print(f"{key:<12}" + "".join(f"{100 * b[k] / b['n']:>10.1f}%" for k in K))
