#!/usr/bin/env python3
"""Soften "open before the enemy" in camp choice (ab3-line bot).

    mkop.py BOTDIR [LATE=0]

Why (GROUND-UP-PLAN.md, "00lost_world on the ladder"): against Rusty Epee our team clears no camp
for 160 rounds on 00lost_world while the enemy clears the central gem clusters from round 27 and
banks at the central altar every few rounds; our champions stand 10-16 steps away and kill three
of theirs early, but never take a cluster. strategy::choose_group ranks camps lexicographically:
any camp we can start damaging before a visible enemy can stand on it beats every camp we cannot,
whatever their value. With the enemy holding the gem-rich centre, every central cluster loses to
a poor far camp, and the trips there run through the enemy.

With this patch "opens before the enemy" is a score penalty of LATE points instead of a
lexicographic rule (LATE=0: the score alone, which already adds 4 a tile for an enemy within 5 of
the camp). Reward tiles and the rest of the score are unchanged.
"""
import sys
from pathlib import Path

src = Path(sys.argv[1]) / "src"
opts = dict(a.split("=", 1) for a in sys.argv[2:])
late = float(opts.get("LATE", 0))


def patch(name, pairs):
    f = src / name
    text = f.read_text()
    for old, new in pairs:
        n = text.count(old)
        if n != 1:
            sys.exit(f"{name}: expected one match, found {n}: {old[:70]!r}")
        text = text.replace(old, new)
    f.write_text(text)


patch("strategy.h", [(
    "        const bool opens = opens_before_enemy(gap, attack_range, reward, nearest, !enemy_positions.empty());\n"
    "        if (!best || (opens && !best_opens) || (opens == best_opens && score < best_score)) {",
    "        const bool opens = opens_before_enemy(gap, attack_range, reward, nearest, !enemy_positions.empty());\n"
    f"        // mkop.py: arriving after the enemy costs {late:g} points instead of losing to every early camp.\n"
    f"        if (!opens) score += {late:g};\n"
    "        if (!best || score < best_score) {")])
print("patched", src, opts)
