// sage2 champion decisions.
//
// Ordered by what the data says matters. 35 real games across ranks 2-250 showed
// our death count roughly constant (21, 27, 28, 19, 11 per game) while the top two
// teams die 2.9 times: not dying is the whole gap. So the survival decision runs
// before farming, and it is an explicit time-to-death versus time-to-escape race
// rather than a health threshold -- the old Python threshold's only threat term was
// summed camp strength, with enemy champion damage absent entirely.
#include "bot.h"

#include <array>
#include <cstdint>
#include <iostream>
#include <variant>
#include <vector>

#include "claims.h"
#include "policy.h"
#include "combat.h"
#include "nav.h"
#include "sim.h"
#include "survive.h"
#include "turnguard.h"

using cambc::vec2;

namespace {

// temporary branch counters, to localise why nothing happens
long c_turn = 0, c_survive = 0, c_bank = 0, c_atk = 0, c_move = 0, c_none = 0,
     c_nogroup = 0, c_disengage = 0, c_shield = 0, c_fight = 0, c_retarget = 0, c_heal = 0, c_skipped = 0, c_bankrun = 0, c_floor = 0, c_healcast = 0, c_boss = 0;

constexpr int MAX_THREATS = 32;
// Margin in turns, covering a camp waking mid-withdrawal or a second champion
// arriving. A quantity with a meaning, unlike a fraction of health.
constexpr double DISENGAGE_MARGIN = 1.5;
constexpr int BANK_GEMS = 8;        // was 24: see Bot::bank
// Flat health floors, from the Python config that this port dropped. The
// time-to-death model replaced them and it only fires a turn or two from
// death, by which point leaving a camp's range donates the hits that kill
// us. Measured cost of having no floor: 1,350 health healed a game against
// boss_full's 51,949. Standing on spawn is the only sustain in this game and
// nothing was ever sending a champion there.
constexpr double RETREAT_HEALTH = 0.30;
constexpr double CARRIER_RETREAT_HEALTH = 0.43;

// Build order ported from the Python config: the emblem passives that measured
// well, then Power shards which carry an extra shard's worth instead of a passive.
const std::array<cambc::item_type, 3> DEFAULT_BUILD{
    cambc::item_type::jungle_shard_of_strength,
    cambc::item_type::monster_shard_of_strength,
    cambc::item_type::durability_shard_of_health};

// Fill our own emblem magnitudes so mitigation is modelled, not guessed.
sim::Unit self_unit() {
    const auto& me = cambc::self();
    sim::Unit u;
    u.hp = me.health();
    u.max_hp = me.max_health();
    u.strength = me.strength();
    u.focus = me.focus();
    u.passive = static_cast<int>(me.passive());
    // A finished emblem carries the passive; a duplicate adds no second passive, so
    // presence is all that matters. Nine named types rather than scanning all 42.
    const auto counts = me.item_count();
    const std::array<cambc::item_type, 3> monster{
        cambc::item_type::monster_emblem_of_strength,
        cambc::item_type::monster_emblem_of_health,
        cambc::item_type::monster_emblem_of_focus};
    const std::array<cambc::item_type, 3> durability{
        cambc::item_type::durability_emblem_of_strength,
        cambc::item_type::durability_emblem_of_health,
        cambc::item_type::durability_emblem_of_focus};
    const std::array<cambc::item_type, 3> jungle{
        cambc::item_type::jungle_emblem_of_strength,
        cambc::item_type::jungle_emblem_of_health,
        cambc::item_type::jungle_emblem_of_focus};
    for (auto it : monster)
        if (counts[it] > 0) { u.mon = it.info().passive_magnitude; break; }
    for (auto it : durability)
        if (counts[it] > 0) { u.dur = it.info().passive_magnitude; break; }
    for (auto it : jungle)
        if (counts[it] > 0) { u.jun = it.info().passive_magnitude; break; }
    const auto b = me.buffs();
    if (b.has_shield()) u.shield = b.get<cambc::buff_shield>().value;
    return u;
}

bool has_dash() { return nav::mobility().radius == 2; }

// Turn ends a tribute takes: ceil(gems / 10), at least one.
int tribute_ticks(std::uint32_t gems) {
    const int t = static_cast<int>((gems + 9) / 10);
    return t < 1 ? 1 : t;
}

}  // namespace

const cambc::map::camp_group* Bot::group_by_handle(int handle) const {
    if (!groups_ || handle < 0) return nullptr;
    for (const auto& g : *groups_)
        if (static_cast<int>(static_cast<std::uint32_t>(static_cast<cambc::handle_camp_group_t>(g))) == handle) return &g;
    return nullptr;
}

