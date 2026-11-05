#!/usr/bin/env python3
"""Every recall started by the focus team (action code 11) and how it ends: completed (champion appears at
spawn), died during the channel, or interrupted. At the start: our health fraction, nearest living enemy
(true position, from the replay), gems carried; for deaths, the round the first enemy damage landed."""
import collections, json, sys
from pathlib import Path
US = "Milk and Potatoes"
CL = Path("/home/user/dihpository/analysis/cloud")
MI = {k.replace("-", "_"): v for k, v in json.loads((CL / "mapinfo.json").read_text()).items()}
def cheb(a, b): return max(abs(a[0]-b[0]), abs(a[1]-b[1]))
bdir, sdir, adir = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
arm = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] != "-" else None
meta = json.loads((bdir / "meta.json").read_text())
out = collections.Counter(); bydist = collections.defaultdict(collections.Counter); hp_d = []; first_hit = collections.Counter()
games = 0
for m in meta:
    if arm and m.get("arm") != arm: continue
    fs = sdir / f"{m['matchId']}.jsonl"; fa = adir / f"{m['matchId']}.jsonl"
    if not (fs.exists() and fa.exists()): continue
    focus = m.get("focus", US)
    me = next(t for t in m["teams"] if t["name"] == focus or t.get("teamId") == focus); ours = 0 if me["side"] == "a" else 1
    games += 1
    starts = []; hits = collections.defaultdict(list)
    rows = [json.loads(l) for l in fs.read_text().splitlines()]; rows = [r for r in rows if r["c"]]
    team = {c[0]: c[1] for c in rows[0]["c"]}
    for l in fa.read_text().splitlines():
        r = json.loads(l)
        if r[8] and r[1] >= 0 and r[2] == 11 and team.get(r[1]) == ours: starts.append((r[0], r[1]))
        for k, dv in r[9]:
            if dv < 0 and r[1] >= 0 and team.get(r[1]) != team.get(k): hits[k].append(r[0])
    byr = {r["r"]: r for r in rows}
    for rd, k in starts:
        st = byr.get(rd)
        if not st: continue
        c = next(x for x in st["c"] if x[0] == k)
        if not c[7]: continue
        enemies = [x for x in st["c"] if x[1] != ours and x[7] and x[3] >= 0]
        d = min((cheb((c[3], c[4]), (e[3], e[4])) for e in enemies), default=99)
        db = "<=3" if d <= 3 else "4-6" if d <= 6 else "7-10" if d <= 10 else ">10"
        res = "completed"
        for rr in range(rd + 1, rd + 8):
            s2 = byr.get(rr)
            if not s2: break
            c2 = next(x for x in s2["c"] if x[0] == k)
            if not c2[7]:
                res = "died"; break
            if cheb((c2[3], c2[4]), (c[3], c[4])) > 2 and rr - rd < 5:
                res = "moved (cancelled?)"; break
        out[res] += 1; bydist[db][res] += 1
        if res == "died":
            hp_d.append(c[5] / max(1, c[6]))
            fh = [h for h in hits[k] if rd <= h <= rd + 8]
            first_hit["hit before start" if any(rd - 3 <= h < rd for h in hits[k]) else "first hit after start"] += 1
n = sum(out.values())
print(f"games {games}: recalls {n} ({n / games:.1f} a game): " + ", ".join(f"{k} {v} ({100 * v / n:.0f}%)" for k, v in out.most_common()))
for db in ("<=3", "4-6", "7-10", ">10"):
    b = bydist[db]; t = sum(b.values())
    if t: print(f"  nearest enemy {db:>5} at the start: {t:>5} recalls, died {b['died']} ({100 * b['died'] / t:.0f}%)")
hp_d.sort()
if hp_d: print(f"  died: health fraction at the start median {hp_d[len(hp_d) // 2]:.2f}; " + ", ".join(f"{k} {v}" for k, v in first_hit.items()))
