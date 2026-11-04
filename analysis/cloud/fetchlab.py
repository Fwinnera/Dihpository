#!/usr/bin/env python3
"""Download every finished match of lab arms (bundle with our stdout + JSON summary) into OUTDIR.

    fetchlab.py OUTDIR ARM [ARM ...]

Writes OUTDIR/<matchId>.repl26a, OUTDIR/<matchId>.json and OUTDIR/meta.json (match records).
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

CAMBC = "/home/user/.venv-cambc/bin/cambc"
WS = Path("/home/user/repo/ws")
LAB = WS / "bench" / "lab"
ENV = dict(os.environ, SSL_CERT_FILE="/root/.ccr/ca-bundle.crt")


def cambc(*args, as_json=True):
    for attempt in range(6):
        r = subprocess.run([CAMBC, *args], cwd=WS, capture_output=True, text=True, env=ENV)
        if r.returncode == 0:
            return json.loads(r.stdout) if as_json else r.stdout
        time.sleep(3 + 4 * attempt)
    print(f"failed: cambc {' '.join(args)}: {r.stderr.strip()[-200:]}", file=sys.stderr)
    return None


def main(out, arms):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    meta_f = out / "meta.json"
    meta = {m["matchId"]: m for m in json.loads(meta_f.read_text())} if meta_f.exists() else {}
    for arm in arms:
        d = json.loads((LAB / f"{arm}.json").read_text())
        for g in d["groups"]:
            s = cambc("match-groups", "show", g["group"], "--json")
            if not s:
                continue
            for m in s["matches"]:
                if m.get("status") != "finished":
                    continue
                mid = m["matchId"]
                meta[mid] = dict(m, arm=arm, group=g["group"])
                b, j = out / f"{mid}.repl26a", out / f"{mid}.json"
                if not b.exists():
                    cambc("matches", "download", mid, "-o", str(b), as_json=False)
                if not j.exists():
                    cambc("matches", "summary", mid, "--json", "-o", str(j), as_json=False)
            time.sleep(1)
    meta_f.write_text(json.dumps(list(meta.values()), indent=1))
    n = sum(1 for m in meta if (out / f"{m}.repl26a").exists() and (out / f"{m}.json").exists())
    print(f"{n} of {len(meta)} matches downloaded into {out}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
