#!/usr/bin/env python3
"""Co-farming squads (2026-11-04, CLOUD; the owner's "big plan": a team controller like the top teams').

Decoded ladder replays (read2.mjs with camp damage): top UK teams spend 17.9% of their living rounds hitting
camps (53.5% of that with a teammate on the same camp, nearest teammate median 3 tiles while farming, 5
otherwise); we spend 12.0% (45.6%; 4 and 7), yet our damage per farming round is the highest (151 against 144).
Squads built on Willow's escort controller (mksquad.py) kept the team closer but the follower barely farmed
(Marcella 17k -> 7k monster damage), because the escort trails its leader.

Here a follower adopts its leader's claimed camp group as its own objective and runs the ordinary farm logic on
it (full damage, its own approach and capture handling); with no leader claim it farms alone. The follower
claims the same group, so the leader's group-aware choice (JOIN) counts its damage.

    PAIRS="marcella:vesper_vale,ryth:varg"   follower:leader (champion_type names); party maps unchanged.

    mkcofarm.py BOTDIR [PAIRS=marcella:vesper_vale] [COFARM_RANGE=30]
"""
import sys
from pathlib import Path

src = Path(sys.argv[1]) / "src"
P = dict(PAIRS="marcella:vesper_vale", COFARM_RANGE="30")
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
    f"// Co-farming squads (mkcofarm.py, PAIRS={P['PAIRS']}): the champion type a follower co-farms with, or -1.\n"
    f"inline constexpr int COFARM_RANGE = {P['COFARM_RANGE']};\n"
    "inline int cofarm_leader(bc::champion_type follower) {\n"
    "    switch (follower) {\n"
    f"{cases}"
    "    default: return -1;\n"
    "    }\n"
    "}\n",
)])

# The co-farmer: before the ordinary farm logic, take the leader's claimed group as the objective.
patch("bot.h", [(
    "// escort.py: keep Willow in healing range of a productive front-line farmer.\n",
    "// Co-farming squads (mkcofarm.py): a follower works its leader's claimed group with the ordinary farm logic.\n"
    "class CoFarmBot : public Bot {\n"
    "public:\n"
    "    void farm(bc::champion& me, const std::vector<bc::champion>& enemies) override {\n"
    "        const int wanted = config::cofarm_leader(me.champion_name());\n"
    "        const auto claims = team->assignments();\n"
    "        for (std::size_t i = 0; i < team->allies.size() && i < claims.size(); ++i) {\n"
    "            turn::check();\n"
    "            const auto& ally = team->allies[i];\n"
    "            if (same(ally, me) || static_cast<int>(ally.champion_name()) != wanted || !ally.is_alive() || claims[i] < 0) continue;\n"
    "            if (ally.is_visible() && distance(me.position(), ally.position()) > config::COFARM_RANGE) break;\n"
    "            for (const auto& o : metadata)\n"
    "                if (o->handle == claims[i]) {\n"
    "                    if (!objective || objective->handle != o->handle) {\n"
    "                        objective = o;\n"
    "                        supporting_handle.reset();\n"
    "                    }\n"
    "                    break;\n"
    "                }\n"
    "            break;\n"
    "        }\n"
    "        Bot::farm(me, enemies);\n"
    "    }\n"
    "};\n\n"
    "// escort.py: keep Willow in healing range of a productive front-line farmer.\n",
)])

patch("main.cpp", [(
    "    if (bc::self().champion_name() == bc::champion_type::willow) return std::make_unique<EscortBot>();\n",
    "    if (bc::self().champion_name() == bc::champion_type::willow) return std::make_unique<EscortBot>();\n"
    "    if (config::cofarm_leader(bc::self().champion_name()) >= 0) return std::make_unique<CoFarmBot>();\n",
)])
print("patched", src, P)
