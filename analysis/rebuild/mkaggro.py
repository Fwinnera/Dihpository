#!/usr/bin/env python3
"""Engagement thresholds in combat::choose_enemy on a j_hjt-line bot.

    mkaggro.py BOTDIR [CLOSE=4] [ODDS=1.15]

CLOSE  an enemy within this many tiles is engaged at any odds (the line's value is 4).
ODDS   beyond that, engage when our local power exceeds the enemy's times ODDS (1.15).

Holding Vesper Vale and Vendetta back from fights cost 72 and 264 games of 1,376, and
requiring odds for close fights cost 206, so these test the other direction.
"""
import sys
from pathlib import Path

src = Path(sys.argv[1]) / "src"
opts = {"CLOSE": "4", "ODDS": "1.15"}
for a in sys.argv[2:]:
    k, v = a.split("=", 1)
    assert k in opts, k
    opts[k] = v
f = src / "combat.h"
t = f.read_text()
pairs = [
    ("        if (!(killable || interrupt || defending || gap <= 4 || allied_power > enemy_power * 1.15)) continue;",
     f"        if (!(killable || interrupt || defending || gap <= {opts['CLOSE']} || allied_power > enemy_power * {opts['ODDS']})) continue;"),
    ("        if (gap > 4 && !(killable || interrupt || allied_power > enemy_power * 1.15)) continue;",
     f"        if (gap > {opts['CLOSE']} && !(killable || interrupt || allied_power > enemy_power * {opts['ODDS']})) continue;"),
]
for old, new in pairs:
    if t.count(old) != 1:
        sys.exit(f"combat.h: expected one match: {old[:60]!r}")
    t = t.replace(old, new)
f.write_text(t)
print("patched", src, opts)
