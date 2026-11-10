#!/usr/bin/env python3
"""fetchlab.py OUTDIR [--replays] ARM [ARM ...]: summaries (and replays) of every finished match of lab arms."""
import json, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
CAMBC = "/home/user/.venv-cambc5/bin/cambc"
WS = Path("/home/user/ws5")
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

def main():
    a = sys.argv[1:]
    replays = "--replays" in a
    if replays: a.remove("--replays")
    out = Path(a[0]); arms = a[1:]
    out.mkdir(parents=True, exist_ok=True)
    meta_f = out / "meta.json"
    meta = {m["matchId"]: m for m in json.loads(meta_f.read_text())} if meta_f.exists() else {}
    jobs = []
    for arm in arms:
        d = json.loads((LAB / f"{arm}.json").read_text())
        for g in d["groups"]:
            cache = LAB / "groups" / f"{g['group']}.json"
            s = json.loads(cache.read_text()) if cache.exists() else cambc("match-groups", "show", g["group"], "--json")
            if not s: continue
            for m in s["matches"]:
                if m.get("status") != "finished": continue
                mid = m["matchId"]
                meta[mid] = dict(m, arm=arm, group=g["group"], oppName=g["name"])
                jobs.append(mid)
    meta_f.write_text(json.dumps(list(meta.values()), indent=1))
    def one(mid):
        b, j = out / f"{mid}.repl26a", out / f"{mid}.json"
        if not j.exists(): cambc("matches", "summary", mid, "--json", "-o", str(j), as_json=False)
        if replays and not b.exists(): cambc("matches", "download", mid, "-o", str(b), as_json=False)
    with ThreadPoolExecutor(4) as ex: list(ex.map(one, jobs))
    n = sum(1 for m in meta if (out / f"{m}.json").exists())
    print(f"{n} of {len(meta)} summaries in {out}")
main()