// The committed group's spawn mask, built on first use and kept.
const cambc::bitboard& Bot::group_mask(const cambc::map::camp_group& g) {
    const int handle = static_cast<int>(
        static_cast<std::uint32_t>(static_cast<cambc::handle_camp_group_t>(g)));
    for (auto& gi : info_)
        if (gi.handle == handle) {
            if (!gi.mask) gi.mask = g.spawn_tiles();
            return *gi.mask;
        }
    static std::optional<cambc::bitboard> fallback;
    fallback = g.spawn_tiles();
    return *fallback;
}

std::int32_t Bot::group_cost(vec2 pos, const GroupInfo& gi,
                            const std::vector<vec2>& enemies, double dps) const {
    std::int32_t travel = 1 << 29;
    for (vec2 p : gi.tiles) {
        const std::int32_t d = pos.chebyshev_distance(p);
        if (d < travel) travel = d;
    }
    // Time to kill the group, plus the capture, in the same units as travel.
    //
    // This cost had no health term at all, so a 20,000-health monolith and a
    // 120-health gem cluster looked equally attractive per unit of value. The
    // measured consequence, over 312 games against four opponents: sage2 spends
    // **237.6 points of camp damage per gem collected against their 133.1**, and
    // earns 35.8 gold per thousand damage against their 69.3. It is not dealing
    // damage inefficiently -- it is spending it on the wrong camps. Mirrors the
    // Python `strategy.choose_group`, where every term is a number of turns and
    // the whole sum is divided by the reward.
    const double clear = gi.hp / (dps > 1.0 ? dps : 1.0);
    const double turns = static_cast<double>(travel) + clear
                         + static_cast<double>(cambc::constants::capture_time);
    std::int32_t cost = static_cast<std::int32_t>(
        turns * 100.0 / static_cast<double>(gi.value));
    // Avoid farming next to an enemy. Mirrors the Python strategy.choose_group
    // enemy-proximity penalty, which measured as the largest single income lever
    // in this bot: being somewhere else beats fighting better.
    for (vec2 e : enemies) {
        std::int32_t near = 1 << 29;
        for (vec2 p : gi.tiles) {
            const std::int32_t d = e.chebyshev_distance(p);
            if (d < near) near = d;
        }
        if (near < 8) cost += (8 - near) * 60;
    }
    return cost;
}

// A committed target stays committed until something says otherwise. Without
// this every champion re-ranks every group every turn from its own position, the
// cheapest one flips as distances change, and they thrash: measured at 64-73% of
// turns spent moving and only ~10% attacking.
bool Bot::target_still_good(const cambc::map::camp_group& g) {
    const cambc::bitboard visible = cambc::vision::visible_tiles();
    if (!(group_mask(g) & visible).is_empty()) {
        const auto state = g.state();
        if (const auto* resp =
                std::get_if<cambc::map::camp_group_respawning>(&state)) {
            // Remember the timer. Caching group geometry removed the per-group
            // state() call from the selection loop for fuel reasons, which also
            // removed the only thing stopping a champion re-picking an empty
            // group every turn: income halved and three more maps went inert.
            // Respawn has to be learned once and remembered, as the Python bot's
            // `respawns` map does.
            const int handle = static_cast<int>(
                static_cast<std::uint32_t>(static_cast<cambc::handle_camp_group_t>(g)));
            if (handle >= 0 && handle < 64)
                blocked_until_[static_cast<std::size_t>(handle)] =
                    static_cast<std::int32_t>(cambc::round_number()) + resp->timer;
            return false;
        }
    }
    // Stall detection: position and remaining camp health both unchanged means we
    // are neither travelling nor damaging anything.
    double health = 0.0;
    for (const auto& c : g.camps())
        if (c.is_visible() && cambc::vision::has_camp(c.spawn_position()))
            health += c.health();
    const cambc::vec2 pos = cambc::self().position();
    if (pos == stall_pos_ && health == stall_health_) {
        if (++stall_ticks_ >= 12) {
            const int handle = static_cast<int>(static_cast<std::uint32_t>(static_cast<cambc::handle_camp_group_t>(g)));
            if (handle >= 0 && handle < 64)
                blocked_until_[static_cast<std::size_t>(handle)] =
                    static_cast<std::int32_t>(cambc::round_number()) + 80;
            stall_ticks_ = 0;
            return false;
        }
    } else {
        stall_pos_ = pos;
        stall_health_ = health;
        stall_ticks_ = 0;
    }
    return true;
}

