#!/usr/bin/env python3
"""Download another team's recent ranked matches and their summaries for study.

    fetch_team.py TEAM_ID OUT_DIR [--count N]

Writes OUT_DIR/matches.json (the listings, newest first) and
OUT_DIR/summaries/<matchId>.json. Summaries are third-party data: they are only
parsed as JSON, never executed.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path

WS = Path(__file__).resolve().parent.parent / "ws"


def cambc(*args: str) -> str:
    for attempt in range(6):
        r = subprocess.run(["cambc", *args], capture_output=True, text=True, cwd=WS)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout
        time.sleep(4 * (attempt + 1))
    raise RuntimeError(f"cambc {' '.join(args)} failed: {(r.stderr or r.stdout)[:200]}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("team")
    ap.add_argument("out")
    ap.add_argument("--count", type=int, default=60)
    a = ap.parse_args()
    # Absolute, because cambc runs from ws/ and would resolve a relative path there.
    out = Path(a.out).resolve()
    (out / "summaries").mkdir(parents=True, exist_ok=True)
    matches, cursor = [], None
    while len(matches) < a.count:
        args = ["matches", "list", "--team", a.team, "--kind", "ranked", "--limit", "50", "--json"]
        if cursor:
            args += ["--cursor", cursor]
        d = json.loads(cambc(*args))
        batch = d.get("matches", [])
        matches += [m for m in batch if m.get("status") == "finished"]
        cursor = d.get("nextCursor")
        if not batch or not cursor:
            break
    matches = sorted(matches, key=lambda m: m["createdAt"], reverse=True)[:a.count]
    (out / "matches.json").write_text(json.dumps(matches, indent=1))
    got = 0
    for m in matches:
        f = out / "summaries" / f"{m['matchId']}.json"
        if not f.exists():
            try:
                cambc("matches", "summary", m["matchId"], "--json", "-o", str(f))
            except RuntimeError as e:
                print("  skipped", m["matchId"][:8], e)
                continue
        got += f.exists()
    print(f"{len(matches)} matches listed, {got} summaries on disk in {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
