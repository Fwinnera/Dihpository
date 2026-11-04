#!/usr/bin/env python3
"""Squads: champions farm and fight beside a teammate (2026-11-04, CLOUD; the owner's choice after the Heart
of Ruin roster lost locally).

Decoded ladder replays: the top UK teams' champions have a teammate within 5 tiles 57% of their living
rounds (median nearest teammate 4 tiles; Heart of Ruin and Vesper Vale pair up), ours 41-44% (median 7). Our
deaths are outnumbered fights, and one teammate within 5 cuts our death rate in a fight by a third.

Willow's escort controller (EscortBot) already joins a leader's claimed camp group as a supporter, fights
its camps and stays beside it; the leader's camp choice counts the supporter's damage (JOIN), so the pair
clears bigger groups faster. Here chosen followers use it with a preferred leader:

    PAIRS="marcella:vesper_vale,ryth:varg"   follower:leader, champion_type names

A follower escorts its preferred leader whenever that leader has a claimed group, otherwise the nearest
teammate with a claim (as Willow does), and farms alone when nobody has one. Party maps are unchanged.
A follower stands within its own attack range of the camp (Willow's 3-tile standoff kept melee followers out of
reach: Marcella's monster damage fell from 17.7k to 5.2k as an escort).

    mksquad.py BOTDIR [PAIRS=marcella:vesper_vale,ryth:varg] [SQUAD_DEPTH=0]

SQUAD_DEPTH > 0: a follower escorts only when the chosen leader's group is at least that far from our spawn
towards theirs (0 at our spawn, 1 at theirs); nearer home it farms alone.
"""
import sys
from pathlib import Path

src = Path(sys.argv[1]) / "src"
P = dict(PAIRS="marcella:vesper_vale,ryth:varg", SQUAD_DEPTH="0")
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


cases = "".join(f"    case bc::champion_type::{a}: return static_cast<int>(bc::champion_type::{b});\n" for a, b in pairs)
patch("config.h", [(
    "inline constexpr bool DEBUG = false;\n",
    "inline constexpr bool DEBUG = false;\n"
    f"// Squads (mksquad.py, PAIRS={P['PAIRS']}): the champion type a follower escorts, or -1.\n"
    "inline int squad_leader(bc::champion_type follower) {\n"
    "    switch (follower) {\n"
    f"{cases}"
    "    default: return -1;\n"
    "    }\n"
    "}\n",
)])

patch("main.cpp", [(
    "    if (bc::self().champion_name() == bc::champion_type::willow) return std::make_unique<EscortBot>();\n",
    "    if (bc::self().champion_name() == bc::champion_type::willow || config::squad_leader(bc::self().champion_name()) >= 0)\n"
    "        return std::make_unique<EscortBot>();\n",
)])

patch("bot.h", [(
    "            double priority = ally.champion_name() == bc::champion_type::varg ? 0 : 1;\n",
    "            const int wanted = config::squad_leader(me.champion_name());\n"
    "            double priority = wanted >= 0 ? (static_cast<int>(ally.champion_name()) == wanted ? 0 : 1)\n"
    "                                          : (ally.champion_name() == bc::champion_type::varg ? 0 : 1);\n",
)])
# A melee follower must stand in reach of the camp; Willow's 3-tile standoff is her attack range.
patch("bot.h", [(
    "                nav::move_to(nav::around(target.position(), leader.is_visible() ? 3 : 1));\n",
    "                nav::move_to(nav::around(target.position(), leader.is_visible() ? std::max<int>(1, me.attack_range()) : 1));\n",
)])
if float(P["SQUAD_DEPTH"]) > 0:
    patch("bot.h", [(
        "        const auto& leader = *chosen.ally;\n        const auto picked = chosen.objective;\n",
        "        const auto& leader = *chosen.ally;\n        const auto picked = chosen.objective;\n"
        "        if (config::squad_leader(me.champion_name()) >= 0) {\n"
        "            static std::map<int, double> depth_of;\n"
        "            auto dt = depth_of.find(picked->handle);\n"
        "            if (dt == depth_of.end()) {\n"
        "                static const auto own_tiles = gm::spawn_region(bc::team::ally).positions();\n"
        "                static const auto their_tiles = gm::spawn_region(bc::team::enemy).positions();\n"
        "                std::int64_t a = 1000, b = 1000;\n"
        "                for (const auto& [px, py] : picked->coords) {\n"
        "                    for (const auto q : own_tiles) a = std::min<std::int64_t>(a, distance(bc::vec2{px, py}, q));\n"
        "                    for (const auto q : their_tiles) b = std::min<std::int64_t>(b, distance(bc::vec2{px, py}, q));\n"
        f"                }}\n"
        "                dt = depth_of.emplace(picked->handle, static_cast<double>(a) / std::max<std::int64_t>(1, a + b)).first;\n"
        "            }\n"
        f"            if (dt->second < {P['SQUAD_DEPTH']}) return Bot::farm(me, enemies);\n"
        "        }\n",
    )])
print("patched", src, P)
