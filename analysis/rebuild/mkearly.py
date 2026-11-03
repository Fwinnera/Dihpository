#!/usr/bin/env python3
"""Early caution on a cHG-line bot: avoid even or worse fights before a round.

    mkearly.py BOTDIR [ROUNDS=150] [ODDS=1.0]

On v140's 220 ranked games the side that lost a champion first won 37-40% of the time
(we die first in 76 of our 110 losses). Before ROUNDS, on solo maps, a champion with a
visible enemy within 4 tiles and local power (health x strength, allies within 4 at 0.75)
below ODDS steps away toward spawn instead of opening a fight, unless one attack or cast
kills. Captures, banking and the ordinary disengage are unchanged.
"""
import sys
from pathlib import Path

src = Path(sys.argv[1]) / "src"
opts = {"ROUNDS": "150", "ODDS": "1.0"}
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
                    "// Early caution (bot.h; analysis/rebuild/mkearly.py): before EARLY_ROUNDS, step away\n"
                    "// from an enemy within 4 unless local power is at least EARLY_ODDS or a hit kills.\n"
                    f"inline constexpr std::int64_t EARLY_ROUNDS = {opts['ROUNDS']};\n"
                    f"inline constexpr double EARLY_ODDS = {opts['ODDS']};")])
patch("bot.h", [("        const auto target = combat::choose_enemy(pursuit, team->allies);\n        if (target) {\n",
                 "        if (static_cast<std::int64_t>(bc::round_number()) < config::EARLY_ROUNDS && !policy::party()) {\n"
                 "            const auto [ratio, threats] = combat::local_power(enemies, team->allies, 4);\n"
                 "            if (threats > 0 && ratio < config::EARLY_ODDS && !combat::finishing_blow(enemies)) {\n"
                 "                status(\"early-avoid\");\n"
                 "                objective = nullptr;\n"
                 "                team->claim();\n"
                 "                nav::retreat(enemies, camps);\n"
                 "                return;\n"
                 "            }\n"
                 "        }\n"
                 "        const auto target = combat::choose_enemy(pursuit, team->allies);\n        if (target) {\n")])
print("patched", src, opts)
