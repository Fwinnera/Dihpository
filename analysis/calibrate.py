#!/usr/bin/env python3
"""Calibrate the disengage threshold against the ratio the rule will act on.

`gs_fightlog` prints one line per champion-turn with an enemy champion within
DISENGAGE_RADIUS: round, champion type id, `combat.local_power` ratio, enemies
counted, health fraction, gems carried. It never disengages, so these are the
outcomes of greatsage's own choices at each ratio. Each line is matched to the
summary's event log: did that champion die within K rounds, and did it take a
kill (or an assist) within K rounds?

    calibrate.py ws/calib             # every *.repl26a with a sibling .json
"""
from __future__ import annotations

import glob
import json
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

K = 8
NAMES = ["Ryth", "Vesper Vale", "Vendetta", "Cassi", "Issac", "Stellar", "Prism",
         "Marcella", "Willow", "Ren", "Varg", "Tavi", "Heart of Ruin"]
EDGES = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0, float("inf")]


def bucket(x: float) -> str:
    lo = 0.0
    for hi in EDGES:
        if x < hi:
            return f"{lo:.2f}-{hi:.2f}" if hi != float("inf") else f">= {lo:.2f}"
        lo = hi
    return f">= {lo:.2f}"


def main(folder: str) -> int:
    turns = defaultdict(lambda: [0, 0, 0, 0])      # bucket -> samples, died, killed, assisted
    entry = defaultdict(lambda: [0, 0, 0, 0])      # first sample of each encounter only
    carry = defaultdict(lambda: [0, 0, 0, 0])      # carriers only
    games = 0
    for bundle in sorted(glob.glob(f"{folder}/*.repl26a")):
        stats = Path(bundle).with_suffix(".json")
        if not stats.exists():
            continue
        d = json.loads(stats.read_text())
        games += 1
        deaths, kills, assists = defaultdict(list), defaultdict(list), defaultdict(list)
        for e in d["events"]:
            o = e.get("owner") or {}
            if o.get("team") != "teamA":
                continue
            book = {"death": deaths, "kill": kills, "assist": assists}.get(e["kind"])
            if book is not None:
                book[o["name"]] += [x["timestamp"]["round"] for x in e["entries"]]
        text = zipfile.ZipFile(bundle).read("team-a.stdout").decode("utf8", "replace")
        last = {}
        for line in text.splitlines():
            f = line.replace("\x00", "").split()
            if len(f) != 7 or f[0] != "PW":
                continue
            r, name = int(f[1]), NAMES[int(f[2])]
            ratio, gems = float(f[3]), int(f[6])
            died = any(r < t <= r + K for t in deaths[name])
            killed = any(r <= t <= r + K for t in kills[name])
            assisted = killed or any(r <= t <= r + K for t in assists[name])
            b = bucket(ratio)
            rows = [turns[b]]
            if r - last.get(name, -99) > 3:
                rows.append(entry[b])
            if gems > 0:
                rows.append(carry[b])
            for row in rows:
                row[0] += 1; row[1] += died; row[2] += killed; row[3] += assisted
            last[name] = r

    print(f"{games} games; outcomes within {K} rounds of each logged champion-turn\n")
    for label, table in (("every champion-turn near an enemy", turns),
                         ("first turn of each encounter", entry),
                         ("carrying gems", carry)):
        print(f"=== {label} ===")
        print("%-12s%9s%9s%9s%11s%9s" % ("ratio", "samples", "died", "killed", "kill/asst", "d - k"))
        keys = sorted(table, key=lambda k: float(k.split("-")[0].replace(">=", "")))
        for k in keys:
            n, dd, kk, aa = table[k]
            if n < 30:
                continue
            print("%-12s%9d%8.1f%%%8.1f%%%10.1f%%%+8.1f" % (k, n, 100 * dd / n, 100 * kk / n,
                                                       100 * aa / n, 100 * (dd - kk) / n))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "ws/calib"))
