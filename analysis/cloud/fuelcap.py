#!/usr/bin/env python3
"""Per-turn fuel use from local bench bundles (team-X.fuel: 13-byte header, eight setup values, then one u64 per
turn): share of the candidate's turns that used at least 90,000 (the bot bails out below 10,000 left) and that
used the whole 100,000 (suspended mid-turn), against the opponent's."""
import struct, sys, zipfile
from pathlib import Path
for tag in sys.argv[1:]:
    d = Path("/home/user/repo/ws/bench") / tag
    tot = {"cand": [0, 0, 0], "opp": [0, 0, 0]}
    for f in sorted(d.glob("*__*__*.repl26a")):
        side = f.stem.rsplit("__", 1)[-1]
        z = zipfile.ZipFile(f)
        for team in ("a", "b"):
            who = "cand" if (team == "a") == (side == "A") else "opp"
            raw = z.read(f"team-{team}.fuel")
            vals = [struct.unpack_from("<Q", raw, 13 + 8 * i)[0] for i in range((len(raw) - 13) // 8)][8:]
            vals = [v for v in vals if v != 200000]
            t = tot[who]
            t[0] += len(vals); t[1] += sum(1 for v in vals if v >= 90000); t[2] += sum(1 for v in vals if v >= 100000)
    print(f"{tag:<40} " + "  ".join(f"{w}: >=90k {100 * t[1] / max(1, t[0]):.2f}%  full {100 * t[2] / max(1, t[0]):.2f}%" for w, t in tot.items()))
