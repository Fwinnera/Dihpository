// Native path fields, legal short dashes and threat-aware withdrawal.
//
// A faithful port of the Python navigation.py, which the measurements say is the
// strongest module in the old bot: it pushes all the work into native SDK
// primitives (bitboard, distance_field, reachable_tiles) and keeps almost nothing
// in interpreted loops. C++ buys only ~3-6x more engine calls per turn, so this
// layer is ported structure-for-structure rather than redesigned.
#pragma once
#include <cambc.h>
#include <cstdint>
#include <optional>
#include <vector>
#include "turnguard.h"

namespace nav {

using cambc::bitboard;
using cambc::vec2;

struct Mobility {
    int radius = 0;
    bool crystal = false;
    bool operator==(const Mobility& o) const {
        return radius == o.radius && crystal == o.crystal;
    }
    bool operator!=(const Mobility& o) const { return !(*this == o); }
};

inline std::optional<bitboard> terrain_cache;
inline std::optional<bool> crystal_needed;
inline std::uint32_t mobility_round = 0xffffffffu;
inline Mobility mobility_value;

inline std::int32_t distance(vec2 a, vec2 b) { return a.chebyshev_distance(b); }

// Walls that never change: terrain plus the enemy spawn we may not enter.
inline const bitboard& static_walls() {
    if (!terrain_cache)
        terrain_cache = cambc::map::walls() | cambc::map::holes()
                      | cambc::map::altars()
                      | cambc::map::spawn_region(cambc::team::enemy);
    return *terrain_cache;
}

inline bitboard around(vec2 position, float radius) {
    guard::check();
    bitboard result;
    result.draw_chebyshev(position, radius);
    return result;
}

// Memoised on the round: nothing feeding it can change inside one round, and the
// Python profile showed it being recomputed two to four times per turn.
inline Mobility mobility() {
    const std::uint32_t now = cambc::round_number();
    if (now == mobility_round) return mobility_value;
    const auto& me = cambc::self();
    Mobility value;
    for (const auto& a : me.abilities())
        if (a.is_dash()) { value.radius = 2; value.crystal = false; break; }
    if (value.radius == 0) {
        const auto& c = me.consumables()[cambc::consumable_type::tp_crystal];
        if (c.count() > 0) { value.radius = 3; value.crystal = true; }
    }
    mobility_round = now;
    mobility_value = value;
    return value;
}

// Everything we may not stand on right now, excluding our own tile.
inline bitboard blocked() {
    bitboard mask = static_walls() | cambc::vision::champion_tiles()
                  | cambc::vision::camp_tiles() | cambc::vision::teleport_tiles();
    guard::check();
    mask.set(cambc::self().position(), false);
    return mask;
}

// Native eight-neighbour dilation; every intermediate dash step stays legal.
inline bitboard expand(const bitboard& mask, int radius, const bitboard& path_walls) {
    bitboard result = mask;
    for (int i = 0; i < radius; ++i) {
        bitboard horizontal = result | result.shift_right(1) | result.shift_right(-1);
        result = (horizontal | horizontal.shift_up(1) | horizontal.shift_up(-1))
                 & ~path_walls;
    }
    return result;
}

// One walking component plus the legal jump portals out of it.
struct Layer {
    cambc::distance_field field;
    bitboard reached;
};

inline bool is_crystal_restricted(const cambc::champion& me) {
    return me.restrictions().contains(cambc::buff_restrictions::consumable);
}

// Travel cost across dash-linked components: a later layer costs 8 per hop.
struct TravelCosts {
    vec2 origin{};
    const std::vector<Layer>* layers = nullptr;

