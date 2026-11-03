#!/usr/bin/env python3
"""Do not walk back to where we just died (cHG-line bot, strategy::choose_group).

    mkdanger.py BOTDIR [ROUNDS=120] [RADIUS=6] [COST=40]

In the lab losses to strong teams the same champions die 15-54 times a game, walking out of
spawn to the camps where the enemy team stands. Each champion remembers where it died; for
ROUNDS after a death, groups within RADIUS tiles of that spot cost COST extra rounds.
"""
import sys
from pathlib import Path

src = Path(sys.argv[1]) / "src"
opts = {"ROUNDS": "120", "RADIUS": "6", "COST": "40"}
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


patch("config.h", [("inline constexpr bool DEBUG = false;",
                    "inline constexpr bool DEBUG = false;\n"
                    "// Death zone (strategy::choose_group; analysis/rebuild/mkdanger.py): for DANGER_ROUNDS\n"
                    "// after a death, groups within DANGER_RADIUS of where we died cost DANGER_COST rounds.\n"
                    f"inline constexpr std::int64_t DANGER_ROUNDS = {opts['ROUNDS']};\n"
                    f"inline constexpr int DANGER_RADIUS = {opts['RADIUS']};\n"
                    f"inline constexpr double DANGER_COST = {opts['COST']};")])
patch("strategy.h", [
    ("inline ObjectivePtr choose_group(",
     "// Where this champion last died, and when (bot.h records it).\n"
     "inline bc::vec2 death_position{};\n"
     "inline std::int64_t death_round = -100000;\n\n"
     "inline ObjectivePtr choose_group("),
    ("        double bias = 0;\n",
     "        double bias = 0;\n"
     "        if (now - death_round < config::DANGER_ROUNDS) {\n"
     "            int near = 1000;\n"
     "            for (const auto& [px, py] : objective->coords)\n"
     "                near = std::min(near, std::max(std::abs(px - death_position.x), std::abs(py - death_position.y)));\n"
     "            if (near <= config::DANGER_RADIUS) bias += config::DANGER_COST;\n"
     "        }\n"),
])
patch("bot.h", [
    ("        shop(me);\n        if (!me.is_alive()) {\n",
     "        shop(me);\n"
     "        if (me.is_alive()) {\n"
     "            last_alive = me.position();\n"
     "            was_alive = true;\n"
     "        } else if (was_alive) {\n"
     "            was_alive = false;\n"
     "            strategy::death_position = last_alive;\n"
     "            strategy::death_round = static_cast<std::int64_t>(bc::round_number());\n"
     "        }\n"
     "        if (!me.is_alive()) {\n"),
    ("    void shop(bc::champion& me) {\n",
     "    bc::vec2 last_alive{};\n"
     "    bool was_alive = false;\n\n"
     "    void shop(bc::champion& me) {\n"),
])
print("patched", src, opts)
