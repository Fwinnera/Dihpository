#!/usr/bin/env python3
"""Do not walk into an enemy group to farm (cHG-line bot, strategy::choose_group).

    mkdg.py BOTDIR [RADIUS=6] [ODDS=1.0] [COST=150]

Camp choice preferred a camp it could open before an enemy reached it, and charged at most
20 for an enemy standing on it; lone champions walked into enemy groups at contested camps
and died (lab losses to 1,700+ teams: 19-51 deaths). For each group, visible enemies within
RADIUS of it are weighed against us plus visible teammates within RADIUS of it (at 0.75),
by total health times total strength; where theirs exceeds ours x ODDS the group costs COST
more, so another group wins unless every one is covered.
"""
import sys
from pathlib import Path

src = Path(sys.argv[1]) / "src"
opts = {"RADIUS": "6", "ODDS": "1.0", "COST": "150"}
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
                    "// Covered groups (strategy::choose_group; analysis/rebuild/mkdg.py): enemy health x\n"
                    "// strength within DG_RADIUS above ours x DG_ODDS costs DG_COST.\n"
                    f"inline constexpr int DG_RADIUS = {opts['RADIUS']};\n"
                    f"inline constexpr double DG_ODDS = {opts['ODDS']};\n"
                    f"inline constexpr double DG_COST = {opts['COST']};")])
patch("strategy.h", [
    ("        if (reward) score = (travel + capture) * 100 / std::max(1.0, row.raw) - 15;\n",
     "        if (!enemies.empty()) {\n"
     "            double eh = 0, es = 0;\n"
     "            for (const auto& e : enemies) {\n"
     "                if (!e.is_visible() || !e.is_alive()) continue;\n"
     "                std::int64_t d = std::numeric_limits<std::int64_t>::max();\n"
     "                for (const auto p : positions) d = std::min(d, distance(p, e.position()));\n"
     "                if (d <= config::DG_RADIUS) {\n"
     "                    eh += D(e.health());\n"
     "                    es += std::max(1.0, D(e.strength()));\n"
     "                }\n"
     "            }\n"
     "            if (eh > 0) {\n"
     "                double oh = D(me.health()), os = std::max(1.0, D(me.strength()));\n"
     "                for (const auto& ally : team.allies) {\n"
     "                    if (same(ally, me) || !ally.is_alive() || !ally.is_visible()) continue;\n"
     "                    std::int64_t d = std::numeric_limits<std::int64_t>::max();\n"
     "                    for (const auto p : positions) d = std::min(d, distance(p, ally.position()));\n"
     "                    if (d <= config::DG_RADIUS) {\n"
     "                        oh += D(ally.health()) * 0.75;\n"
     "                        os += std::max(1.0, D(ally.strength())) * 0.75;\n"
     "                    }\n"
     "                }\n"
     "                if (eh * es > oh * os * config::DG_ODDS) score += config::DG_COST;\n"
     "            }\n"
     "        }\n"
     "        if (reward) score = (travel + capture) * 100 / std::max(1.0, row.raw) - 15;\n"),
])
print("patched", src, opts)
