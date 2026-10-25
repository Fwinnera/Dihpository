// combat.py: select useful casts, preserve resets, and fight only for a concrete gain.
#pragma once
#include "common.h"
#include "config.h"
#include "nav.h"
#include "policy.h"
#include "teamwork.h"
#include "turn.h"

namespace combat {

inline std::vector<bc::camp> visible_camps(std::span<const bc::camp> camps) {
    std::vector<bc::camp> result;
    for (const auto& camp : camps) {
        turn::check();
        if (camp.is_visible() && bc::vision::has_camp(camp.spawn_position()) && camp.health() > 0) result.push_back(camp);
    }
    return result;
}

// Score splash targets in O(9N), without live-position queries in a nested loop.
inline std::optional<bc::camp> choose_camp(const std::vector<bc::camp>& camps) {
    turn::check();
    auto& me = bc::self();
    const auto origin = me.position();
    const auto radius = me.attack_range();
    struct Row {
        const bc::camp* camp;
        int x, y;
        double hp;
    };
    std::vector<Row> rows;
    for (const auto& camp : camps) {
        turn::check();
        if (!camp.is_visible() || !bc::vision::has_camp(camp.spawn_position())) continue;
        const double hp = camp.health();
        if (hp > 0) {
            const auto p = camp.spawn_position();  // Camps never move; this is public static data.
            rows.push_back({&camp, p.x, p.y, hp});
        }
    }
    if (rows.empty()) return std::nullopt;
    const bool splash = me.champion_name() == bc::champion_type::varg;
    std::optional<std::tuple<bool, int, double>> best_score;
    const bc::camp* best = nullptr;
    for (const auto& row : rows) {
        const auto gap = std::max(std::abs(origin.x - row.x), std::abs(origin.y - row.y));
        int neighbours = 0;
        if (splash)
            for (const auto& other : rows)
                if (std::max(std::abs(row.x - other.x), std::abs(row.y - other.y)) <= 1) ++neighbours;
        const auto score = std::make_tuple(gap > radius, -neighbours, row.hp);
        if (!best_score || score < *best_score) {
            best_score = score;
            best = row.camp;
        }
    }
    turn::check();
    return *best;
}

inline bool live(const bc::camp& target) {
    turn::check();
    return bc::vision::has_camp(target.spawn_position());
}

inline bool live(const bc::champion& target) {
    turn::check();
    return target.is_visible() && target.is_alive();
}

template <class T>
inline bool attack(const T& target) {
    auto& me = bc::self();
    if (me.can_attack() && live(target) && target.health() > 0 && me.attack_tiles().is_set(target.position())) {
        turn::check();
        me.attack(target);
        return true;
    }
    return false;
}

inline bool heal_allies(const std::vector<bc::champion>& allies) {
    turn::check();
    auto& me = bc::self();
    for (const auto& ability : me.abilities()) {
        if (!ability.is_heal() || !ability.is_ready() || !turn::may_cast(ability)) continue;
        const auto mask = ability.valid_tiles();
        std::vector<const bc::champion*> targets;
        for (const auto& a : allies)
            if (!same(a, me) && a.is_alive() && a.is_visible() && mask.is_set(a.position()) &&
                D(a.max_health()) - D(a.health()) >= config::HEAL_MIN_MISSING)
                targets.push_back(&a);
        if (!targets.empty()) {
            const auto* target = *first_min(targets.begin(), targets.end(),
                                             [](const bc::champion* a) { return D(a->health()) / D(a->max_health()); });
            turn::check();
            return ability.use(*target);
        }
    }
    return false;
}

inline double damage_against(const bc::ability& ability, const bc::champion& target) { return ability.damage_amount(target); }
inline double damage_against(const bc::ability& ability, const bc::camp&) { return ability.damage_amount(); }

inline bool use_on(const bc::ability& ability, const bc::champion& target) { return ability.use(target); }
inline bool use_on(const bc::ability& ability, const bc::camp& target) { return ability.use(target); }

template <class T>
inline bool fight(const T& target, const std::vector<T>& nearby = {}) {
    auto& me = bc::self();
    if (!live(target) || target.health() <= 0) return false;
    constexpr bool enemy = std::is_same_v<T, bc::champion>;
    const auto position = target.position();
    const bool in_attack = me.can_attack() && me.attack_tiles().is_set(position);
    // aimed: none (index 0), a tile, or the target itself.
    struct Choice {
        double value;
        const bc::ability* ability;
        int aim;  // 0 none, 1 tile, 2 target
        bc::vec2 tile;
    };
    std::vector<Choice> choices;
    const auto abilities = me.abilities();
    for (const auto& ability : abilities) {
        turn::check();
        if (!ability.is_ready() || !turn::may_cast(ability)) continue;
        if (ability.is_attack_reset()) {
            if (in_attack && D(target.health()) > D(me.strength())) choices.push_back({D(me.strength()), &ability, 0, {}});
            continue;
        }
        if (ability.is_shield()) {
            const double incoming = target.strength();
            if (incoming && D(me.health()) < D(me.max_health()) * 0.70 && distance(me.position(), position) <= 4)
                choices.push_back({std::min(D(ability.shield_amount()), incoming * 4) * 0.65, &ability, 0, {}});
            continue;
        }
        if (!(ability.is_damage() || ability.is_aoe_damage() || ability.is_cc())) continue;
        if (enemy && !ability.can_target_enemies()) continue;
        if (!enemy && !ability.can_target_camps()) continue;
        const double amount = damage_against(ability, target);
        double control = 0;
        bool controllable = true;
        if constexpr (enemy) controllable = target.champion_name() != bc::champion_type::marcella;
        if (ability.is_cc() && controllable) {
            if constexpr (enemy) {
                control = D(target.strength()) * 0.8 + (target.is_submitting_gems() ? 120 : 0);
            } else {
                if (target.strength() && distance(me.position(), position) <= target.attack_range())
                    control = D(target.strength()) * 0.8;
            }
        }
        if (!amount && !control) continue;
        const auto mask = ability.valid_tiles();
        if (ability.can_target_ground()) {
            const int radius = static_cast<int>(info_radius(ability, 1));
            std::vector<const T*> units;
            bool included = false;
            for (const auto& u : nearby)
                if (live(u) && u.health() > 0) {
                    units.push_back(&u);
                    if (same(u, target)) included = true;
                }
            if (!included) units.push_back(&target);
            std::optional<bc::vec2> best;
            double best_value = -1;
            for (const auto p : (nav::around(position, radius) & mask).positions()) {
                turn::check();
                double value = 0;
                for (const auto* u : units)
                    if (distance(p, u->position()) <= radius) value += std::min(amount, D(u->health()));
                if (distance(p, position) <= radius) value += control;
                if (value > best_value) {
                    best = p;
                    best_value = value;
                }
            }
            if (best) choices.push_back({best_value, &ability, 1, *best});
        } else if (mask.is_set(position)) {
            choices.push_back({std::min(amount, D(target.health())) + control, &ability, 2, {}});
        }
    }
    std::stable_sort(choices.begin(), choices.end(), [](const Choice& a, const Choice& b) { return a.value > b.value; });
    bool acted = false;
    if (!choices.empty()) {
        const auto& choice = choices.front();
        const auto& ability = *choice.ability;
        if (ability.is_attack_reset()) {
            // Reset after the ordinary attack, including after a ranged walk
            // when an attack allowance has already been consumed.
            acted = attack(target);
            if (live(target) && target.health() > 0 && ability.is_ready()) {
                turn::check();
                if (ability.use()) {
                    acted = true;
                    attack(target);
                }
            }
        } else {
            turn::check();
            if (choice.aim == 0) acted = ability.use();
            else if (choice.aim == 1) acted = ability.use(choice.tile);
            else acted = use_on(ability, target);
        }
    }
    if (attack(target)) acted = true;
    // An earlier spell may have killed a camp and refreshed Vendetta's reset.
    // One successful cast per turn is still enforced by is_ready/can_cast.
    if (me.is_alive() && live(target) && target.health() > 0 && !me.can_attack()) {
        if (me.attack_tiles().is_set(target.position())) {
            for (const auto& ability : me.abilities()) {
                if (ability.is_attack_reset() && ability.is_ready() && turn::may_cast(ability)) {
                    turn::check();
                    if (ability.use()) {
                        acted = true;
                        attack(target);
                    }
                    break;
                }
            }
        }
    }
    return acted;
}

inline std::optional<bc::champion> choose_enemy(const std::vector<bc::champion>& enemies,
                                                const std::vector<bc::champion>& allies, bool defending = false) {
    auto& me = bc::self();
    const auto attack_mask = me.attack_tiles();
    using Score = std::tuple<bool, bool, bool, double, std::int64_t, std::int64_t>;
    std::optional<Score> best_score;
    std::optional<bc::champion> best;
    for (const auto& enemy : enemies) {
        turn::check();
        const auto gap = distance(me.position(), enemy.position());
        if (gap > 7) continue;
        double allied_power = D(me.health()) * std::max(1.0, D(me.strength()));
        for (const auto& ally : allies)
            if (!same(ally, me) && ally.is_alive() && ally.is_visible() && distance(ally.position(), enemy.position()) <= 5)
                allied_power += D(ally.health()) * std::max(1.0, D(ally.strength())) * 0.75;
        double enemy_power = 0;
        for (const auto& e : enemies)
            if (distance(e.position(), enemy.position()) <= 4) enemy_power += D(e.health()) * std::max(1.0, D(e.strength()));
        double burst = D(me.strength()) * 2;
        for (const auto& a : me.abilities())
            if (a.is_ready() && (a.is_damage() || a.is_cc() || a.is_aoe_damage()))
                burst = std::max(burst, D(me.strength()) + D(a.damage_amount(enemy)));
        const bool killable = D(enemy.health()) <= burst;
        const bool interrupt = enemy.is_submitting_gems() && enemy.gem_count() > 0;
        // Trailing: still take a kill, a deposit interrupt, or an adjacent fight.
        // Do not walk five tiles to open one.
        // Only on light camp maps. Heavier maps kept losing close fights under this hold.
        if (!config::map_has_monolith && config::camp_strength > 0 && config::camp_strength <= 370 &&
            config::economy_trailing && gap > 4 && !(killable || interrupt || defending))
            continue;
        if (!(killable || interrupt || defending || gap <= 4 || allied_power > enemy_power * 1.15)) continue;
        // A carrier banks rather than travelling after a healthy enemy.
        if (me.gem_count() >= 22 && !(attack_mask.is_set(enemy.position()) && killable)) continue;
        if (gap > 4 && !(killable || interrupt || allied_power > enemy_power * 1.15)) continue;
        Score score{!attack_mask.is_set(enemy.position()), !interrupt, !killable,
                    D(enemy.health()) / std::max(1.0, D(me.strength())), gap, -static_cast<std::int64_t>(enemy.gem_count())};
        if (!best_score || score < *best_score) {
            best_score = score;
            best = enemy;
        }
    }
    return best;
}

// Our strength against the enemy champions within `radius` of this champion: the
// health-times-strength measure choose_enemy uses, centred on us. Returns the
// ratio and the number of enemies counted; the ratio is infinite when none are.
inline std::pair<double, int> local_power(const std::vector<bc::champion>& enemies,
                                          const std::vector<bc::champion>& allies, int radius) {
    auto& me = bc::self();
    const auto position = me.position();
    double hostile = 0;
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
}

// An enemy in reach that one attack or cast kills.
inline std::optional<bc::champion> finishing_blow(const std::vector<bc::champion>& enemies) {
    auto& me = bc::self();
    const auto attack_mask = me.attack_tiles();
    const double burst = D(me.strength()) * 2;
    std::optional<bc::champion> best;
    for (const auto& enemy : enemies) {
        if (attack_mask.is_set(enemy.position())) {
            double kill = burst;
            for (const auto& a : me.abilities())
                if (a.is_ready() && (a.is_damage() || a.is_cc() || a.is_aoe_damage()))
                    kill = std::max(kill, D(me.strength()) + D(a.damage_amount(enemy)));
            if (D(enemy.health()) <= kill && (!best || enemy.health() < best->health())) best = enemy;
        }
    }
    return best;
}

}  // namespace combat
