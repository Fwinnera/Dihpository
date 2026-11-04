// navigation.py: native path fields, legal short dashes, and threat-aware withdrawal.
#pragma once
#include "common.h"
#include "turn.h"

namespace nav {

struct Layer {
    bc::distance_field field;
    bc::bitboard reached;
};

// Python's field_from returns either a plain DistanceField or a TravelCosts over
// dash/crystal layers; both answer get(position).
struct Costs {
    bc::vec2 origin{};
    std::vector<Layer> layers;
    bool travel = false;

    int get(bc::vec2 p) const {
        if (!travel) return layers[0].field.get(p);
        for (std::size_t index = 0; index < layers.size(); ++index)
            if (layers[index].reached.is_set(p))
                return static_cast<int>(std::max<std::int64_t>(distance(origin, p),
                                                               layers[index].field.get(p) + static_cast<std::int64_t>(index) * 8));
        return 65535;
    }
};

struct FieldResult {
    Costs costs;
    bc::bitboard reached;
};

using Mode = std::pair<int, bool>;

inline std::optional<bc::bitboard> terrain;
inline std::int64_t last_ward = -100;
inline std::optional<bc::distance_field> last_field;
inline std::optional<bc::bitboard> route_goals;
inline std::vector<Layer> route_layers;
inline std::optional<Mode> route_mode;
inline std::optional<bc::bitboard> route_camps;
inline std::optional<bool> crystal_needed;
inline std::optional<std::tuple<int, int, int, bool>> cost_key;
inline std::optional<FieldResult> cost_cache;

inline bc::bitboard around(bc::vec2 position, double radius) {
    turn::check();
    bc::bitboard result;
    result.draw_chebyshev(position, static_cast<float>(radius));
    return result;
}

inline const bc::bitboard& static_walls() {
    if (!terrain)
        terrain = gm::walls() | gm::holes() | gm::altars() | gm::spawn_region(bc::team::enemy);
    return *terrain;
}

inline bc::bitboard blocked() {
    auto mask = static_walls() | bc::vision::champion_tiles() | bc::vision::camp_tiles() | bc::vision::teleport_tiles();
    const auto position = bc::self().position();
    turn::check();
    mask.set(position, false);
    return mask;
}

inline bool needs_crystal() {
    if (!crystal_needed) {
        bc::distance_field field;
        bc::bitboard reached;
        field.compute(static_walls(), gm::spawn_region(bc::team::ally), reached);
        bool needed = false;
        for (const auto& group : gm::camp_groups())
            if (!(group.spawn_tiles() & ~reached).is_empty()) needed = true;
        if (!needed && gm::altars().count() == 1)
            for (const auto& group : gm::camp_groups())
                for (const auto& camp : group.camps())
                    if (camp.is_monolith()) needed = true;
        crystal_needed = needed;
    }
    return *crystal_needed;
}

inline Mode mobility() {
    auto& me = bc::self();
    for (const auto& ability : me.abilities())
        if (ability.is_dash()) return {2, false};
    if (me.consumables()[bc::consumable_type::tp_crystal].count()) return {3, true};
    return {0, false};
}

// Native eight-neighbour dilation; every intermediate dash step is legal.
inline bc::bitboard expand(const bc::bitboard& mask, int radius, const bc::bitboard& path_walls) {
    bc::bitboard result = mask;
    for (int i = 0; i < radius; ++i) {
        const auto horizontal = result | result.shift_right(1) | result.shift_right(-1);
        result = (horizontal | horizontal.shift_up(1) | horizontal.shift_up(-1)) & ~path_walls;
    }
    return result;
}

// Flood walking components, then add legal jump portals between them.
inline std::pair<std::vector<Layer>, bc::bitboard> layers_from(
    const bc::bitboard& roots, int radius, bool crystal, std::optional<Layer> first = std::nullopt,
    std::optional<bc::vec2> stop = std::nullopt, const bc::bitboard* camps = nullptr) {
    bc::bitboard walls = static_walls();
    bc::bitboard path_walls = crystal ? bc::bitboard{} : (gm::walls() | gm::altars() | gm::spawn_region(bc::team::enemy));
    if (camps != nullptr) {
        walls = walls | *camps;
        if (!crystal) path_walls = path_walls | *camps;
    }
    std::vector<Layer> layers;
    if (!first) {
        Layer layer;
        layer.field.compute(walls, roots & ~walls, layer.reached);
        layers.push_back(std::move(layer));
    } else {
        layers.push_back(std::move(*first));
    }
    // Keep each layer's component mask independent from the cumulative frontier.
    bc::bitboard united = layers[0].reached;
    if (stop && united.is_set(*stop)) return {std::move(layers), united};
    for (int i = 0; i < (crystal ? 1 : 8); ++i) {
        turn::check();
        const auto frontier = expand(united, radius, path_walls) & ~walls & ~united;
        if (frontier.is_empty()) break;
        Layer layer;
        layer.field.compute(walls, frontier, layer.reached);
        if (layer.reached.is_empty()) break;
        united |= layer.reached;
        layers.push_back(std::move(layer));
        if (stop && united.is_set(*stop)) break;
    }
    return {std::move(layers), united};
}

// A travel flood that fuel cut short, kept so that the next call from the same
// origin and mobility resumes it instead of starting again. On 01big-world a
// dash champion's flood costs ~79k of a turn's 100k fuel, so it was cut every
// turn and restarted: Vendetta never chose a camp and earned 0 gold all game.
struct PartialFlood {
    std::tuple<int, int, int, bool> key;
    std::vector<Layer> layers;
    bc::bitboard united;
    bool done = false;
};
inline std::optional<PartialFlood> flood_partial;

// Terrain distances depend only on origin and mobility. Preparation, solo
// selection and a possible rally can all reuse this expensive flood. The layers
// are those layers_from would build, in the same order; only the work is spread
// over as many turns as it needs.
inline const FieldResult& field_from(bc::vec2 position) {
    const auto mode = mobility();
    const auto key = std::make_tuple(position.x, position.y, mode.first, mode.second);
    if (cost_key && *cost_key == key) return *cost_cache;
    if (!flood_partial || flood_partial->key != key) {
        flood_partial.reset();
        Layer base;
        turn::check();
        base.field.compute(static_walls(), around(position, 0), base.reached);
        PartialFlood partial;
        partial.key = key;
        partial.united = base.reached;
        partial.layers.push_back(std::move(base));
        flood_partial = std::move(partial);
    }
    turn::check();
    auto& partial = *flood_partial;
    FieldResult result;
    result.costs.origin = position;
    if (mode.first) {
        const bool crystal = mode.second;
        const auto& walls = static_walls();
        const auto path_walls = crystal ? bc::bitboard{} : (gm::walls() | gm::altars() | gm::spawn_region(bc::team::enemy));
        while (!partial.done && partial.layers.size() <= static_cast<std::size_t>(crystal ? 1 : 8)) {
            turn::check();
            const auto frontier = expand(partial.united, mode.first, path_walls) & ~walls & ~partial.united;
            if (frontier.is_empty()) {
                partial.done = true;
                break;
            }
            Layer layer;
            layer.field.compute(walls, frontier, layer.reached);
            if (layer.reached.is_empty()) {
                partial.done = true;
                break;
            }
            // No turn::check() between these two: a resumed flood must hold each
            // layer in both the union and the list, or in neither.
            partial.united |= layer.reached;
            partial.layers.push_back(std::move(layer));
        }
        result.costs.layers = std::move(partial.layers);
        result.costs.travel = true;
        result.reached = partial.united;
    } else {
        result.reached = partial.layers[0].reached;
        result.costs.layers.push_back(std::move(partial.layers[0]));
    }
    flood_partial.reset();
    cost_key = key;
    cost_cache = std::move(result);
    return *cost_cache;
}

inline bool cross_component(const bc::bitboard& goals, const bc::bitboard* extra_blocked = nullptr) {
    turn::check();
    auto& me = bc::self();
    if (!me.is_alive()) return false;
    const auto mode = mobility();
    const auto [radius, crystal] = mode;
    if (!radius) return false;
    const auto camps = bc::vision::camp_tiles();
    auto origin = me.position();
    turn::check();
    if (!(0 <= origin.x && origin.x < gm::width() && 0 <= origin.y && origin.y < gm::height())) return false;
    // A camp can occupy the only apparent portal. Keep it out of both the
    // walking flood and every intermediate dash step, not just the landing.
    bool rebuild = !route_goals || !(goals == *route_goals) || route_mode != mode || !(camps == *route_camps);
    if (!rebuild) {
        bool any = false;
        for (const auto& layer : route_layers)
            if (layer.reached.is_set(origin)) any = true;
        rebuild = !any;
    }
    if (rebuild) {
        auto [layers, reached] = layers_from(goals, radius, crystal, std::nullopt, origin, &camps);
        route_layers = std::move(layers);
        route_goals = goals;
        route_mode = mode;
        route_camps = camps;
    }
    turn::check();
    if (!me.is_alive()) return false;
    origin = me.position();
    turn::check();
    if (!(0 <= origin.x && origin.x < gm::width() && 0 <= origin.y && origin.y < gm::height())) return false;
    int layer = -1;
    for (std::size_t i = 0; i < route_layers.size(); ++i)
        if (route_layers[i].reached.is_set(origin)) {
            layer = static_cast<int>(i);
            break;
        }
    if (layer <= 0) return false;
    const auto& field = route_layers[layer].field;
    const auto& previous = route_layers[layer - 1].reached;
    auto path_walls = gm::walls() | gm::altars() | gm::spawn_region(bc::team::enemy) | bc::vision::champion_tiles() |
                      bc::vision::camp_tiles() | bc::vision::teleport_tiles();
    path_walls.set(origin, false);
    const auto possible = crystal ? around(origin, radius) : path_walls.reachable_tiles(origin, static_cast<std::uint16_t>(radius));
    auto landings = possible & previous & ~blocked();
    if (extra_blocked != nullptr) landings &= ~*extra_blocked;
    auto candidates = landings.positions();
    const auto& order = route_layers[layer - 1].field;
    std::stable_sort(candidates.begin(), candidates.end(),
                     [&](bc::vec2 a, bc::vec2 b) { return order.get(a) < order.get(b); });
    if (!candidates.empty()) {
        if (crystal) {
            const auto& consumable = me.consumables()[bc::consumable_type::tp_crystal];
            turn::check();
            if (consumable.use(candidates[0])) return true;
        } else {
            for (const auto& ability : me.abilities())
                if (ability.is_dash() && ability.is_ready() && turn::may_cast(ability))
                    for (const auto p : candidates) {
                        turn::check();
                        if (ability.use(p)) return true;
                    }
        }
    }
    // Walk to a portal, then wait for our dash rather than oscillating on shore.
    if (me.can_move()) {
        for (const auto delta : field.next_moves_from(origin)) {
            turn::check();
            const auto p = origin + delta;
            if (!blocked().is_set(p) && (extra_blocked == nullptr || !extra_blocked->is_set(p))) {
                if (me.move(delta)) {
                    turn::walked = true;
                    return true;
                }
            }
        }
    }
    return field.get(origin) == 0;
}

// Bypass a camp choke without pretending that dashes can pass through units.
inline bool teleport_past_blocker(const bc::bitboard& goals, const bc::bitboard* extra_blocked = nullptr) {
    auto& me = bc::self();
    if (me.restrictions().contains(bc::buff_restrictions::consumable)) return false;
    const auto& crystal = me.consumables()[bc::consumable_type::tp_crystal];
    if (!crystal.count()) return false;
    bc::distance_field field;
    bc::bitboard reached;
    field.compute(static_walls(), goals & ~static_walls(), reached);
    turn::check();
    if (!me.is_alive()) return false;
    const auto origin = me.position();
    auto candidates = around(origin, 3) & ~blocked();
    if (extra_blocked != nullptr) candidates &= ~*extra_blocked;
    auto positions = candidates.positions();
    std::stable_sort(positions.begin(), positions.end(),
                     [&](bc::vec2 a, bc::vec2 b) { return field.get(a) < field.get(b); });
    for (const auto p : positions) {
        if (!reached.is_set(p) || static_cast<int>(field.get(p)) >= static_cast<int>(field.get(origin)) - 2) break;
        turn::check();
        if (crystal.use(p)) return true;
    }
    return false;
}

inline void scout(const bc::distance_field& field) {
    auto& me = bc::self();
    if (static_cast<std::int64_t>(bc::round_number()) - last_ward < 6 || me.ward_cooldown() ||
        me.restrictions().contains(bc::buff_restrictions::ward))
        return;
    const auto tiles = (me.ward_placement_tiles() & bc::vision::visible_tiles() & ~static_walls() &
                        ~bc::vision::ward_tiles(bc::team::ally)).positions();
    if (tiles.empty()) return;
    const auto p = *first_min(tiles.begin(), tiles.end(), [&](bc::vec2 q) { return field.get(q); });
    const auto old = me.ward_positions();
    if (!old.empty() && distance(old[0], p) < 3) return;
    turn::check();
    if (me.place_ward(p)) last_ward = bc::round_number();
}

inline bool dash(const bc::distance_field& field, const bc::bitboard& walls) {
    auto& me = bc::self();
    if (!me.can_cast()) return false;
    const auto origin = me.position();
    const int start = field.get(origin);
    for (const auto& ability : me.abilities()) {
        if (!ability.is_dash() || !ability.is_ready() || !turn::may_cast(ability)) continue;
        // A dash can cross a hole, but cannot cross a wall or land on an
        // occupied/impassable tile. Compute the actual two-step path mask.
        auto path_walls = gm::walls() | gm::altars() | gm::spawn_region(bc::team::enemy) |
                          bc::vision::champion_tiles() | bc::vision::camp_tiles() | bc::vision::teleport_tiles();
        path_walls.set(origin, false);
        auto landings = (path_walls.reachable_tiles(origin, static_cast<std::uint16_t>(static_cast<int>(info_range(ability)))) &
                         ability.valid_tiles() & ~walls).positions();
        std::stable_sort(landings.begin(), landings.end(),
                         [&](bc::vec2 a, bc::vec2 b) { return field.get(a) < field.get(b); });
        for (const auto p : landings) {
            if (static_cast<int>(field.get(p)) > start - 2) break;
            turn::check();
            if (!blocked().is_set(p) && ability.use(p)) return true;
        }
    }
    return false;
}

inline bool move_to(const bc::bitboard& goals, const bc::bitboard* extra_blocked = nullptr, bool use_dash = true) {
    turn::check();
    auto& me = bc::self();
    if (!me.is_alive()) return false;
    auto origin = me.position();
    if (goals.is_set(origin)) return false;
    if (!me.can_move() && !me.can_cast()) return false;
    auto walls = blocked();
    if (extra_blocked != nullptr) {
        walls |= *extra_blocked;
        walls.set(origin, false);
    }
    const auto legal = goals & ~walls;
    if (legal.is_empty()) return false;
    bc::distance_field field;
    bc::bitboard reached;
    field.compute_to(walls, legal, around(origin, 0), reached);
    turn::check();
    if (!reached.is_set(origin) && !use_dash) return false;
    if (!reached.is_set(origin))
        return cross_component(goals, extra_blocked) || teleport_past_blocker(goals, extra_blocked);
    bool moved = use_dash && dash(field, walls);
    if (moved) {
        origin = me.position();
        if (goals.is_set(origin)) return true;
    }
    if (me.can_move()) {
        for (const auto delta : field.next_moves_from(origin)) {
            turn::check();
            if (!blocked().is_set(origin + delta) && me.move(delta)) {
                turn::walked = true;
                moved = true;
                break;
            }
        }
    }
    last_field = std::move(field);
    return moved;
}

template <class Enemies, class Camps>
inline bc::bitboard threat_mask(const Enemies& enemies, const Camps& camps, int margin = 0) {
    bc::bitboard mask;
    for (const auto& enemy : enemies) {
        if (!enemy.is_visible() || !enemy.is_alive()) continue;
        mask |= around(enemy.position(), std::max(4, enemy.attack_range()) + margin);
    }
    for (const auto& camp : camps)
        if (camp.is_visible() && camp.strength() > 0 && camp.is_awake())
            mask |= around(camp.position(), camp.attack_range());
    return mask;
}

template <class Enemies, class Camps>
inline bool retreat(const Enemies& enemies, const Camps& camps) {
    auto& me = bc::self();
    {
        const auto threat = threat_mask(enemies, camps, 1);
        if (move_to(gm::spawn_region(bc::team::ally), &threat)) return true;
    }
    turn::check();
    if (!me.is_alive() || (!me.can_move() && !me.can_cast())) return false;
    const auto origin = me.position();
    struct Threat {
        bc::vec2 position;
        std::int64_t range;
        double strength;
    };
    std::vector<Threat> threats;
    // A long comprehension can otherwise cross a fuel suspension between the
    // visibility guard and the live query. Camps have public fixed spawn tiles.
    for (const auto& e : enemies) {
        turn::check();
        if (e.is_visible() && e.is_alive())
            threats.push_back({e.position(), std::max(4, e.attack_range()), D(e.strength())});
    }
    for (const auto& c : camps) {
        turn::check();
        if (c.is_visible() && c.strength() > 0 && c.is_awake())
            threats.push_back({c.spawn_position(), c.attack_range(), D(c.strength())});
    }
    const auto home = gm::spawn_region(bc::team::ally).positions();
    const auto walls = blocked();
    auto candidates = walls.reachable_tiles(origin, 1).positions();
    // Staying put is a legal alternative when every step takes more damage.
    if (std::find(candidates.begin(), candidates.end(), origin) == candidates.end()) candidates.push_back(origin);
    auto risk = [&](bc::vec2 p) {
        double damage = 0;
        for (const auto& t : threats)
            if (distance(p, t.position) <= t.range) damage += t.strength;
        std::int64_t gap = 10;
        bool first = true;
        for (const auto& t : threats) {
            const auto g = distance(p, t.position) - t.range;
            if (first || g < gap) gap = g;
            first = false;
        }
        std::int64_t nearest = std::numeric_limits<std::int64_t>::max();
        for (const auto h : home) nearest = std::min(nearest, distance(p, h));
        return std::make_tuple(damage, -gap, nearest);
    };
    bc::vec2 best = origin;
    if (!candidates.empty()) best = *first_min(candidates.begin(), candidates.end(), risk);
    // Build a gradient towards the best escape square so dashes can also escape.
    if (best != origin) return move_to(around(best, 0));
    return false;
}

inline void finish_turn() {
    // A carried lock denies enemy tributes and cancels an existing channel.
    auto& me = bc::self();
    if (me.is_alive() && !me.is_recalling() && !me.is_submitting_gems() && !me.is_teleporting() &&
        bc::fuel_remaining() > turn::fuel(400'000) && !me.restrictions().contains(bc::buff_restrictions::consumable)) {
        const auto& lock = me.consumables()[bc::consumable_type::altar_lock];
        if (lock.count()) {
            const auto visible = bc::vision::visible_tiles();
            for (const auto altar : gm::altars().positions()) {
                if (distance(me.position(), altar) <= 2 && visible.is_set(altar) && !bc::vision::has_altar_lock(altar)) {
                    turn::check();
                    lock.use(altar);
                    break;
                }
            }
        }
    }
    // Relocating a ward can remove vision. Do it after every decision/action.
    if (last_field && me.is_alive() && !me.is_recalling() && !me.is_submitting_gems() && !me.is_teleporting() &&
        bc::fuel_remaining() > turn::fuel(200'000)) {
        turn::check();
        scout(*last_field);
    }
}

// Release task endpoints; a large region may need several ordinary steps.
inline bool park_nearby(const bc::bitboard& forbidden) {
    turn::check();
    auto& me = bc::self();
    if (!me.is_alive() || !me.can_move()) return false;
    return move_to(around(me.position(), 4) & ~forbidden, nullptr, false);
}

}  // namespace nav
