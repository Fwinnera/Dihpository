#!/usr/bin/env python3
"""Build camps.json from the probe bundles: camptab.py PROBEDIR OUT.json"""
import json, sys, zipfile
from pathlib import Path
probe, out = Path(sys.argv[1]), Path(sys.argv[2])
table = {}
for d in sorted(probe.iterdir()):
    b = next(d.glob("*.repl26a"), None)
    if not b: continue
    z = zipfile.ZipFile(b)
    sides = {}
    for side in ("a", "b"):
        t = z.read(f"team-{side}.stdout").decode("utf8", "replace").replace("\x00", "")
        info = {}
        # Champions share stdout, so a probe line may be broken by another's record.
        # Keep the longest copy of each.
        lines = []
        for key in ("CONST", "SPAWN", "ALTARS", "SIZE"):
            copies = [line[line.index(key):] for line in t.splitlines() if key in line]
            if copies:
                lines.append(max(copies, key=lambda s: len(s.split())))
        for line in lines:
            if line.startswith("CONST") and "groups" not in info:
                groups = []
                for tok in line.split(" groups ")[1].split():
                    f = tok.split(":")
                    if len(f) < 9: continue
                    groups.append(dict(id=int(f[0]), gems=int(f[1]), gold=int(f[2]), respawn=int(f[3]), hp=float(f[4]),
                                       strength=float(f[5]), monolith=int(f[6]), x=int(f[7]), y=int(f[8])))
                info["groups"] = groups
            elif line.startswith("SPAWN") and "spawn" not in info:
                info["spawn"] = [tuple(map(int, p.split(","))) for p in line.split()[1:]]
            elif line.startswith("ALTARS") and "altars" not in info:
                info["altars"] = [tuple(map(int, p.split(","))) for p in line.split()[1:]]
            elif line.startswith("SIZE") and "size" not in info:
                info["size"] = tuple(map(int, line.split()[1:]))
        sides[side] = info
    if sides["a"].get("groups"):
        table[d.name] = {"groups": sides["a"]["groups"], "spawn_a": sides["a"].get("spawn"), "spawn_b": sides["b"].get("spawn"),
                         "altars": sides["a"].get("altars"), "size": sides["a"].get("size")}
out.write_text(json.dumps(table))
print(len(table), "maps")
