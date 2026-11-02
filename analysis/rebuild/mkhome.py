#!/usr/bin/env python3
"""Trips home priced by the walk back, on a j_hjt-line bot.

    mkhome.py BOTDIR [NAME=VALUE ...]   # BANK_RESET, HEAL_NEAR, HEAL_FAR, SHOP_PER_STEP

BANK_RESET    back at spawn with less than a full bag: drop a banking decision made
              somewhere else (deposit_before_camp's "the altar is nearer than the camp").
HEAL_NEAR     heal-recall below HEAL_RECALL only within this many steps of home,
HEAL_FAR      or below this fraction of max health anywhere.
SHOP_PER_STEP shop-recall needs SHOP_GOLD plus this much gold per step of the walk back.
"""
import sys
from pathlib import Path

src = Path(sys.argv[1]) / "src"
opts = {"BANK_RESET": "true", "HEAL_NEAR": "15", "HEAL_FAR": "0.45", "SHOP_PER_STEP": "4"}
for a in sys.argv[2:]:
    k, v = a.split("=", 1)
    assert k in opts, k
    opts[k] = v


def patch(name, pairs):
    f = src / name
    text = f.read_text()
    for old, new in pairs:
        n = text.count(old)
        if n != 1:
            sys.exit(f"{name}: expected one match, found {n}: {old[:70]!r}")
        text = text.replace(old, new)
    f.write_text(text)


patch("config.h", [(
    "inline constexpr bool DEBUG = false;",
    "inline constexpr bool DEBUG = false;\n"
    "// Trips home are priced by the walk back (bot.h, home_steps). A banking decision\n"
    "// made in the field is dropped back at spawn with less than a full bag; heal-recall\n"
    "// needs home within HEAL_NEAR steps unless health is below HEAL_FAR; shop-recall\n"
    "// needs SHOP_PER_STEP more gold for every step of the walk back.\n"
    f"inline constexpr bool BANK_RESET = {opts['BANK_RESET']};\n"
    f"inline constexpr int HEAL_NEAR = {opts['HEAL_NEAR']};\n"
    f"inline constexpr double HEAL_FAR = {opts['HEAL_FAR']};\n"
    f"inline constexpr std::uint32_t SHOP_PER_STEP = {opts['SHOP_PER_STEP']};",
)])

patch("bot.h", [
    ("    std::optional<bc::distance_field> altar_field;\n",
     "    std::optional<bc::distance_field> altar_field;\n"
     "    std::optional<bc::distance_field> home_field;\n"),
    ("    ObjectivePtr held_at(bc::vec2 p) const {",
     "    // Steps from here back out to this point after a recall: the walk a trip home costs.\n"
     "    int home_steps(const bc::champion& me) {\n"
     "        if (!home_field) {\n"
     "            home_field.emplace();\n"
     "            bc::bitboard ignored;\n"
     "            home_field->compute(nav::static_walls(), gm::spawn_region(bc::team::ally) & ~nav::static_walls(), ignored);\n"
     "        }\n"
     "        return std::min(200, static_cast<int>(home_field->get(me.position())));\n"
     "    }\n\n"
     "    ObjectivePtr held_at(bc::vec2 p) const {"),
    ("        const bool at_spawn = gm::spawn_region(bc::team::ally).is_set(me.position());\n",
     "        const bool at_spawn = gm::spawn_region(bc::team::ally).is_set(me.position());\n"
     "        if (config::BANK_RESET && at_spawn && banking && me.gem_count() < static_cast<std::uint32_t>(config::BANK_GEMS)) {\n"
     "            banking = false;\n"
     "            bank_progress.reset();\n"
     "        }\n"),
    ("        if (!policy::party() && !at_spawn && D(me.health()) < D(me.max_health()) * config::HEAL_RECALL &&\n"
     "            !held_at(me.position()) && recall_safe(me, enemies, camps)) {",
     "        if (!policy::party() && !at_spawn && D(me.health()) < D(me.max_health()) * config::HEAL_RECALL &&\n"
     "            (home_steps(me) <= config::HEAL_NEAR || D(me.health()) < D(me.max_health()) * config::HEAL_FAR) &&\n"
     "            !held_at(me.position()) && recall_safe(me, enemies, camps)) {"),
    ("        if (!at_spawn && me.gold_count() >= config::SHOP_GOLD &&\n",
     "        if (!at_spawn && me.gold_count() >= config::SHOP_GOLD + config::SHOP_PER_STEP * static_cast<std::uint32_t>(home_steps(me)) &&\n"),
])
print("patched", src, opts)
