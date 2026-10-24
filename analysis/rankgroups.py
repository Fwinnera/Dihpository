#!/usr/bin/env python3
"""Queue unranked groups against a list of teams, closest rank first.

    rankgroups.py TARGETS_JSON OUT_JSON START COUNT

TARGETS_JSON is a list of {rank, rating, name, teamId} in the order to play.
Team i gets five maps rotating through the map pool (so the run covers the
pool), sides a,b,a,b,a. Skips teams with no eligible bot; stops at any other refusal (such as the quota).
"""
import json
import subprocess
import sys
from pathlib import Path

WS = Path(__file__).resolve().parent.parent / "ws"
CAMBC = str(Path.home() / "Library/Python/3.9/bin/cambc")


def main() -> None:
    targets = json.loads(Path(sys.argv[1]).read_text())
    out = Path(sys.argv[2]); start, count = int(sys.argv[3]), int(sys.argv[4])
    done = json.loads(out.read_text()) if out.exists() else []
    maps = sorted(p.stem.replace("-", "_") for p in (WS / "maps").glob("*.map26a"))
    for i in range(start, min(start + count, len(targets))):
        t = targets[i]
        chosen = [maps[(5 * i + k) % len(maps)] for k in range(5)]
        r = subprocess.run([CAMBC, "match-groups", "create", t["teamId"], "--maps", ",".join(chosen),
                            "--sides", "a,b,a,b,a", "--json"], cwd=WS, capture_output=True, text=True)
        try:
            gid = json.loads(r.stdout)["groupId"]
        except Exception:
            msg = (r.stdout + r.stderr).strip()
            if "eligible bot" in msg:
                print(f"rank {t['rank']} {t['name']}: skipped (no eligible bot)")
                continue
            print(f"rank {t['rank']} {t['name']}: REFUSED: {msg[:200]}")
            break
        done.append({**t, "maps": chosen, "groupId": gid})
        out.write_text(json.dumps(done, indent=1))
        print(f"rank {t['rank']:3d} {t['name'][:28]:28} -> {gid[:8]}  {','.join(chosen)}")


if __name__ == "__main__":
    main()
