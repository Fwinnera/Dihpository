#!/usr/bin/env python3
"""mkroster.py SRC_BOT DST_BOT PICK [BASE=ia|v183]: PICK takes Tavi's (fourth) draft slot on ordinary maps; Tavi drops
to sixth. Casters (prism, stellar) get a Focus build and Focus/Health Power scaling."""
import shutil, sys
from pathlib import Path
src, dst, pick = sys.argv[1], sys.argv[2], sys.argv[3]
W = Path("/home/user/ws5/bots")
if (W / dst).exists(): sys.exit(f"{dst} exists")
(W / dst).mkdir()
shutil.copytree(W / src / "src", W / dst / "src")
S = W / dst / "src"
def sub(name, old, new):
    p = S / name; t = p.read_text()
    assert t.count(old) == 1, (name, old[:70], t.count(old))
    p.write_text(t.replace(old, new))
old = "order = {D::varg, D::vendetta, D::vesper_vale, D::tavi, D::marcella, D::willow, D::ryth, D::cassi_and_issac, D::ren, D::stellar, D::prism, D::heart_of_ruin};"
rest = [c for c in ["marcella", "tavi", "willow", "ryth", "cassi_and_issac", "ren", "stellar", "prism", "heart_of_ruin"] if c != pick]
new = "order = {D::varg, D::vendetta, D::vesper_vale, D::" + pick + ", " + ", ".join("D::" + c for c in rest) + "};"
sub("draft.h", old, new)
if pick in ("prism", "stellar"):
    sub("config.h", "    if (type == bc::champion_type::vesper_vale)\n",
        f"    if (type == bc::champion_type::{pick})\n"
        "        return {I::monster_shard_of_focus, I::durability_shard_of_health, I::jungle_shard_of_focus};\n"
        "    if (type == bc::champion_type::vesper_vale)\n")
    sub("bot.h",
        "                    scaling_item = health_gain > damage_gain ? bc::item_type::power_shard_of_health\n"
        "                                                             : bc::item_type::power_shard_of_strength;\n",
        "                    scaling_item = health_gain > damage_gain ? bc::item_type::power_shard_of_health\n"
        "                                                             : bc::item_type::power_shard_of_strength;\n"
        f"                    if (me.champion_name() == bc::champion_type::{pick})\n"
        "                        scaling_item = D(stats.health_growth) * D(me.focus()) > D(stats.focus_growth) * D(me.max_health())\n"
        "                                           ? bc::item_type::power_shard_of_health : bc::item_type::power_shard_of_focus;\n")
print(dst, "pick", pick)
