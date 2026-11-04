#!/usr/bin/env python3
"""Party-map fixes on ab3 (BossBot only, so other maps play as before).

    mkparty.py BOTDIR [altar] [gate] [early=ROUND]

altar -- 00anvil: gem groups that cannot fight back with a tile within ALTAR_NEAR of an
         altar (its two 21-gem clusters, two tiles from the only altar, respawning every 50
         rounds) score ALTAR_BONUS times better; while one respawns within ALTAR_WAIT rounds
         the party waits beside it instead of leaving; a carrier within ALTAR_BANK steps of
         the altar banks whatever it holds. Ladder teams bank those clusters from round 21-51,
         21-81 times a game; ab3 opened on gold camps and reached its cluster at round ~65.
gate  -- 01boss-battle and 02guardians: every open tile in reach of the only altar is a
         monolith camp's own tile, so nobody can bank while that camp lives. ab3's carriers
         walked there, waited inside the monolith's range for 12 turns and gave up for 80
         rounds. Here the gate's state is observed (tile visible: camp or not) and shared
         through shared-memory bytes 8-15; while it is closed a carrier keeps farming; while it
         is open every carrier banks whatever it holds; an ally on the only free gate tile is a
         queue (wait two tiles off), not a blocked deposit.
early -- with gate: the boss gate opens at ROUND instead of 650 on gated maps only.
"""
import sys
from pathlib import Path

src = Path(sys.argv[1]) / "src"
opts = sys.argv[2:]
ALTAR = "altar" in opts
GATE = "gate" in opts
QUEUE = "queue" in opts
NEAR = "near" in opts or "near=auto" in opts or "near=noaltar" in opts
NOALTAR = "near=noaltar" in opts or "near=plain" in opts
NEAR = NEAR or "near=plain" in opts
# near=plain: also not where a boss group can be hit from our spawn (03homonoliths, sp).
PLAIN = "near=plain" in opts
AUTO = "near=auto" in opts
# twin=K: a decision-identical build (a dead loop of 50K steps at the top of BossBot::farm) that
# re-rolls party-map games through fuel timing alone; its spread is the screen's noise band.
TWIN = next((int(o.split("=")[1]) for o in opts if o.startswith("twin=")), 0)
ORDER = "order" in opts or NEAR
EARLY = next((int(o.split("=")[1]) for o in opts if o.startswith("early=")), 650)
# altar=UNTIL: the cluster bonus and the wait apply only before round UNTIL (the opening rush).
UNTIL = next((int(o.split("=")[1]) for o in opts if o.startswith("altar=")), 100000)
ALTAR = ALTAR or any(o.startswith("altar=") for o in opts)


def patch(name, pairs):
    f = src / name
    text = f.read_text()
    for old, new in pairs:
        n = text.count(old)
        if n != 1:
            sys.exit(f"{name}: expected one match, found {n}: {old[:80]!r}")
        text = text.replace(old, new)
    f.write_text(text)


patch("config.h", [
    ("inline constexpr int JOIN_SLACK = 8;\n",
     "inline constexpr int JOIN_SLACK = 8;\n"
     "// Party-map fixes (analysis/rebuild/mkparty.py).\n"
     f"inline constexpr bool P_ALTAR = {'true' if ALTAR else 'false'};\n"
     "inline constexpr int ALTAR_NEAR = 3;\n"
     "inline constexpr double ALTAR_BONUS = 3;\n"
     "inline constexpr std::int64_t ALTAR_WAIT = 30;\n"
     "inline constexpr int ALTAR_BANK = 2;\n"
     f"inline constexpr std::int64_t ALTAR_UNTIL = {UNTIL};\n"
     f"inline constexpr bool P_GATE = {'true' if GATE else 'false'};\n"
     f"inline constexpr std::int64_t GATE_BOSS_ROUND = {EARLY};\n"
     f"inline constexpr bool P_QUEUE = {'true' if QUEUE else 'false'};\n"
     f"inline constexpr bool P_NEAR = {'true' if NEAR else 'false'};\n"
     f"inline constexpr bool NEAR_AUTO = {'true' if AUTO else 'false'};\n"
     f"inline constexpr bool NEAR_NOALTAR = {'true' if NOALTAR else 'false'};\n"
     f"inline constexpr bool NEAR_PLAIN = {'true' if PLAIN else 'false'};\n"),
])

