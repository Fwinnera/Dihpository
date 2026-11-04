#!/usr/bin/env python3
"""Assist: teammates come to a fight (2026-11-04, CLOUD).

Ladder evidence (lab set 1 with a profiled v166 and the replays decoded by tools/replay/read.mjs): our
champions die outnumbered (1v2, 1v3, 0v2) while a teammate is within 8 tiles about half the time, and in
60% of those deaths the nearby teammate is travelling, banking, farming or leaving. Each champion only
reacts to enemies within 7 of itself.

  - assist: a champion with at least ASSIST_HEALTH of its health and fewer than ASSIST_GEMS gems, not on a
    party map, helps the nearest teammate within ASSIST_RANGE that has an enemy within ASSIST_ENGAGED of it,
    when our health x strength within 5 of that teammate (with this champion added) is at least ASSIST_ODDS
    of theirs. It fights the weakest enemy next to the teammate, walking into reach.
  - hold: the disengage check also counts healthy teammates within ASSIST_RANGE (half weight), the ones that
    would come, so a champion does not run from a fight its help is walking into.

    mkassist.py BOTDIR [KEY=VALUE ...]     e.g. ASSIST_RANGE=10 HOLD=0 ASSIST_NEED=1.2 ASSIST=0 REGROUP=1
"""
import sys
from pathlib import Path

src = Path(sys.argv[1]) / "src"
opts = dict(a.split("=", 1) for a in sys.argv[2:])
P = dict(ASSIST="1", ASSIST_RANGE="8", ASSIST_ENGAGED="3", ASSIST_ODDS="0.8", ASSIST_HEALTH="0.5", ASSIST_GEMS="15",
         ASSIST_NEED="0", HOLD="1", HOLD_WEIGHT="0.5", REGROUP="0", REGROUP_RANGE="12")
P.update(opts)


def patch(name, pairs):
    f = src / name
    text = f.read_text()
    for old, new in pairs:
        n = text.count(old)
        if n != 1:
            sys.exit(f"{name}: expected one match, found {n}: {old[:70]!r}")
        text = text.replace(old, new)
    f.write_text(text)


patch("config.h", [(
    "inline constexpr bool DEBUG = false;\n",
    "inline constexpr bool DEBUG = false;\n"
    "// Assist (mkassist.py): help a teammate within ASSIST_RANGE that an enemy has reached.\n"
    f"inline constexpr bool ASSIST = {'true' if P['ASSIST'] == '1' else 'false'};\n"
    f"inline constexpr int ASSIST_RANGE = {P['ASSIST_RANGE']};\n"
    f"inline constexpr int ASSIST_ENGAGED = {P['ASSIST_ENGAGED']};\n"
    f"inline constexpr double ASSIST_ODDS = {P['ASSIST_ODDS']};\n"
    f"inline constexpr double ASSIST_HEALTH = {P['ASSIST_HEALTH']};\n"
    f"inline constexpr std::uint32_t ASSIST_GEMS = {P['ASSIST_GEMS']};\n"
    "// Help only a teammate whose side is losing: our health x strength near it, before we add ours, below\n"
    "// ASSIST_NEED times theirs (0 = always).\n"
    f"inline constexpr double ASSIST_NEED = {P['ASSIST_NEED']};\n"
    f"inline constexpr bool HOLD = {'true' if P['HOLD'] == '1' else 'false'};\n"
    f"inline constexpr double HOLD_WEIGHT = {P['HOLD_WEIGHT']};\n"
    "// Regroup: a champion disengaging from a fight falls back to the nearest healthy teammate within\n"
    "// REGROUP_RANGE that no enemy threatens, instead of towards spawn (the low-health retreat is unchanged).\n"
    f"inline constexpr bool REGROUP = {'true' if P['REGROUP'] == '1' else 'false'};\n"
    f"inline constexpr int REGROUP_RANGE = {P['REGROUP_RANGE']};\n",
)])

