#!/usr/bin/env python3
"""Prospector first on cluster maps (cHG-line bot; policy.h + bot.h shop).

    mkprosp.py BOTDIR [SHARE=0.5]

Prospector (+25% gold and gems from clusters, the camps that do not attack) is never
bought. On 12 of 78 maps 78-100% of the gems sit in strength-0 groups (the five
adgato_gemcombat maps, 00breadcrumbs, 00vault, 02stalactites, 00galaxy, 00the-line,
03ultrastarvation, 03one-gem). Where at least SHARE of the map's gems are in such groups,
every champion's build is Prospector > Hunter > Durability (Jungle's camp-damage cut is
worthless there); elsewhere nothing changes.
"""
import sys
from pathlib import Path

src = Path(sys.argv[1]) / "src"
opts = {"SHARE": "0.5"}
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


patch("policy.h", [("// Maps played by the party controller.",
                    "// Share of the map's gems in groups whose camps never attack (clusters): Prospector's\n"
                    "// +25% applies to them (analysis/rebuild/mkprosp.py).\n"
                    "inline double cluster_share() {\n"
                    "    static double cached_share = -1;\n"
                    "    if (cached_share < 0) {\n"
                    "        double all = 0, clusters = 0;\n"
                    "        for (const auto& group : gm::camp_groups()) {\n"
                    "            bool quiet = true;\n"
                    "            for (const auto& camp : group.camps())\n"
                    "                if (camp.is_monolith() || camp.base_stats().base_strength > 0) quiet = false;\n"
                    "            all += group.gem_value();\n"
                    "            if (quiet) clusters += group.gem_value();\n"
                    "        }\n"
                    "        cached_share = all > 0 ? clusters / all : 0;\n"
                    "    }\n"
                    "    return cached_share;\n"
                    "}\n\n"
                    "// Maps played by the party controller.")])
patch("bot.h", [("        const auto build = config::build(me.champion_name());",
                 "        using I = bc::item_type;\n"
                 f"        const auto build = policy::cluster_share() >= {opts['SHARE']}\n"
                 "                               ? std::vector<bc::item_type>{I::prospector_shard_of_strength, I::hunter_shard_of_strength,\n"
                 "                                                            I::durability_shard_of_health}\n"
                 "                               : config::build(me.champion_name());")])
print("patched", src, opts)
