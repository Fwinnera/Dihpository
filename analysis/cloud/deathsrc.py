#!/usr/bin/env python3
"""Who deals the damage behind each death (action streams: health drops attributed to the acting unit, a camp
when no champion is acting) over the 8 rounds before it, and what the victim did in those rounds."""
import collections, json, sys
from pathlib import Path
US = "Milk and Potatoes"
T = ["ryth","vv","vend","cassi","issac","stel","prism","marc","willow","ren","varg","tavi","hor"]
bdir, sdir, adir = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
arm = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] != "-" else None
meta = json.loads((bdir / "meta.json").read_text())
W = 8
kinds = {"focus": collections.Counter(), "opp": collections.Counter()}
doing = {"focus": collections.Counter(), "opp": collections.Counter()}
camp_share = {"focus": [], "opp": []}
deaths = collections.Counter(); games = 0
for m in meta:
    if arm and m.get("arm") != arm: continue
    fs = sdir / f"{m['matchId']}.jsonl"; fa = adir / f"{m['matchId']}.jsonl"
    if not (fs.exists() and fa.exists()): continue
    focus = m.get("focus", US)
    me = next(t for t in m["teams"] if t["name"] == focus or t.get("teamId") == focus); ours = 0 if me["side"] == "a" else 1
    games += 1
    dmg = collections.defaultdict(lambda: collections.defaultdict(float))  # (round, victim) -> source -> damage
    acts = collections.defaultdict(list)
    for l in fa.read_text().splitlines():
        r = json.loads(l)
        if r[8] and r[1] >= 0: acts[(r[0], r[1])].append(r[2])
        for k, dv in r[9]:
            if dv < 0: dmg[(r[0], k)][("champ", r[1]) if r[1] >= 0 else ("camp", (r[3], r[4]))] += -dv
    rows = [json.loads(l) for l in fs.read_text().splitlines()]; rows = [r for r in rows if r["c"]]
    team = {c[0]: c[1] for c in rows[0]["c"]}
    for i in range(1, len(rows)):
        for c in rows[i]["c"]:
            prev = next((x for x in rows[i - 1]["c"] if x[0] == c[0]), None)
            if not prev or not prev[7] or c[7]: continue
            side = "focus" if c[1] == ours else "opp"
            deaths[side] += 1
            r_end = rows[i]["r"]
            src = collections.defaultdict(float)
            for rr in range(r_end - W, r_end + 1):
                for s, v in dmg.get((rr, c[0]), {}).items(): src[s] += v
            champs = {s[1] for s, v in src.items() if s[0] == "champ" and team.get(s[1]) != c[1] and v > 0}
            camp = sum(v for s, v in src.items() if s[0] == "camp")
            tot = sum(v for s, v in src.items() if s[0] == "camp" or team.get(s[1]) != c[1])
            share = camp / tot if tot else 0
            camp_share[side].append(share)
            if not champs: k = "camps only"
            elif share >= 0.3: k = f"camps + {min(len(champs), 3)} champ"
            else: k = f"{min(len(champs), 3)} champ" + ("s" if len(champs) > 1 else "")
            kinds[side][k] += 1
            did = collections.Counter()
            for rr in range(r_end - W, r_end):
                cs = acts.get((rr, c[0]), [])
                did["attack" if 5 in cs else "cast" if 6 in cs else "move" if 4 in cs else "idle"] += 1
            doing[side][max(did, key=did.get) if did else "none"] += 1
print(f"games {games}; deaths per game: focus {deaths['focus'] / games:.1f}, opponents {deaths['opp'] / games:.1f}")
for side in ("focus", "opp"):
    n = deaths[side]
    print(f"{side}: " + ", ".join(f"{k} {100 * v / n:.0f}%" for k, v in kinds[side].most_common()))
    print(f"   victim mostly did (last {W} rounds): " + ", ".join(f"{k} {100 * v / n:.0f}%" for k, v in doing[side].most_common()))
