#!/usr/bin/env python3
"""Opening rush on a tf1 tree (mkjoin.py applied): before round RUSH_ROUNDS, the
teammates within RUSH_NEAR that have no target yet count as joiners for every group,
so the first claim is priced for the whole team and the rest converge on it.

    mkrush.py BOTDIR [RUSH_ROUNDS=60] [RUSH_NEAR=4] [RUSH_DIST=1000]

RUSH_DIST caps the rush to groups within that many steps (straight line) of us.
"""
import sys
from pathlib import Path

src = Path(sys.argv[1]) / "src"
opts = {"RUSH_ROUNDS": "60", "RUSH_NEAR": "4", "RUSH_DIST": "1000"}
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
    "inline constexpr int JOIN_SLACK = ",
    "// Opening rush: before RUSH_ROUNDS, while no teammate has a target, price groups as\n"
    "// if the teammates within RUSH_NEAR will come too.\n"
    f"inline constexpr std::int64_t RUSH_ROUNDS = {opts['RUSH_ROUNDS']};\n"
    f"inline constexpr int RUSH_NEAR = {opts['RUSH_NEAR']};\n"
    f"inline constexpr int RUSH_DIST = {opts['RUSH_DIST']};\n"
    "inline constexpr int JOIN_SLACK = ",
)])

patch("strategy.h", [
    ("            auto& j = joined[claims[i]];\n            j.first += d;\n            ++j.second;\n        }\n",
     "            auto& j = joined[claims[i]];\n            j.first += d;\n            ++j.second;\n        }\n"
     "    double rush_dps = 0;\n    int rush_n = 0;\n"
     "    if (config::JOIN && now < config::RUSH_ROUNDS) {\n"
     "        // Teammates beside us without a target yet will follow a claim, so they\n"
     "        // count for every group; one that has a target counts for that group only.\n"
     "        for (std::size_t i = 0; i < team.allies.size(); ++i) {\n"
     "            if (static_cast<int>(i) == team.slot || (i < claims.size() && claims[i] >= 0)) continue;\n"
     "            turn::check();\n"
     "            const auto& ally = team.allies[i];\n"
     "            if (!ally.is_alive() || !ally.is_visible() || distance(ally.position(), position) > config::RUSH_NEAR) continue;\n"
     "            rush_dps += dps(ally, 2);\n"
     "            ++rush_n;\n"
     "        }\n"
     "    }\n"),
    # ranked pre-pass
    ("        if (!objective->monolith) {\n            const auto jt = joined.find(handle);\n"
     "            if (jt != joined.end()) {\n                join_dps = jt->second.first;\n                join_n = jt->second.second;\n            }\n        }\n",
     "        if (!objective->monolith) {\n            const auto jt = joined.find(handle);\n"
     "            if (jt != joined.end()) {\n                join_dps = jt->second.first;\n                join_n = jt->second.second;\n            }\n"
     "            if (travel <= config::RUSH_DIST) {\n                join_dps += rush_dps;\n                join_n += rush_n;\n            }\n        }\n"),
    # exact pass
    ("            // row.clear used every joiner; rescale to the ones that will be there.\n"
     "            const auto jt = joined.find(objective->handle);\n"
     "            const double all = jt == joined.end() ? 0 : jt->second.first;\n",
     "            int cheb = 10000;\n"
     "            for (const auto& [px, py] : objective->coords) cheb = std::min(cheb, std::max(std::abs(x - px), std::abs(y - py)));\n"
     "            const double rushed = cheb <= config::RUSH_DIST ? rush_dps : 0;\n"
     "            join_dps += rushed;\n            if (rushed > 0) join_n += rush_n;\n"
     "            // row.clear used every joiner; rescale to the ones that will be there.\n"
     "            const auto jt = joined.find(objective->handle);\n"
     "            const double all = (jt == joined.end() ? 0 : jt->second.first) + rushed;\n"),
])
print("patched", src, opts)
