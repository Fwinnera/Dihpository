#!/usr/bin/env python3
"""Opening radius on a j_hjt-line bot (strategy::choose_group): before OPEN_ROUNDS, a group
whose nearest spawn tile is more than OPEN_RADIUS steps (straight line) from our spawn
costs OPEN_COST extra rounds per step beyond it, so the near camps are cleared first and
their gold arrives early (02cuts: four champions walked 41 tiles to one camp while camps
7, 8, 17 and 20 tiles from spawn waited; first hits at rounds 52-71).

    mkopen.py BOTDIR [OPEN_ROUNDS=100] [OPEN_RADIUS=18] [OPEN_COST=2]
"""
import sys
from pathlib import Path

src = Path(sys.argv[1]) / "src"
opts = {"OPEN_ROUNDS": "100", "OPEN_RADIUS": "18", "OPEN_COST": "2"}
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
    "// Opening radius: before OPEN_ROUNDS, a group more than OPEN_RADIUS steps from our spawn\n"
    "// costs OPEN_COST rounds per step beyond it.\n"
    f"inline constexpr std::int64_t OPEN_ROUNDS = {opts['OPEN_ROUNDS']};\n"
    f"inline constexpr int OPEN_RADIUS = {opts['OPEN_RADIUS']};\n"
    f"inline constexpr double OPEN_COST = {opts['OPEN_COST']};",
)])

patch("strategy.h", [
    ("inline bool should_bank(bool enemies_seen, int altar_distance) {",
     "// Straight-line steps from a group's nearest spawn tile to our spawn region. Static.\n"
     "inline int home_gap(const Objective& o) {\n"
     "    static std::map<int, int> cache;\n"
     "    const auto it = cache.find(o.handle);\n"
     "    if (it != cache.end()) return it->second;\n"
     "    const auto home = gm::spawn_region(bc::team::ally).positions();\n"
     "    std::int64_t best = 1000;\n"
     "    for (const auto p : o.positions)\n"
     "        for (const auto q : home) best = std::min(best, distance(p, q));\n"
     "    cache[o.handle] = static_cast<int>(best);\n"
     "    return static_cast<int>(best);\n"
     "}\n\n"
     "inline bool should_bank(bool enemies_seen, int altar_distance) {"),
    ("        if (current && handle == *current) bias -= 5;\n",
     "        if (current && handle == *current) bias -= 5;\n"
     "        if (now < config::OPEN_ROUNDS) {\n"
     "            turn::check();\n"
     "            const int beyond = home_gap(*objective) - config::OPEN_RADIUS;\n"
     "            if (beyond > 0) bias += beyond * config::OPEN_COST * 100 / std::max(1.0, objective->gems + objective->gold * 0.3);\n"
     "        }\n"),
])
print("patched", src, opts)
