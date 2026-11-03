#!/usr/bin/env python3
"""Fixes for the maps v137 loses almost every ladder game on, each behind a switch.

    mkmaps.py BOTDIR [CONTEST_HUNT=true] [BREACH=true] [PARTY_SIZE=true] [SCARCE_GEMS=50]

CONTEST_HUNT  a held reward contested for three rounds with no enemy in sight on the group
              walks round its tiles to the far side, where a wall can hide the contester
              (02gift-wrapping: both teams held the walled centre group for 1,900 rounds).
              A visible contester is left to the ordinary capture fight.
BREACH        banking stuck for three rounds within 8 steps of an altar walled in by camps
              hits the nearest camp beside it, never a monolith or anything above strength
              60 (02the-pack: 48 wolves ring the only altar; 4,347 failed bank calls).
PARTY_SIZE    on maps where every gem is behind a heavy group (policy 3), the party
              controller's ready test needs min(4, roster) champions, with health and
              damage scaled to match (03homonoliths has three picks and never reached four).
SCARCE_GEMS   below this many gems on the whole map, monoliths included (03one-gem: 7),
              gems are worth 30 gold-weighted units each and any carried gem is banked.
              0 = off.
"""
import sys
from pathlib import Path

src = Path(sys.argv[1]) / "src"
opts = {"CONTEST_HUNT": "true", "BREACH": "true", "PARTY_SIZE": "true", "SCARCE_GEMS": "50"}
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


patch("config.h", [(
    "inline constexpr bool DEBUG = false;",
    "inline constexpr bool DEBUG = false;\n"
    "// Map fixes (analysis/rebuild/mkmaps.py): contested captures, walled-in altars,\n"
    "// party size on three-pick maps, and maps with almost no gems.\n"
    f"inline constexpr bool CONTEST_HUNT = {opts['CONTEST_HUNT']};\n"
    f"inline constexpr bool BREACH = {opts['BREACH']};\n"
    f"inline constexpr bool PARTY_SIZE = {opts['PARTY_SIZE']};\n"
    f"inline constexpr double SCARCE_GEMS = {opts['SCARCE_GEMS']};",
)])

patch("strategy.h", [
    ("inline bool should_bank(bool enemies_seen, int altar_distance) {\n"
     "    auto& me = bc::self();\n"
     "    const auto gems = static_cast<std::int64_t>(me.gem_count());\n"
     "    if (!gems) return false;\n",
     "// Fewer than SCARCE_GEMS gems on the whole map, monoliths included: every gem decides the\n"
     "// game, which then ends at round 2,000 on gems and earned gold.\n"
     "inline bool scarce_gems() {\n"
     "    static int cached = -1;\n"
     "    if (cached < 0) {\n"
     "        double total = 0;\n"
     "        for (const auto& group : gm::camp_groups()) {\n"
     "            bool monolith = false;\n"
     "            for (const auto& camp : group.camps())\n"
     "                if (camp.is_monolith()) monolith = true;\n"
     "            (void)monolith;\n            total += group.gem_value();\n"
     "        }\n"
     "        cached = config::SCARCE_GEMS > 0 && total < config::SCARCE_GEMS ? 1 : 0;\n"
     "    }\n"
     "    return cached == 1;\n"
     "}\n\n"
     "inline bool should_bank(bool enemies_seen, int altar_distance) {\n"
     "    auto& me = bc::self();\n"
     "    const auto gems = static_cast<std::int64_t>(me.gem_count());\n"
     "    if (!gems) return false;\n"
     "    if (scarce_gems()) return true;\n"),
    ("        const double raw = objective->gems + objective->gold * (now < 500 ? 0.3 : 0.25);\n",
     "        const double raw = objective->gems * (scarce_gems() ? 30.0 : 1.0) + objective->gold * (now < 500 ? 0.3 : 0.25);\n"),
])