void Bot::load_altars() {
    if (altars_loaded_) return;
    altars_loaded_ = true;
    altars_ = cambc::map::altars().positions();
    for (vec2 a : altars_) {
        cambc::bitboard ring;
        ring.draw_chebyshev(a, static_cast<float>(cambc::constants::submit_gems_range));
        altar_goals_ = altar_goals_ | ring;
    }
}

// A camp's base health by kind. `kind()` is noexcept and needs no vision, and the
// design lookup is per-kind, so caching by kind costs one SDK call per camp type
// for the whole match instead of one per camp on a turn that already spends 61-77%
// of its budget reading the map.
double camp_design_health(const cambc::camp& c) {
    static double cache[16] = {0};
    const int k = static_cast<int>(c.kind());
    if (k < 0 || k >= 16) return 0.0;
    if (cache[k] == 0.0) cache[k] = c.base_stats().base_health;
    return cache[k];
}

void Bot::load_groups() {
    // Read the engine once. Group geometry and design values are fixed for the
    // match, and the selection loop runs every turn over every group, so nothing
    // in it may cost an SDK call.
    //
    // Loading the altars here rather than lazily is worth 12 gems a game and, on
    // 01yellow-brick-road, the difference between winning and not: measured both
    // ways. Banking and every withdrawal read `altars_`, and the first champion to
    // need them is by definition one already carrying gems or already losing a
    // fight -- the worst turn to spend the SDK calls on. Pay for them on the turn
    // that is already reading the map.
    load_altars();
    groups_ = cambc::map::camp_groups();
    info_.clear();
    info_.reserve(groups_->size());
    for (std::size_t i = 0; i < groups_->size(); ++i) {
        const auto& g = (*groups_)[i];
        GroupInfo gi;
        gi.handle = static_cast<int>(
            static_cast<std::uint32_t>(static_cast<cambc::handle_camp_group_t>(g)));
        gi.index = i;
        // A group's spawn tiles are exactly its camps' spawn positions, and both
        // `camps()` and `spawn_position()` are noexcept reads of data the SDK
        // already holds. `spawn_tiles().positions()` produced the identical set
        // through the engine: `spawn_tiles` clears a bitboard and then calls
        // `sdk_Bitboard_Set` once per camp, and `positions` adds a `count()` and a
        // `GetSetBits` -- about six engine calls per group, which is where 61,000
        // to 77,100 fuel on this one function came from. This is zero.
        gi.tiles.clear();
        gi.tiles.reserve(g.camps().size());
        for (const auto& c : g.camps()) gi.tiles.push_back(c.spawn_position());
        gi.value = g.gem_value() + g.gold_value() / 2;
        gi.gems = g.gem_value();
        gi.gold = g.gold_value();
        for (const auto& c : g.camps()) {
            if (c.is_monolith()) gi.monolith = true;
            gi.hp += camp_design_health(c);
        }
        info_.push_back(std::move(gi));
    }
}

double Bot::camp_dps(const sim::Unit& u) const {
    const auto& me = cambc::self();
    double ability = 0.0, reset = 0.0;
    for (const auto& a : me.abilities()) {
        if (!a.info()) continue;
        if (a.is_attack_reset()) reset += u.strength;
        else if (a.is_damage() || a.is_aoe_damage()) ability += a.damage_amount();
    }
    return survive::camp_dps(u, u.strength, ability, reset);
}

void Bot::shop() {
    auto& me = cambc::self();
    if (me.gold_count() < 30) return;        // nothing to decide below one shard
    for (int i = 0; i < 40; ++i) {
        const int emblem = purchase_index_ / 5;
        const auto item = emblem < static_cast<int>(DEFAULT_BUILD.size())
                              ? DEFAULT_BUILD[static_cast<std::size_t>(emblem)]
                              : cambc::item_type::power_shard_of_strength;
        if (!me.can_buy(item)) break;
        guard::check();
        me.buy(item);
        ++purchase_index_;
    }
}

