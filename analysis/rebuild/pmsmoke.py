#!/usr/bin/env python3
"""Smoke check of a candidate's games: ERROR lines in its stdout, bot faults, fuel exhaustion.

    pmsmoke.py TAG CAND

Reads ws/bench/TAG/<CAND>__*: the replay zip's team-<side>.stdout for our side, and the match
summary's diagnostics.botFaults and fuelExhausted events for our team.
"""
import gzip
import json
import sys
import zipfile
from pathlib import Path

BENCH = Path(__file__).resolve().parents[2] / "ws/bench"


def main(tag, cand):
    games = errors = faults = 0
    fuel = 0
    bad = []
    for rep in sorted((BENCH / tag).glob(f"{cand}__*__*__*.repl26a")):
        side = rep.stem.split("__")[-1]
        team = "teamA" if side == "A" else "teamB"
        games += 1
        try:
            out = zipfile.ZipFile(rep).read(f"team-{side.lower()}.stdout").decode("utf8", "replace")
        except (KeyError, zipfile.BadZipFile):
            out = ""
        e = sum(1 for line in out.splitlines() if "ERROR" in line)
        js = rep.with_suffix(".json")
        d = json.loads(gzip.open(str(js) + ".gz").read()) if not js.exists() and Path(str(js) + ".gz").exists() else (json.loads(js.read_text()) if js.exists() else None)
        f = int(d["diagnostics"]["botFaults"].get(team, 0)) if d else 0
        if d:
            fuel += sum(len(ev["entries"]) for ev in d["events"] if ev["kind"] == "fuelExhausted" and ev["owner"].get("team") == team)
        errors += e
        faults += f
        if e or f:
            bad.append(f"{rep.stem} errors={e} faults={f}")
    print(f"{tag}/{cand}: {games} games, ERROR lines {errors}, bot faults {faults}, fuel exhaustions {fuel} "
          f"({fuel / max(1, games):.1f} a game)")
    for b in bad[:20]:
        print("  ", b)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