patch("combat.h", [
    # hold: count teammates that would come.
    ("    double allied = D(me.health()) * std::max(1.0, D(me.strength()));\n"
     "    for (const auto& ally : allies)\n"
     "        if (!same(ally, me) && ally.is_alive() && ally.is_visible() && distance(position, ally.position()) <= radius)\n"
     "            allied += D(ally.health()) * std::max(1.0, D(ally.strength())) * 0.75;\n"
     "    return {allied / std::max(1.0, hostile), threats};\n",
     "    double allied = D(me.health()) * std::max(1.0, D(me.strength()));\n"
     "    for (const auto& ally : allies) {\n"
     "        if (same(ally, me) || !ally.is_alive() || !ally.is_visible()) continue;\n"
     "        const auto gap = distance(position, ally.position());\n"
     "        if (gap <= radius)\n"
     "            allied += D(ally.health()) * std::max(1.0, D(ally.strength())) * 0.75;\n"
     "        else if (config::HOLD && gap <= config::ASSIST_RANGE && D(ally.health()) >= D(ally.max_health()) * config::ASSIST_HEALTH &&\n"
     "                 ally.gem_count() < config::ASSIST_GEMS)\n"
     "            allied += D(ally.health()) * std::max(1.0, D(ally.strength())) * config::HOLD_WEIGHT;\n"
     "    }\n"
     "    return {allied / std::max(1.0, hostile), threats};\n"),
    # assist target.
    ("// Raise a ready self-shield while withdrawing",
     "// Fall back to the nearest healthy teammate within REGROUP_RANGE that is outside the enemies' threat,\n"
     "// so the pursuit runs into it; with none, the ordinary retreat towards spawn.\n"
     "template <class Camps>\n"
     "inline bool regroup(const std::vector<bc::champion>& enemies, const Camps& camps, const std::vector<bc::champion>& allies) {\n"
     "    auto& me = bc::self();\n"
     "    const auto threat = nav::threat_mask(enemies, camps, 1);\n"
     "    const auto position = me.position();\n"
     "    bc::bitboard goals;\n"
     "    for (const auto& a : allies) {\n"
     "        turn::check();\n"
     "        if (same(a, me) || !a.is_alive() || !a.is_visible()) continue;\n"
     "        if (distance(position, a.position()) > config::REGROUP_RANGE || threat.is_set(a.position())) continue;\n"
     "        if (D(a.health()) < D(a.max_health()) * config::ASSIST_HEALTH) continue;\n"
     "        goals |= nav::around(a.position(), 1);\n"
     "    }\n"
     "    goals &= ~threat;\n"
     "    if (!goals.is_empty() && nav::move_to(goals, &threat)) return true;\n"
     "    return nav::retreat(enemies, camps);\n"
     "}\n\n"
     "// The weakest enemy next to the nearest teammate (within ASSIST_RANGE) that an enemy has reached, when\n"
     "// our health x strength around that teammate, with us added, is at least ASSIST_ODDS of theirs.\n"
     "inline std::optional<bc::champion> assist_target(const std::vector<bc::champion>& enemies,\n"
     "                                                 const std::vector<bc::champion>& allies) {\n"
     "    auto& me = bc::self();\n"
     "    if (D(me.health()) < D(me.max_health()) * config::ASSIST_HEALTH || me.gem_count() >= config::ASSIST_GEMS) return std::nullopt;\n"
     "    const auto position = me.position();\n"
     "    std::optional<bc::champion> best;\n"
     "    std::int64_t best_gap = 0;\n"
     "    for (const auto& ally : allies) {\n"
     "        turn::check();\n"
     "        if (same(ally, me) || !ally.is_alive() || !ally.is_visible()) continue;\n"
     "        const auto at = ally.position();\n"
     "        const auto gap = distance(position, at);\n"
     "        if (gap > config::ASSIST_RANGE || (best && gap >= best_gap)) continue;\n"
     "        double hostile = 0;\n"
     "        const bc::champion* weakest = nullptr;\n"
     "        for (const auto& e : enemies) {\n"
     "            const auto d = distance(at, e.position());\n"
     "            if (d <= 5) hostile += D(e.health()) * std::max(1.0, D(e.strength()));\n"
     "            if (d <= config::ASSIST_ENGAGED && (!weakest || e.health() < weakest->health())) weakest = &e;\n"
     "        }\n"
     "        if (!weakest) continue;\n"
     "        double friendly = D(me.health()) * std::max(1.0, D(me.strength()));\n"
     "        for (const auto& a : allies)\n"
     "            if (!same(a, me) && a.is_alive() && a.is_visible() && distance(a.position(), at) <= 5)\n"
     "                friendly += D(a.health()) * std::max(1.0, D(a.strength()));\n"
     "        if (config::ASSIST_NEED > 0 && friendly - D(me.health()) * std::max(1.0, D(me.strength())) >= hostile * config::ASSIST_NEED) continue;\n"
     "        if (friendly < hostile * config::ASSIST_ODDS) continue;\n"
     "        best = *weakest;\n"
     "        best_gap = gap;\n"
     "    }\n"
     "    return best;\n"
     "}\n\n"
     "// Raise a ready self-shield while withdrawing"),
])

patch("bot.h", [
    ("                combat::shield_on_retreat(enemies);\n"
     "                nav::retreat(enemies, camps);\n"
     "                return;\n"
     "            }\n"
     "        }\n"
     "        auto holding = held_at(me.position());\n",
     "                combat::shield_on_retreat(enemies);\n"
     "                if (config::REGROUP && !policy::party()) combat::regroup(enemies, camps, team->allies);\n"
     "                else nav::retreat(enemies, camps);\n"
     "                return;\n"
     "            }\n"
     "        }\n"
     "        auto holding = held_at(me.position());\n"),
    (
    "        if (!at_spawn && me.gold_count() >= config::SHOP_GOLD &&\n",
    "        if (config::ASSIST && !policy::party()) {\n"
    "            const auto& their_spawn = gm::spawn_region(bc::team::enemy);\n"
    "            std::vector<bc::champion> reachable;\n"
    "            for (const auto& e : enemies)\n"
    "                if (!their_spawn.is_set(e.position())) reachable.push_back(e);\n"
    "            const auto target = combat::assist_target(reachable, team->allies);\n"
    "            if (target) {\n"
    "                status(\"assist\");\n"
    "                bool acted = combat::fight(*target, reachable);\n"
    "                bool moved = false;\n"
    "                if (combat::live(*target) && target->health() > 0) {\n"
    "                    moved = nav::move_to(nav::around(target->position(), me.attack_range()));\n"
    "                    if (moved && combat::live(*target) && target->health() > 0) acted = combat::fight(*target, reachable) || acted;\n"
    "                }\n"
    "                if (acted || moved) return;\n"
    "            }\n"
    "        }\n"
    "        if (!at_spawn && me.gold_count() >= config::SHOP_GOLD &&\n",
)])
print("patched", src, P)
