// Ability selection, ported from the Python combat.py.
//
// sage2's first playing version used only basic attacks and earned 542 gold in a
// game where boss_full earned 14,108. Abilities are a large share of the Python
// bot's damage: an attack reset is an extra attack on an eight-turn cycle, an area
// spell hits a whole camp group at once, and crowd control bought at the right
// moment is worth more than its damage.
#pragma once
#include <cambc.h>
#include <cstdint>
#include <span>
#include <variant>
#include <vector>
#include "turnguard.h"

namespace combat {

using cambc::vec2;

// A walk-exclusive spell cannot share a turn with an ordinary walk, so once we
// have walked it is unavailable. Mirrors Python's turn.may_cast.
inline bool exclusive_with_movement(const cambc::ability& a) {
    const auto info = a.info();
    if (!info) return false;
    return std::visit([](const auto& props) { return props.exclusive_with_movement; },
                      *info);
}

inline bool may_cast(const cambc::ability& a) {
    if (!a.info()) return false;
    return !(guard::walked && exclusive_with_movement(a));
}

inline float ground_radius(const cambc::ability& a) {
    if (a.is_aoe_damage()) return a.get<cambc::ability_aoe_damage>().radius;
    if (a.is_dash()) return a.get<cambc::ability_dash>().radius;
    return 1.0f;
}

// A camp that dies mid-turn leaves vision, and then health() throws "Unit is not
// in vision". Every read after an action must be guarded, exactly as the Python
// combat.live() did. The first version of this port omitted it and threw 43 times
// in one game.
inline bool still_there(const cambc::camp& c) {
    if (!cambc::vision::has_camp(c.spawn_position())) return false;
    return c.health() > 0.0;
}

inline bool attack_camp(const cambc::camp& target) {
    auto& me = cambc::self();
    if (!me.can_attack() || !still_there(target)) return false;
    if (!me.attack_tiles().is_set(target.position())) return false;
    guard::check();
    me.attack(target);
    return true;
}

// Prefer an in-range camp, then the one whose neighbours Varg's splash would also
// hit, then the weakest. Splash deals Strength to every valid target within one
// tile of the primary, so a dense cluster is worth far more per attack.
inline const cambc::camp* choose_camp(std::span<const cambc::camp> camps) {
    auto& me = cambc::self();
    const vec2 origin = me.position();
    const std::int32_t reach = me.attack_range();
    const bool splash = me.passive() == cambc::passive_type::splash_attack;
    const cambc::bitboard occupied = cambc::vision::camp_tiles();

    const cambc::camp* best = nullptr;
    bool best_out_of_range = true;
    int best_neighbours = -1;
    double best_hp = 0.0;
    for (const auto& c : camps) {
        if (!c.is_visible() || !still_there(c)) continue;
        const vec2 p = c.position();
        const bool out = origin.chebyshev_distance(p) > reach;
        int neighbours = 0;
        if (splash)
            for (int dx = -1; dx <= 1; ++dx)
                for (int dy = -1; dy <= 1; ++dy)
                    if (occupied.is_set(vec2{p.x + dx, p.y + dy})) ++neighbours;
        const double hp = c.health();
        const bool better = !best
            || (out != best_out_of_range ? !out
                : (neighbours != best_neighbours ? neighbours > best_neighbours
                                                 : hp < best_hp));
        if (better) {
            best = &c; best_out_of_range = out;
            best_neighbours = neighbours; best_hp = hp;
        }
    }
    return best;
}

// Score every ready ability against a camp, cast the best, then attack.
// Returns true if anything was spent.
inline bool fight_camp(const cambc::camp& target,
                       std::span<const cambc::camp> nearby) {
    auto& me = cambc::self();
    if (!still_there(target)) return false;
    const vec2 position = target.position();
    const bool in_attack = me.can_attack() && me.attack_tiles().is_set(position);

    double best_value = -1.0;
    int best_slot = -1;
    bool best_is_reset = false;
    bool best_is_ground = false;
    vec2 best_tile{};

    const auto abilities = me.abilities();
    for (int slot = 0; slot < 2; ++slot) {
        const auto& ability = abilities[static_cast<std::size_t>(slot)];
        guard::check();
        if (!ability.is_ready() || !may_cast(ability)) continue;

        if (ability.is_attack_reset()) {
            // Worth it only if the extra attack would not be wasted overkill.
            if (in_attack && target.health() > me.strength()) {
                const double value = me.strength();
                if (value > best_value) {
                    best_value = value; best_slot = slot;
                    best_is_reset = true; best_is_ground = false;
                }
            }
            continue;
        }
        if (ability.is_shield()) {
            const double incoming = target.strength();
            if (incoming > 0.0 && me.health() < me.max_health() * 0.70
                && me.position().chebyshev_distance(position) <= 4) {
                const double cap = ability.shield_amount();
                const double value = (cap < incoming * 4 ? cap : incoming * 4) * 0.65;
                if (value > best_value) {
                    best_value = value; best_slot = slot;
                    best_is_reset = false; best_is_ground = false;
                }
            }
            continue;
        }
        if (!(ability.is_damage() || ability.is_aoe_damage() || ability.is_cc()))
            continue;
        if (!ability.can_target_camps()) continue;

        const double amount = ability.damage_amount();
        double control = 0.0;
        if (ability.is_cc() && target.strength() > 0.0
            && me.position().chebyshev_distance(position) <= target.attack_range())
            control = target.strength() * 0.8;   // a stunned camp is a turn not taken
        if (amount <= 0.0 && control <= 0.0) continue;

        const cambc::bitboard mask = ability.valid_tiles();
        if (ability.can_target_ground()) {
            // Aim the area so it covers as much live health as possible.
            const float radius = ground_radius(ability);
            const auto ir = static_cast<std::int32_t>(radius);
            cambc::bitboard ring;
            ring.draw_chebyshev(position, radius);
            ring &= mask;
            for (vec2 p : ring.positions()) {
                guard::check();
                double value = 0.0;
                for (const auto& u : nearby) {
                    if (!u.is_visible() || !still_there(u)) continue;
                    if (p.chebyshev_distance(u.position()) > ir) continue;
                    value += amount < u.health() ? amount : u.health();
                }
                if (p.chebyshev_distance(position) <= ir) value += control;
                if (value > best_value) {
                    best_value = value; best_slot = slot;
                    best_is_reset = false; best_is_ground = true; best_tile = p;
                }
            }
        } else if (mask.is_set(position)) {
            const double hp = target.health();
            const double value = (amount < hp ? amount : hp) + control;
            if (value > best_value) {
                best_value = value; best_slot = slot;
                best_is_reset = false; best_is_ground = false;
            }
        }
    }

    bool acted = false;
    if (best_slot >= 0) {
        const auto& ability = abilities[static_cast<std::size_t>(best_slot)];
        if (best_is_reset) {
            // Spend the ordinary attack first, then reset it and attack again.
            acted = attack_camp(target);
            if (still_there(target) && ability.is_ready()) {
                guard::check();
                if (ability.use()) { acted = true; attack_camp(target); }
            }
        } else {
            guard::check();
            if (best_is_ground) acted = ability.use(best_tile);
            else if (ability.can_target_camps() && !ability.is_shield())
                acted = ability.use(target);
            else acted = ability.use();
        }
    }
    if (attack_camp(target)) acted = true;

    // A kill can refresh Vendetta's cooldowns, leaving a reset unused.
    if (me.is_alive() && still_there(target) && !me.can_attack()
        && me.attack_tiles().is_set(target.position())) {
        for (const auto& ability : abilities) {
            if (!ability.is_attack_reset() || !ability.is_ready() || !may_cast(ability))
                continue;
            guard::check();
            if (ability.use()) { acted = true; attack_camp(target); }
            break;
        }
    }
    return acted;
}

// Willow's heal, the one sustain source that does not require walking home.
// Unported until now, and worth 11,117 health a game to boss_full -- a fifth of
// its total sustain. Cheapest target first in relative terms, since a champion at
// 20% of maximum is the one about to die. The 120 floor stops a full-strength cast
// being spent topping someone up by a few points.
constexpr float HEAL_MIN_MISSING = 120.0f;

inline bool heal_allies() {
    guard::check();
    auto& me = cambc::self();
    for (const auto& ability : me.abilities()) {
        if (!ability.is_heal() || !ability.is_ready() || !may_cast(ability)) continue;
        const cambc::bitboard mask = ability.valid_tiles();
        const cambc::champion* best = nullptr;
        float best_frac = 2.0f;
        for (const auto& a : cambc::vision::champions(cambc::team::ally)) {
            if (a == me || !a.is_alive() || !a.is_visible()) continue;
            if (!mask.is_set(a.position())) continue;
            const float max_hp = a.max_health();
            if (max_hp <= 0.0f || max_hp - a.health() < HEAL_MIN_MISSING) continue;
            const float frac = a.health() / max_hp;
            if (frac < best_frac) { best_frac = frac; best = &a; }
        }
        if (best) {
            guard::check();
            if (ability.use(*best)) return true;
        }
    }
    return false;
}

}  // namespace combat
