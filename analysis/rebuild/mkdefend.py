#!/usr/bin/env python3
"""Home defence: converge on enemies inside our half when we would clearly outnumber them (2026-11-04, CLOUD).

Ladder evidence: we die 6 times a game in our own half, outnumbered, while their champions die there 0.9 times,
only when we outnumber them (2v1, 2v2, 3v1). Assist (mkassist.py) pulled helpers out of fights they were winning
in the enemy half (their deaths there -1.05 a game on the lab). This acts only on enemies inside our half.

A champion with at least DEF_HEALTH of its health and fewer than DEF_GEMS gems, not on a party map, attacks the
weakest visible enemy that stands in our half (closer to our spawn than DEF_DEPTH of the way to theirs) within
DEF_RANGE of it, when the health x strength of our champions within DEF_RADIUS + their distance budget of that
enemy (counting this one) is at least DEF_ODDS times the enemies' within DEF_RADIUS of it.

    mkdefend.py BOTDIR [DEF_RANGE=10] [DEF_ODDS=1.2] [DEF_DEPTH=0.45] [DEF_HEALTH=0.6] [DEF_GEMS=15] [DEF_RADIUS=6]
"""
import sys
from pathlib import Path

src = Path(sys.argv[1]) / "src"
P = dict(DEF_RANGE="10", DEF_ODDS="1.2", DEF_DEPTH="0.45", DEF_HEALTH="0.6", DEF_GEMS="15", DEF_RADIUS="6")
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


patch("config.h", [(
    "inline constexpr bool DEBUG = false;\n",
    "inline constexpr bool DEBUG = false;\n"
    "// Home defence (mkdefend.py).\n"
    f"inline constexpr int DEF_RANGE = {P['DEF_RANGE']};\n"
    f"inline constexpr double DEF_ODDS = {P['DEF_ODDS']};\n"
    f"inline constexpr double DEF_DEPTH = {P['DEF_DEPTH']};\n"
    f"inline constexpr double DEF_HEALTH = {P['DEF_HEALTH']};\n"
    f"inline constexpr std::uint32_t DEF_GEMS = {P['DEF_GEMS']};\n"
    f"inline constexpr int DEF_RADIUS = {P['DEF_RADIUS']};\n",
)])

patch("combat.h", [(
    "// Raise a ready self-shield while withdrawing",
    "// The weakest enemy inside our half within DEF_RANGE that our nearby champions (with us) clearly outweigh.\n"
    "inline std::optional<bc::champion> defend_target(const std::vector<bc::champion>& enemies,\n"
    "                                                 const std::vector<bc::champion>& allies) {\n"
    "    auto& me = bc::self();\n"
    "    if (D(me.health()) < D(me.max_health()) * config::DEF_HEALTH || me.gem_count() >= config::DEF_GEMS) return std::nullopt;\n"
    "    static const auto own_tiles = gm::spawn_region(bc::team::ally).positions();\n"
    "    static const auto their_tiles = gm::spawn_region(bc::team::enemy).positions();\n"
    "    const auto position = me.position();\n"
    "    std::optional<bc::champion> best;\n"
    "    for (const auto& e : enemies) {\n"
    "        turn::check();\n"
    "        const auto at = e.position();\n"
    "        if (distance(position, at) > config::DEF_RANGE) continue;\n"
    "        std::int64_t a = 1000, b = 1000;\n"
    "        for (const auto q : own_tiles) a = std::min<std::int64_t>(a, distance(at, q));\n"
    "        for (const auto q : their_tiles) b = std::min<std::int64_t>(b, distance(at, q));\n"
    "        if (static_cast<double>(a) / std::max<std::int64_t>(1, a + b) >= config::DEF_DEPTH) continue;\n"
    "        double hostile = 0;\n"
    "        for (const auto& o : enemies)\n"
    "            if (distance(o.position(), at) <= config::DEF_RADIUS) hostile += D(o.health()) * std::max(1.0, D(o.strength()));\n"
    "        double friendly = D(me.health()) * std::max(1.0, D(me.strength()));\n"
    "        for (const auto& ally : allies)\n"
    "            if (!same(ally, me) && ally.is_alive() && ally.is_visible() && distance(ally.position(), at) <= config::DEF_RADIUS + 2 &&\n"
    "                D(ally.health()) >= D(ally.max_health()) * 0.4)\n"
    "                friendly += D(ally.health()) * std::max(1.0, D(ally.strength()));\n"
    "        if (friendly < hostile * config::DEF_ODDS) continue;\n"
    "        if (!best || e.health() < best->health()) best = e;\n"
    "    }\n"
    "    return best;\n"
    "}\n\n"
    "// Raise a ready self-shield while withdrawing",
)])

patch("bot.h", [(
    "        if (!at_spawn && me.gold_count() >= config::SHOP_GOLD &&\n",
    "        if (!policy::party()) {\n"
    "            const auto target = combat::defend_target(enemies, team->allies);\n"
    "            if (target) {\n"
    "                status(\"defend\");\n"
    "                bool acted = combat::fight(*target, enemies);\n"
    "                bool moved = false;\n"
    "                if (combat::live(*target) && target->health() > 0) {\n"
    "                    moved = nav::move_to(nav::around(target->position(), me.attack_range()));\n"
    "                    if (moved && combat::live(*target) && target->health() > 0) acted = combat::fight(*target, enemies) || acted;\n"
    "                }\n"
    "                if (acted || moved) return;\n"
    "            }\n"
    "        }\n"
    "        if (!at_spawn && me.gold_count() >= config::SHOP_GOLD &&\n",
)])
print("patched", src, P)
