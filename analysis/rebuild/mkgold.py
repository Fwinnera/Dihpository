#!/usr/bin/env python3
"""Early gold weight in camp choice (2026-11-04, CLOUD).

Ladder evidence (v166's 150 lab games and 35 games of the top UK teams, first 600 rounds): 38% of our camp
captures give no gems (lab teams 25%, top UK teams 21%); we take 9.6 gems a capture against their 13.0 and
14.8, and bank 207 gems by round 600 against their 294 and 412. Excluding kill gold our income is level with
the lab teams', so the gold-only camps do not buy us more gold. v140 (cHG) raised the early weight of gold
to 1.0 a gem, a local gain that did not show on the ladder.

    mkgold.py BOTDIR GOLD_EARLY     (camp value = gems + GOLD_EARLY x gold before round 500; 0.25 after)
"""
import sys
from pathlib import Path

src = Path(sys.argv[1]) / "src"
w = sys.argv[2]
f = src / "strategy.h"
t = f.read_text()
old = "objective->gold * (now < 500 ? 1.0 : 0.25)"
assert t.count(old) == 1, t.count(old)
f.write_text(t.replace(old, f"objective->gold * (now < 500 ? {w} : 0.25)"))
print("patched", src, "GOLD_EARLY", w)
