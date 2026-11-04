#!/usr/bin/env python3
"""Download recent finished ranked games of named teams (replay + JSON summary) into OUTDIR.

    fetchteam.py OUTDIR N "TEAM A" "TEAM B" ...

meta.json records each match with a `focus` field naming the team it was fetched for.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

CAMBC = "/home/user/.venv-cambc/bin/cambc"
WS = "/home/user/repo/ws"
ENV = dict(os.environ, SSL_CERT_FILE="/root/.ccr/ca-bundle.crt")


def run(*args):
    for attempt in range(5):
        r = subprocess.run([CAMBC, *args], cwd=WS, capture_output=True, text=True, env=ENV)
        if r.returncode == 0:
            return r.stdout
        time.sleep(3 + 4 * attempt)
    print(f"failed: {' '.join(args)}: {r.stderr.strip()[-200:]}", file=sys.stderr)
    return None


def main(out, n, teams):
    out = Path(out)
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
            mid = m["matchId"]
            b, j = out / f"{mid}.repl26a", out / f"{mid}.json"
            if not b.exists():
                run("matches", "download", mid, "-o", str(b))
            if not j.exists():
                run("matches", "summary", mid, "--json", "-o", str(j))
            if b.exists() and j.exists():
                meta[mid] = dict(m, focus=team)
                got += 1
        print(f"{team}: {got} games")
        meta_f.write_text(json.dumps(list(meta.values()), indent=1))


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), sys.argv[3:])
