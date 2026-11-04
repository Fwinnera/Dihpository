#!/usr/bin/env python3
"""Chase timeout (ab3-line bot): give up a chase that is not producing attacks.

    mkct.py BOTDIR [LIMIT=4] [GAP=6] [COOLDOWN=12]

Why (GROUND-UP-PLAN.md, "00lost_world's chase loop"; fc's per-map screen): on 00lost_world our
champions flip between travel and combat for 150+ rounds, stepping toward any enemy within 4 that
then steps away, and never farm; fc ("chase only when it pays") wins exactly the maps where that
happens (00ribs, 00lost-world, 01corridors, 01hooks, 03fan, 03shrines against the opponents whose
local verdicts predict the ladder lab) but loses fight maps (01elk-arena, 00dunes, 00vault), where
the chase is the fight.

This keeps every chase as it is and ends only futile ones: when the combat branch has moved toward
enemies for LIMIT turns without attacking (turns at most GAP rounds apart count as one chase), the
champion does not step toward enemies for COOLDOWN rounds; it still attacks whatever is in reach,
and the turn otherwise falls through to farming. An attack resets the count. Party maps unchanged.
"""
import sys
from pathlib import Path

src = Path(sys.argv[1]) / "src"
opts = dict(a.split("=", 1) for a in sys.argv[2:])
limit = int(opts.get("LIMIT", 4))
gap = int(opts.get("GAP", 6))
cooldown = int(opts.get("COOLDOWN", 12))


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
                    "// Chase timeout (analysis/rebuild/mkct.py).\n"
                    f"inline constexpr std::int64_t CT_LIMIT = {limit};\n"
                    f"inline constexpr std::int64_t CT_GAP = {gap};\n"
                    f"inline constexpr std::int64_t CT_COOLDOWN = {cooldown};")])

patch("bot.h", [
    ("    bool disengaging = false;\n    std::unique_ptr<Teamwork> team;",
     "    bool disengaging = false;\n"
     "    // Chase timeout: turns spent moving toward enemies without attacking.\n"
     "    std::int64_t ct_count = 0, ct_last = -100, ct_until = -1;\n"
     "    std::unique_ptr<Teamwork> team;"),
    ("            status(\"combat\");\n"
     "            bool acted = combat::fight(*target, pursuit);\n"
     "            bool moved = false;\n"
     "            if (combat::live(*target) && target->health() > 0) {\n"
     "                moved = nav::move_to(nav::around(target->position(), me.attack_range()));\n"
     "                if (moved && combat::live(*target) && target->health() > 0) acted = combat::fight(*target, pursuit) || acted;\n"
     "            }\n"
     "            if (acted || moved) return;",
     "            status(\"combat\");\n"
     "            const auto now = static_cast<std::int64_t>(bc::round_number());\n"
     "            bool acted = combat::fight(*target, pursuit);\n"
     "            bool moved = false;\n"
     "            if (combat::live(*target) && target->health() > 0 && (policy::party() || now >= ct_until)) {\n"
     "                moved = nav::move_to(nav::around(target->position(), me.attack_range()));\n"
     "                if (moved && combat::live(*target) && target->health() > 0) acted = combat::fight(*target, pursuit) || acted;\n"
     "            }\n"
     "            if (acted) {\n"
     "                ct_count = 0;\n"
     "            } else if (moved) {\n"
     "                if (now - ct_last > config::CT_GAP) ct_count = 0;\n"
     "                ct_last = now;\n"
     "                if (++ct_count >= config::CT_LIMIT) {\n"
     "                    ct_until = now + config::CT_COOLDOWN;\n"
     "                    ct_count = 0;\n"
     "                }\n"
     "            }\n"
     "            if (acted || moved) return;"),
])
print("patched", src, opts)
