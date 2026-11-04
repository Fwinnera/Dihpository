#!/usr/bin/env python3
"""Late-game item: Bruiser shards of strength instead of the Power health/strength balance (2026-11-04, CLOUD).

Top UK teams farm 25.8 monster damage per living champion-round against our 18.1 (decoded replays), building
about 2:1 strength to health with Bruiser emblems (5 strength + 1 health + 1 focus point for 150 gold; Power
gives 6). After the three passive emblems our shop maximises health x strength with Power shards.

    mkbuild.py BOTDIR [ITEM=bruiser_shard_of_strength]
"""
import sys
from pathlib import Path

src = Path(sys.argv[1]) / "src"
item = dict(a.split("=", 1) for a in sys.argv[2:]).get("ITEM", "bruiser_shard_of_strength")
f = src / "bot.h"
t = f.read_text()
old = ("                    scaling_item = health_gain > damage_gain ? bc::item_type::power_shard_of_health\n"
       "                                                             : bc::item_type::power_shard_of_strength;\n")
assert t.count(old) == 1
f.write_text(t.replace(old, f"                    (void)health_gain; (void)damage_gain;\n                    scaling_item = bc::item_type::{item};\n"))
print("patched", src, item)
