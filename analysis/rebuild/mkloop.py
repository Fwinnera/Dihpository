#!/usr/bin/env python3
"""Travel that circles: give up an objective we are not getting closer to (2026-11-06, CLOUD; 04sanctum).

04sanctum (new, ring maze): v166 sends all five champions to a group 103 steps away (gold counts like gems
before round 500) and they walk a closed loop around the ring corridor by our spawn for the whole game: the
route runs through corridor tiles held by camps that block it when seen and look free when not, so the
route flips each time a camp comes into or out of view. progress.blocked() never fires because the position
changes every turn. 0 of 12 ranked games, 0 gems locally.

While travelling to an objective with no visible camp of it (farm's move_to branch), track the best
straight-line distance to the objective's tiles; if it has not improved for LOOP_ROUNDS rounds, the objective
is treated as blocked for 80 rounds (as progress.blocked() does) and the champion re-plans.

    LOOP_MIN_GROUPS=N  only on maps with at least N camp groups (0: everywhere). Everywhere (lp1) it rescued
                       04sanctum and other mazes but cost 3 of 768 local games on balance elsewhere.

    mkloop.py BOTDIR [LOOP_ROUNDS=30] [LOOP_MIN_GROUPS=0]
"""
import sys
from pathlib import Path

src = Path(sys.argv[1]) / "src"
P = dict(LOOP_ROUNDS="30", LOOP_MIN_GROUPS="0")
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


patch("bot.h", [
    ("    std::int64_t contest_last = -1;\n",
     "    std::int64_t contest_last = -1;\n"
     "    // mkloop.py: best straight-line distance to the travel objective and when it last improved.\n"
     "    int loop_handle = -1;\n"
     "    std::int64_t loop_best = 1 << 30;\n"
     "    std::int64_t loop_since = 0;\n"),
    ("        const auto& targets = observed;\n"
     "        if (targets.empty()) {\n"
     "            nav::move_to(chosen->spawns);\n"
     "            return;\n"
     "        }\n",
     "        const auto& targets = observed;\n"
     "        if (targets.empty()) {\n"
     f"            if (metadata.size() >= {P['LOOP_MIN_GROUPS']}) {{\n"
     "                const auto now = static_cast<std::int64_t>(bc::round_number());\n"
     "                std::int64_t gap = 1 << 30;\n"
     "                for (const auto p : chosen->positions) gap = std::min(gap, distance(me.position(), p));\n"
     "                if (loop_handle != chosen->handle || gap < loop_best) {\n"
     "                    loop_handle = chosen->handle;\n"
     "                    loop_best = gap;\n"
     "                    loop_since = now;\n"
     f"                }} else if (now - loop_since >= {P['LOOP_ROUNDS']}) {{\n"
     "                    respawns[chosen->handle] = now + 80;\n"
     "                    objective = nullptr;\n"
     "                    current_group.reset();\n"
     "                    team->claim();\n"
     "                    loop_handle = -1;\n"
     "                    return;\n"
     "                }\n"
     "            }\n"
     "            nav::move_to(chosen->spawns);\n"
     "            return;\n"
     "        }\n"),
])
print("patched", src, P)
