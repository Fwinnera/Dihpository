#!/usr/bin/env python3
"""fetch.py OUTDIR N TEAM_ID [TEAM_ID ...] [--since ISO] [--losses US_ID]: recent finished ranked games (replay + summary)."""
import json, os, subprocess, sys, time
from pathlib import Path
CAMBC = "/home/user/.venv-cambc5/bin/cambc"
WS = "/home/user/ws5"
ENV = dict(os.environ, SSL_CERT_FILE="/root/.ccr/ca-bundle.crt")

def run(*args):
    for attempt in range(5):
        r = subprocess.run([CAMBC, *args], cwd=WS, capture_output=True, text=True, env=ENV)
        if r.returncode == 0:
            return r.stdout
        time.sleep(3 + 4 * attempt)
    print(f"failed: {' '.join(args)}: {r.stderr.strip()[-200:]}", file=sys.stderr)
    return None

def main():
    a = sys.argv[1:]
    since = None; losses = None
    if "--since" in a:
        i = a.index("--since"); since = a[i + 1]; del a[i:i + 2]
    if "--losses" in a:
        i = a.index("--losses"); losses = a[i + 1]; del a[i:i + 2]
    out = Path(a[0]); n = int(a[1]); teams = a[2:]
    out.mkdir(parents=True, exist_ok=True)
    meta_f = out / "meta.json"
    meta = {m["matchId"]: m for m in json.loads(meta_f.read_text())} if meta_f.exists() else {}
    for team in teams:
        s = run("matches", "list", "--team", team, "--kind", "ranked", "--json", "--limit", "50")
        if not s:
            continue
        got = 0
        for m in json.loads(s)["matches"]:
            if m.get("status") != "finished" or got >= n:
                continue
            if since and (m.get("finishedAt") or "") < since:
                continue
            if losses:
                me = next((t for t in m["teams"] if t["teamId"] == losses), None)
                if not me or me.get("result") == "win":
                    continue
            mid = m["matchId"]
            b, j = out / f"{mid}.repl26a", out / f"{mid}.json"
            if not b.exists():
                run("matches", "download", mid, "-o", str(b))
            if not j.exists():
                run("matches", "summary", mid, "--json", "-o", str(j))
            if b.exists() and j.exists():
                meta[mid] = dict(m, focus=team)
                got += 1
        print(f"{team}: {got} games", flush=True)
        meta_f.write_text(json.dumps(list(meta.values()), indent=1))

main()
