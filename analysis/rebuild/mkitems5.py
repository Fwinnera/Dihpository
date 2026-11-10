#!/usr/bin/env python3
"""mkitems5.py SRC DST [SK=4|1|0] [GREED=0|1]: item builds for Patch 4.0.0 (engine 5.0.x).

Patch 4.0.0 doubled the Skirmish Emblem (10% more damage to champions, was 5%) and raised Greed
(25 shards, 750 gold, now give 40 shards of stats, was 35). Read from the engine with
ws5/bots/probe_i5: Power emblem 6 points; Skirmish 5 points + 10% champion damage; Greed 40 points
for 25 shards; there is no item cap.

SK=4      Skirmish (strength) as the fourth emblem, in place of the first Power emblem: one stat
          point for 10% more champion damage for the rest of the game.
SK=1      Skirmish first and Hunter fourth.
GREED=1   after the fixed build, a champion standing in the shop with 750 gold or more and no Power
          emblem half-bought buys a whole Greed emblem (25 shards, 40 points) of the stat the Power rule
          would have picked, instead of five Power emblems (30 points). Below 750 it buys Power as before,
          so a poor champion's purchases are unchanged.

Willow's build is unchanged. Copies SRC to DST first (src/ only).
"""
import shutil
import sys
from pathlib import Path

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
opts = dict(a.split("=", 1) for a in sys.argv[3:])
sk = int(opts.get("SK", "4"))
greed = int(opts.get("GREED", "0"))

if dst.exists():
    sys.exit(f"{dst} exists")
dst.mkdir(parents=True)
shutil.copytree(src / "src", dst / "src")

cfg = dst / "src" / "config.h"
s = cfg.read_text()
old = "    return {I::hunter_shard_of_strength, I::durability_shard_of_health, I::jungle_shard_of_strength};\n"
assert s.count(old) == 1, "build anchor not found"
if sk == 4:
    new = ("    // mkitems5 SK=4: Skirmish (10% champion damage since Patch 4.0.0) in place of the first Power emblem.\n"
           "    return {I::hunter_shard_of_strength, I::durability_shard_of_health, I::jungle_shard_of_strength,\n"
           "            I::skirmish_shard_of_strength};\n")
elif sk == 1:
    new = ("    // mkitems5 SK=1: Skirmish first (10% champion damage since Patch 4.0.0), Hunter fourth.\n"
           "    return {I::skirmish_shard_of_strength, I::durability_shard_of_health, I::jungle_shard_of_strength,\n"
           "            I::hunter_shard_of_strength};\n")
else:
    new = old
s = s.replace(old, new)
cfg.write_text(s)

if greed:
    bot = dst / "src" / "bot.h"
    b = bot.read_text()
    anchor = ("            } else {\n"
              "                // Finish the current emblem before comparing the next purchase.\n")
    assert b.count(anchor) == 1, "shop anchor not found"
    insert = (
        "            } else if (purchase_index % 5 == 0 && me.gold_count() >= 750) {\n"
        "                // mkitems5 GREED: a whole Greed emblem (25 shards, 750 gold) gives 40 points against\n"
        "                // five Power emblems' 30. Same stat rule as Power; bought only when affordable at once.\n"
        "                const auto stats = me.base_stats();\n"
        "                const double health_gain = D(stats.health_growth) * D(me.strength());\n"
        "                const double damage_gain = D(stats.strength_growth) * D(me.max_health());\n"
        "                const auto greed_item = health_gain > damage_gain ? bc::item_type::greed_shard_of_health\n"
        "                                                                  : bc::item_type::greed_shard_of_strength;\n"
        "                if (!me.can_buy(greed_item, 25)) break;\n"
        "                turn::check();\n"
        "                me.buy(greed_item, 25);\n"
        "                purchase_index += 25;\n"
        "                last_purchase = bc::round_number();\n"
        "                continue;\n"
    )
    b = b.replace(anchor, insert + anchor)
    bot.write_text(b)

print(f"{dst}: SK={sk} GREED={greed}")