patch("bot.h", [
    ("    Progress bank_progress{10};\n",
     "    Progress bank_progress{10};\n"
     "    // Consecutive rounds the reward we stand on has been contested.\n"
     "    int contest_rounds = 0;\n"
     "    std::int64_t contest_last = -1;\n"),
    # contested capture
    ("            if (reserve_capture(holding)) return;\n            status(\"capture\");\n",
     "            if (reserve_capture(holding)) return;\n            status(\"capture\");\n"
     "            if (config::CONTEST_HUNT && contest(me, holding, enemies)) return;\n"),
    # breach a walled-in altar
    ("        if (!goals.is_empty()) {\n"
     "            const auto threat = nav::threat_mask(enemies, camps);\n",
     "        if (!goals.is_empty()) {\n"
     "            // Sealed in by camps, not walls: every route search would fail and the dash\n"
     "            // crossing would burn the turn's fuel. Open the way instead.\n"
     "            // Only once stuck for three rounds within eight steps of the altar: the two\n"
     "            // floods cost fuel the big maps do not have.\n"
     "            if (config::BREACH && near_free <= 8 && bank_progress.ticks >= 3 && sealed(me, goals) && breach(me, goals)) return;\n"
     "            const auto threat = nav::threat_mask(enemies, camps);\n"),
    ("    // Keep an executing collector; helpers step away only after handover.\n",
     "    // A capture never completes while an enemy also stands on the group. Fight a visible\n"
     "    // contester, walking into reach; with none in sight for three rounds, walk round the\n"
     "    // group's tiles to the far side, where a wall can hide it.\n"
     "    bool contest(bc::champion& me, const ObjectivePtr& holding, const std::vector<bc::champion>& enemies) {\n"
     "        turn::check();\n"
     "        const auto cs = holding->group.capture_state();\n"
     "        using C = bc::map::camp_group_capture_type;\n"
     "        if (cs.state != C::contested && cs.state != C::enemy_capturing) {\n"
     "            contest_rounds = 0;\n"
     "            return false;\n"
     "        }\n"
     "        const auto now = static_cast<std::int64_t>(bc::round_number());\n"
     "        contest_rounds = contest_last == now - 1 ? contest_rounds + 1 : 1;\n"
     "        contest_last = now;\n"
     "        const auto here = me.position();\n"
     "        std::optional<bc::champion> rival;\n"
     "        for (const auto& e : enemies) {\n"
     "            turn::check();\n"
     "            if (e.is_visible() && e.is_alive() && holding->spawns.is_set(e.position()) &&\n"
     "                (!rival || distance(here, e.position()) < distance(here, rival->position())))\n"
     "                rival = e;\n"
     "        }\n"
     "        // A visible contester is the ordinary capture fight below; chasing it lost\n"
     "        // 01yellow-brick-road.\n"
     "        if (rival) return false;\n"
     "        if (contest_rounds < 3 || holding->positions.empty()) return false;\n"
     "        const auto far = *std::max_element(holding->positions.begin(), holding->positions.end(),\n"
     "                                           [&](bc::vec2 a, bc::vec2 b) { return distance(here, a) < distance(here, b); });\n"
     "        return nav::move_to(nav::around(far, 0));\n"
     "    }\n\n"
     "    // The goal tiles are reachable through static terrain but not past the camps.\n"
     "    bool sealed(const bc::champion& me, const bc::bitboard& goals) const {\n"
     "        turn::check();\n"
     "        const auto here = me.position();\n"
     "        auto open = nav::static_walls();\n"
     "        open.set(here, false);\n"
     "        bc::distance_field terrain;\n"
     "        bc::bitboard by_terrain;\n"
     "        terrain.compute(open, goals & ~open, by_terrain);\n"
     "        if (!by_terrain.is_set(here)) return false;\n"
     "        auto shut = open | bc::vision::camp_tiles();\n"
     "        shut.set(here, false);\n"
     "        bc::distance_field field;\n"
     "        bc::bitboard by_camps;\n"
     "        field.compute(shut, goals & ~shut, by_camps);\n"
     "        return !by_camps.is_set(here);\n"
     "    }\n\n"
     "    // The free tiles beside an altar can be walled in by camps (02the-pack: 48 wolves\n"
     "    // round the map's only altar). Open a way: hit the nearest visible camp beside it.\n"
     "    bool breach(bc::champion& me, const bc::bitboard& goals) {\n"
     "        turn::check();\n"
     "        const auto ring = nav::expand(goals, 3, bc::bitboard{});\n"
     "        const auto here = me.position();\n"
     "        std::optional<bc::camp> best;\n"
     "        for (const auto& c : bc::vision::camps()) {\n"
     "            turn::check();\n"
     "            if (!c.is_visible() || c.health() <= 0 || !ring.is_set(c.position())) continue;\n"
     "            // Never the boss beside a boss altar (01boss-battle), nor anything that hits hard.\n"
     "            if (c.is_monolith() || c.base_stats().base_strength > 60) continue;\n"
     "            if (!best || distance(here, c.position()) < distance(here, best->position())) best = c;\n"
     "        }\n"
     "        if (!best) return false;\n"
     "        bank_progress.reset();\n"
     "        const std::vector<bc::camp> near{*best};\n"
     "        if (combat::fight(*best, near)) return true;\n"
     "        return nav::move_to(nav::around(best->position(), me.attack_range()));\n"
     "    }\n\n"
     "    // Keep an executing collector; helpers step away only after handover.\n"),
    # party size
    ("        bool boss_ready = now >= 650 && purchase_index >= 10 && nearby.size() >= 4 && health >= 7000;\n"
     "        if (boss_ready) {\n"
     "            for (const auto* a : nearby) damage += strategy::dps(*a, 2);\n"
     "            boss_ready = damage >= 400;\n"
     "        }\n",
     "        // A three-pick map can never gather four champions: scale the gate to the roster.\n"
     "        std::size_t need = 4;\n"
     "        // Only where every gem is behind a heavy group (policy 3): with a monolith beside\n"
     "        // other gems (00anvil), three champions on the boss lose the game.\n"
     "        if (config::PARTY_SIZE && policy::kind() == 3) need = std::max<std::size_t>(1, std::min<std::size_t>(4, team->allies.size()));\n"
     "        bool boss_ready = now >= 650 && purchase_index >= 10 && nearby.size() >= need && health >= 1750.0 * D(need);\n"
     "        if (boss_ready) {\n"
     "            for (const auto* a : nearby) damage += strategy::dps(*a, 2);\n"
     "            boss_ready = damage >= 100.0 * D(need);\n"
     "        }\n"),
])
print("patched", src, opts)
