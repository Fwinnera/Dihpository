#!/usr/bin/env python3
"""ranked.py [PAGES]: our ranked games by live-version window (from `cambc matches list --team me --kind ranked`)."""
import json, os, subprocess, sys, time
CAMBC = "/home/user/.venv-cambc5/bin/cambc"; WS = "/home/user/ws5"
ENV = dict(os.environ, SSL_CERT_FILE="/root/.ccr/ca-bundle.crt")
US = "246f9cef-b416-4864-964e-ebcafb97f7ad"
def run(*args):
    for attempt in range(6):
        r = subprocess.run([CAMBC, *args], cwd=WS, capture_output=True, text=True, env=ENV)
        if r.returncode == 0: return json.loads(r.stdout)
        time.sleep(2 + 3 * attempt)
    sys.exit(r.stderr[-300:])
pages = int(sys.argv[1]) if len(sys.argv) > 1 else 6
rows = {}; cursor = None
for p in range(pages):
    a = ["matches", "list", "--team", "me", "--kind", "ranked", "--limit", "100", "--json"]
    if cursor: a += ["--cursor", cursor]
    d = run(*a)
    for m in d["matches"]:
        if m.get("status") != "finished": continue
        me = next(t for t in m["teams"] if t["teamId"] == US); op = next(t for t in m["teams"] if t["teamId"] != US)
        rows[m["matchId"]] = dict(t=m.get("finishedAt") or m["createdAt"], win=me.get("result") == "win", map=m["map"], opp=op["name"], oppId=op["teamId"],
                                  n=len(me.get("characters") or []), group=m.get("groupId"), id=m["matchId"])
    cursor = d.get("nextCursor")
    if not cursor: break
    time.sleep(1)
json.dump(list(rows.values()), open("/home/user/data/ranked.json", "w"))
rs = sorted(rows.values(), key=lambda r: r["t"])
print(len(rs), "ranked games", rs[0]["t"], "to", rs[-1]["t"])
W = [("2026-11-08T14:11", "2026-11-09T16:10", "v182"), ("2026-11-09T17:41", "2026-11-10T02:25", "v183 (a)"), ("2026-11-10T02:25", "2026-11-10T03:52", "v184"),
     ("2026-11-10T03:52", "2026-11-10T08:02", "v183 (b)")]
W += [tuple(x.split(",")) for x in sys.argv[2:]]
for a, b, name in W:
    sel = [r for r in rs if a <= r["t"] < b]
    if not sel: continue
    w = sum(r["win"] for r in sel)
    by = {}
    for r in sel: by.setdefault(r["n"], []).append(r["win"])
    print(f"{name:<10} {w:>4} of {len(sel):<4} = {100*w/len(sel):.1f}%   by roster " + ", ".join(f"{k}: {sum(v)}/{len(v)}" for k, v in sorted(by.items())))
