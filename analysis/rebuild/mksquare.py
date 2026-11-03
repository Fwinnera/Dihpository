#!/usr/bin/env python3
"""Fight odds by the square law on a cHG-line bot (combat::choose_enemy, combat::local_power).

    mksquare.py BOTDIR

Both odds were a sum of health x strength per champion (allies at 0.75), so one champion
against two equal enemies scored 0.5: not below the 0.5 disengage line, and an enemy within
4 tiles is engaged at any odds, so it stayed and fought a fight it loses. Group fights go
by total health times total damage: (health_me + 0.75 x allies') x (strength_me + 0.75 x
allies') against the same product for the enemies. One against one is unchanged; one
against two scores 0.25 and leaves, two against one scores 3.1 and engages.
"""
import sys
from pathlib import Path

src = Path(sys.argv[1]) / "src"
f = src / "combat.h"
t = f.read_text()
pairs = [
    ("""        double allied_power = D(me.health()) * std::max(1.0, D(me.strength()));
        for (const auto& ally : allies)
            if (!same(ally, me) && ally.is_alive() && ally.is_visible() && distance(ally.position(), enemy.position()) <= 5)
                allied_power += D(ally.health()) * std::max(1.0, D(ally.strength())) * 0.75;
        double enemy_power = 0;
        for (const auto& e : enemies)
            if (distance(e.position(), enemy.position()) <= 4) enemy_power += D(e.health()) * std::max(1.0, D(e.strength()));
""",
     """        double allied_health = D(me.health()), allied_strength = std::max(1.0, D(me.strength()));
        for (const auto& ally : allies)
            if (!same(ally, me) && ally.is_alive() && ally.is_visible() && distance(ally.position(), enemy.position()) <= 5) {
                allied_health += D(ally.health()) * 0.75;
                allied_strength += std::max(1.0, D(ally.strength())) * 0.75;
            }
        const double allied_power = allied_health * allied_strength;
        double enemy_health = 0, enemy_strength = 0;
        for (const auto& e : enemies)
            if (distance(e.position(), enemy.position()) <= 4) {
                enemy_health += D(e.health());
                enemy_strength += std::max(1.0, D(e.strength()));
            }
        const double enemy_power = enemy_health * enemy_strength;
"""),
    ("""    double hostile = 0;
    int threats = 0;
    for (const auto& enemy : enemies) {
        turn::check();
        if (enemy.is_visible() && distance(position, enemy.position()) <= radius) {
            hostile += D(enemy.health()) * std::max(1.0, D(enemy.strength()));
            ++threats;
        }
    }
    if (!threats) return {std::numeric_limits<double>::infinity(), 0};
    double allied = D(me.health()) * std::max(1.0, D(me.strength()));
    for (const auto& ally : allies)
        if (!same(ally, me) && ally.is_alive() && ally.is_visible() && distance(position, ally.position()) <= radius)
            allied += D(ally.health()) * std::max(1.0, D(ally.strength())) * 0.75;
    return {allied / std::max(1.0, hostile), threats};
""",
     """    double hostile_health = 0, hostile_strength = 0;
    int threats = 0;
    for (const auto& enemy : enemies) {
        turn::check();
        if (enemy.is_visible() && distance(position, enemy.position()) <= radius) {
            hostile_health += D(enemy.health());
            hostile_strength += std::max(1.0, D(enemy.strength()));
            ++threats;
        }
    }
    if (!threats) return {std::numeric_limits<double>::infinity(), 0};
    double allied_health = D(me.health()), allied_strength = std::max(1.0, D(me.strength()));
    for (const auto& ally : allies)
        if (!same(ally, me) && ally.is_alive() && ally.is_visible() && distance(position, ally.position()) <= radius) {
            allied_health += D(ally.health()) * 0.75;
            allied_strength += std::max(1.0, D(ally.strength())) * 0.75;
        }
    // Square law: a group's power is its total health times its total damage.
    return {allied_health * allied_strength / std::max(1.0, hostile_health * hostile_strength), threats};
"""),
]
for old, new in pairs:
    if t.count(old) != 1:
        sys.exit(f"combat.h: expected one match: {old[:70]!r}")
    t = t.replace(old, new)
f.write_text(t)
print("patched", src)