// Returns true if survival took the turn.
bool Bot::survive_check() {
    auto& me = cambc::self();
    const sim::Unit u = self_unit();

    double strength[MAX_THREATS];
    int range[MAX_THREATS], dist[MAX_THREATS], kind[MAX_THREATS];
    int n = 0;
    const vec2 pos = me.position();

    std::vector<cambc::camp> live_camps;
    for (const auto& c : cambc::vision::camps()) {
        if (n >= MAX_THREATS) break;
        if (!c.is_visible() || !c.is_awake() || c.strength() <= 0.0) continue;
        live_camps.push_back(c);
        strength[n] = c.strength();
        range[n] = nav::camp_range(c);
        dist[n] = nav::distance(pos, c.position());
        kind[n] = survive::KIND_CAMP;
        ++n;
    }
    std::vector<cambc::champion> enemies;
    for (const auto& e : cambc::vision::champions(cambc::team::enemy)) {
        if (!e.is_alive() || !e.is_visible()) continue;
        enemies.push_back(e);
        if (n >= MAX_THREATS) continue;
        strength[n] = e.strength();
        range[n] = e.attack_range();
        dist[n] = nav::distance(pos, e.position());
        kind[n] = survive::KIND_CHAMPION;
        ++n;
    }
    if (n == 0) return false;

    const double incoming = survive::incoming_per_turn(u, n, strength, range, dist, kind);
    if (incoming <= 0.0) return false;
    const double ttd = survive::turns_to_death(u, incoming);
    const int tte = survive::turns_to_escape(n, range, dist, kind, has_dash());

    // A shield is health for this race, so spend it before the damage lands.
    for (const auto& a : me.abilities()) {
        if (!a.is_ready() || !a.is_shield()) continue;
        if (survive::shield_now(a.shield_amount(), incoming, 5, 0.6)) {
            guard::check();
            if (a.use()) { ++c_shield; return true; }
        }
    }

    const survive::Action action = survive::decide(ttd, tte, DISENGAGE_MARGIN);
    if (action == survive::ACT_CARRY_ON) return false;

    if (action == survive::ACT_FIGHT) {
        // A champion matches our speed, so walking away only donates free hits.
        // Hit back: the weakest reachable enemy, so something dies if we do.
        ++c_fight;
        if (me.can_attack()) {
            const auto attack_tiles = me.attack_tiles();
            const cambc::champion* weakest = nullptr;
            for (const auto& e : enemies) {
                if (!attack_tiles.is_set(e.position())) continue;
                if (!weakest || e.health() < weakest->health()) weakest = &e;
            }
            if (weakest) {
                guard::check();
                me.attack(*weakest);
                return true;
            }
        }
        // Not in reach yet. Close only if the duel is ours; otherwise fall back
        // on withdrawing toward home, where allies and spawn healing are.
        const cambc::champion* nearest = nullptr;
        std::int32_t best_d = 1 << 29;
        for (const auto& e : enemies) {
            const std::int32_t d = nav::distance(pos, e.position());
            if (d < best_d) { best_d = d; nearest = &e; }
        }
        if (nearest) {
            const double my_dps = u.strength;
            if (survive::wins_duel(u, my_dps, nearest->health(), 0.0,
                                   nearest->strength(), 1.0)) {
                if (nav::move_to(nav::around(nearest->position(),
                                             static_cast<float>(me.attack_range()))))
                    return true;
            }
        }
    }

    ++c_disengage;
    return withdraw(enemies, live_camps, ttd);
}

// Going home, shared by the reactive survival check and the health floor. A
// tribute is not cancelled by damage, so if an altar is already in reach and we
// outlast the channel, banking under fire beats fleeing with the bag: fleeing
// risks losing all of it to a killer.
bool Bot::withdraw(const std::vector<cambc::champion>& enemies,
                   const std::vector<cambc::camp>& live_camps, double ttd) {
    auto& me = cambc::self();
    const vec2 pos = me.position();
    if (me.gem_count() > 0) {
        load_altars();
        const int ticks = tribute_ticks(me.gem_count());
        for (vec2 altar : altars_) {
            if (nav::distance(pos, altar) > cambc::constants::submit_gems_range) continue;
            if (ttd > static_cast<double>(ticks) + 1.0) {
                guard::check();
                me.submit_gems(altar);
                ++c_bankrun;
                return true;
            }
        }
    }

    // Recall only when nothing can interrupt the channel. Recall is for healing
    // first and shopping second. Requiring gold here was my own error: a champion
    // at 15% health with no gold still needs to go home, and spawn heals to full.
    bool safe = true;
    for (const auto& e : enemies)
        if (nav::distance(pos, e.position()) <= 6) safe = false;
    for (const auto& c : live_camps)
        if (nav::distance(pos, c.position()) <= nav::camp_range(c)) safe = false;
    if (safe) {
        guard::check();
        me.recall();
        return true;
    }
    const cambc::bitboard threat = nav::threat_mask(enemies, live_camps, 1);
    // Withdrawing toward an altar banks the bag instead of merely saving it.
    if (me.gem_count() > 0 && !altar_goals_.is_empty()) {
        if (nav::move_to(altar_goals_, &threat)) { ++c_bankrun; return true; }
        if (nav::move_to(altar_goals_)) { ++c_bankrun; return true; }
    }
    const cambc::bitboard home = cambc::map::spawn_region(cambc::team::ally);
    if (nav::move_to(home, &threat)) return true;
    return nav::move_to(home);
}

