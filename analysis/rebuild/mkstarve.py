#!/usr/bin/env python3
"""Maps starved of soloable gems (2026-11-04, CLOUD; map fixes with v166 kept safe).

Ranked (v155/v166 era): 01starvation 1/11, 00great-wall 4/9. Their soloable gems (groups that are not monoliths
and no stronger than one golem) are 8% and 11% of all gems; every other map under 15% is already played by the
party controller (00contest, 00stampede, 03homonoliths 10/11). policy::party_map needs every gem group to be
unsoloable, so one small cluster keeps these two on the solo controller, which raids monoliths only after
round 900.

    MODE=party  a map whose soloable gems are under STARVE_SHARE of its gems is a party map.
    MODE=raid   on such a map (solo controller) monolith raids may start from STARVE_RAID_ROUND, not 900.

Every other map is unchanged.

    mkstarve.py BOTDIR [MODE=party] [STARVE_SHARE=0.15] [STARVE_RAID_ROUND=300]
"""
import sys
from pathlib import Path

src = Path(sys.argv[1]) / "src"
P = dict(MODE="party", STARVE_SHARE="0.15", STARVE_RAID_ROUND="300")
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


helper = (
    "// Share of the map's gems in groups one champion can clear alone (mkstarve.py).\n"
    "inline double soloable_share() {\n"
    "    static double cached = -1;\n"
    "    if (cached < 0) {\n"
    "        double total = 0, solo = 0;\n"
    "        for (const auto& group : gm::camp_groups()) {\n"
    "            if (!group.gem_value()) continue;\n"
    "            bool monolith = false;\n"
    "            double strength = 0;\n"
    "            for (const auto& camp : group.camps()) {\n"
    "                if (camp.is_monolith()) monolith = true;\n"
    "                strength += camp.base_stats().base_strength;\n"
    "            }\n"
    "            total += group.gem_value();\n"
    "            if (!monolith && strength <= SOLO_STRENGTH) solo += group.gem_value();\n"
    "        }\n"
    "        cached = total > 0 ? solo / total : 1.0;\n"
    "    }\n"
    "    return cached;\n"
    "}\n\n"
)

if P["MODE"] == "party":
    patch("policy.h", [
        ("inline bool party_map() {\n",
         helper + f"inline bool party_map() {{\n    if (soloable_share() < {P['STARVE_SHARE']}) return true;\n"),
    ])
elif P["MODE"] == "raid":
    patch("policy.h", [
        ("inline bool party_map() {\n", helper + "inline bool party_map() {\n"),
    ])
    # Lazy gate nested in the existing monolith test: a group without a monolith runs exactly v166's
    # instructions, and the share is computed only for a monolith group between STARVE_RAID_ROUND and RAID_ROUND.
    patch("strategy.h", [
        ("        if ((objective->monolith && (now < config::RAID_ROUND || monolith_share() < config::RAID_SHARE)) ||\n",
         "        if ((objective->monolith && ((now < config::RAID_ROUND && !(now >= "
         f"{P['STARVE_RAID_ROUND']} && policy::soloable_share() < {P['STARVE_SHARE']})) || monolith_share() < config::RAID_SHARE)) ||\n"),
    ])
    patch("strategy.h", [
        ('#include "teamwork.h"\n', '#include "teamwork.h"\n#include "policy.h"\n'),
    ])
else:
    sys.exit("MODE must be party or raid")
print("patched", src, P)
