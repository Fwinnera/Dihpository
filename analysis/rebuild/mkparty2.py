#!/usr/bin/env python3
"""Party controller only where it is needed (2026-11-06, CLOUD; engine 3.0.0, 128-map pool).

policy::party() sends every single-altar map with a monolith (kind 2) to the party controller and the party
draft (Varg, Willow, Ryth, ...). Our ranked games on engine 3.0.0: party mode won 16 of 57 on kind-2 maps
(04two_kingdoms 0/4, 04spiral_moat 1/11, 04comb 1/9, 01boss_battle 2/8, 03showdown 2/7, 00anvil 1/2,
02guardians 5/11, 04duel_ring 4/5) against 52% in solo mode; maps where no gem group can be soloed (kind 3)
went 11 of 16 in party mode. Most kind-2 maps are full of soloable gem groups (04comb 38 of 39).

Here a kind-2 map is played as a party only when its altar is gated (every open tile within tribute range of
the only altar is a monolith spawn tile, as BossBot::gate_tiles tests: 01boss-battle and 02guardians, where
solo play deposits nothing) or monoliths hold at least PARTY_MONO of its gems (04duel-ring, 84%). Kind 3 is
unchanged. The others (03showdown, 00anvil, 04comb, 04spiral-moat, 04two-kingdoms) are played solo with the
solo draft. Locally on the eight kind-2 maps: 36 of 48 against v166's 35.

    mkparty2.py BOTDIR [PARTY_MONO=0.8]
"""
import sys
from pathlib import Path

src = Path(sys.argv[1]) / "src"
P = dict(PARTY_MONO="0.8")
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


patch("policy.h", [(
    "// Maps played by the party controller.\ninline bool party() { return kind() == 2 || kind() == 3; }\n",
    "// mkparty2.py: a single-altar monolith map (kind 2) is played as a party only when its altar is gated by\n"
    "// monoliths or monoliths hold most of its gems.\n"
    "inline int party2_cache = -1;\n"
    "inline bool kind2_party() {\n"
    "    if (party2_cache < 0) {\n"
    "        std::vector<bc::vec2> mono;\n"
    "        double total = 0, mono_gems = 0;\n"
    "        for (const auto& g : gm::camp_groups()) {\n"
    "            bool m = false;\n"
    "            for (const auto& c : g.camps())\n"
    "                if (c.is_monolith()) {\n"
    "                    m = true;\n"
    "                    mono.push_back(c.spawn_position());\n"
    "                }\n"
    "            total += g.gem_value();\n"
    "            if (m) mono_gems += g.gem_value();\n"
    "        }\n"
    "        bool gated = false;\n"
    "        if (gm::altars().count() == 1) {\n"
    "            const auto altar = gm::altars().positions()[0];\n"
    "            bc::bitboard open;\n"
    "            open.draw_chebyshev(altar, static_cast<float>(bc::constants::submit_gems_range));\n"
    "            open = open & ~(gm::walls() | gm::holes() | gm::altars() | gm::spawn_region(bc::team::enemy));\n"
    "            gated = !open.is_empty();\n"
    "            for (const auto p : open.positions())\n"
    "                if (std::find(mono.begin(), mono.end(), p) == mono.end()) gated = false;\n"
    "        }\n"
    f"        party2_cache = (gated || (total > 0 && mono_gems / total >= {P['PARTY_MONO']})) ? 1 : 0;\n"
    "    }\n"
    "    return party2_cache == 1;\n"
    "}\n\n"
    "// Maps played by the party controller.\n"
    "inline bool party() { return kind() == 3 || (kind() == 2 && kind2_party()); }\n",
)])
print("patched", src, P)
