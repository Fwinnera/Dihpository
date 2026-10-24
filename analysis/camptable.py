#!/usr/bin/env python3
"""Dump every map's camp groups: id, gems, gold, total health, monolith or not.

Design data is only readable inside a match, so a probe bot prints it on its
first turn and the line is read back out of each replay bundle's stdout.

    camptable.py            # writes ws/bench/camptable.json for all pool maps
"""
from __future__ import annotations

import ast
import glob
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

WS = Path(__file__).resolve().parent.parent / "ws"
PROBE = '''
def _camps():
    import cambc as bc
    from cambc import game_map as gm
    rows = []
    for g in gm.camp_groups():
        cs = g.camps()
        rows.append("%d:%d:%d:%d:%d:%d" % (g.__index__(), g.gem_value(), g.gold_value(),
                    sum(c.base_stats().base_health for c in cs), int(any(c.is_monolith() for c in cs)),
                    sum(c.base_stats().base_strength for c in cs)))
    print("CAMPS " + " ".join(rows), flush=True)

'''


def main() -> int:
    probe = WS / "bots/probe_camps"
    if probe.exists():
        shutil.rmtree(probe)
    shutil.copytree(WS / "bots/greatsage", probe, ignore=shutil.ignore_patterns("__pycache__", ".cambc"))
    m = probe / "src/main.py"
    t = PROBE + m.read_text().replace("def main():", 'def main():\n    if not globals().get("_c"):\n'
                                       '        globals()["_c"] = True\n        _camps()\n', 1)
    m.write_text(t); ast.parse(t)
    out = Path(tempfile.mkdtemp(prefix="camps-"))
    maps = sorted(glob.glob(str(WS / "maps/*.map26a")))
    man = out / "m.txt"
    man.write_text("".join(f"{probe} {WS / 'bots/colleague'} {mp} {out / Path(mp).stem}.repl26a\n" for mp in maps))
    subprocess.run(["cambc", "run-batch", "--release", "--jobs", "6", "--timeout", "120",
                    "--rounds", "2", str(man)], capture_output=True, cwd=WS)
    table = {}
    for mp in maps:
        b = out / f"{Path(mp).stem}.repl26a"
        if not b.exists():
            continue
        txt = zipfile.ZipFile(b).read("team-a.stdout").decode("utf8", "replace").replace("\x00", "")
        line = next((l for l in txt.splitlines() if l.startswith("CAMPS ")), None)
        if line:
            table[Path(mp).stem.replace("-", "_")] = [
                dict(zip(("id", "gems", "gold", "hp", "monolith", "strength"), map(int, r.split(":"))))
                for r in line[6:].split()]
    (WS / "bench/camptable.json").write_text(json.dumps(table))
    print(f"{len(table)} of {len(maps)} maps tabulated -> ws/bench/camptable.json")
    shutil.rmtree(out, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
