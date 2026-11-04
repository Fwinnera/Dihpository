#!/usr/bin/env python3
"""For our deaths with a teammate within 6 in the 10 rounds before: what that teammate's PF labels were in
those rounds (did it fight, leave, or carry on farming/travelling?)."""
import collections, json, re, sys, zipfile
from pathlib import Path
US = "Milk and Potatoes"
T = ["ryth","vesper_vale","vendetta","cassi","issac","stellar","prism","marcella","willow","ren","varg","tavi","heart_of_ruin"]
PF = re.compile(r"PF (\d+) (\d+) ([a-z-]+) ")
def cheb(a, b): return max(abs(a[0]-b[0]), abs(a[1]-b[1]))
bdir, sdir = Path(sys.argv[1]), Path(sys.argv[2])
meta = {m["matchId"]: m for m in json.loads((bdir / "meta.json").read_text())}
fights = [x for x in json.loads(Path("/home/user/runs/fights.json").read_text()) if x["victim"] == "us" and x["zone"] in ("our half", "middle")]
labs_by = collections.Counter(); n = 0; per = collections.Counter()
cur = None
for x in sorted(fights, key=lambda x: x["match"]):
    if cur != x["match"]:
        cur = x["match"]
        m = meta[cur]; me = next(t for t in m["teams"] if t["name"] == US); ours = 0 if me["side"] == "a" else 1
        st = {json.loads(l)["r"]: json.loads(l) for l in (sdir / f"{cur}.jsonl").read_text().splitlines()}
        out = zipfile.ZipFile(bdir / f"{cur}.repl26a").read(f"team-{me['side']}.stdout").decode("utf8", "replace").replace("\x00", "")
        pf = {}
        for p in PF.finditer(out): pf[(int(p[1]), int(p[2]))] = p[3]
    r = x["round"]
    dead_now = {c[0] for c in st.get(r, {"c": []})["c"] if not c[7]}
    v = next((c for c in st.get(r - 1, {"c": []})["c"] if c[1] == ours and c[7] and c[0] in dead_now), None)
    if not v: continue
    mates = set()
    for q in range(r - 10, r):
        if q not in st: continue
        vq = next((c for c in st[q]["c"] if c[0] == v[0]), None)
        if not vq or not vq[7]: continue
        for c in st[q]["c"]:
            if c[1] == ours and c[0] != v[0] and c[7] and cheb((vq[3], vq[4]), (c[3], c[4])) <= 6: mates.add((c[0], c[2]))
    if not mates: continue
    n += 1
    for idx, typ in mates:
        seq = [pf.get((q, typ)) for q in range(r - 10, r + 1)]
        seq = [s for s in seq if s]
        main = collections.Counter(seq).most_common(1)[0][0] if seq else "none"
        per[main] += 1
        for s in seq: labs_by[s] += 1
print(f"{n} of our deaths (our half + middle) had a teammate within 6 in the 10 rounds before")
print("teammate's most common label in those rounds:", ", ".join(f"{k} {v}" for k, v in per.most_common(12)))
tot = sum(labs_by.values())
print("all teammate turns:", ", ".join(f"{k} {100 * v / tot:.0f}%" for k, v in labs_by.most_common(12)))