// The flat floor the port dropped. Two terms, whichever is higher: a fraction of
// maximum health, and twice the damage arriving each turn from camps already in
// range plus a buffer -- monsters act before our next turn, so a melee champion
// walking out of a dense pack must budget for two more attacks.
bool Bot::heal_trip() {
    auto& me = cambc::self();
    const double max_hp = me.max_health();
    if (max_hp <= 0.0) return false;
    const vec2 pos = me.position();

    std::vector<cambc::camp> live_camps;
    double pressure = 0.0;
    for (const auto& c : cambc::vision::camps()) {
        if (!c.is_visible() || !c.is_awake() || c.strength() <= 0.0) continue;
        live_camps.push_back(c);
        if (nav::distance(pos, c.position()) <= nav::camp_range(c)) pressure += c.strength();
    }
    std::vector<cambc::champion> enemies;
    for (const auto& e : cambc::vision::champions(cambc::team::enemy)) {
        if (!e.is_alive() || !e.is_visible()) continue;
        enemies.push_back(e);
        if (nav::distance(pos, e.position()) <= e.attack_range()) pressure += e.strength();
    }

    const double frac = me.gem_count() > 0 ? CARRIER_RETREAT_HEALTH : RETREAT_HEALTH;
    const double leave_at = std::max(max_hp * frac, pressure * 2.0 + max_hp * 0.08);
    if (me.health() >= leave_at) return false;

    // Dropping the claim matters: a champion walking home must not hold a group
    // that an ally at full health could be clearing.
    target_handle_ = -1;
    claims::claim(-1);
    ++c_floor;
    const double ttd = pressure > 0.0 ? me.health() / pressure : 1e9;
    return withdraw(enemies, live_camps, ttd);
}

// Whether a deposit attempt is worth making at all. Only consulted on boss maps.
bool Bot::bank_allowed() {
    auto& me = cambc::self();
    const std::int32_t now = static_cast<std::int32_t>(cambc::round_number());
    if (now < bank_retry_at_) return false;
    const vec2 p = me.position();
    const std::uint32_t g = me.gem_count();
    if (p == bank_sig_pos_ && g == bank_sig_gems_) {
        if (++bank_stall_ >= 12) {          // Progress(limit=12)
            bank_retry_at_ = now + 80;
            bank_stall_ = 0;
            bank_sig_gems_ = 0xffffffffu;
            return false;
        }
    } else {
        bank_sig_pos_ = p;
        bank_sig_gems_ = g;
        bank_stall_ = 0;
    }
    return true;
}

bool Bot::bank() {
    auto& me = cambc::self();
    load_altars();
    const std::uint32_t carried = me.gem_count();
    if (carried == 0 || altars_.empty()) return false;

    // A tribute survives damage -- only a stun, a death or an altar lock stops it
    // -- so submitting whatever we hold when an altar is already in reach is close
    // to free, whatever the bag size.
    for (vec2 altar : altars_) {
        if (nav::distance(me.position(), altar) <= cambc::constants::submit_gems_range) {
            guard::check();
            me.submit_gems(altar);
            return true;
        }
    }

    // Measured: 95.7 gems collected a game, 39.6 submitted. Fifty-six were being
    // carried into a death, where the killer takes the lot. A 24-gem threshold
    // assumes a carrier survives long enough to fill the bag; at 52 deaths a game
    // it does not, so bank far smaller loads and more often. The trip costs
    // ceil(gems/10) turn ends either way.
    if (carried < BANK_GEMS) return false;
    return !altar_goals_.is_empty() && nav::move_to(altar_goals_);
}

// The escort lived here: the healer attached itself to an ally that already held a
// claim, reserved the same group with the support bit and cleared it from within
// three tiles of the leader. It was removed after a 2x2 ablation on a fuel-stable
// build measured it at **zero gems** -- 140 against 140 with it gone, 12 maps
// better and 18 worse -- for about a quarter of a turn's fuel budget on the
// healer. `claims`' support bit and `group_cost()` remain; `combat::heal_allies`
// remains and costs nothing. The mechanism was not broken: it doubled what the
// heal achieved alone (4,270 against 2,095) and removing only the heal while
// keeping the escort cost 23 gems, so the positioning did work. It simply bought
// collection rather than banking -- 183 gems collected against 172, the same 140
// submitted -- and the 60% of champion turns spent walking, which it was built to
// fix, it never touched. See GROUND-UP-PLAN.md for the full table.

