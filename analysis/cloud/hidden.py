#!/usr/bin/env python3
"""At each of our deaths' contact turn (diag rows): visible enemies within 8 (PF) vs true enemies within 8 and 12
(decoded state), and whether those extra enemies had been seen in the 20 rounds before."""
import collections, json, sys
from pathlib import Path
US = "Milk and Potatoes"
T = ["ryth","vesper_vale","vendetta","cassi","issac","stellar","prism","marcella","willow","ren","varg","tavi","heart_of_ruin"]
def cheb(a, b): return max(abs(a[0]-b[0]), abs(a[1]-b[1]))
rows = json.loads(Path("/home/user/runs/diag_rows.json").read_text())
meta = {m["matchId"]: m for m in json.loads(Path(sys.argv[1], "meta.json").read_text())}
cache = {}
res = collections.Counter(); n = 0; tot_vis = tot_true8 = tot_true12 = 0
for x in rows:
    if x["zone"] not in ("our spawn", "our half", "middle") or not x["by_champ"] or x["live"] is None: continue
    mid = x["match"]
    if mid not in cache:
        cache.clear()
        cache[mid] = {json.loads(l)["r"]: json.loads(l) for l in Path(sys.argv[2], f"{mid}.jsonl").read_text().splitlines()}
    st = cache[mid]
    me = next(t for t in meta[mid]["teams"] if t["name"] == US); ours = 0 if me["side"] == "a" else 1
    rc = x["round"] - x["live"]
    s = st.get(rc)
    if not s: continue
    v = next((c for c in s["c"] if c[1] == ours and T[c[2]] == x["champ"]), None)
    if not v or not v[7]: continue
    pos = (v[3], v[4])
    true8 = sum(1 for c in s["c"] if c[1] != ours and c[7] and c[3] >= 0 and cheb(pos, (c[3], c[4])) <= 8)
    true12 = sum(1 for c in s["c"] if c[1] != ours and c[7] and c[3] >= 0 and cheb(pos, (c[3], c[4])) <= 12)
    n += 1; tot_vis += x["c_ne8"] or 0; tot_true8 += true8; tot_true12 += true12
    res[(min(x["c_ne8"] or 0, 3), min(true8, 3))] += 1
print(f"{n} of our deaths (home + middle, to champions) with a contact turn")
print(f"mean enemies within 8 at contact: visible {tot_vis / n:.2f}, actually {tot_true8 / n:.2f}; within 12 actually {tot_true12 / n:.2f}")
print("(visible, actual) within 8:", ", ".join(f"{k}: {v}" for k, v in sorted(res.items(), key=lambda kv: -kv[1])[:10]))
