#!/usr/bin/env python3
"""Make a version live for one unranked lab arm, then put the ranked bot back.

    labtest.py ARM --version N            an uploaded version
    labtest.py ARM --bot BOTDIR --note T  upload ws/bots/BOTDIR first (it stays inactive)

The ranked bot (RANKED below) is re-pinned straight after an upload, so the new version
is only live while its groups are queued. Ranked batches start on the ten-minute marks,
so the switch waits for a minute that ends in 1-6 and the groups are queued at once;
`finally` re-pins RANKED whatever happens. Results: `lab.py show v140 ARM`.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

CAMBC = str(Path.home() / "Library/Python/3.9/bin/cambc")
WS = Path("/Users/faeezaullyar/Claude/battlecode/ws")
LAB = Path(__file__).resolve().parent / "lab.py"
RANKED = int(os.environ.get("RANKED", "140"))


def cambc(*args, check=True):
    for attempt in range(6):
        r = subprocess.run([CAMBC, *args], cwd=WS, capture_output=True, text=True, env=dict(os.environ))
        if r.returncode == 0:
            return json.loads(r.stdout) if r.stdout.strip().startswith("{") else r.stdout
        time.sleep(3 + 4 * attempt)
    if check:
        sys.exit(f"cambc {' '.join(args)} failed: {r.stderr.strip()[-300:]}")
    return None


def live():
    return cambc("submissions", "list", "--json")["active"]["version"]


def pin(v):
    cambc("submissions", "activate", str(v), "--json")
    for _ in range(10):
        if live() == v:
            return
        time.sleep(3)
    sys.exit(f"version {v} did not become live")


arm = sys.argv[1]
args = sys.argv[2:]
version = int(args[args.index("--version") + 1]) if "--version" in args else None
if "--bot" in args:
    bot = args[args.index("--bot") + 1]
    note = args[args.index("--note") + 1]
    before = {s["version"] for s in cambc("submissions", "list", "--json")["submissions"]}
    out = cambc("submit", bot, "--note", note)
    print(str(out).strip()[-300:])
    pin(RANKED)
    for _ in range(60):
        subs = cambc("submissions", "list", "--json")["submissions"]
        new = [s for s in subs if s["version"] not in before]
        if new and new[0]["status"] in ("inactive", "ready", "active"):
            version = new[0]["version"]
            break
        if new and new[0]["status"] in ("failed", "error", "rejected"):
            sys.exit(f"build failed: {new[0]}")
        time.sleep(5)
    else:
        sys.exit("upload did not become ready")
    print(f"uploaded as version {version}")
assert version, "need --version or --bot"
while time.gmtime().tm_min % 10 not in (1, 2, 3, 4, 5, 6):
    time.sleep(10)
try:
    pin(version)
    print(time.strftime("%H:%M:%SZ", time.gmtime()), "live:", version)
    subprocess.run([sys.executable, "-I", str(LAB), "queue", arm, "--from", "v140"], check=True)
    # Wait for the groups to start, so none can pick up the ranked bot instead.
    d = json.loads((WS / "bench" / "lab" / f"{arm}.json").read_text())
    for g in d["groups"]:
        for _ in range(60):
            s = cambc("match-groups", "show", g["group"], "--json")
            if all(m.get("status") in ("running", "finished") for m in s["matches"]):
                break
            time.sleep(5)
finally:
    pin(RANKED)
    print(time.strftime("%H:%M:%SZ", time.gmtime()), "live again:", RANKED)
