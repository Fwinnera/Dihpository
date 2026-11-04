#!/usr/bin/env python3
"""Which local opponent's verdict predicts the ladder lab? Rank correlation across versions.

    labpredict.py

Reads every screen log (ws/bench/s*_screen.log, "CAND vs OPP: games won X of 172") and every lab
arm with results (ws/bench/lab/ARM.json and ARM_s2.json, summaries fetched by labmargin.py), then
prints, per local opponent and for a few composites, the Spearman correlation across versions of
the local win rate with the lab's set-1 gem margin and with its wins over both sets, and the
composite gs_mix_camp + b_tbd + next_trial for recent candidates.
"""
import glob, json, re, statistics as stt, collections
from pathlib import Path
B = Path("/Users/faeezaullyar/Claude/battlecode/ws/bench")
LAB = B / "lab"
US = "Milk and Potatoes"
local = {}
for f in sorted(glob.glob(str(B / "s*_screen.log"))):
    for line in open(f):
        m = re.match(r"\d\d:\d\d (\S+) vs (\S+):\s+games won (\d+) of (\d+)", line)
        if m:
            c, o = m[1].replace("_submit", ""), m[2].replace("_submit", "")
            local[(c, o)] = int(m[3]) / int(m[4])
def labres(arm):
    p = LAB / f"{arm}.json"
    if not p.exists(): return None
    d = json.loads(p.read_text()); w = n = 0; mg = []
    for g in d["groups"]:
        s = json.loads((LAB / "groups" / f"{g['group']}.json").read_text())
        for m in s["matches"]:
            me = next(t for t in m["teams"] if t["name"] == US)
            if me.get("result") not in ("win", "loss", "draw"): continue
            n += 1; w += me.get("result") == "win"
            f = LAB / "summaries" / f"{m['matchId']}.json"
            if f.exists():
                side = "teamA" if me["side"] == "a" else "teamB"
                sm = json.loads(f.read_text())
                o = sum(float(c["metrics"]["submittedGems"]) for c in sm["champions"] if c["team"] == side)
                t = sum(float(c["metrics"]["submittedGems"]) for c in sm["champions"] if c["team"] != side)
                mg.append(o - t)
    return (w, n, stt.mean(mg) if mg else None)
arms = {"v140": "cHG", "rl": "rl", "tf": "tf", "gp120": "gp120", "cb": "cb", "sh": "sh", "ab2": "ab2", "ab3": "ab3",
        "ab3v": "ab3v", "ab4": "ab4", "dg": "dg", "sgA": "sgA", "es_best": "es_best", "dH": "dH", "e1": "e1", "ec": "ec", "sq": "sq"}
rows = []
for arm, cand in arms.items():
    r1, r2 = labres(arm), labres(arm + "_s2")
    if not r1: continue
    rows.append((arm, cand, r1, r2))
    print(f"{arm:<8} lab set1 {r1[0]}/{r1[1]} margin {r1[2] if r1[2] is None else round(r1[2])}" + (f"  set2 {r2[0]}/{r2[1]} margin {round(r2[2]) if r2[2] is not None else None}" if r2 else ""))
def rank(v):
    s = sorted(range(len(v)), key=lambda i: v[i]); r = [0] * len(v)
    for k, i in enumerate(s): r[i] = k
    return r
def spearman(a, b):
    ra, rb = rank(a), rank(b)
    ma, mb = stt.mean(ra), stt.mean(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = (sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb)) ** 0.5
    return num / den if den else 0
opps = sorted({o for (c, o) in local})
print("\nopponent: versions with both, Spearman of local win rate against lab set-1 margin, and against set 1+2 wins (both sets only)")
out = []
for o in opps:
    xs, ys, xs2, ys2 = [], [], [], []
    for arm, cand, r1, r2 in rows:
        if (cand, o) in local and r1[2] is not None:
            xs.append(local[(cand, o)]); ys.append(r1[2])
            if r2:
                xs2.append(local[(cand, o)]); ys2.append(r1[0] + r2[0])
    if len(xs) >= 6:
        out.append((spearman(xs, ys), o, len(xs), spearman(xs2, ys2) if len(xs2) >= 6 else None, len(xs2)))
for s, o, k, s2, k2 in sorted(out, reverse=True):
    print(f"  {o:<16} n {k:>2}  rho(set1 margin) {s:+.2f}   rho(both-set wins) {'' if s2 is None else f'{s2:+.2f}'} (n {k2})")

print("\ncomposites (mean local win rate over the set; versions with all of them):")
for combo in (("gs_mix_camp", "b_tbd"), ("gs_mix_camp", "b_tbd", "next_trial"), ("gs_mix_camp", "b_tbd", "next_trial", "f_hor_h"),
              ("gs_mix_camp", "b_tbd", "next_trial", "f_hor_h", "cHG"), ("gs_mix_camp",)):
    xs, ys, xs2, ys2, names = [], [], [], [], []
    for arm, cand, r1, r2 in rows:
        if all((cand, o) in local for o in combo) and r1[2] is not None:
            v = stt.mean(local[(cand, o)] for o in combo)
            xs.append(v); ys.append(r1[2])
            if r2:
                xs2.append(v); ys2.append(r1[0] + r2[0]); names.append((arm, round(v * 172), r1[0] + r2[0]))
    print(f"  {'+'.join(combo):<46} n {len(xs):>2} rho(set1 margin) {spearman(xs, ys):+.2f}  n {len(xs2)} rho(both-set wins) {spearman(xs2, ys2):+.2f}")
    if combo == ("gs_mix_camp", "b_tbd", "next_trial"):
        for nm in sorted(names, key=lambda x: -x[1]):
            print("      ", nm)
import sys
for c in ("ab3", "fc", "fcN", "fcG", "hf", "hfC", "hfR", "ab3A", "ab3C", "ab5", "bk2", "bg", "ab6b"):
    vals = [local.get((c, o)) for o in ("gs_mix_camp", "b_tbd", "next_trial")]
    print(f"  {c:<6} gs_mix_camp {vals[0] and round(vals[0] * 172)}  b_tbd {vals[1] and round(vals[1] * 172)}  next_trial {vals[2] and round(vals[2] * 172)}"
          + (f"  mean {stt.mean(v for v in vals if v) * 172:.1f}" if any(vals) else ""))