    std::uint16_t get(vec2 p) const {
        if (!layers) return cambc::distance_field::unreachable;
        for (std::size_t i = 0; i < layers->size(); ++i) {
            const Layer& l = (*layers)[i];
            if (l.reached.is_set(p)) {
                const std::uint16_t walk = l.field.get(p);
                const std::int32_t hops = static_cast<std::int32_t>(i) * 8;
                const std::int32_t cheb = origin.chebyshev_distance(p);
                const std::int32_t cost = static_cast<std::int32_t>(walk) + hops;
                return static_cast<std::uint16_t>(cheb > cost ? cheb : cost);
            }
        }
        return cambc::distance_field::unreachable;
    }
};

// Try a dash that makes real progress down `field`, never landing illegally.
inline bool dash(const cambc::distance_field& field, const bitboard& walls) {
    const auto& me = cambc::self();
    if (!me.state().contains(cambc::champion_state::can_cast)) return false;
    const vec2 origin = me.position();
    const std::uint16_t start = field.get(origin);
    for (const auto& ability : me.abilities()) {
        if (!ability.is_dash() || !ability.is_ready()) continue;
        // A dash crosses holes but not walls, and cannot land on an occupied tile.
        bitboard path_walls = cambc::map::walls() | cambc::map::altars()
                            | cambc::map::spawn_region(cambc::team::enemy)
                            | cambc::vision::champion_tiles()
                            | cambc::vision::camp_tiles()
                            | cambc::vision::teleport_tiles();
        path_walls.set(origin, false);
        if (!ability.info()) continue;
        const auto dash_info = ability.get<cambc::ability_dash>();
        const auto reach = static_cast<std::uint16_t>(dash_info.range);
        bitboard landings = path_walls.reachable_tiles(origin, reach)
                          & ability.valid_tiles() & ~walls;
        const bitboard live = blocked();
        std::uint16_t best = start;
        vec2 chosen = origin;
        for (vec2 p : landings.positions()) {
            const std::uint16_t d = field.get(p);
            // require two turns' worth of progress, as the Python version did
            if (d + 2 > start) continue;
            if (d < best && !live.is_set(p)) { best = d; chosen = p; }
        }
        if (chosen != origin) {
            guard::check();
            if (ability.use(chosen)) return true;
        }
    }
    return false;
}

// Walk or dash one step toward the cheapest tile of `goals`.
// Returns true if we actually moved.
inline bool move_to(const bitboard& goals, const bitboard* extra_blocked = nullptr,
                    bool use_dash = true) {
    guard::check();
    const auto& me = cambc::self();
    if (!me.is_alive()) return false;
    const vec2 origin = me.position();
    if (goals.is_set(origin)) return false;
    const auto st = me.state();
    if (!st.contains(cambc::champion_state::can_move)
        && !st.contains(cambc::champion_state::can_cast)) return false;

    bitboard walls = blocked();
    if (extra_blocked) {
        walls = walls | *extra_blocked;
        walls.set(origin, false);
    }
    const bitboard legal = goals & ~walls;
    if (legal.is_empty()) return false;

    cambc::distance_field field;
    bitboard visited;
    bitboard roots = legal;
    bitboard destinations;
    destinations.set(origin, true);
    field.compute_to(walls, roots, destinations, visited);
    guard::check();
    if (!visited.is_set(origin)) return false;   // cross-component handled by caller

    bool moved = false;
    if (use_dash && dash(field, walls)) {
        if (goals.is_set(cambc::self().position())) return true;
        moved = true;
    }
    if (cambc::self().state().contains(cambc::champion_state::can_move)) {
        const bitboard live = blocked();
        for (vec2 delta : field.next_moves_from(cambc::self().position())) {
            guard::check();
            const vec2 target = cambc::self().position() + delta;
            if (live.is_set(target)) continue;
            if (cambc::self().move_absolute(target)) {
                guard::walked = true;
                moved = true;
                break;
            }
        }
    }
    return moved;
}

// Tiles within reach of a live threat, used to prefer safe routes.
// A camp's attack range by kind. `attack_range()` is `base_stats().base_attack_range`
// and `base_stats()` is an engine design lookup, so asking a camp its range costs a
// call every time. The answer depends only on the kind, and `kind()` is noexcept.
inline std::int32_t camp_range(const cambc::camp& c) {
    static std::int32_t cache[16] = {0};
    const int k = static_cast<int>(c.kind());
    if (k < 0 || k >= 16) return c.attack_range();
    if (cache[k] == 0) cache[k] = c.base_stats().base_attack_range;
    return cache[k];
}

inline bitboard threat_mask(const std::vector<cambc::champion>& enemies,
                            const std::vector<cambc::camp>& camps, int margin = 0) {
    // `draw_chebyshev` ORs a disc into the board it is called on, so drawing each
    // threat straight into one mask is a single engine call per threat. The old
    // `mask = mask | around(...)` built a throwaway bitboard, drew into it, then
    // allocated again for the union: two allocations and two calls per threat, for
    // the same result. Pathfinding is the largest remaining cost inside farm().
    // The per-threat `guard::check()` stays. It came along for free inside
    // `around()`, and dropping it with the allocation was a correctness change
    // smuggled into a fuel change: without it the mask can be built across a fuel
    // suspension and the move acted on afterwards, which is the stale-plan bug the
    // whole turn guard exists to prevent. It costs about 45 fuel.
    bitboard mask;
    for (const auto& e : enemies) {
        if (!e.is_visible() || !e.is_alive()) continue;
        guard::check();
        const int r = e.attack_range() > 4 ? e.attack_range() : 4;
        mask.draw_chebyshev(e.position(), static_cast<float>(r + margin));
    }
    for (const auto& c : camps) {
        if (!c.is_visible() || c.strength() <= 0.0 || !c.is_awake()) continue;
        guard::check();
        mask.draw_chebyshev(c.position(), static_cast<float>(camp_range(c)));
    }
    return mask;
}

}  // namespace nav
