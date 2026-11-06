#!/usr/bin/env python3
"""Fuel: re-planning the camp group must leave fuel for the move (2026-11-05, CLOUD; fight execution, part 2).

Local diagnostics on hb3 (ws/bots/p_idle, p_fuel: fuel checkpoints printed only on low-fuel bail-outs) found
about 94 turns a game that end in a bail-out (turn::Replan below 10,000 fuel) before the champion did
anything. About 80 of them follow strategy::choose_group: its ranking pre-pass costs a median 23,000 fuel
(a std::pow per group, called even when no teammate has joined, where it is exactly 1), the distance field
11,000, and the exact scoring runs on until only 38,000 remain, so the move to the chosen group (nav::move_to,
another flood) runs out. Every re-plan (after a capture, a retreat, a disengage, a heal or a deposit) cost
the whole turn.

    pow skip    std::pow only when a teammate has joined the group (the result is identical);
    lookup      one std::map find instead of count + operator[] for the claim count;
    CUT=...     the exact scoring stops once a best group is held and fuel falls below CUT/25 (v166: 950,000,
                that is 38,000; default here 1,375,000, that is 55,000).

    mkfuel.py BOTDIR [CUT=1375000]
"""
import sys
from pathlib import Path

src = Path(sys.argv[1]) / "src"
P = dict(CUT="1375000")
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


patch("strategy.h", [
    ("        const double value = raw * std::pow(own / (own + join_dps), config::JOIN_ALPHA);\n",
     "        // mkfuel.py: the power of 1 is 1; std::pow costs hundreds of instructions of fuel per group.\n"
     "        const double value = join_dps > 0 ? raw * std::pow(own / (own + join_dps), config::JOIN_ALPHA) : raw;\n"),
    ("            value = row.raw * std::pow(row.own / (row.own + join_dps), config::JOIN_ALPHA);\n",
     "            value = join_dps > 0 ? row.raw * std::pow(row.own / (row.own + join_dps), config::JOIN_ALPHA) : row.raw;\n"),
    ("        const int committed = claimed.count(handle) ? claimed[handle] : 0;\n",
     "        const auto claim_it = claimed.find(handle);\n"
     "        const int committed = claim_it == claimed.end() ? 0 : claim_it->second;\n"),
    ("        if (best && bc::fuel_remaining() < turn::fuel(950'000)) break;\n",
     f"        // mkfuel.py: stop early enough to leave the move to the chosen group its fuel.\n"
     f"        if (best && bc::fuel_remaining() < turn::fuel({P['CUT']})) break;\n"),
])
print("patched", src, P)
