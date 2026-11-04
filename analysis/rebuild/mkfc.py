#!/usr/bin/env python3
"""Farm, don't chase (ab3-line bot): leave the objective for an enemy only when the chase pays.

    mkfc.py BOTDIR [THREAT=1] [GATE=0]

Why (GROUND-UP-PLAN.md, "00lost_world"): on the ladder our team does no camp damage in the
first 150 rounds of 00lost_world (the winners bank 245 gems by then); profiled locally, every
champion flips between travel and combat every 1-5 rounds for 50+ rounds, walking toward an enemy
within 4 tiles whenever one appears and back toward its camp when it leaves, while the enemy
farms the central clusters. The combat branch moved toward any eligible enemy, so the farm
branch never ran.

With this patch the combat branch still attacks an enemy in reach, but only steps toward one
that is out of reach when the chase pays: it can be killed with what we have ready, it is
depositing gems, it can already hit us (THREAT=1), or our local odds are 1.15 or better (the
measure choose_enemy uses). Otherwise the turn falls through to farming. Party maps unchanged.
GATE=1 applies the rule only while the champion's objective is a harmless gem cluster group
(gems, no camp strength), as on 00lost_world; elsewhere it chases as before.
"""
import sys
from pathlib import Path

src = Path(sys.argv[1]) / "src"
opts = dict(a.split("=", 1) for a in sys.argv[2:])
threat = int(opts.get("THREAT", 1))
gate = int(opts.get("GATE", 0))


def patch(name, pairs):
    f = src / name
    text = f.read_text()
    for old, new in pairs:
        n = text.count(old)
        if n != 1:
            sys.exit(f"{name}: expected one match, found {n}: {old[:70]!r}")
        text = text.replace(old, new)
    f.write_text(text)


patch("config.h", [("inline constexpr bool DEBUG = false;",
                    "inline constexpr bool DEBUG = false;\n"
                    "// Farm, don't chase (analysis/rebuild/mkfc.py).\n"
                    "inline constexpr bool FC_CHASE = true;\n"
                    f"inline constexpr bool FC_THREAT = {'true' if threat else 'false'};\n"
                    f"inline constexpr bool FC_GATE = {'true' if gate else 'false'};")])

patch("combat.h", [(
    "// Our strength against the enemy champions within `radius` of this champion: the",
    "// fc (mkfc.py): whether stepping toward an enemy out of reach is worth leaving the objective.\n"
    "inline bool worth_chase(const bc::champion& target, const std::vector<bc::champion>& enemies,\n"
    "                        const std::vector<bc::champion>& allies) {\n"
    "    auto& me = bc::self();\n"
    "    if (target.is_submitting_gems() && target.gem_count() > 0) return true;\n"
    "    if (config::FC_THREAT && distance(me.position(), target.position()) <= target.attack_range() + 1) return true;\n"
    "    double burst = D(me.strength()) * 2;\n"
    "    for (const auto& a : me.abilities())\n"
    "        if (a.is_ready() && (a.is_damage() || a.is_cc() || a.is_aoe_damage()))\n"
    "            burst = std::max(burst, D(me.strength()) + D(a.damage_amount(target)));\n"
    "    if (D(target.health()) <= burst) return true;\n"
    "    double allied_power = D(me.health()) * std::max(1.0, D(me.strength()));\n"
    "    for (const auto& ally : allies)\n"
    "        if (!same(ally, me) && ally.is_alive() && ally.is_visible() && distance(ally.position(), target.position()) <= 5)\n"
    "            allied_power += D(ally.health()) * std::max(1.0, D(ally.strength())) * 0.75;\n"
    "    double enemy_power = 0;\n"
    "    for (const auto& e : enemies)\n"
    "        if (distance(e.position(), target.position()) <= 4) enemy_power += D(e.health()) * std::max(1.0, D(e.strength()));\n"
    "    return allied_power > enemy_power * 1.15;\n"
    "}\n\n"
    "// Our strength against the enemy champions within `radius` of this champion: the")])

patch("bot.h", [(
    "            if (combat::live(*target) && target->health() > 0) {\n"
    "                moved = nav::move_to(nav::around(target->position(), me.attack_range()));",
    "            if (combat::live(*target) && target->health() > 0 &&\n"
    "                (!config::FC_CHASE || policy::party() ||\n"
    "                 (config::FC_GATE && !(objective && objective->gems > 0 && objective->incoming <= 0)) ||\n"
    "                 combat::worth_chase(*target, pursuit, team->allies))) {\n"
    "                moved = nav::move_to(nav::around(target->position(), me.attack_range()));")])
print("patched", src, opts)
