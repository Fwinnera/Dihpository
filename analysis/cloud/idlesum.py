#!/usr/bin/env python3
"""Summarise the p_idle diagnostic (ID lines: could move and attack but did neither; RP lines: fuel bail-outs)
from a local bench tag's bundles."""
import collections, sys, zipfile
from pathlib import Path
d = Path("/home/user/repo/ws/bench") / sys.argv[1]
idle = collections.Counter(); idle_c = collections.Counter(); low = collections.Counter(); rp = collections.Counter(); games = 0
for f in sorted(d.glob("*__*__*.repl26a")):
    side = f.stem.rsplit("__", 1)[-1]
    out = zipfile.ZipFile(f).read(f"team-{'a' if side == 'A' else 'b'}.stdout").decode("utf8", "replace").replace("\x00", "")
    games += 1
    for l in out.splitlines():
        p = l.split()
        if not p: continue
        if p[0] == "ID":
            if len(p) == 6: p = p[:3] + ["(none)"] + p[3:]
            if len(p) < 7: continue
            lab, ne3, ne6, hp = p[3], int(p[4]), int(p[5]), int(p[6])
            idle[lab] += 1
            if ne3 > 0: idle_c[lab] += 1
            if ne3 > 0 and hp < 45: low[lab] += 1
        elif p[0] == "RP" and int(p[1]) > 5: rp["replan"] += 1
print(f"games {games}; fuel bail-outs after round 5: {rp['replan'] / games:.1f} a game")
print("idle turns per game by label:", ", ".join(f"{k} {v / games:.1f}" for k, v in idle.most_common(14)))
print("... with a visible enemy within 3:", ", ".join(f"{k} {v / games:.2f}" for k, v in idle_c.most_common(12)))
print("... and below 45% health:", ", ".join(f"{k} {v / games:.2f}" for k, v in low.most_common(8)))
