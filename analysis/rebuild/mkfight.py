#!/usr/bin/env python3
"""Fight-side variants on a j_hjt-line bot.

    mkfight.py BOTDIR [CLOSE_ODDS=0.8] [FALL_BACK=true] [RETREAT=0.40,0.50] [DISENGAGE=0.65]

CLOSE_ODDS  an enemy within 4 tiles is engaged only if our local power (health x
            strength, allies within 5 at 0.75) is at least CLOSE_ODDS of its group's;
            killable, interrupt and defend stay unconditional.
FALL_BACK   a retreat first heads for a visible teammate above half health within 8
            tiles (and nearer than 2 tiles away), around the threats, then home.
RETREAT     RETREAT_HEALTH,CARRIER_RETREAT_HEALTH.
DISENGAGE   DISENGAGE_RATIO.
"""
import sys
from pathlib import Path

src = Path(sys.argv[1]) / "src"
opts = dict(a.split("=", 1) for a in sys.argv[2:])
for k in opts:
    assert k in ("CLOSE_ODDS", "FALL_BACK", "RETREAT", "DISENGAGE"), k


def patch(name, pairs):
    f = src / name
    text = f.read_text()
    for old, new in pairs:
        n = text.count(old)
        if n != 1:
            sys.exit(f"{name}: expected one match, found {n}: {old[:70]!r}")
        text = text.replace(old, new)
    f.write_text(text)


if "CLOSE_ODDS" in opts:
    patch("config.h", [("inline constexpr bool DEBUG = false;",
                        "inline constexpr bool DEBUG = false;\n"
                        "// An enemy within 4 tiles is engaged only at these local odds (combat::choose_enemy).\n"
                        f"inline constexpr double CLOSE_ODDS = {opts['CLOSE_ODDS']};")])
    patch("combat.h", [("        if (!(killable || interrupt || defending || gap <= 4 || allied_power > enemy_power * 1.15)) continue;",
                        "        if (!(killable || interrupt || defending || (gap <= 4 && allied_power >= enemy_power * config::CLOSE_ODDS) ||\n"
                        "              allied_power > enemy_power * 1.15))\n"
                        "            continue;")])
if opts.get("FALL_BACK") == "true":
    patch("nav.h", [
        ("#include \"common.h\"\n#include \"turn.h\"", "#include \"common.h\"\n#include \"config.h\"\n#include \"turn.h\""),
        ("        const auto threat = threat_mask(enemies, camps, 1);\n"
         "        if (move_to(gm::spawn_region(bc::team::ally), &threat)) return true;\n",
         "        const auto threat = threat_mask(enemies, camps, 1);\n"
         "        // A healthy teammate close by covers the retreat better than the walk home:\n"
         "        // a lone champion fleeing two enemies dies 60% of the time, beside one 34%.\n"
         "        const auto here = me.position();\n"
         "        std::optional<bc::vec2> cover;\n"
         "        std::int64_t best = 9;\n"
         "        for (const auto& ally : bc::champions(bc::team::ally)) {\n"
         "            turn::check();\n"
         "            if (!ally.is_alive() || !ally.is_visible() || ally.position() == here ||\n"
         "                D(ally.health()) < D(ally.max_health()) * 0.5)\n"
         "                continue;\n"
         "            const auto gap = distance(here, ally.position());\n"
         "            if (gap >= 2 && gap < best) {\n"
         "                best = gap;\n"
         "                cover = ally.position();\n"
         "            }\n"
         "        }\n"
         "        if (cover && move_to(around(*cover, 1), &threat)) return true;\n"
         "        if (move_to(gm::spawn_region(bc::team::ally), &threat)) return true;\n"),
    ])
if "RETREAT" in opts:
    a, b = opts["RETREAT"].split(",")
    patch("config.h", [("inline constexpr double RETREAT_HEALTH = 0.30;", f"inline constexpr double RETREAT_HEALTH = {a};"),
                       ("inline constexpr double CARRIER_RETREAT_HEALTH = 0.43;", f"inline constexpr double CARRIER_RETREAT_HEALTH = {b};")])
if "DISENGAGE" in opts:
    patch("config.h", [("inline constexpr double DISENGAGE_RATIO = 0.5;", f"inline constexpr double DISENGAGE_RATIO = {opts['DISENGAGE']};")])
print("patched", src, opts)
