#!/usr/bin/env python3
"""Loose squads: farm your own camp, but near your partner (2026-11-04, CLOUD).

Tight squads (mksquad.py, the escort controller) group our champions as the top teams do (alone 55% -> 46%
locally) but cost 13-14% of the early camp clears: two champions share one capture. Top teams keep a teammate
within 4 tiles (median) while farming 43% more per living champion, so they often work neighbouring camps.

In strategy::choose_group a camp group more than LOOSE_RADIUS tiles from every tile of the partner's position
and claimed group costs LOOSE_ROUNDS more rounds. Partners are symmetric pairs (PAIRS, champion_type names);
a champion without a living partner is unaffected.

    mkloose.py BOTDIR [PAIRS=marcella:vesper_vale,ryth:varg] [LOOSE_ROUNDS=15] [LOOSE_RADIUS=6]
"""
import sys
from pathlib import Path

src = Path(sys.argv[1]) / "src"
P = dict(PAIRS="marcella:vesper_vale,ryth:varg", LOOSE_ROUNDS="15", LOOSE_RADIUS="6")
P.update(dict(a.split("=", 1) for a in sys.argv[2:]))
pairs = [tuple(x.split(":")) for x in P["PAIRS"].split(",") if x]


def patch(name, olds):
    f = src / name
    text = f.read_text()
    for old, new in olds:
        n = text.count(old)
        if n != 1:
            sys.exit(f"{name}: expected one match, found {n}: {old[:70]!r}")
        text = text.replace(old, new)
    f.write_text(text)


cases = "".join(f"    case bc::champion_type::{a}: return static_cast<int>(bc::champion_type::{b});\n"
                f"    case bc::champion_type::{b}: return static_cast<int>(bc::champion_type::{a});\n" for a, b in pairs)
patch("config.h", [(
    "inline constexpr bool DEBUG = false;\n",
    "inline constexpr bool DEBUG = false;\n"
    f"// Loose squads (mkloose.py, PAIRS={P['PAIRS']}): farm within LOOSE_RADIUS of the partner, else LOOSE_ROUNDS more.\n"
    f"inline constexpr double LOOSE_ROUNDS = {P['LOOSE_ROUNDS']};\n"
    f"inline constexpr int LOOSE_RADIUS = {P['LOOSE_RADIUS']};\n"
    "inline int loose_partner(bc::champion_type self) {\n"
    "    switch (self) {\n"
    f"{cases}"
    "    default: return -1;\n"
    "    }\n"
    "}\n",
)])

patch("strategy.h", [
    ("    ObjectivePtr best;\n    double best_score = std::numeric_limits<double>::infinity();\n    bool best_opens = false;\n",
     "    std::vector<bc::vec2> partner_tiles;\n"
     "    {\n"
     "        const int partner = config::loose_partner(me.champion_name());\n"
     "        if (partner >= 0)\n"
     "            for (std::size_t i = 0; i < team.allies.size(); ++i) {\n"
     "                const auto& ally = team.allies[i];\n"
     "                if (static_cast<int>(i) == team.slot || static_cast<int>(ally.champion_name()) != partner || !ally.is_alive()) continue;\n"
     "                if (ally.is_visible()) partner_tiles.push_back(ally.position());\n"
     "                if (i < claims.size() && claims[i] >= 0)\n"
     "                    for (const auto& o : metadata)\n"
     "                        if (o->handle == claims[i])\n"
     "                            for (const auto& [px, py] : o->coords) partner_tiles.push_back(bc::vec2{px, py});\n"
     "            }\n"
     "    }\n"
     "    ObjectivePtr best;\n    double best_score = std::numeric_limits<double>::infinity();\n    bool best_opens = false;\n"),
    ("        double score = (travel + clear + capture + risk + wear) * 100 / std::max(1.0, value) + row.bias;\n",
     "        double apart = 0;\n"
     "        if (!partner_tiles.empty()) {\n"
     "            bool near = false;\n"
     "            for (const auto q : partner_tiles) {\n"
     "                for (const auto& [px, py] : objective->coords)\n"
     "                    if (distance(bc::vec2{px, py}, q) <= config::LOOSE_RADIUS) { near = true; break; }\n"
     "                if (near) break;\n"
     "            }\n"
     "            if (!near) apart = config::LOOSE_ROUNDS;\n"
     "        }\n"
     "        double score = (travel + clear + capture + risk + wear + apart) * 100 / std::max(1.0, value) + row.bias;\n"),
])
print("patched", src, P)
