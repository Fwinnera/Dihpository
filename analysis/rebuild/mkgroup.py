#!/usr/bin/env python3
"""Early group play on a cHG-line bot: before a round, follow the leader's group.

    mkgroup.py BOTDIR [ROUNDS=120]

The game snowballs from early kills (the side that lost a champion first won 37-40% of
v140's ranked games; in the lab losses the opponents' gold by round 100 is often 2-6x
ours). Before ROUNDS, on solo maps, a champion without an objective takes the group
claimed by the lowest-slot living teammate ahead of it, so the team farms and meets the
enemy together; the first claimer (usually Varg) chooses as before.
"""
import sys
from pathlib import Path

src = Path(sys.argv[1]) / "src"
opts = {"ROUNDS": "120"}
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
                    "// Early group play (bot.h farm; analysis/rebuild/mkgroup.py): before GROUP_ROUNDS a\n"
                    "// champion without an objective follows the lowest-slot claimer's group.\n"
                    f"inline constexpr std::int64_t GROUP_ROUNDS = {opts['ROUNDS']};")])
patch("bot.h", [("        if (!chosen) {\n            supporting_handle.reset();\n            chosen = strategy::choose_group(",
                 "        if (!chosen && static_cast<std::int64_t>(bc::round_number()) < config::GROUP_ROUNDS && !policy::party()) {\n"
                 "            const auto now = static_cast<std::int64_t>(bc::round_number());\n"
                 "            const auto claims = team->assignments();\n"
                 "            for (std::size_t i = 0; i < claims.size() && i < team->allies.size() && static_cast<int>(i) < team->slot; ++i) {\n"
                 "                if (claims[i] < 0 || !team->allies[i].is_alive()) continue;\n"
                 "                turn::check();\n"
                 "                for (const auto& o : metadata)\n"
                 "                    if (o->handle == claims[i] && strategy::respawn_at(respawns, o->handle) <= now) {\n"
                 "                        chosen = o;\n"
                 "                        break;\n"
                 "                    }\n"
                 "                break;\n"
                 "            }\n"
                 "        }\n"
                 "        if (!chosen) {\n            supporting_handle.reset();\n            chosen = strategy::choose_group(")])
print("patched", src, opts)
