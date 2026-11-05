#!/usr/bin/env python3
"""What a champion was doing in the 8 rounds before it died, finer than deathsrc.py: attacking camps,
attacking champions, moving, or idle while capturing (near a camp group), depositing (carrying gems near an
altar), recalling (recall action in the window), or otherwise idle (stunned, out of fuel). Plus who killed it."""
import collections, json, sys
from pathlib import Path
US = "Milk and Potatoes"
CL = Path("/home/user/dihpository/analysis/cloud")
MI = {k.replace("-", "_"): v for k, v in json.loads((CL / "mapinfo.json").read_text()).items()}
CA = {k.replace("-", "_"): v for k, v in json.loads((CL / "camps_all.json").read_text()).items()}
def cheb(a, b): return max(abs(a[0]-b[0]), abs(a[1]-b[1]))
bdir, sdir, adir = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
arm = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] != "-" else None
meta = json.loads((bdir / "meta.json").read_text())
W = 8
what = {"focus": collections.Counter(), "opp": collections.Counter()}
killers = {"focus": collections.defaultdict(collections.Counter), "opp": collections.defaultdict(collections.Counter)}
deaths = collections.Counter(); games = 0; nomap = 0
for m in meta:
    if arm and m.get("arm") != arm: continue
    fs = sdir / f"{m['matchId']}.jsonl"; fa = adir / f"{m['matchId']}.jsonl"
    if not (fs.exists() and fa.exists()): continue
    mp = m["map"].replace("-", "_")
    if mp not in MI: nomap += 1; continue
    altars = [tuple(a) for a in MI[mp]["altars"]]; groups = [(g["x"], g["y"]) for g in CA[mp]]
    focus = m.get("focus", US)
    me = next(t for t in m["teams"] if t["name"] == focus or t.get("teamId") == focus); ours = 0 if me["side"] == "a" else 1
    games += 1
    dmg = collections.defaultdict(lambda: collections.defaultdict(float))
    acts = collections.defaultdict(list)
    for l in fa.read_text().splitlines():
        r = json.loads(l)
        if r[8] and r[1] >= 0: acts[(r[0], r[1])].append(r)
        for k, dv in r[9]:
            if dv < 0: dmg[(r[0], k)][r[1] if r[1] >= 0 else -1] += -dv
    rows = [json.loads(l) for l in fs.read_text().splitlines()]; rows = [r for r in rows if r["c"]]
    team = {c[0]: c[1] for c in rows[0]["c"]}
    byr = {r["r"]: r for r in rows}
    for i in range(1, len(rows)):
        for c in rows[i]["c"]:
            prev = next((x for x in rows[i - 1]["c"] if x[0] == c[0]), None)
            if not prev or not prev[7] or c[7]: continue
            side = "focus" if c[1] == ours else "opp"
            deaths[side] += 1
            r_end = rows[i]["r"]
            did = collections.Counter(); recall = False; gems = prev[9]; p = (prev[3], prev[4])
            for rr in range(r_end - W, r_end):
                rs = acts.get((rr, c[0]), [])
                codes = [x[2] for x in rs]
                if 11 in codes: recall = True
                st = byr.get(rr)
                pos = {}
                if st:
                    for x in st["c"]:
                        if x[7] and x[3] >= 0: pos[(x[3], x[4])] = x
                atk = [x for x in rs if x[2] == 5]
                if atk:
                    tgt = pos.get((atk[0][5], atk[0][6]))
                    did["attack champ" if tgt and tgt[1] != c[1] else "attack camp"] += 1
                elif 6 in codes: did["cast"] += 1
                elif 4 in codes: did["move"] += 1
                else: did["idle"] += 1
            k = max(did, key=did.get) if did else "none"
            if k == "idle":
                if recall: k = "idle: recall"
                elif gems and any(cheb(p, a) <= 3 for a in altars): k = "idle: deposit"
                elif any(cheb(p, g) <= 3 for g in groups): k = "idle: capture?"
                else: k = "idle: other"
            what[side][k] += 1
            src = collections.Counter()
            for rr in range(r_end - W, r_end + 1):
                for s, v in dmg.get((rr, c[0]), {}).items():
                    if s == -1 or team.get(s) != c[1]: src["camp" if s == -1 else "champ"] += v
            champs = len({s for rr in range(r_end - W, r_end + 1) for s in dmg.get((rr, c[0]), {}) if s >= 0 and team.get(s) != c[1]})
            killers[side][k][f"{min(champs, 3)}"] += 1
print(f"games {games} (no map info {nomap}); deaths per game: focus {deaths['focus'] / games:.1f}, opponents {deaths['opp'] / games:.1f}")
for side in ("focus", "opp"):
    n = deaths[side]
    print(f"## {side}: per game")
    for k, v in what[side].most_common():
        kc = killers[side][k]
        print(f"   {k:<16}{v / games:>6.2f}   enemy champions involved 0/1/2/3+: " + "/".join(f"{100 * kc[x] / v:.0f}" for x in "0123"))