// Boss mode: the whole team on one objective, ported from the Python boss.py.
//
// On a map whose only altar is gated by a monolith, the normal controller cannot
// score at all -- five champions each pick their own group, none of them can bring
// 20,000 health down alone, and every gem collected is eventually carried into a
// death. Measured on 01boss-battle: 73,425 monster damage dealt, 80 deaths, **zero
// gems banked**, and the same for boss_full when it loses the race to assemble.
//
// Two rules do the work. Every champion follows the claim the first living ally
// published, so the team converges rather than scattering; and the monolith is
// off-limits until the party is actually assembled and upgraded, after which it is
// the *only* target, so the damage lands on one 20,000-health pool instead of
// being spread over thirty-one groups.
bool Bot::boss_farm() {
    auto& me = cambc::self();
    if (!groups_) load_groups();
    const std::int32_t now = static_cast<std::int32_t>(cambc::round_number());
    const vec2 pos = me.position();

    const auto allies = cambc::champions(cambc::team::ally);
    int nearby = 0;
    double party_hp = 0.0, party_dps = 0.0, power = 0.0;
    for (const auto& a : allies) {
        if (!a.is_alive()) continue;
        // `strength()`, `focus()`, `health()` and `max_health()` all read the live
        // unit record, which throws "Unit is not in vision" for an ally we cannot
        // see -- 8,700 throws in one game when this was written with them. The
        // Python used `base_stats()` here for exactly this reason: it is a design
        // lookup by champion type and needs no vision.
        const auto design = a.base_stats();
        power += design.base_strength + design.base_focus / 4.0;
        if (!a.is_visible() || nav::distance(pos, a.position()) > 6) continue;
        ++nearby;
        party_hp += a.max_health();
        party_dps += a.strength();
    }
    // The gate from boss.py, kept at its measured thresholds: a party of four
    // within six tiles, ten purchases deep, 7,000 combined health and 400
    // combined strength, no earlier than round 650. Attacking a monolith with
    // less than this is feeding it.
    const bool boss_ready = now >= 650 && purchase_index_ >= 10 && nearby >= 4
                            && party_hp >= 7000.0 && party_dps >= 400.0;

    const claims::Snapshot held = claims::snapshot();
    const auto allowed = [&](const GroupInfo& gi) {
        if (gi.value == 0) return false;
        if (gi.handle >= 0 && gi.handle < 64
            && blocked_until_[static_cast<std::size_t>(gi.handle)] > now) return false;
        if (gi.monolith && now < 650) return false;   // too early for anyone
        return boss_ready ? gi.monolith : !gi.monolith;
    };

    // Follow the team. Any living ally's published claim will do -- they are all
    // running this same function, so the first one to publish anchors the rest.
    const GroupInfo* objective = nullptr;
    for (int i = 0; i < held.count; ++i) {
        if (!held.alive[i] || held.slots[i] < 0) continue;
        const GroupInfo* gi = nullptr;
        for (const auto& g : info_) if (g.handle == held.slots[i]) { gi = &g; break; }
        if (gi && allowed(*gi)) { objective = gi; break; }
    }

    if (!objective) {
        // Nobody has a usable claim: pick one. Cost in turns rather than tiles --
        // the walk there, plus the time to chew through the group's health at the
        // team's combined rate, plus the capture -- over what it pays.
        double best = 1e30;
        for (const auto& gi : info_) {
            if (!allowed(gi)) continue;
            std::int32_t travel = 1 << 29;
            for (vec2 p : gi.tiles) {
                const std::int32_t d = nav::distance(pos, p);
                if (d < travel) travel = d;
            }
            const double pay = static_cast<double>(gi.gems)
                               + static_cast<double>(gi.gold) * 0.4;
            if (pay <= 0.0) continue;
            const double score = (static_cast<double>(travel)
                                  + gi.hp / (power > 1.0 ? power : 1.0)
                                  + static_cast<double>(cambc::constants::capture_time))
                                 / pay;
            if (score < best) { best = score; objective = &gi; }
        }
    }

    if (!objective) { ++c_nogroup; claims::claim(-1); return false; }

    const cambc::map::camp_group* group = group_by_handle(objective->handle);
    if (!group) { ++c_nogroup; claims::claim(-1); return false; }
    target_handle_ = objective->handle;
    claims::claim(target_handle_);
    ++c_boss;

    std::vector<cambc::camp> live;
    for (const auto& c : group->camps())
        if (c.is_visible() && combat::still_there(c)) live.push_back(c);

    if (live.empty()) {
        // Not in sight, or cleared. Learn the respawn timer if we can see the
        // tiles, then walk to the group -- the party travels together because
        // every champion is reading the same claim.
        if (target_handle_ >= 0 && target_handle_ < 64) {
            const cambc::bitboard vis = cambc::vision::visible_tiles();
            if (!(group_mask(*group) & vis).is_empty()) {
                const auto st = group->state();
                if (const auto* r = std::get_if<cambc::map::camp_group_respawning>(&st))
                    blocked_until_[static_cast<std::size_t>(target_handle_)] =
                        now + r->timer;
            }
        }
        if (nav::move_to(group_mask(*group))) { ++c_move; return true; }
        return false;
    }

    const cambc::camp* pick = combat::choose_camp(live);
    if (!pick) return false;
    if (combat::fight_camp(*pick, live)) { ++c_atk; return true; }
    const cambc::bitboard ring =
        nav::around(pick->position(), static_cast<float>(me.attack_range()))
        & ~cambc::vision::camp_tiles();
    if (nav::move_to(ring)) { ++c_move; return true; }
    return false;
}

