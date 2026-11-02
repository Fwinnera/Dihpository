#!/usr/bin/env python3
"""Opening preference for our own half, on a j_hjt-line bot (strategy::choose_group).

    mkhalf.py BOTDIR [NAME=VALUE ...]    # HALF_ROUNDS, HALF_MARGIN, HALF_COST

Before round HALF_ROUNDS a group whose nearest spawn tile is not at least HALF_MARGIN
steps nearer our spawn than the enemy's costs HALF_COST rounds per step short of that.
"""
import sys
from pathlib import Path

src = Path(sys.argv[1]) / "src"
opts = {"HALF_ROUNDS": "150", "HALF_MARGIN": "6", "HALF_COST": "3"}
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
    "// Opening on our own half: before HALF_ROUNDS, a group not at least HALF_MARGIN steps\n"
    "// nearer our spawn than the enemy's costs HALF_COST rounds per step short of that.\n"
    f"inline constexpr std::int64_t HALF_ROUNDS = {opts['HALF_ROUNDS']};\n"
    f"inline constexpr int HALF_MARGIN = {opts['HALF_MARGIN']};\n"
    f"inline constexpr double HALF_COST = {opts['HALF_COST']};",
)])

patch("strategy.h", [
    ("inline bool should_bank(bool enemies_seen, int altar_distance) {",
     "// Steps from a group to the enemy's spawn minus steps to ours, by straight-line\n"
     "// (Chebyshev) distance between nearest tiles. Static, so cached per handle.\n"
     "inline int half_margin(const Objective& o) {\n"
     "    static std::map<int, int> cache;\n"
     "    const auto it = cache.find(o.handle);\n"
     "    if (it != cache.end()) return it->second;\n"
     "    const auto ours = gm::spawn_region(bc::team::ally).positions();\n"
     "    const auto theirs = gm::spawn_region(bc::team::enemy).positions();\n"
     "    std::int64_t a = std::numeric_limits<std::int64_t>::max(), b = a;\n"
     "    for (const auto p : o.positions) {\n"
     "        for (const auto q : ours) a = std::min(a, distance(p, q));\n"
     "        for (const auto q : theirs) b = std::min(b, distance(p, q));\n"
     "    }\n"
     "    const int margin = ours.empty() || theirs.empty() ? 1000 : static_cast<int>(b - a);\n"
     "    cache[o.handle] = margin;\n"
     "    return margin;\n"
     "}\n\n"
     "inline bool should_bank(bool enemies_seen, int altar_distance) {"),
    ("        if (current && handle == *current) bias -= 5;\n",
     "        if (current && handle == *current) bias -= 5;\n"
     "        if (now < config::HALF_ROUNDS) {\n"
     "            turn::check();\n"
     "            const int short_by = config::HALF_MARGIN - half_margin(*objective);\n"
     "            if (short_by > 0) bias += short_by * config::HALF_COST * 100 / std::max(1.0, objective->gems + objective->gold * 0.3);\n"
     "        }\n"),
])
print("patched", src, opts)
