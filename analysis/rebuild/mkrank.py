#!/usr/bin/env python3
"""Rank camp groups by walking distance, not straight-line distance (2026-11-06, CLOUD; engine 3.0.0 maps).

04sanctum (new with engine 3.0.0, 128-map pool) is a labyrinth of concentric ring walls with twelve rich
groups that do not fight back (14-28 gems each) around the single central altar. v166 collected 4 gems in
2,000 rounds there (0 of 12 local games); next_trial took 1,000+. strategy::choose_group ranks every group by
an estimate whose travel term is the Chebyshev distance, then scores candidates exactly (walking distance from
nav::field_from) in that order until its fuel reserve is reached: on a maze the first candidates are groups
just across a wall, and all five champions chose the same 4-gem group nine tiles away through the wall and
paced the corridors for the rest of the game.

The fix computes nav::field_from before the ranking pass (it is computed, and cached, right after it anyway)
and uses walking distance in the estimate; unreachable groups rank last. On open maps walking and Chebyshev
distance mostly agree.

    mkrank.py BOTDIR
"""
import sys
from pathlib import Path

src = Path(sys.argv[1]) / "src"


def patch(name, olds):
    f = src / name
    text = f.read_text()
    for old, new in olds:
        n = text.count(old)
        if n != 1:
            sys.exit(f"{name}: expected one match, found {n}: {old[:70]!r}")
        text = text.replace(old, new)
    f.write_text(text)


patch("strategy.h", [
    ("    std::vector<Ranked> ranked;\n    for (std::size_t i = 0; i < metadata.size(); ++i) {\n",
     "    std::vector<Ranked> ranked;\n"
     "    // mkrank.py: walking distance for the ranking too (the flood is cached for the exact pass below).\n"
     "    const auto& walk = nav::field_from(position);\n"
     "    for (std::size_t i = 0; i < metadata.size(); ++i) {\n"),
    ("        int travel = 10000;\n"
     "        for (const auto& [px, py] : objective->coords) {\n"
     "            const int gap = std::max(std::abs(x - px), std::abs(y - py));\n"
     "            if (gap < travel) travel = gap;\n"
     "        }\n",
     "        int travel = 10000;\n"
     "        for (const auto p : objective->positions)\n"
     "            if (walk.reached.is_set(p)) travel = std::min(travel, walk.costs.get(p));\n"),
])
print("patched", src)