bool Bot::farm() {
    auto& me = cambc::self();
    if (!groups_) load_groups();

    const vec2 pos = me.position();
    const std::int32_t now = static_cast<std::int32_t>(cambc::round_number());

    // Keep the committed target unless it has gone bad.
    const cambc::map::camp_group* target = group_by_handle(target_handle_);
    if (target && !target_still_good(*target)) { target = nullptr; target_handle_ = -1; }

    if (!target) {
        // camp_group::state() throws "camp group is not in vision" unless we can
        // actually see the group, so it may only be asked about one whose spawn
        // tiles intersect our vision. The first version of this port dropped that
        // guard and threw 4,726 times in one game, scoring nothing.
        const cambc::bitboard visible = cambc::vision::visible_tiles();
        // Exactly two engine reads for the whole selection: the claims word and
        // the enemy champion list. Everything else comes from geometry cached at
        // load time. The previous version called spawn_tiles(), positions(),
        // camps(), base_stats() and has_camp() per group -- several hundred SDK
        // calls against a budget of roughly 77, which threw replan 4,851 times in
        // one game on 00lanes and left the bot inert there.
        const claims::Snapshot held = claims::snapshot();
        const double my_dps = camp_dps(self_unit());
        std::vector<vec2> enemy_positions;
        for (const auto& e : cambc::vision::champions(cambc::team::enemy))
            if (e.is_alive() && e.is_visible()) enemy_positions.push_back(e.position());
        int best = -1, fallback = -1;
        std::int32_t best_cost = 1 << 30, fallback_cost = 1 << 30;
        for (const auto& gi : info_) {
            if (gi.value == 0) continue;
            if (gi.handle >= 0 && gi.handle < 64
                && blocked_until_[static_cast<std::size_t>(gi.handle)] > now) continue;
            if (held.taken_by_other(gi.handle)) continue;   // an ally has it
            // Respawn is learned from observation, not queried: state() needs
            // vision and costs a call, so it is asked only about the group we
            // actually commit to, inside target_still_good().
            const bool affordable = true;
            // Costing the return leg to an altar here was measured and reverted:
            // -45 gems, -443 gold, +4 deaths a game. `altar_dist` is static per
            // group, so adding it does not rank a champion's options, it reorders
            // every champion's options identically -- all five converge on the few
            // groups nearest an altar, the claim protocol then locks four of them
            // out, and they fall through to worse targets or to nothing. Gold does
            // not need an altar either. Kept on GroupInfo as a measured dead end.
            const std::int32_t cost = group_cost(pos, gi, enemy_positions, my_dps);
            if (affordable) {
                if (cost < best_cost) { best_cost = cost; best = static_cast<int>(gi.index); }
            } else if (cost < fallback_cost) {
                // Keep the least bad unaffordable option. Early on, with starter
                // stats and no shards, nothing passes the affordability test, and
                // the first version of this check left champions idle for 74 turns
                // in 400 rather than farm anything. Idling earns nothing and still
                // risks nothing back; a hard camp at least pays if it goes well,
                // and the survival race will pull us off it if it does not.
                fallback_cost = cost;
                fallback = static_cast<int>(gi.index);
                ++c_skipped;
            }
        }
        if (best < 0) best = fallback;
        if (best < 0) { ++c_nogroup; claims::claim(-1); return false; }
        target = &(*groups_)[static_cast<std::size_t>(best)];
        target_handle_ = static_cast<int>(static_cast<std::uint32_t>(static_cast<cambc::handle_camp_group_t>(*target)));
        stall_ticks_ = 0;
        stall_health_ = -1.0;
        ++c_retarget;
    }
    claims::claim(target_handle_);
    const auto& group = *target;

    // Which of the group's camps are actually there. `is_visible()` plus
    // `still_there()` is three engine calls per camp -- a vision check, a
    // `has_camp` and a `health` -- and this exact loop used to run twice a turn,
    // once to decide whether to learn a respawn timer and again to pick a target.
    // It was 9,300 to 14,700 fuel a turn, 70-85% of everything farm() spends,
    // against a selection loop that costs 500. Once is enough.
    std::vector<cambc::camp> live;
    for (const auto& c : group.camps())
        if (c.is_visible() && combat::still_there(c)) live.push_back(c);

    // Learn respawn timers for whatever is in sight, so the selection loop never
    // has to ask.
    if (live.empty() && target_handle_ >= 0 && target_handle_ < 64) {
        const cambc::bitboard vis = cambc::vision::visible_tiles();
        if (!(group_mask(group) & vis).is_empty()) {
            const auto st = group.state();
            if (const auto* r =
                    std::get_if<cambc::map::camp_group_respawning>(&st))
                blocked_until_[static_cast<std::size_t>(target_handle_)] =
                    static_cast<std::int32_t>(cambc::round_number()) + r->timer;
        }
    }

    if (!live.empty()) {
        const cambc::camp* pick = combat::choose_camp(live);
        if (pick) {
            if (combat::fight_camp(*pick, live)) { ++c_atk; return true; }
            // Out of reach: close to a tile within attack range of it. Routing onto
            // the camp's own tile has no legal goal, since blocked() excludes
            // occupied tiles.
            const cambc::bitboard ring =
                nav::around(pick->position(), static_cast<float>(me.attack_range()))
                & ~cambc::vision::camp_tiles();
            if (nav::move_to(ring)) { ++c_move; return true; }
        }
    }

    // Group not in sight yet: travel to its spawn tiles. This only works while the
    // group is unseen, because blocked() is built from vision and live camps
    // occupy exactly those tiles once we can see them.
    //
    // Prefer a route that stays out of reach of anything live, and fall back to the
    // direct one when no safe route exists.
    std::vector<cambc::champion> threats;
    for (const auto& e : cambc::vision::champions(cambc::team::enemy))
        if (e.is_alive() && e.is_visible()) threats.push_back(e);
    std::vector<cambc::camp> awake;
    for (const auto& c : cambc::vision::camps())
        if (c.is_visible() && c.is_awake() && c.strength() > 0.0) awake.push_back(c);
    if (!threats.empty() || !awake.empty()) {
        const cambc::bitboard avoid = nav::threat_mask(threats, awake, 1);
        if (nav::move_to(group_mask(group), &avoid)) { ++c_move; return true; }
    }
    if (nav::move_to(group_mask(group))) { ++c_move; return true; }
    return false;
}

