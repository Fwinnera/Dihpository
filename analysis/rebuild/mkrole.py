#!/usr/bin/env python3
"""Capture rewards go to the champion whose passive pays for them (cHG-line bot).

    mkrole.py BOTDIR [NEAR=3]

A group's gold and gems go to the champion that captures its reward. Vesper Vale gains
33% more of every gold gain and Marcella 2 gold per gem she tributes, but the collector
protocol hands a reward to whichever claimer stands on it first, else the lowest slot
(Varg): on v140's ladder games our Vesper Vale earned 571 gold per 1,000 rounds against
the opponents' 999. Here, among the teammates claiming a group, a visible Vesper Vale
within NEAR tiles of the reward collects it when it carries gold, else a Marcella when it
carries gems; a teammate already standing on it steps off once that collector is within
NEAR. Every other rule is unchanged.
"""
import sys
from pathlib import Path

src = Path(sys.argv[1]) / "src"
opts = {"NEAR": "3"}
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
                    "// Rewards go to Vesper Vale (gold +33%) or Marcella (2 gold per gem tributed) when\n"
                    "// either is claiming the group and within ROLE_NEAR of it (teamwork.h; mkrole.py).\n"
                    f"inline constexpr int ROLE_NEAR = {opts['NEAR']};")])
patch("teamwork.h", [
    ('#include "common.h"\n#include "turn.h"', '#include "common.h"\n#include "config.h"\n#include "turn.h"'),
    ("    std::optional<int> collector(int handle, const bc::bitboard* region = nullptr) const {",
     "    static int distance_to(const bc::bitboard& region, bc::vec2 p) {\n"
     "        int best = 1000;\n"
     "        for (const auto q : region.positions()) best = std::min<int>(best, static_cast<int>(std::max(std::abs(p.x - q.x), std::abs(p.y - q.y))));\n"
     "        return best;\n"
     "    }\n\n"
     "    std::optional<int> collector(int handle, const bc::bitboard* region = nullptr, double gold = 0, double gems = 0) const {"),
    ("        if (region != nullptr) {\n            // A task already being executed is not stolen by a traveller.",
     "        if (region != nullptr && (gold > 0 || gems > 0)) {\n"
     "            // The champion whose passive pays for this reward collects it.\n"
     "            std::optional<int> pick;\n"
     "            int best = 2;\n"
     "            for (int i : candidates) {\n"
     "                const auto& ally = allies[i];\n"
     "                int rank = 2;\n"
     "                if (gold > 0 && ally.champion_name() == bc::champion_type::vesper_vale) rank = 0;\n"
     "                else if (gems > 0 && ally.champion_name() == bc::champion_type::marcella) rank = 1;\n"
     "                if (rank >= best || !ally.is_visible()) continue;\n"
     "                turn::check();\n"
     "                if (distance_to(*region, ally.position()) <= config::ROLE_NEAR) {\n"
     "                    pick = i;\n"
     "                    best = rank;\n"
     "                }\n"
     "            }\n"
     "            if (pick) return pick;\n"
     "        }\n"
     "        if (region != nullptr) {\n            // A task already being executed is not stolen by a traveller."),
])
patch("bot.h", [
    ("                    const auto owner = team->collector(chosen->handle, &chosen->spawns);",
     "                    const auto owner = team->collector(chosen->handle, &chosen->spawns, chosen->gold, chosen->gems);"),
    ("            if (chosen && team->collector(chosen->handle, &chosen->spawns)) supporting_handle = chosen->handle;",
     "            if (chosen && team->collector(chosen->handle, &chosen->spawns, chosen->gold, chosen->gems)) supporting_handle = chosen->handle;"),
    ("        const auto owner = team->collector(holding->handle, &holding->spawns);\n        const bool assisting",
     "        const auto owner = team->collector(holding->handle, &holding->spawns, holding->gold, holding->gems);\n        const bool assisting"),
    ("            if (collector.is_visible() && holding->spawns.is_set(collector.position())) {",
     "            if (collector.is_visible() && Teamwork::distance_to(holding->spawns, collector.position()) <= config::ROLE_NEAR) {"),
    ("                const auto owner = team->collector(held->handle, &held->spawns);",
     "                const auto owner = team->collector(held->handle, &held->spawns, held->gold, held->gems);"),
])
patch("strategy.h", [
    ("                const auto owner = team.collector(objective->handle, &objective->spawns);",
     "                const auto owner = team.collector(objective->handle, &objective->spawns, objective->gold, objective->gems);"),
])
print("patched", src, opts)
