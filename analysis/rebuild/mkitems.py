#!/usr/bin/env python3
"""Item builds (ab3-line bot): the field's families instead of ours.

    mkitems.py BOTDIR [SCALE=power|bruiser] [EXTRA=none|prospector|capture|treasure]

Why (GROUND-UP-PLAN.md, "UK-level teams"): the teams at the UK top-8 line buy Bruiser shards for
half their stats (QS2isLaw 58%, policy wonk 46%) plus economy emblems (Prospector 10-11%,
Capture 8%, Treasure 10%); we buy Power for 71% and no economy emblem besides Hunter. Our earlier
item tests were judged head to head against our own lineage, which does not predict the lab.

SCALE=bruiser: after the three-emblem build, the scaling purchases (health or strength, by the
live health x damage rule) are Bruiser shards: an emblem is 5 of its stat plus 1 of each other
(7 points) instead of Power's 6. EXTRA adds a fourth emblem of that family before scaling, in
the champion's strength (Willow: focus): Prospector +25% cluster rewards, Capture 3-turn
captures, Treasure +10% gold.
"""
import sys
from pathlib import Path

src = Path(sys.argv[1]) / "src"
opts = dict(a.split("=", 1) for a in sys.argv[2:])
scale = opts.get("SCALE", "power")
extra = opts.get("EXTRA", "none")


def patch(name, pairs):
    f = src / name
    text = f.read_text()
    for old, new in pairs:
        n = text.count(old)
        if n != 1:
            sys.exit(f"{name}: expected one match, found {n}: {old[:70]!r}")
        text = text.replace(old, new)
    f.write_text(text)


if extra != "none":
    patch("config.h", [
        ("        return {I::jungle_shard_of_focus, I::durability_shard_of_health, I::power_shard_of_focus};\n"
         "    return {I::hunter_shard_of_strength, I::durability_shard_of_health, I::jungle_shard_of_strength};",
         f"        return {{I::jungle_shard_of_focus, I::durability_shard_of_health, I::{extra}_shard_of_focus, I::power_shard_of_focus}};\n"
         f"    return {{I::hunter_shard_of_strength, I::durability_shard_of_health, I::jungle_shard_of_strength, I::{extra}_shard_of_strength}};"),
    ])
if scale == "bruiser":
    patch("bot.h", [
        ("                    scaling_item = health_gain > damage_gain ? bc::item_type::power_shard_of_health\n"
         "                                                             : bc::item_type::power_shard_of_strength;",
         "                    scaling_item = health_gain > damage_gain ? bc::item_type::bruiser_shard_of_health\n"
         "                                                             : bc::item_type::bruiser_shard_of_strength;"),
    ])
print("patched", src, opts)
