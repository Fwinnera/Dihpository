#!/usr/bin/env python3
"""Party centre (ab3-line bot): play one-altar maps whose gems all sit around the altar as party maps.

    mkpc.py BOTDIR [RADIUS=8] [SHARE=0.8]

Why (GROUND-UP-PLAN.md, "01hooks"): on 01hooks (one altar, all 88 gems in four strength-60 camps
within 6 tiles of it) v155 collects 0 gems in 1,252 rounds against gs_mix_camp and its profiled
champions are dead 44-58% of all turns: the solo controller sends them to the centre one at a
time, into the grouped enemy. On the ladder lab the maps with this layout are among our worst:
01hooks 17% won (54 deaths a game), 00breadcrumbs 0 of 12 (0.9 kills a game), 00the-line 4%.

policy::kind() returns 3 (the party controller, BossBot) also when the map has one altar and at
least SHARE of its gems lie in groups within RADIUS tiles of it: every champion then takes the
shared objective, moves and clears as a pack, banks without the solo channel check and does not
leave alone to heal. Elsewhere nothing changes (00breadcrumbs, 01hooks and 00the-line qualify
at the defaults).
"""
import sys
from pathlib import Path

src = Path(sys.argv[1]) / "src"
opts = dict(a.split("=", 1) for a in sys.argv[2:])
radius = int(opts.get("RADIUS", 8))
share = float(opts.get("SHARE", 0.8))


def patch(name, pairs):
    f = src / name
    text = f.read_text()
    for old, new in pairs:
        n = text.count(old)
        if n != 1:
            sys.exit(f"{name}: expected one match, found {n}: {old[:70]!r}")
        text = text.replace(old, new)
    f.write_text(text)


patch("policy.h", [
    ("inline int kind() {",
     "// mkpc.py: one altar with (nearly) every gem around it -- the game is one contested centre,\n"
     "// and solo farmers arrive there one at a time (01hooks, 00breadcrumbs, 00the-line).\n"
     "inline bool central_map() {\n"
     "    if (gm::altars().count() != 1) return false;\n"
     "    bc::vec2 altar{};\n"
     "    for (const auto p : gm::altars().positions()) altar = p;\n"
     "    double near = 0, total = 0;\n"
     "    for (const auto& group : gm::camp_groups()) {\n"
     "        const double gems = static_cast<double>(group.gem_value());\n"
     "        if (gems <= 0) continue;\n"
     "        total += gems;\n"
     "        std::int64_t gap = 1 << 20;\n"
     "        for (const auto p : group.spawn_tiles().positions()) gap = std::min(gap, distance(p, altar));\n"
     f"        if (gap <= {radius}) near += gems;\n"
     "    }\n"
     f"    return total > 0 && near >= {share} * total;\n"
     "}\n\n"
     "inline int kind() {"),
    ("        cached = gm::altars().count() == 1 && monolith ? 2 : party_map() ? 3 : 0;",
     "        cached = gm::altars().count() == 1 && monolith ? 2 : (party_map() || central_map()) ? 3 : 0;"),
])
print("patched", src, opts)
