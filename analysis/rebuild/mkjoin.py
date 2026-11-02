#!/usr/bin/env python3
"""Group-aware camp choice on a j_hjt-line bot: teammates bound for a group share its
clear and its hits, and camp damage costs time.

    mkjoin.py BOTDIR [NAME=VALUE ...]     # JOIN, JOIN_ALPHA, DMG_COST, JOIN_SLACK
"""
import sys
from pathlib import Path

src = Path(sys.argv[1]) / "src"
opts = {"JOIN": "true", "JOIN_ALPHA": "0.5", "DMG_COST": "25", "JOIN_SLACK": "8"}
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
    "// Group-aware camp choice (strategy::choose_group). Teammates whose claim is a group\n"
    "// add their damage to its clear and take their share of its hits; the joiner is\n"
    "// credited value x (its share of the damage) ^ JOIN_ALPHA. Camp damage taken costs\n"
    "// DMG_COST rounds per full health bar, the walk home to heal it back. A visible\n"
    "// teammate counts only if it is no more than JOIN_SLACK steps further away than us.\n"
    f"inline constexpr bool JOIN = {opts['JOIN']};\n"
    f"inline constexpr double JOIN_ALPHA = {opts['JOIN_ALPHA']};\n"
    f"inline constexpr double DMG_COST = {opts['DMG_COST']};\n"
    f"inline constexpr int JOIN_SLACK = {opts['JOIN_SLACK']};",
)])

