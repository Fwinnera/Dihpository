#!/usr/bin/env python3
"""Company: avoid farming alone where the ladder kills us (2026-11-04, CLOUD).

Ladder evidence (lab set 1 and the decoded replays): per 1,000 champion turns we die within 10 turns 4 times
while travelling at home but 10-11 times in the middle or the enemy half, and 7 vs 17-18 while farming.
Our champions have no teammate within 5 for 57% of their turns (ladder teams 42%), and one teammate within 5
cuts our death rate in a fight by a third.

In strategy::choose_group, a camp group whose nearest tile is at least COMPANY_DEPTH of the way from our
spawn to theirs, with no teammate within COMPANY_RADIUS of it (alive and visible there now, or claiming a
group whose tiles are within COMPANY_RADIUS), costs COMPANY_ROUNDS more rounds in the score.

    mkcompany.py BOTDIR [COMPANY_ROUNDS=25] [COMPANY_DEPTH=0.4] [COMPANY_RADIUS=6]
"""
import sys
from pathlib import Path

src = Path(sys.argv[1]) / "src"
P = dict(COMPANY_ROUNDS="25", COMPANY_DEPTH="0.4", COMPANY_RADIUS="6")
P.update(dict(a.split("=", 1) for a in sys.argv[2:]))


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
    "inline constexpr bool DEBUG = false;\n",
    "inline constexpr bool DEBUG = false;\n"
    "// Company (mkcompany.py): a group in contested ground with no teammate near it costs more rounds.\n"
    f"inline constexpr double COMPANY_ROUNDS = {P['COMPANY_ROUNDS']};\n"
    f"inline constexpr double COMPANY_DEPTH = {P['COMPANY_DEPTH']};\n"
    f"inline constexpr int COMPANY_RADIUS = {P['COMPANY_RADIUS']};\n",
)])

patch("strategy.h", [
    # Teammates' positions and claimed groups' tiles, once per call.
    ("    ObjectivePtr best;\n    double best_score = std::numeric_limits<double>::infinity();\n    bool best_opens = false;\n",
     "    std::vector<bc::vec2> company;\n"
     "    if (config::COMPANY_ROUNDS > 0) {\n"
     "        for (std::size_t i = 0; i < team.allies.size(); ++i) {\n"
     "            if (static_cast<int>(i) == team.slot) continue;\n"
     "            const auto& ally = team.allies[i];\n"
     "            if (!ally.is_alive()) continue;\n"
     "            if (ally.is_visible()) company.push_back(ally.position());\n"
     "            if (i < claims.size() && claims[i] >= 0)\n"
     "                for (const auto& o : metadata)\n"
     "                    if (o->handle == claims[i])\n"
     "                        for (const auto& [px, py] : o->coords) company.push_back(bc::vec2{px, py});\n"
     "        }\n"
     "    }\n"
     "    const auto& own_spawn = gm::spawn_region(bc::team::ally);\n"
     "    const auto& their_spawn = gm::spawn_region(bc::team::enemy);\n"
     "    ObjectivePtr best;\n    double best_score = std::numeric_limits<double>::infinity();\n    bool best_opens = false;\n"),
    # The penalty, inside the score's time sum.
    ("        double score = (travel + clear + capture + risk + wear) * 100 / std::max(1.0, value) + row.bias;\n",
     "        double solo = 0;\n"
     "        if (config::COMPANY_ROUNDS > 0) {\n"
     "            static std::map<int, double> depth_of;\n"
     "            auto dt = depth_of.find(objective->handle);\n"
     "            if (dt == depth_of.end()) {\n"
     "                static const auto own_tiles = own_spawn.positions();\n"
     "                static const auto their_tiles = their_spawn.positions();\n"
     "                std::int64_t a = 1000, b = 1000;\n"
     "                for (const auto& [px, py] : objective->coords) {\n"
     "                    for (const auto q : own_tiles) a = std::min<std::int64_t>(a, distance(bc::vec2{px, py}, q));\n"
     "                    for (const auto q : their_tiles) b = std::min<std::int64_t>(b, distance(bc::vec2{px, py}, q));\n"
     "                }\n"
     "                dt = depth_of.emplace(objective->handle, static_cast<double>(a) / std::max<std::int64_t>(1, a + b)).first;\n"
     "            }\n"
     "            if (dt->second >= config::COMPANY_DEPTH) {\n"
     "                bool accompanied = false;\n"
     "                for (const auto q : company) {\n"
     "                    for (const auto& [px, py] : objective->coords)\n"
     "                        if (distance(bc::vec2{px, py}, q) <= config::COMPANY_RADIUS) { accompanied = true; break; }\n"
     "                    if (accompanied) break;\n"
     "                }\n"
     "                if (!accompanied) solo = config::COMPANY_ROUNDS;\n"
     "            }\n"
     "        }\n"
     "        double score = (travel + clear + capture + risk + wear + solo) * 100 / std::max(1.0, value) + row.bias;\n"),
])
print("patched", src, P)
