#!/usr/bin/env python3
"""Twin of an ab3-line bot: identical decisions, slightly different fuel use, on every map.

    mktwin.py BOTDIR K

A dead loop of K volatile additions at the start of every turn costs fuel and nothing else, so
fuel-driven search cutoffs (turn::check) fall at slightly different points and the chaotic part
of each game is re-dealt, while every rule stays the same. The party session's twins (a dead loop
in BossBot::farm) showed that five such builds of ab3 score 37-48 of 70 on party maps. These twins
measure the same build-to-build noise on every map, locally and on the lab, so a single build's
score can be read against its family's spread.
"""
import sys
from pathlib import Path

src = Path(sys.argv[1]) / "src"
k = int(sys.argv[2])
f = src / "bot.h"
t = f.read_text()
old = "    void play_turn() {\n"
if t.count(old) != 1:
    sys.exit("bot.h: play_turn not found once")
t = t.replace(old, old + f"        {{ volatile int twin = 0; for (int i = 0; i < {k}; ++i) twin = twin + i; }}  // mktwin.py: fuel only\n")
f.write_text(t)
print("patched", src, "K", k)
