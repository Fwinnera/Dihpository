#!/usr/bin/env python3
"""Queue unranked groups against a target list in order, within the hourly quota.

    nearqueue.py TARGETS_JSON OUT_JSON [MINUTES]

TARGETS_JSON: {"targets": [{rank, rating, name, teamId, maps[5]}, ...]} in play
order. Sides a,b,a,b,a. A team with no eligible bot is skipped; on the hourly
quota refusal (HTTP 429) it waits the retry-after the platform gives and tries
again, for up to MINUTES (default 90). OUT_JSON records each queued group.
"""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

WS = Path(__file__).resolve().parent.parent / "ws"
CAMBC = str(Path.home() / "Library/Python/3.9/bin/cambc")


def main() -> None:
    targets = json.loads(Path(sys.argv[1]).read_text())["targets"]
    out = Path(sys.argv[2]); minutes = float(sys.argv[3]) if len(sys.argv) > 3 else 90
    done = json.loads(out.read_text()) if out.exists() else []
    have = {d["teamId"] for d in done}
    deadline = time.time() + minutes * 60
    for t in targets:
        if t["teamId"] in have:
            continue
        while True:
            r = subprocess.run([CAMBC, "match-groups", "create", t["teamId"], "--maps", ",".join(t["maps"]),
                                "--sides", "a,b,a,b,a", "--json"], cwd=WS, capture_output=True, text=True)
            stamp = time.strftime("%H:%M:%S", time.gmtime())
            try:
                gid = json.loads(r.stdout)["groupId"]
            except Exception:
                msg = (r.stdout + r.stderr).strip()
                if "eligible bot" in msg:
                    print(f"{stamp} rank {t['rank']} {t['name'][:28]}: skipped (no eligible bot)", flush=True)
                    break
                m = re.search(r"retry after (\d+)", msg)
                if not m or time.time() > deadline:
                    print(f"{stamp} stopping at rank {t['rank']}: {msg[:160]}", flush=True)
                    return
                time.sleep(int(m.group(1)) + 5)
                continue
            done.append({**t, "groupId": gid, "queuedAt": stamp})
            out.write_text(json.dumps(done, indent=1))
            print(f"{stamp} rank {t['rank']:3d} {t['name'][:28]:28} -> {gid[:8]}", flush=True)
            break
    print("all targets queued", flush=True)


if __name__ == "__main__":
    main()
