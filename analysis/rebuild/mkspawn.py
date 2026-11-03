#!/usr/bin/env python3
"""Attack a heavy group from our own spawn when it is in reach (cHG-line bot; party maps).

    mkspawn.py BOTDIR

On 03homonoliths each team's 600-gem monolith group sits two tiles from its spawn, and the
spawn heals 100% a round: a champion on a spawn tile within attack range of a monolith hits
it forever without dying. Strong teams clear their own group, then ours (1,200 gems to 0),
while BossBot waits for round 650. Here, on party maps, a gated group with a camp within our
attack range of a spawn tile is eligible at once; we attack it from a spawn tile in range,
and a champion on spawn with such a camp in range attacks instead of waiting to heal.
"""
import sys
from pathlib import Path

src = Path(sys.argv[1]) / "src"


def patch(name, pairs):
    f = src / name
    text = f.read_text()
    for old, new in pairs:
        n = text.count(old)
        if n != 1:
            sys.exit(f"{name}: expected one match, found {n}: {old[:70]!r}")
        text = text.replace(old, new)
    f.write_text(text)


patch("bot.h", [
    # 1. Do not sit healing on spawn when a camp is in reach from here (party maps only).
    ("        const bool at_spawn = gm::spawn_region(bc::team::ally).is_set(me.position());\n"
     "        if (at_spawn && me.health() < me.max_health()) {\n",
     "        const bool at_spawn = gm::spawn_region(bc::team::ally).is_set(me.position());\n"
     "        bool camp_in_reach = false;\n"
     "        if (at_spawn && policy::party()) {\n"
     "            const auto mask = me.attack_tiles();\n"
     "            for (const auto& c : bc::vision::camps())\n"
     "                if (c.is_visible() && c.health() > 0 && mask.is_set(c.position())) camp_in_reach = true;\n"
     "        }\n"
     "        if (at_spawn && me.health() < me.max_health() && !camp_in_reach) {\n"),
    # 2. BossBot: a gated group reachable from spawn is ready at once.
    ("        const auto gated = [](const ObjectivePtr& o) { return policy::kind() == 3 ? o->heavy : o->monolith; };\n",
     "        const auto gated = [](const ObjectivePtr& o) { return policy::kind() == 3 ? o->heavy : o->monolith; };\n"
     "        const auto spawn = gm::spawn_region(bc::team::ally);\n"
     "        const int reach_range = static_cast<int>(me.attack_range());\n"
     "        const auto from_spawn = [&](const ObjectivePtr& o) {\n"
     "            for (const auto p : o->positions)\n"
     "                if (!(nav::around(p, reach_range) & spawn).is_empty()) return true;\n"
     "            return false;\n"
     "        };\n"
     "        const auto ready_for = [&](const ObjectivePtr& o) { return boss_ready || (gated(o) && from_spawn(o)); };\n"),
    ("                if (o->handle == *shared && (!gated(o) || now >= 650) && (!boss_ready || gated(o))) {",
     "                if (o->handle == *shared && (!gated(o) || now >= 650 || from_spawn(o)) && (!boss_ready || gated(o))) {"),
    ("                if (strategy::respawn_at(respawns, o->handle) > now || (gated(o) && !boss_ready) ||\n",
     "                if (strategy::respawn_at(respawns, o->handle) > now || (gated(o) && !ready_for(o)) ||\n"),
    # 3. Attack it from a spawn tile in range.
    ("        status(\"party-clear\");\n        combat::fight(target, targets);\n        if (combat::live(target) && target.health() > 0) {\n"
     "            if (nav::move_to(nav::around(target.position(), me.attack_range())))\n",
     "        status(\"party-clear\");\n        combat::fight(target, targets);\n        if (combat::live(target) && target.health() > 0) {\n"
     "            const auto in_range = nav::around(target.position(), me.attack_range());\n"
     "            const auto safe = in_range & gm::spawn_region(bc::team::ally);\n"
     "            if (nav::move_to(gated(chosen) && !safe.is_empty() ? safe : in_range))\n"),
])
print("patched", src)
