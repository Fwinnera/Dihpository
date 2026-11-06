#!/usr/bin/env python3
"""Maps with very many camp groups: rank only the nearest (2026-11-06, CLOUD; engine 3.0.0 maps).

04gem-caverns (new in the 128-map pool) has over a hundred single-camp groups (7 gems, 0 strength). v166 and
its whole lineage score 0 gems there in every game (0 of 4 ranked games, 0-0 locally): every turn starts
with 40,000-66,000 fuel and strategy::choose_group's ranking pass over all groups spends it before an
objective is chosen, so the turn bails out (turn::Replan) and the next one starts the same pass again, for
2,000 rounds.

On maps with more than MANY_GROUPS groups, the ranking pass first keeps the MANY_KEEP groups nearest by
straight-line distance (one cheap pass, std::nth_element) and ranks only those. Maps with at most MANY_GROUPS
groups run v166's code apart from one size comparison per call.

    mkmany.py BOTDIR [MANY_GROUPS=64] [MANY_KEEP=32]
"""
import sys
from pathlib import Path

src = Path(sys.argv[1]) / "src"
P = dict(MANY_GROUPS="64", MANY_KEEP="32")
P.update(dict(a.split("=", 1) for a in sys.argv[2:]))


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
    ("    std::vector<Ranked> ranked;\n    for (std::size_t i = 0; i < metadata.size(); ++i) {\n"
     "        if (i % 8 == 0) turn::check();\n        const auto& objective = metadata[i];\n",
     "    std::vector<Ranked> ranked;\n"
     "    // mkmany.py: on maps with very many groups the full ranking pass costs more fuel than a turn has.\n"
     f"    std::vector<std::size_t> many_pick;\n"
     f"    if (metadata.size() > {P['MANY_GROUPS']}) {{\n"
     "        std::vector<std::pair<int, std::size_t>> near;\n"
     "        near.reserve(metadata.size());\n"
     "        for (std::size_t i = 0; i < metadata.size(); ++i) {\n"
     "            int gap = 10000;\n"
     "            for (const auto& [px, py] : metadata[i]->coords) gap = std::min(gap, std::max(std::abs(x - px), std::abs(y - py)));\n"
     "            near.emplace_back(gap, i);\n"
     "        }\n"
     f"        const std::size_t keep = std::min<std::size_t>({P['MANY_KEEP']}, near.size());\n"
     "        std::nth_element(near.begin(), near.begin() + static_cast<std::ptrdiff_t>(keep - 1), near.end());\n"
     "        for (std::size_t k = 0; k < keep; ++k) many_pick.push_back(near[k].second);\n"
     "    }\n"
     "    const std::size_t rank_n = many_pick.empty() ? metadata.size() : many_pick.size();\n"
     "    for (std::size_t j = 0; j < rank_n; ++j) {\n"
     "        const std::size_t i = many_pick.empty() ? j : many_pick[j];\n"
     "        if (j % 8 == 0) turn::check();\n        const auto& objective = metadata[i];\n"),
])
print("patched", src, P)
