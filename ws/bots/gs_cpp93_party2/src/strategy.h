// strategy.py: route-aware camp utility, live reward checks, and score-aware banking.
#pragma once
#include "common.h"
#include "config.h"
#include "nav.h"
#include "policy.h"
#include "teamwork.h"
#include "turn.h"

namespace strategy {

struct Objective {
    bc::map::camp_group group;
    int handle;
    bc::bitboard spawns;
    std::vector<bc::vec2> positions;
    std::vector<std::pair<int, int>> coords;
    int count;
    std::vector<bc::camp> camps;
    double hp = 0, incoming = 0;
    double gems, gold;
    bool monolith = false;
    bool heavy = false;  // a monolith, or more strength than one champion can clear alone

    explicit Objective(const bc::map::camp_group& g)
        : group{g}, handle{handle_of(g)}, spawns{g.spawn_tiles()}, positions{spawns.positions()},
          count{static_cast<int>(positions.size())}, camps{g.camps().begin(), g.camps().end()},
          gems{static_cast<double>(g.gem_value())}, gold{static_cast<double>(g.gold_value())} {
        for (const auto p : positions) coords.emplace_back(p.x, p.y);
        for (const auto& c : camps) {
            hp += c.base_stats().base_health;
            incoming += c.base_stats().base_strength;
            if (c.is_monolith()) monolith = true;
        }
        heavy = monolith || incoming > policy::SOLO_STRENGTH;
    }
};

using ObjectivePtr = std::shared_ptr<const Objective>;
using Respawns = std::map<int, std::int64_t>;

inline std::int64_t respawn_at(const Respawns& respawns, int handle) {
    const auto it = respawns.find(handle);
    return it == respawns.end() ? 0 : it->second;
}

inline std::vector<ObjectivePtr> prepare(const std::vector<bc::map::camp_group>& groups) {
    const auto& result = nav::field_from(bc::self().position());
    std::vector<ObjectivePtr> objectives;
    for (const auto& g : groups) {
        bool reachable = false;
        for (const auto p : g.spawn_tiles().positions())
            if (result.reached.is_set(p)) {
                reachable = true;
                break;
            }
        if (reachable) objectives.push_back(std::make_shared<const Objective>(g));
    }
    return objectives;
}

inline double dps(const bc::champion& me, int count = 1) {
    const double strength = me.strength();
    double damage = strength;
    for (const auto& ability : me.abilities()) {
        if (!ability.info()) continue;
        if (ability.is_attack_reset()) {
            damage += strength / 8;
        } else if (ability.is_damage() || ability.is_cc() || ability.is_aoe_damage()) {
            damage += info_modifier(ability) * D(me.focus()) / 8 * (ability.is_aoe_damage() ? std::min(count, 3) : 1);
        }
    }
    if (me.champion_name() == bc::champion_type::varg) damage *= std::min(count, 3);
    return std::max(1.0, damage);
}

inline bool should_bank(bool enemies_seen, int altar_distance) {
    auto& me = bc::self();
    const auto gems = static_cast<std::int64_t>(me.gem_count());
    if (!gems) return false;
    const auto now = static_cast<std::int64_t>(bc::round_number());
    const auto ticks = (gems + 9) / 10;
    return gems >= config::BANK_GEMS || (gems >= 22 && altar_distance <= 4) ||
           static_cast<std::int64_t>(bc::global_submitted_gems(bc::team::ally)) + gems >=
               static_cast<std::int64_t>(bc::constants::winning_gems) ||
           now + altar_distance + ticks + 20 >= static_cast<std::int64_t>(bc::constants::max_rounds) ||
           (enemies_seen && gems >= 22 && D(me.health()) < D(me.max_health()) * 0.70);
}

template <class State>
inline bool is_state(const bc::map::camp_group& group) {
    return std::holds_alternative<State>(group.state());
}

inline ObjectivePtr choose_group(const std::vector<ObjectivePtr>& metadata, const bc::champion& me, Respawns& respawns,
                                 std::optional<int> current, const Teamwork& team,
                                 const std::vector<bc::champion>& enemies) {
    const auto now = static_cast<std::int64_t>(bc::round_number());
    const auto position = me.position();
    const int x = position.x, y = position.y;
    const double damage = dps(me);
    const bool splash = me.champion_name() == bc::champion_type::varg;
    const double hp_budget = std::max(100.0, D(me.health()) - D(me.max_health()) * 0.20);
    double heal_rate = 0, helper_dps = 0;
    if (splash) {
        for (const auto& ally : team.allies) {
            if (!same(ally, me) && ally.champion_name() == bc::champion_type::willow && ally.is_alive() && ally.is_visible() &&
                distance(position, ally.position()) <= 8) {
                helper_dps += D(ally.strength()) * 0.8;
                for (const auto& ability : ally.abilities())
                    if (ability.is_heal())
                        heal_rate += D(ability.heal_amount()) / std::max(1, info_max_cooldown(ability));
            }
        }
    }
    const auto claims = team.assignments();
    std::map<int, int> claimed;
    for (std::size_t i = 0; i < claims.size(); ++i)
        if (static_cast<int>(i) != team.slot) ++claimed[claims[i]];
    // Bound Python work before asking the native pathfinder for exact costs.
    // Exact route evaluation is an anytime search: return the best objective
    // before the reserve for movement and combat is spent.
    const double capture = bc::constants::capture_time;
    struct Ranked {
        double estimate;
        ObjectivePtr objective;
        double clear, value, bias;
    };
    std::vector<Ranked> ranked;
    for (std::size_t i = 0; i < metadata.size(); ++i) {
        if (i % 8 == 0) turn::check();
        const auto& objective = metadata[i];
        const int handle = objective->handle;
        if (objective->monolith || respawn_at(respawns, handle) > now) continue;
        int travel = 10000;
        for (const auto& [px, py] : objective->coords) {
            const int gap = std::max(std::abs(x - px), std::abs(y - py));
            if (gap < travel) travel = gap;
        }
        const double clear = objective->hp / (damage * (splash ? std::min(objective->count, 3) : 1) + helper_dps);
        const double value = objective->gems + objective->gold * (now < 500 ? 0.3 : 0.25);
        const double cost = (clear + capture) * 100 / std::max(1.0, value);
        double bias = claimed.count(handle) && claimed[handle] ? (objective->incoming < 70 ? 20 : 5) : 0;
        if (current && handle == *current) bias -= 5;
        const double risk = std::min(45.0, std::max(0.0, objective->incoming * clear * 0.55 / hp_budget - 0.7) * 12);
        const double estimate = cost + (travel + risk) * 100 / std::max(1.0, value) + bias;
        ranked.push_back({estimate, objective, clear, value, bias});
    }
    std::stable_sort(ranked.begin(), ranked.end(), [](const Ranked& a, const Ranked& b) { return a.estimate < b.estimate; });
    const auto& costs = nav::field_from(position);
    const auto visible = bc::vision::visible_tiles();
    std::vector<bc::vec2> enemy_positions;
    for (const auto& enemy : enemies) {
        turn::check();
        if (enemy.is_visible() && enemy.is_alive()) enemy_positions.push_back(enemy.position());
    }
    ObjectivePtr best;
    double best_score = std::numeric_limits<double>::infinity();
    for (const auto& row : ranked) {
        turn::check();
        if (best && bc::fuel_remaining() < turn::fuel(950'000)) break;
        const auto& objective = row.objective;
        double clear = row.clear;
        std::vector<bc::vec2> positions;
        for (const auto p : objective->positions)
            if (costs.reached.is_set(p)) positions.push_back(p);
        if (positions.empty()) continue;
        int travel = std::numeric_limits<int>::max();
        for (const auto p : positions) travel = std::min(travel, costs.costs.get(p));
        bool reward = false;
        double incoming = objective->incoming;
        if (!(objective->spawns & visible).is_empty()) {
            const auto state = objective->group.state();
            if (const auto* respawning = std::get_if<bc::map::camp_group_respawning>(&state)) {
                respawns[objective->handle] = now + respawning->timer;
                continue;
            }
            if (std::holds_alternative<bc::map::camp_group_reward_available>(state)) {
                const auto owner = team.collector(objective->handle, &objective->spawns);
                if (owner && *owner != team.slot && !objective->spawns.is_set(position)) continue;
                reward = true;
                clear = 0;
                incoming = 0;
            } else {
                // A half-cleared camp is cheaper than its original design HP.
                double remaining_hp = 0;
                incoming = 0;
                for (const auto& camp : objective->camps) {
                    turn::check();
                    if (camp.is_visible()) {
                        if (!bc::vision::has_camp(camp.spawn_position())) continue;
                        remaining_hp += camp.health();
                        incoming += camp.strength();
                    } else {
                        remaining_hp += camp.base_stats().base_health;
                        incoming += camp.base_stats().base_strength;
                    }
                }
                clear *= remaining_hp / std::max(1.0, objective->hp);
            }
        }
        const double expected_damage = std::max(0.0, incoming * clear * 0.55 - heal_rate * clear);
        if (expected_damage > hp_budget) continue;
        const double risk = std::min(45.0, std::max(0.0, expected_damage / hp_budget - 0.7) * 12);
        double score = (travel + clear + capture + risk) * 100 / std::max(1.0, row.value) + row.bias;
        if (!enemy_positions.empty()) {
            std::int64_t nearest = std::numeric_limits<std::int64_t>::max();
            for (const auto p : positions)
                for (const auto q : enemy_positions) nearest = std::min(nearest, distance(p, q));
            score += std::max<std::int64_t>(0, 5 - nearest) * 4;
        }
        if (reward) score = (travel + capture) * 100 / std::max(1.0, row.value) - 15;
        if (score < best_score) {
            best = objective;
            best_score = score;
        }
    }
    return best;
}

// Break the zero-income deadlock by rallying at one affordable group.
// A claim is a rendezvous, never permission to read an unseen ally's stats.
// Existing leaders take precedence so stranded farmers combine their damage.
inline ObjectivePtr choose_cooperative(const std::vector<ObjectivePtr>& metadata, const bc::champion& me, Respawns& respawns,
                                       const Teamwork& team) {
    const auto now = static_cast<std::int64_t>(bc::round_number());
    const auto claims = team.assignments();
    std::map<int, int> grouped;
    for (std::size_t index = 0; index < team.allies.size(); ++index)
        if (static_cast<int>(index) != team.slot && team.allies[index].is_alive() && claims[index] >= 0)
            ++grouped[claims[index]];
    const auto& costs = nav::field_from(me.position());
    const auto visible = bc::vision::visible_tiles();
    ObjectivePtr best;
    double score = std::numeric_limits<double>::infinity();
    for (const auto& o : metadata) {
        turn::check();
        if (o->monolith || respawn_at(respawns, o->handle) > now) continue;
        std::vector<bc::vec2> positions;
        for (const auto p : o->positions)
            if (costs.reached.is_set(p)) positions.push_back(p);
        if (positions.empty()) continue;
        double hp = o->hp;
        if (!(o->spawns & visible).is_empty()) {
            const auto state = o->group.state();
            if (const auto* respawning = std::get_if<bc::map::camp_group_respawning>(&state)) {
                respawns[o->handle] = now + respawning->timer;
                continue;
            }
            if (std::holds_alternative<bc::map::camp_group_reward_available>(state)) hp = 0;
        }
        int travel = std::numeric_limits<int>::max();
        for (const auto p : positions) travel = std::min(travel, costs.costs.get(p));
        const bool leader = grouped.count(o->handle) && grouped[o->handle];
        // Bound the initial gamble. A team can bootstrap elk packs; it cannot
        // tank several golems with starter stats and no equipment.
        if (o->incoming > 180 && !leader) continue;
        double cost = (travel + hp / 180 + bc::constants::capture_time) / std::max(1.0, o->gems + o->gold * 0.2);
        if (leader) cost *= 0.35;
        if (cost < score) {
            best = o;
            score = cost;
        }
        if (best && bc::fuel_remaining() < turn::fuel(800'000)) break;
    }
    return best;
}

}  // namespace strategy
