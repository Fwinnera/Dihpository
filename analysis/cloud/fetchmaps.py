#!/usr/bin/env python3
"""Download summaries of our ranked games on given maps (from ranked_all.json) into OUTDIR with meta.json."""
import json, os, subprocess, sys, time
from pathlib import Path
C = "/home/user/.venv-cambc/bin/cambc"; ENV = dict(os.environ, SSL_CERT_FILE="/root/.ccr/ca-bundle.crt")
out = Path(sys.argv[1]); maps = set(sys.argv[2].split(",")); out.mkdir(parents=True, exist_ok=True)
allm = json.load(open("/home/user/plat/ranked_all.json"))
meta = []
for m in allm:
    if m.get("status") != "finished" or m["map"] not in maps or m["createdAt"] < "2026-11-03T15:00": continue
    j = out / f"{m['matchId']}.json"
    for attempt in range(4):
        if j.exists(): break
        subprocess.run([C, "matches", "summary", m["matchId"], "--json", "-o", str(j)], cwd="/home/user/repo/ws", capture_output=True, env=ENV)
        if not j.exists(): time.sleep(2 + 3 * attempt)
    if j.exists(): meta.append(m)
(out / "meta.json").write_text(json.dumps(meta)); print(len(meta), "summaries")