patch("bot.h", [
    # Helpers and state.
    ("class BossBot : public Bot {\npublic:\n    std::int64_t bank_retry_at = 0;\n\n    BossBot() { bank_progress = Progress{}; }\n",
     "class BossBot : public Bot {\npublic:\n    std::int64_t bank_retry_at = 0;\n\n    BossBot() { bank_progress = Progress{}; }\n"
     "\n"
     "    // 00anvil: a gem group that cannot fight back, with a tile beside an altar.\n"
     "    std::map<int, bool> side_cache;\n"
     "    bool altar_side(const ObjectivePtr& o) {\n"
     "        const auto it = side_cache.find(o->handle);\n"
     "        if (it != side_cache.end()) return it->second;\n"
     "        bool side = false;\n"
     "        if (o->gems > 0 && !o->heavy && o->incoming <= 0)\n"
     "            for (const auto altar : gm::altars().positions())\n"
     "                for (const auto p : o->positions)\n"
     "                    if (distance(p, altar) <= config::ALTAR_NEAR) side = true;\n"
     "        side_cache[o->handle] = side;\n"
     "        return side;\n"
     "    }\n"
     "    int altar_map = -1;\n"
     "    bool has_altar_side() {\n"
     "        if (altar_map < 0) {\n"
     "            altar_map = 0;\n"
     "            for (const auto& o : metadata)\n"
     "                if (o->gems > 0 && !o->heavy && o->incoming <= 0 && altar_side(o)) altar_map = 1;\n"
     "        }\n"
     "        return altar_map == 1;\n"
     "    }\n"
     "\n"
     "    // The opening scan runs out of fuel after the first few groups in list order (00anvil:\n"
     "    // a 4-gem camp by spawn). Score the altar clusters first while their bonus applies.\n"
     "    std::vector<ObjectivePtr> order_cache;\n"
     "    int scan_count = 0, scan_cuts = 0;\n"
     "    int spawn_raid = -1;  // a gated group in reach of our spawn (03homonoliths)\n"
     "    const std::vector<ObjectivePtr>& scan_order() {\n"
     "        const bool rush = config::P_ALTAR && static_cast<std::int64_t>(bc::round_number()) < config::ALTAR_UNTIL && has_altar_side();\n"
     "        // Nearest first only where this champion's scans run out of fuel (NEAR_AUTO): at least five\n"
     "        // cut scans and a quarter of all of them (02guardians about a third, 00anvil 1%).\n"
     "        const bool near = config::P_NEAR && (!config::NEAR_AUTO || (scan_cuts >= 5 && scan_cuts * 4 >= scan_count)) &&\n"
     "                          !(config::NEAR_NOALTAR && has_altar_side()) && !(config::NEAR_PLAIN && spawn_raid == 1);\n"
     "        if (!rush && !near) return metadata;\n"
     "        order_cache = metadata;\n"
     "        if (near) {\n"
     "            // The scan stops when fuel runs short (01boss-battle: 80% of scans, about 12 of 31\n"
     "            // groups): evaluate the nearest groups first so a cut scan still picks a near one.\n"
     "            const auto here = bc::self().position();\n"
     "            std::vector<std::pair<std::int64_t, ObjectivePtr>> keyed;\n"
     "            for (const auto& o : metadata) {\n"
     "                std::int64_t d = std::numeric_limits<std::int64_t>::max();\n"
     "                for (const auto p : o->positions) d = std::min(d, distance(here, p));\n"
     "                keyed.emplace_back(d, o);\n"
     "            }\n"
     "            std::stable_sort(keyed.begin(), keyed.end(), [](const auto& a, const auto& b) { return a.first < b.first; });\n"
     "            for (std::size_t i = 0; i < keyed.size(); ++i) order_cache[i] = keyed[i].second;\n"
     "        }\n"
     "        if (rush) std::stable_partition(order_cache.begin(), order_cache.end(), [&](const ObjectivePtr& o) { return altar_side(o); });\n"
     "        return order_cache;\n"
     "    }\n"
     "\n"
     "    // 01boss-battle, 02guardians: the only altar's open tiles are all monolith spawn tiles.\n"
     "    std::optional<std::vector<bc::vec2>> gate_tiles_cache;\n"
     "    const std::vector<bc::vec2>& gate_tiles() {\n"
     "        if (!gate_tiles_cache) {\n"
     "            gate_tiles_cache.emplace();\n"
     "            if (gm::altars().count() == 1) {\n"
     "                std::vector<bc::vec2> mono;\n"
     "                for (const auto& g : gm::camp_groups())\n"
     "                    for (const auto& c : g.camps())\n"
     "                        if (c.is_monolith()) mono.push_back(c.spawn_position());\n"
     "                const auto altar = gm::altars().positions()[0];\n"
     "                const auto open = nav::around(altar, bc::constants::submit_gems_range) & ~nav::static_walls();\n"
     "                bool all = !open.is_empty();\n"
     "                for (const auto p : open.positions())\n"
     "                    if (std::find(mono.begin(), mono.end(), p) == mono.end()) all = false;\n"
     "                if (all) *gate_tiles_cache = open.positions();\n"
     "            }\n"
     "        }\n"
     "        return *gate_tiles_cache;\n"
     "    }\n"
     "    bool gate_map() { return !gate_tiles().empty(); }\n"
     "    bool gated_map() { return config::P_GATE && gate_map(); }\n"
     "    // Round until which the gate is believed open; 0 = closed (monoliths start alive).\n"
     "    std::int64_t gate_until = 0;\n"
     "    std::int64_t gate_seen = -1;\n"
     "    static std::uint32_t read_u32(std::size_t offset) {\n"
     "        std::array<std::byte, 4> b{};\n"
     "        bc::shared_memory.read(offset, std::span<std::byte>{b});\n"
     "        return std::uint32_t(b[0]) | std::uint32_t(b[1]) << 8 | std::uint32_t(b[2]) << 16 | std::uint32_t(b[3]) << 24;\n"
     "    }\n"
     "    static void write_u32(std::size_t offset, std::uint32_t v) {\n"
     "        const std::array<std::byte, 4> b{std::byte(v & 255), std::byte((v >> 8) & 255), std::byte((v >> 16) & 255), std::byte(v >> 24)};\n"
     "        bc::shared_memory.write(offset, std::span<const std::byte>{b});\n"
     "    }\n"
     "    void observe_gate() {\n"
     "        const auto now = static_cast<std::int64_t>(bc::round_number());\n"
     "        if (gate_seen == now) return;\n"
     "        gate_seen = now;\n"
     "        const bool shared = bc::shared_memory.size() >= 16;\n"
     "        const auto visible = bc::vision::visible_tiles();\n"
     "        bool seen = false, open = false;\n"
     "        turn::check();\n"
     "        for (const auto p : gate_tiles()) {\n"
     "            if (!visible.is_set(p)) continue;\n"
     "            seen = true;\n"
     "            if (!bc::vision::has_camp(p)) open = true;\n"
     "        }\n"
     "        if (seen) {\n"
     "            std::int64_t until = 0;\n"
     "            if (open) {\n"
     "                until = now + 40;\n"
     "                for (const auto& g : *groups) {\n"
     "                    if ((g.spawn_tiles() & visible).is_empty()) continue;\n"
     "                    bool gate = false;\n"
     "                    for (const auto p : gate_tiles())\n"
     "                        if (g.spawn_tiles().is_set(p)) gate = true;\n"
     "                    if (!gate) continue;\n"
     "                    const auto state = g.state();\n"
     "                    if (const auto* r = std::get_if<bc::map::camp_group_respawning>(&state)) until = std::max<std::int64_t>(until, now + r->timer);\n"
     "                }\n"
     "            }\n"
     "            gate_until = until;\n"
     "            turn::check();\n"
     "            if (shared) {\n"
     "                write_u32(8, static_cast<std::uint32_t>(now));\n"
     "                write_u32(12, static_cast<std::uint32_t>(until));\n"
     "            }\n"
     "        } else if (shared) {\n"
     "            turn::check();\n"
     "            if (static_cast<std::int64_t>(read_u32(8)) > 0) gate_until = read_u32(12);\n"
     "        }\n"
     "    }\n"
     "    bool gate_closed() {\n"
     "        if (!gate_map()) return false;\n"
     "        observe_gate();\n"
     "        return gate_until <= static_cast<std::int64_t>(bc::round_number());\n"
     "    }\n"),
    # bank: keep farming while the gate is closed; queue behind an ally on the only free tile.
    ("    void bank(bc::champion& me, const std::vector<bc::champion>& enemies, const std::vector<bc::camp>& camps) override {\n"
     "        const auto now = static_cast<std::int64_t>(bc::round_number());\n"
     "        if (now >= bank_retry_at) {\n",
     "    void bank(bc::champion& me, const std::vector<bc::champion>& enemies, const std::vector<bc::camp>& camps) override {\n"
     "        const auto now = static_cast<std::int64_t>(bc::round_number());\n"
     "        if (gated_map() || (config::P_QUEUE && gate_map())) {\n"
     "            if (gated_map() && gate_closed()) {\n"
     "                banking = false;\n"
     "                bank_progress.reset();\n"
     "                status(\"gate-closed\");\n"
     "                farm(me, enemies);\n"
     "                return;\n"
     "            }\n"
     "            const auto visible = bc::vision::visible_tiles();\n"
     "            bool free_tile = false, ally_on = false;\n"
     "            turn::check();\n"
     "            for (const auto p : gate_tiles()) {\n"
     "                if (!visible.is_set(p)) {\n"
     "                    free_tile = true;\n"
     "                    continue;\n"
     "                }\n"
     "                if (bc::vision::has_camp(p) || p == me.position()) {\n"
     "                    if (p == me.position()) free_tile = true;\n"
     "                    continue;\n"
     "                }\n"
     "                bool ally = false;\n"
     "                for (const auto& a : team->allies)\n"
     "                    if (!same(a, me) && a.is_alive() && a.is_visible() && a.position() == p) ally = true;\n"
     "                if (ally) ally_on = true;\n"
     "                else free_tile = true;\n"
     "            }\n"
     "            if (ally_on && !free_tile) {\n"
     "                bank_progress.reset();\n"
     "                status(\"bank-queue\");\n"
     "                const auto altar = gm::altars().positions()[0];\n"
     "                nav::move_to(nav::around(altar, 3) & ~nav::around(altar, 1) & ~nav::static_walls());\n"
     "                return;\n"
     "            }\n"
     "        }\n"
     "        if (now >= bank_retry_at) {\n"),
    # farm: bank now beside the altar (altar) or while the gate is open (gate).
    ("    void farm(bc::champion& me, const std::vector<bc::champion>& enemies) override {\n"
     "        const auto now = static_cast<std::int64_t>(bc::round_number());\n"
     "        const auto visible = bc::vision::visible_tiles();\n",
     "    void farm(bc::champion& me, const std::vector<bc::champion>& enemies) override {\n"
     + (f"        for (volatile int twin = 0; twin < {50 * TWIN}; ++twin) {{}}\n" if TWIN else "")
     + "        const auto now = static_cast<std::int64_t>(bc::round_number());\n"
     "        const auto visible = bc::vision::visible_tiles();\n"
     "        if (me.gem_count() > 0 && now >= bank_retry_at && altar_field &&\n"
     "            ((config::P_ALTAR && has_altar_side() && altar_field->get(me.position()) <= config::ALTAR_BANK) ||\n"
     "             (gated_map() && !gate_closed()))) {\n"
     "            banking = true;\n"
     "            objective = nullptr;\n"
     "            current_group.reset();\n"
     "            status(\"bank\");\n"
     "            bank(me, enemies, bc::vision::camps());\n"
     "            return;\n"
     "        }\n"),
    # Boss gate round on gated maps.
    ("        bool boss_ready = now >= 650 && purchase_index >= 10 && nearby.size() >= need && health >= 1750.0 * D(need);\n",
     "        const std::int64_t boss_round = gated_map() ? config::GATE_BOSS_ROUND : 650;\n"
     "        bool boss_ready = now >= boss_round && purchase_index >= 10 && nearby.size() >= need && health >= 1750.0 * D(need);\n"),
    ("                if (o->handle == *shared && (!gated(o) || now >= 650 || from_spawn(o)) && (!boss_ready || gated(o))) {\n",
     "                if (o->handle == *shared && (!gated(o) || now >= boss_round || from_spawn(o)) && (!boss_ready || gated(o))) {\n"),
    # Shared claim on a respawning altar cluster: wait for it.
    ("                respawns[chosen->handle] = now + respawning->timer;\n                chosen = nullptr;\n",
     "                respawns[chosen->handle] = now + respawning->timer;\n"
     "                if (!(config::P_ALTAR && now < config::ALTAR_UNTIL && has_altar_side() && altar_side(chosen) && respawning->timer <= config::ALTAR_WAIT)) chosen = nullptr;\n"),
    ("            double best = std::numeric_limits<double>::infinity();\n            bool best_opens = false;\n            for (const auto& o : metadata) {\n",
     "            double best = std::numeric_limits<double>::infinity();\n            bool best_opens = false;\n"
     f"            for (const auto& o : {'scan_order()' if ORDER else 'metadata'}) {{\n"),
    ("                if (chosen && bc::fuel_remaining() < turn::fuel(700'000)) break;\n            }\n        }\n        objective = chosen;\n",
     "                if (chosen && bc::fuel_remaining() < turn::fuel(700'000)) {\n"
     "                    cut_now = true;\n"
     "                    break;\n"
     "                }\n"
     "            }\n"
     "            ++scan_count;\n"
     "            if (cut_now) ++scan_cuts;\n"
     "        }\n        objective = chosen;\n"),
    ("            double best = std::numeric_limits<double>::infinity();\n            bool best_opens = false;\n"
     f"            for (const auto& o : {'scan_order()' if ORDER else 'metadata'}) {{\n",
     "            double best = std::numeric_limits<double>::infinity();\n            bool best_opens = false;\n            bool cut_now = false;\n"
     f"            for (const auto& o : {'scan_order()' if ORDER else 'metadata'}) {{\n"),
    # Scoring: altar clusters count ALTAR_BONUS times, and a respawning one costs its wait.
    ("                if (strategy::respawn_at(respawns, o->handle) > now || (gated(o) && !ready_for(o)) ||\n"
     "                    (boss_ready && !gated(o)))\n"
     "                    continue;\n",
     "                const bool side = config::P_ALTAR && now < config::ALTAR_UNTIL && has_altar_side() && altar_side(o);\n"
     "                const auto back = strategy::respawn_at(respawns, o->handle);\n"
     "                if ((back > now && !(side && back - now <= config::ALTAR_WAIT)) || (gated(o) && !ready_for(o)) ||\n"
     "                    (boss_ready && !gated(o)))\n"
     "                    continue;\n"
     "                double wait = side && back > now ? D(back - now) : 0;\n"),
    ("                    if (const auto* respawning = std::get_if<bc::map::camp_group_respawning>(&state)) {\n"
     "                        respawns[o->handle] = now + respawning->timer;\n"
     "                        continue;\n"
     "                    }\n"
     "                    if (std::holds_alternative<bc::map::camp_group_reward_available>(state)) hp = 0;\n",
     "                    if (const auto* respawning = std::get_if<bc::map::camp_group_respawning>(&state)) {\n"
     "                        respawns[o->handle] = now + respawning->timer;\n"
     "                        if (!(side && respawning->timer <= config::ALTAR_WAIT)) continue;\n"
     "                        wait = respawning->timer;\n"
     "                    } else if (std::holds_alternative<bc::map::camp_group_reward_available>(state)) hp = 0;\n"),
    ("                const double score = (travel + hp / std::max(1.0, power) + bc::constants::capture_time) /\n"
     "                                     std::max(1.0, o->gems + o->gold * 0.4);\n",
     "                double score = (std::max<double>(travel, wait) + hp / std::max(1.0, power) + bc::constants::capture_time) /\n"
     "                               std::max(1.0, o->gems + o->gold * 0.4);\n"
     "                if (side) score /= config::ALTAR_BONUS;\n"),
    # No deposit detour toward a closed gate.
    ("        if (deposit_before_camp(me, chosen, enemies)) return;\n        current_group = chosen->handle;\n        team->claim(chosen->handle);\n",
     "        if (!(gated_map() && gate_closed()) && deposit_before_camp(me, chosen, enemies)) return;\n"
     "        current_group = chosen->handle;\n        team->claim(chosen->handle);\n"),
    # Wait beside (not on) a respawning altar cluster.
    ("        if (targets.empty()) {\n            status(\"party-travel\");\n            nav::move_to(chosen->spawns);\n            return;\n        }\n",
     "        if (targets.empty()) {\n            status(\"party-travel\");\n"
     "            if (config::P_ALTAR && now < config::ALTAR_UNTIL && has_altar_side() && altar_side(chosen) && strategy::respawn_at(respawns, chosen->handle) > now) {\n"
     "                nav::move_to(nav::expand(chosen->spawns, 1, nav::static_walls()) & ~chosen->spawns & ~nav::static_walls());\n"
     "                return;\n"
     "            }\n"
     "            nav::move_to(chosen->spawns);\n            return;\n        }\n"),
    # near=plain: note once whether a gated group is in reach of our spawn.
    ("        const auto ready_for = [&](const ObjectivePtr& o) { return boss_ready || (gated(o) && from_spawn(o)); };\n",
     "        const auto ready_for = [&](const ObjectivePtr& o) { return boss_ready || (gated(o) && from_spawn(o)); };\n"
     "        if (config::NEAR_PLAIN && spawn_raid < 0) {\n"
     "            spawn_raid = 0;\n"
     "            for (const auto& o : metadata)\n"
     "                if (gated(o) && from_spawn(o)) spawn_raid = 1;\n"
     "        }\n"),
])
print("patched", src, "altar" if ALTAR else "", "gate" if GATE else "", f"early={EARLY}" if GATE and EARLY != 650 else "")