void Bot::play_turn() {
    guard::begin();
    auto& me = cambc::self();
    shop();
    if (!me.is_alive()) { target_handle_ = -1; claims::claim(-1); return; }
    const auto st = me.state();
    if (st.contains(cambc::champion_state::recalling)
        || st.contains(cambc::champion_state::submitting_gems)
        || st.contains(cambc::champion_state::teleporting)) return;
    if (!me.can_move() && !me.can_attack()
        && !st.contains(cambc::champion_state::can_cast)) return;

    ++c_turn;
    // Spawn heals to full at turn end, so leaving early wastes the trip home.
    if (cambc::map::spawn_region(cambc::team::ally).is_set(me.position())
        && me.health() < me.max_health()) {
        claims::claim(-1);
        ++c_heal;
        goto report;
    }
    // Healing an ally does not take the turn: it is cast and then the champion
    // carries on, as the Python bot does. A walk-exclusive heal is already ruled
    // out by may_cast once we have walked.
    if (combat::heal_allies()) ++c_healcast;
    if (survive_check()) { ++c_survive; goto report; }
    if (heal_trip()) goto report;
    if ((!policy::boss_map() || bank_allowed()) && bank()) { ++c_bank; goto report; }
    if (policy::boss_map()) { if (!boss_farm()) ++c_none; }
    else if (!farm()) ++c_none;
report:
    if (c_turn % 400 == 0)
        std::cout << "SAGE2 BRANCH turns=" << c_turn << " survive=" << c_survive
                  << " (disengage=" << c_disengage << " shield=" << c_shield << " fight=" << c_fight << " retarget=" << c_retarget << " heal=" << c_heal << " skipped=" << c_skipped << " bankrun=" << c_bankrun << " floor=" << c_floor << " healcast=" << c_healcast << " boss=" << c_boss
                  << ") bank=" << c_bank << " attack=" << c_atk
                  << " move=" << c_move << " nogroup=" << c_nogroup
                  << " idle=" << c_none << std::endl;
}
