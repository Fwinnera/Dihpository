#!/usr/bin/env python3
"""Recover the engine's item design table, which exists only inside a match.

`ItemType.info()` reads engine design data, so there is no way to read costs,
stat points or passives from outside a running game, and `cambc run-batch` does
not surface bot stdout anywhere. `cambc run` does keep it: each replay bundle is
a ZIP holding `team-a.stdout`. So the table comes out by running a bot that
prints it on its first turn and reading that member back out of the bundle.

    analysis/itemtable.py            # builds bots/probe, plays 3 rounds, prints
"""
from __future__ import annotations

import ast
import glob
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

WS = Path(__file__).resolve().parent.parent / "ws"
PROBE = '''
def _probe():
    import cambc as bc
    for it in bc.ItemType._members:
        try:
            i = it.info()
            print("ITEM %s %d %d %d %d %s %.3f %d %d" % (
                it.name, i.cost, i.health_points, i.strength_points,
                i.focus_points, ("none" if i.passive is None else str(int(i.passive))),
                i.passive_magnitude, i.combine_count, int(i.purchasable)), flush=True)
        except Exception as exc:
            print("ITEM %s ERR %r" % (it.name, exc), flush=True)

'''
PASSIVES = {"1": "MONSTER +10% camp dmg", "2": "DURABILITY -10% dmg taken",
            "3": "TREASURE +20% gold", "4": "JUNGLE -30% camp dmg",
            "5": "HOME recall 3 not 5", "none": "-"}


def main() -> int:
    probe = WS / "bots/probe"
    if probe.exists():
        shutil.rmtree(probe)
    shutil.copytree(WS / "bots/greatsage", probe)
    main_py = probe / "src/main.py"
    text = PROBE + main_py.read_text().replace(
        "def main():",
        'def main():\n    if not globals().get("_probed"):\n'
        '        globals()["_probed"] = True\n        _probe()\n', 1)
    main_py.write_text(text)
    ast.parse(text)

    out = Path(tempfile.mkdtemp(prefix="itemtable-"))
    subprocess.run(["cambc", "run", "--release", "--rounds", "3",
                    "--map", str(WS / "maps/00swirl.map26a"), "-o", str(out),
                    str(probe), str(WS / "bots/colleague")],
                   check=True, capture_output=True)
    bundles = glob.glob(str(out / "*.repl26a"))
    if not bundles:
        print("no replay bundle produced", file=sys.stderr)
        return 1
    lines = zipfile.ZipFile(bundles[0]).read("team-a.stdout").decode("utf8", "replace")

    rows = {}
    for line in lines.splitlines():
        if not line.startswith("ITEM ") or " ERR " in line:
            continue
        f = line.split()
        rows[f[1]] = (int(f[2]), int(f[3]), int(f[4]), int(f[5]), f[6], float(f[7]),
                      int(f[8]), int(f[9]))
    print("%-30s%6s%5s%5s%7s%7s%6s  %s"
          % ("item", "cost", "hp", "str", "focus", "comb", "buy", "passive"))
    for name in sorted(rows, key=lambda k: (k.split("_")[0], rows[k][0])):
        cost, hp, st, fo, pv, mag, comb, buy = rows[name]
        print("%-30s%6d%5d%5d%7d%7d%6d  %s"
              % (name, cost, hp, st, fo, comb, buy, PASSIVES.get(pv, pv)))
    shutil.rmtree(out, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
