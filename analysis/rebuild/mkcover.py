#!/usr/bin/env python3
"""Fights only with cover, for the champions that die most, on a j_hjt-line bot.

    mkcover.py BOTDIR [COVER=vv|vv_vend]

Vesper Vale dies 3.6 times a game and Vendetta 3.5, 42% and 41% of those deaths starting
with a fight it chose, usually alone (0.4-0.5 allies within 5). With COVER set, the named
champions do not open a fight from play_turn's pursuit branch unless a living teammate is
within 5 tiles or the target dies to one attack or cast. Defending a capture, disengaging
and retreating are unchanged.
"""
import sys
from pathlib import Path

src = Path(sys.argv[1]) / "src"
opts = {"COVER": "vv"}
for a in sys.argv[2:]:
    k, v = a.split("=", 1)
    assert k in opts, k
    opts[k] = v
names = {"vv": ["vesper_vale"], "vv_vend": ["vesper_vale", "vendetta"]}[opts["COVER"]]


def patch(name, pairs):
    f = src / name
    text = f.read_text()
    for old, new in pairs:
        n = text.count(old)
        if n != 1:
            sys.exit(f"{name}: expected one match, found {n}: {old[:70]!r}")
        text = text.replace(old, new)
    f.write_text(text)


test = " || ".join(f"type == bc::champion_type::{n}" for n in names)
patch("config.h", [(
    "inline constexpr bool DEBUG = false;",
    "inline constexpr bool DEBUG = false;\n"
    "// Champions that open fights only with a teammate within 5 or a one-hit kill\n"
    "// (bot.h pursuit branch; analysis/rebuild/mkcover.py).\n"
    "inline bool needs_cover(bc::champion_type type) { return " + test + "; }",
)])
patch("bot.h", [
    ("        const auto target = combat::choose_enemy(pursuit, team->allies);\n        if (target) {\n",
     "        auto target = combat::choose_enemy(pursuit, team->allies);\n"
     "        if (target && config::needs_cover(me.champion_name())) {\n"
     "            bool covered = false;\n"
     "            for (const auto& ally : team->allies)\n"
     "                if (!same(ally, me) && ally.is_alive() && ally.is_visible() && distance(ally.position(), me.position()) <= 5)\n"
     "                    covered = true;\n"
     "            if (!covered && !combat::finishing_blow(std::vector<bc::champion>{*target})) target.reset();\n"
     "        }\n"
     "        if (target) {\n"),
])
print("patched", src, opts)
