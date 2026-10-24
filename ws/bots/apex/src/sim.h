// sim.h: a small deterministic fight simulator. Every visible champion near us,
// and the awake camps among them, fight for up to a few rounds; the result says
// who dies. A Python turn cannot afford it (one Python operation costs about 500
// fuel); in C++ a full simulation costs a few thousand of a turn's 100,000.
#pragma once
#include "common.h"
#include "teamwork.h"
#include "turn.h"

namespace sim {

enum Side { ours = 0, theirs = 1, camp = 2 };

struct Unit {
    Side side;
    double hp, max_hp;
    double damage;  // per round, against champions
    double heal;    // per round, to the most hurt ally within heal_range
    int range, heal_range, speed;
    int x, y;
    bool me = false;
    bool hor = false;  // Heart of Ruin: up to +50% damage at full missing health
    bool alive = true;
};

struct Outcome {
    bool me_dies = false;
    int round = 0;           // the round I die, 0 if I live
    double me_hp = 0;        // my health when the simulation ends
    int ours_dead = 0, theirs_dead = 0;
    double theirs_lost = 0;  // enemy health removed
};

// A champion's design, reduced to what the simulation needs: per-round damage is
// strength * per_strength + focus * per_focus (one basic attack, plus attack
// resets and Focus-scaled abilities spread over their cooldowns), and healing is
// focus * heal_focus. Design data never changes, so it is read once per champion;
// a unit then costs five live reads (each engine call costs fuel).
struct Design {
    double per_strength = 1, per_focus = 0, heal_focus = 0;
    int heal_range = 0, speed = 1;
    bool hor = false;
};

inline const Design& design_of(const bc::champion& c) {
    static std::map<std::uint32_t, Design> cache;
    const auto key = handle_of(c);
    const auto it = cache.find(key);
    if (it != cache.end()) return it->second;
    Design d;
    for (const auto& a : c.abilities()) {
        if (!a.info()) continue;
        const double cooldown = std::max(1, info_max_cooldown(a));
        if (a.is_attack_reset()) d.per_strength += 1 / cooldown;
        else if (a.is_damage() || a.is_aoe_damage() || a.is_dash()) d.per_focus += info_modifier(a) / cooldown;
        else if (a.is_heal()) {
            d.heal_focus += info_modifier(a) / cooldown;
            d.heal_range = std::max(d.heal_range, static_cast<int>(info_range(a)));
        }
    }
    d.speed = std::max(1, c.base_stats().base_move_speed);
    d.hor = c.champion_name() == bc::champion_type::heart_of_ruin;
    return cache.emplace(key, d).first->second;
}

inline Unit of(const bc::champion& c, Side side, bc::vec2 p) {
    const auto& d = design_of(c);
    Unit u{};
    u.side = side;
    u.hp = c.health();
    u.max_hp = c.max_health();
    const double focus = c.focus();
    u.damage = D(c.strength()) * d.per_strength + focus * d.per_focus;
    u.heal = focus * d.heal_focus;
    u.heal_range = d.heal_range;
    u.range = c.attack_range();
    u.speed = d.speed;
    u.x = p.x;
    u.y = p.y;
    u.hor = d.hor;
    return u;
}

inline int gap(const Unit& a, const Unit& b) { return std::max(std::abs(a.x - b.x), std::abs(a.y - b.y)); }

inline int sign(int v) { return (v > 0) - (v < 0); }

// Everyone fights: champions close on the nearest enemy champion and hit the
// weakest one in reach; camps hit the nearest champion in reach; healers mend
// their most hurt ally. Simultaneous rounds, no terrain.
inline Outcome run(std::vector<Unit> units, int horizon) {
    Outcome out;
    const int n = static_cast<int>(units.size());
    static std::vector<double> hit, mend;
    hit.resize(n);
    mend.resize(n);
    for (int round = 1; round <= horizon; ++round) {
        // A turn that ran dry here would resume next round on stale units.
        turn::check();
        bool moved = false, struck = false;
        for (int i = 0; i < n; ++i) {
            auto& u = units[i];
            if (!u.alive || u.side == camp) continue;
            int best = -1, near = 1 << 20;
            for (int j = 0; j < n; ++j) {
                const auto& v = units[j];
                if (v.alive && v.side != camp && v.side != u.side && gap(u, v) < near) {
                    near = gap(u, v);
                    best = j;
                }
            }
            if (best < 0 || near <= u.range) continue;
            const int steps = std::min(u.speed, near - u.range);
            const auto& v = units[best];
            const int dx = v.x - u.x, dy = v.y - u.y;
            u.x += sign(dx) * std::min(steps, std::abs(dx));
            u.y += sign(dy) * std::min(steps, std::abs(dy));
            moved = moved || steps > 0;
        }
        std::fill(hit.begin(), hit.end(), 0.0);
        std::fill(mend.begin(), mend.end(), 0.0);
        for (int i = 0; i < n; ++i) {
            const auto& u = units[i];
            if (!u.alive) continue;
            int target = -1;
            for (int j = 0; j < n; ++j) {
                const auto& v = units[j];
                if (!v.alive || v.side == camp || j == i || gap(u, v) > u.range) continue;
                if (u.side != camp && v.side == u.side) continue;
                if (target < 0) { target = j; continue; }
                const auto& t = units[target];
                // Camps hit the nearest champion; champions the weakest enemy.
                if (u.side == camp ? gap(u, v) < gap(u, t) : v.hp < t.hp) target = j;
            }
            if (target >= 0) {
                double damage = u.damage;
                if (u.hor) damage *= 1 + 0.5 * (1 - u.hp / std::max(1.0, u.max_hp));
                hit[target] += damage;
                struck = true;
            }
            if (u.heal > 0 && u.side != camp) {
                int ally = -1;
                for (int j = 0; j < n; ++j) {
                    const auto& v = units[j];
                    if (!v.alive || v.side != u.side || j == i || gap(u, v) > u.heal_range || v.hp >= v.max_hp) continue;
                    if (ally < 0 || v.hp / v.max_hp < units[ally].hp / units[ally].max_hp) ally = j;
                }
                if (ally >= 0) mend[ally] += u.heal;
            }
        }
        for (int i = 0; i < n; ++i) {
            auto& u = units[i];
            if (!u.alive) continue;
            const double before = u.hp;
            u.hp = std::min(u.max_hp, u.hp - hit[i] + mend[i]);
            if (u.side == theirs) out.theirs_lost += std::max(0.0, before - std::max(0.0, u.hp));
            if (u.hp <= 0) {
                u.alive = false;
                if (u.side == ours) ++out.ours_dead;
                if (u.side == theirs) ++out.theirs_dead;
                if (u.me) {
                    out.me_dies = true;
                    out.round = round;
                }
            }
        }
        if (out.me_dies || !(moved || struck)) break;
        bool foes = false;
        for (const auto& u : units)
            if (u.alive && u.side == theirs) foes = true;
        if (!foes) break;
    }
    for (const auto& u : units)
        if (u.me) out.me_hp = std::max(0.0, u.hp);
    return out;
}

// The fight around this champion, as it stands: allies and enemies within
// `radius`, and awake camps within it. A simulation costs about per_unit(horizon)
// fuel a unit (measured at 8 rounds: 9k with two units, 36k with six), so it runs
// only when the turn can pay for it and still keep `reserve` plus turn::MIN_FUEL;
// otherwise there is no prediction and the caller falls back to the ratio rule.
// A turn that ran dry part-way would resume next round on units it cannot see.
inline constexpr std::uint64_t per_unit(int horizon) { return 1'000 + 650 * static_cast<std::uint64_t>(horizon); }

inline std::optional<Outcome> predict(const std::vector<bc::champion>& allies, const std::vector<bc::champion>& enemies,
                                      const std::vector<bc::camp>& camps, int radius, int horizon,
                                      std::uint64_t reserve = 0) {
    auto& me = bc::self();
    const auto origin = me.position();
    // Every engine read costs fuel (a few hundred each, about eleven a unit), so
    // positions are read once, camps are first filtered on their fixed spawn tile,
    // and the fuel check runs once a list, not once a unit.
    std::vector<std::pair<const bc::champion*, bc::vec2>> ally_in, enemy_in;
    std::vector<const bc::camp*> camp_in;
    // Filtering reads a few engine values a unit with no check between them; a turn
    // entering it near turn::MIN_FUEL could run dry inside and resume next round on
    // units it can no longer see (1 game in ~320 hit "Unit is not in vision").
    if (bc::fuel_remaining() < turn::MIN_FUEL + reserve + 20'000) return std::nullopt;
    turn::check();
    for (const auto& a : allies) {
        if (same(a, me) || !a.is_alive() || !a.is_visible()) continue;
        const auto p = a.position();
        if (distance(origin, p) <= radius) ally_in.emplace_back(&a, p);
    }
    turn::check();
    for (const auto& e : enemies) {
        if (!e.is_visible()) continue;
        const auto p = e.position();
        if (distance(origin, p) <= radius && e.is_alive()) enemy_in.emplace_back(&e, p);
    }
    turn::check();
    for (const auto& c : camps)
        if (distance(origin, c.spawn_position()) <= radius && c.is_visible() && c.is_awake() && c.strength() > 0)
            camp_in.push_back(&c);
    const auto count = 1 + ally_in.size() + enemy_in.size() + camp_in.size();
    if (bc::fuel_remaining() < turn::MIN_FUEL + reserve + per_unit(horizon) * count + 4'000) return std::nullopt;
    std::vector<Unit> units;
    units.reserve(count);
    auto self = of(me, ours, origin);
    self.me = true;
    units.push_back(self);
    for (const auto& [a, p] : ally_in) units.push_back(of(*a, ours, p));
    for (const auto& [e, p] : enemy_in) units.push_back(of(*e, theirs, p));
    for (const auto* c : camp_in) {
        Unit u{};
        u.side = camp;
        u.hp = c->health();
        u.max_hp = c->max_health();
        u.damage = c->strength();
        u.range = c->attack_range();
        u.speed = 0;
        const auto p = c->spawn_position();
        u.x = p.x;
        u.y = p.y;
        units.push_back(u);
    }
    turn::check();
    auto out = run(std::move(units), horizon);
    turn::check();
    return out;
}

}  // namespace sim