patch("strategy.h", [
    ("#pragma once\n#include \"common.h\"", "#pragma once\n#include <cmath>\n#include \"common.h\""),
    # Collect the teammates bound for each group, with their damage and position.
    ("    const auto claims = team.assignments();\n    std::map<int, int> claimed;\n"
     "    for (std::size_t i = 0; i < claims.size(); ++i)\n"
     "        if (static_cast<int>(i) != team.slot) ++claimed[claims[i]];\n",
     "    const auto claims = team.assignments();\n    std::map<int, int> claimed;\n"
     "    for (std::size_t i = 0; i < claims.size(); ++i)\n"
     "        if (static_cast<int>(i) != team.slot) ++claimed[claims[i]];\n"
     "    struct Joiner {\n        int handle;\n        double dps;\n        bool seen;\n        bc::vec2 position;\n    };\n"
     "    std::vector<Joiner> joiners;\n"
     "    std::map<int, std::pair<double, int>> joined;  // handle -> (damage, count), every joiner\n"
     "    if (config::JOIN)\n"
     "        for (std::size_t i = 0; i < claims.size() && i < team.allies.size(); ++i) {\n"
     "            if (static_cast<int>(i) == team.slot || claims[i] < 0) continue;\n"
     "            turn::check();\n"
     "            const auto& ally = team.allies[i];\n"
     "            if (!ally.is_alive()) continue;\n"
     "            // An unseen teammate is assumed to hit as hard as we do.\n"
     "            const bool seen = ally.is_visible();\n"
     "            const double d = seen ? dps(ally, 2) : damage;\n"
     "            joiners.push_back({claims[i], d, seen, seen ? ally.position() : bc::vec2{}});\n"
     "            auto& j = joined[claims[i]];\n"
     "            j.first += d;\n"
     "            ++j.second;\n"
     "        }\n"),
    ("    struct Ranked {\n        double estimate;\n        ObjectivePtr objective;\n        double clear, value, bias;\n    };",
     "    struct Ranked {\n        double estimate;\n        ObjectivePtr objective;\n        double clear, value, bias, own, raw;\n    };"),
    # Ranked pre-pass: every joiner counts.
    ("        const double base_clear = objective->hp / (damage * (splash ? std::min(objective->count, 3) : 1) + helper_dps);\n",
     "        const double own = damage * (splash ? std::min(objective->count, 3) : 1) + helper_dps;\n"
     "        double join_dps = 0;\n        int join_n = 0;\n"
     "        if (!objective->monolith) {\n"
     "            const auto jt = joined.find(handle);\n"
     "            if (jt != joined.end()) {\n                join_dps = jt->second.first;\n                join_n = jt->second.second;\n            }\n"
     "        }\n"
     "        const double base_clear = objective->hp / (own + join_dps);\n"),
    ("        const double value = objective->gems + objective->gold * (now < 500 ? 0.3 : 0.25);\n"
     "        const double cost = (clear + capture) * 100 / std::max(1.0, value);\n",
     "        const double raw = objective->gems + objective->gold * (now < 500 ? 0.3 : 0.25);\n"
     "        const double value = raw * std::pow(own / (own + join_dps), config::JOIN_ALPHA);\n"
     "        const double cost = (clear + capture) * 100 / std::max(1.0, value);\n"),
    ("        else if (committed)\n            bias = objective->incoming < 70 ? 20 : 5;\n",
     "        else if (committed && !config::JOIN)\n            bias = objective->incoming < 70 ? 20 : 5;\n"),
    ("        const double shared_incoming = objective->incoming / raiders;\n"
     "        const double risk = std::min(45.0, std::max(0.0, shared_incoming * clear * 0.55 / hp_budget - 0.7) * 12);\n"
     "        const double estimate = cost + (travel + risk) * 100 / std::max(1.0, value) + bias;\n"
     "        ranked.push_back({estimate, objective, clear, value, bias});",
     "        const double shared_incoming = objective->incoming / raiders / (1 + join_n);\n"
     "        const double hits = shared_incoming * clear * 0.55;\n"
     "        const double risk = std::min(45.0, std::max(0.0, hits / hp_budget - 0.7) * 12);\n"
     "        const double wear = config::DMG_COST * hits / std::max(1.0, D(me.max_health()));\n"
     "        const double estimate = cost + (travel + risk + wear) * 100 / std::max(1.0, value) + bias;\n"
     "        ranked.push_back({estimate, objective, clear, value, bias, own, raw});"),
    # Exact pass: joiners further than JOIN_SLACK behind us are left out.
    ("        const int committed = claimed.count(objective->handle) ? claimed[objective->handle] : 0;\n"
     "        const double raiders = objective->monolith ? 1.0 + std::max(committed, config::RAID_ASSUME) : 1.0;\n"
     "        // `clear` was already divided by raiders when the row was ranked.\n"
     "        const double expected_damage = std::max(0.0, (incoming / raiders) * clear * 0.55 - heal_rate * clear);\n"
     "        if (expected_damage > hp_budget) continue;\n"
     "        const double risk = std::min(45.0, std::max(0.0, expected_damage / hp_budget - 0.7) * 12);\n"
     "        double score = (travel + clear + capture + risk) * 100 / std::max(1.0, row.value) + row.bias;\n",
     "        const int committed = claimed.count(objective->handle) ? claimed[objective->handle] : 0;\n"
     "        const double raiders = objective->monolith ? 1.0 + std::max(committed, config::RAID_ASSUME) : 1.0;\n"
     "        double value = row.value;\n"
     "        int join_n = 0;\n"
     "        if (config::JOIN && !objective->monolith) {\n"
     "            double join_dps = 0;\n"
     "            for (const auto& j : joiners) {\n"
     "                if (j.handle != objective->handle) continue;\n"
     "                if (j.seen) {\n"
     "                    std::int64_t eta = std::numeric_limits<std::int64_t>::max();\n"
     "                    for (const auto p : positions) eta = std::min(eta, distance(j.position, p));\n"
     "                    if (eta > static_cast<std::int64_t>(gap) + config::JOIN_SLACK) continue;\n"
     "                }\n"
     "                join_dps += j.dps;\n"
     "                ++join_n;\n"
     "            }\n"
     "            // row.clear used every joiner; rescale to the ones that will be there.\n"
     "            const auto jt = joined.find(objective->handle);\n"
     "            const double all = jt == joined.end() ? 0 : jt->second.first;\n"
     "            clear *= (row.own + all) / (row.own + join_dps);\n"
     "            value = row.raw * std::pow(row.own / (row.own + join_dps), config::JOIN_ALPHA);\n"
     "        }\n"
     "        // `clear` was already divided by raiders when the row was ranked.\n"
     "        const double expected_damage = std::max(0.0, (incoming / raiders) * clear * 0.55 / (1 + join_n) - heal_rate * clear);\n"
     "        if (expected_damage > hp_budget) continue;\n"
     "        const double risk = std::min(45.0, std::max(0.0, expected_damage / hp_budget - 0.7) * 12);\n"
     "        const double wear = config::DMG_COST * expected_damage / std::max(1.0, D(me.max_health()));\n"
     "        double score = (travel + clear + capture + risk + wear) * 100 / std::max(1.0, value) + row.bias;\n"),
    ("        if (reward) score = (travel + capture) * 100 / std::max(1.0, row.value) - 15;",
     "        if (reward) score = (travel + capture) * 100 / std::max(1.0, row.raw) - 15;"),
])
print("patched", src, opts)
