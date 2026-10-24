#!/usr/bin/env python3
"""Per-map structure from two 3-round probe batches: what each rule fires on.

`ws/bots/probe_camps` prints every camp group's design data on its first turn
(`CAMPS altars=N id:gems:gold:health:monolith:strength ...`), and
`ws/bots/probe_nav` prints `NAV crystal=0|1 kind=0|2|3` (whether some group
needs a teleport crystal, and the policy kind: 2 boss map, 3 party map). Run
both for three rounds on every map with `cambc run-batch --rounds 3`, naming
the bundles `camps__<map>.repl26a` and `nav__<map>.repl26a`, then:

    maptable.py DIR            # prints the table, writes ws/bench/maptable.json
"""
from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "ws" / "bench" / "maptable.json"


def stdout(bundle: Path) -> str:
    with zipfile.ZipFile(bundle) as z:
        return z.read("team-a.stdout").replace(b"\x00", b"").decode("utf-8", "replace")


def main(folder: Path) -> None:
    rows = {}
    for bundle in sorted(folder.glob("camps__*.repl26a")):
        name = bundle.stem.split("__", 1)[1]
        line = next((l for l in stdout(bundle).splitlines() if l.startswith("CAMPS ")), None)
        if line is None:
            continue
        parts = line.split()
        altars = int(parts[1].split("=")[1])
        groups = [dict(zip(("id", "gems", "gold", "health", "monolith", "strength"), map(int, g.split(":"))))
                  for g in parts[2:]]
        gems = sum(g["gems"] for g in groups)
        mono = sum(g["gems"] for g in groups if g["monolith"])
        row = {"altars": altars, "groups": len(groups), "gems": gems,
               "mono_share": round(mono / max(1, gems), 3), "camp_groups": groups}
        nav = folder / f"nav__{name}.repl26a"
        if nav.exists():
            l = next((l for l in stdout(nav).splitlines() if l.startswith("NAV ")), "")
            for kv in l.split()[1:]:
                k, _, v = kv.partition("=")
                row[k] = int(v)
        rows[name] = row
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, indent=1))
    print(f"{'map':24}{'altars':>7}{'groups':>7}{'gems':>6}{'mono':>6}{'crystal':>8}{'kind':>5}")
    for name, r in rows.items():
        print(f"{name:24}{r['altars']:7}{r['groups']:7}{r['gems']:6}{r['mono_share']:6.2f}"
              f"{r.get('crystal', -1):8}{r.get('kind', -1):5}")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else sys.exit(__doc__))
