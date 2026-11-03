#!/usr/bin/env python3
"""Home field (ab3-line bot): play more carefully the deeper a champion stands in enemy territory.

    mkhf.py BOTDIR [ENGAGE=1] [GAP=5] [RETREAT=0.2] [DISENGAGE=0.3] [DEPTH=0.5]

Why (GROUND-UP-PLAN.md, "Where our champions die"): on the ladder our champions die in the enemy
half 5.1 times a game against the field's 1.65 in ours, though both sides clear 13% of their
camps there. Profiled locally (deepwhy.py), they cross the middle at full health (travel 41%, a
chase in combat 29%), fight in 30% of their turns over there (6% at home) and die retreating (81%)
on the long walk home, against enemies who heal 100% a round on a spawn nearby.

Depth = steps to our spawn / (steps to ours + steps to theirs), Chebyshev; deep = how far past
DEPTH, scaled 0..1. Past the middle, and never on party maps:
  ENGAGE     1: no fight is opened just because an enemy is within 4 tiles; only a kill in
             reach, an interrupted deposit, a defence or local odds of 1.15 open one.
  GAP        do not pursue an enemy within GAP tiles of its spawn (0 = only on it, as before).
  RETREAT    the retreat threshold rises by RETREAT x deep (of max health).
  DISENGAGE  the disengage ratio rises by DISENGAGE x deep.
"""
import sys
from pathlib import Path

src = Path(sys.argv[1]) / "src"
opts = dict(a.split("=", 1) for a in sys.argv[2:])
engage = int(opts.get("ENGAGE", 1))
gap = int(opts.get("GAP", 5))
retreat = float(opts.get("RETREAT", 0.2))
disengage = float(opts.get("DISENGAGE", 0.3))
depth = float(opts.get("DEPTH", 0.5))


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
                    "// Home field (analysis/rebuild/mkhf.py): care past the middle of the map.\n"
                    f"inline constexpr double HF_DEPTH = {depth};\n"
                    f"inline constexpr bool HF_ENGAGE = {'true' if engage else 'false'};\n"
                    f"inline constexpr std::int64_t HF_SPAWN_GAP = {gap};\n"
                    f"inline constexpr double HF_RETREAT = {retreat};\n"
                    f"inline constexpr double HF_DISENGAGE = {disengage};")])

patch("combat.h", [
    ("const std::vector<bc::champion>& allies, bool defending = false) {",
     "const std::vector<bc::champion>& allies, bool defending = false,\n"
     "                                                bool cautious = false) {"),
    ("        if (!(killable || interrupt || defending || gap <= 4 || allied_power > enemy_power * 1.15)) continue;",
     "        if (!(killable || interrupt || defending || (gap <= 4 && !cautious) || allied_power > enemy_power * 1.15)) continue;"),
])

patch("bot.h", [
    ("        const auto position = me.position();\n",
     "        const auto position = me.position();\n"
     "        // Home field: how far past the middle we stand toward the enemy spawn (0..1).\n"
     "        double deep = 0;\n"
     "        if (!policy::party()) {\n"
     "            std::int64_t own = 1 << 20, foe = 1 << 20;\n"
     "            for (const auto p : gm::spawn_region(bc::team::ally).positions()) own = std::min(own, distance(p, position));\n"
     "            for (const auto p : gm::spawn_region(bc::team::enemy).positions()) foe = std::min(foe, distance(p, position));\n"
     "            const double depth = D(own) / std::max(1.0, D(own + foe));\n"
     "            deep = std::max(0.0, depth - config::HF_DEPTH) / (1.0 - config::HF_DEPTH);\n"
     "        }\n"),
    ("        const double retreat_at = std::max(D(me.max_health()) * threshold, camp_pressure * 2 + D(me.max_health()) * 0.08);",
     "        const double retreat_at = std::max(D(me.max_health()) * (threshold + config::HF_RETREAT * deep),\n"
     "                                           camp_pressure * 2 + D(me.max_health()) * 0.08);"),
    ("            const double leave = config::DISENGAGE_RATIO + (disengaging ? config::DISENGAGE_HYSTERESIS : 0);",
     "            const double leave = config::DISENGAGE_RATIO + (disengaging ? config::DISENGAGE_HYSTERESIS : 0) +\n"
     "                                 config::HF_DISENGAGE * deep;"),
    ("            if (enemy_spawn.is_set(e.position())) continue;\n",
     "            if (enemy_spawn.is_set(e.position())) continue;\n"
     "            if (deep > 0 && config::HF_SPAWN_GAP > 0) {\n"
     "                std::int64_t home = 1 << 20;\n"
     "                for (const auto p : enemy_spawn.positions()) home = std::min(home, distance(p, e.position()));\n"
     "                if (home <= config::HF_SPAWN_GAP) continue;\n"
     "            }\n"),
    ("        const auto target = combat::choose_enemy(pursuit, team->allies);",
     "        const auto target = combat::choose_enemy(pursuit, team->allies, false, config::HF_ENGAGE && deep > 0);"),
])
print("patched", src, opts)
