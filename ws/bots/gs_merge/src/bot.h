// bot.py, escort.py, boss.py: score first: survive, bank, defend captures, then clear assigned camps.
#pragma once
#include "combat.h"
#include "common.h"
#include "config.h"
#include "nav.h"
#include "policy.h"
#include "progress.h"
#include "strategy.h"
#include "teamwork.h"
#include "turn.h"

using strategy::ObjectivePtr;

// An idle champion away from spawn recalls home after this many consecutive idle rounds.
inline constexpr int IDLE_HOME = 10;

class Bot {
public:
    std::optional<std::vector<bc::map::camp_group>> groups;
    std::vector<ObjectivePtr> metadata;
    bool have_metadata = false;
    strategy::Respawns respawns;
    std::optional<int> current_group;
    ObjectivePtr objective;
    int purchase_index = 0;
    std::optional<bc::item_type> scaling_item;
    std::int64_t last_purchase = -100;
    bool banking = false;
    bool altar_divert = false;
    bool disengaging = false;
    std::unique_ptr<Teamwork> team;
    std::optional<bc::distance_field> altar_field;
    std::string last_state;
    std::optional<nav::Mode> mobility_mode;
    // The tiles the group list was prepared from can reach; outside them it is stale.
    bc::bitboard prepared_reach;
    // Consecutive rounds in which farm found nothing to do.
    int idle_rounds = 0;
    std::int64_t idle_last = -1;
    std::map<std::pair<int, int>, ObjectivePtr> by_tile;
    Progress progress{};
    std::optional<int> supporting_handle;
    Progress bank_progress{10};

    virtual ~Bot() = default;

    void status(const std::string& label) {
        if (config::DEBUG && label != last_state)
            std::cout << "STATE r=" << bc::round_number() << " " << label << " fuel=" << bc::fuel_remaining() << std::endl;
        last_state = label;
    }

    ObjectivePtr held_at(bc::vec2 p) const {
        const auto it = by_tile.find(key_of(p));
        return it == by_tile.end() ? nullptr : it->second;
    }

    void shop(bc::champion& me) {
        // Buy the route-enabling tool before shards drain the purse. A dash
        // cannot land on a monster blocking a narrow island entrance.
        if (nav::needs_crystal() && me.can_buy(bc::consumable_type::tp_crystal)) {
            turn::check();
            me.buy(bc::consumable_type::tp_crystal);
        }
        if (me.can_buy(bc::consumable_type::altar_lock)) {
            turn::check();
            me.buy(bc::consumable_type::altar_lock);
        }
        const auto build = config::build(me.champion_name());
        const int rounds = std::min<int>(40, static_cast<int>(me.gold_count() / 30));
        for (int i = 0; i < rounds; ++i) {
            const auto emblem = static_cast<std::size_t>(purchase_index / 5);
            bc::item_type item = bc::item_type::power_shard_of_strength;
            if (emblem < build.size()) {
                item = build[emblem];
            } else {
                // Finish the current emblem before comparing the next purchase.
                // Maximise the marginal health x damage product using live stats.
                if (!scaling_item || purchase_index % 5 == 0) {
                    const auto stats = me.base_stats();
                    const double health_gain = D(stats.health_growth) * D(me.strength());
                    const double damage_gain = D(stats.strength_growth) * D(me.max_health());
                    scaling_item = health_gain > damage_gain ? bc::item_type::power_shard_of_health
                                                             : bc::item_type::power_shard_of_strength;
                }
                item = *scaling_item;
            }
            if (!me.can_buy(item)) break;
            // Batch the remainder of this emblem; this also reduces SDK/fuel
            // overhead on a rich respawn without skipping any shard purchases.
            const auto count = std::min<std::uint32_t>(5 - purchase_index % 5, me.gold_count() / 30);
            turn::check();
            me.buy(item, count);
            purchase_index += static_cast<int>(count);
            last_purchase = bc::round_number();
        }
        if (nav::needs_crystal() && me.can_buy(bc::consumable_type::tp_crystal)) {
            turn::check();
            me.buy(bc::consumable_type::tp_crystal);
        }
    }

    template <class Camps>
    bool recall_safe(const bc::champion& me, const std::vector<bc::champion>& enemies, const Camps& camps) const {
        for (const auto& e : enemies)
            if (!(distance(me.position(), e.position()) > 6)) return false;
        for (const auto& c : camps)
            if (!(!c.is_awake() || c.strength() <= 0 || distance(me.position(), c.position()) > c.attack_range())) return false;
        return true;
    }

    // A long tribute is how a monolith raid hands its gems to the other team.
    // Short deposits are unchanged. A fat bag channels only when the tile is
    // clear or two allies are standing on it.
    template <class Camps>
    bool channel_ok(const bc::champion& me, const std::vector<bc::champion>& enemies, const Camps& camps) const {
        if (me.gem_count() < config::FAT_BAG) return true;
        if (recall_safe(me, enemies, camps)) return true;
        int near = 0;
        for (const auto& ally : team->allies)
            if (!same(ally, me) && ally.is_alive() && ally.is_visible() && distance(ally.position(), me.position()) <= 4)
                ++near;
        return near >= 2;
    }

    virtual void bank(bc::champion& me, const std::vector<bc::champion>& enemies, const std::vector<bc::camp>& camps) {
        team->claim();
        if (bank_progress.blocked({D(me.position().x), D(me.position().y), D(me.gem_count())})) {
            if (recall_safe(me, enemies, camps)) {
                turn::check();
                me.recall();
                bank_progress.reset();
                return;
            }
        }
        bc::bitboard goals, locked;
        const auto range = bc::constants::submit_gems_range;
        std::int64_t near_free = 10000, near_locked = 10000;
        // Party maps already bank big bags with the group on the altar. The
        // fat-bag hold is for a solo carrier, which is who died in the raid smoke.
        const bool may_channel = policy::party() || channel_ok(me, enemies, camps);
        for (const auto altar : gm::altars().positions()) {
            turn::check();
            std::optional<bc::altar_lock> lock;
            if (bc::vision::has_altar_lock(altar)) lock = bc::vision::altar_lock_at(altar);
            if (lock && lock->is_enemy()) {
                if (me.can_attack() && me.attack_tiles().is_set(altar)) {
                    turn::check();
                    me.attack(*lock);
                    return;
                }
                locked |= nav::around(altar, range);
                near_locked = std::min(near_locked, distance(me.position(), altar));
            } else {
                if (distance(me.position(), altar) <= range) {
                    if (may_channel) {
                        turn::check();
                        me.submit_gems(altar);
                        return;
                    }
                    // Standing on the altar with a fat bag and no cover. Leave
                    // rather than start a twenty-round channel.
                    nav::retreat(enemies, camps);
                    return;
                }
                goals |= nav::around(altar, range);
                near_free = std::min(near_free, distance(me.position(), altar));
            }
        }
        // A locked altar close by beats a free one far away: five hits clear a lock.
        if (!locked.is_empty() && near_locked + config::LOCK_BREAK < near_free) goals = bc::bitboard{};
        if (!goals.is_empty()) {
            const auto threat = nav::threat_mask(enemies, camps);
            if (nav::move_to(goals, &threat)) return;
            // A fat bag does not take the unguarded fallback through a visible enemy.
            if (policy::party() || me.gem_count() < config::FAT_BAG || recall_safe(me, enemies, camps)) {
                if (nav::move_to(goals)) return;
            } else {
                nav::retreat(enemies, camps);
                return;
            }
        }
        nav::move_to(locked);
    }

    // Separate from the 24-gem bank. With at least 16 gems, deposit before the
    // walk when the altar is a strictly shorter walk than the camp this
    // champion would take next. A nearby enemy does not start a deposit.
    bool deposit_before_camp(bc::champion& me, const ObjectivePtr& camp, const std::vector<bc::champion>& enemies) {
        // Leaving a monolith to bank lost 00monolith from both sides. Other
        // camps still deposit when the altar is the shorter walk.
        if (altar_divert || !camp || !altar_field || me.gem_count() < 16) return false;
        bool leaving_monolith = false;
        for (const auto& camp_def : camp->camps)
            if (camp_def.is_monolith()) leaving_monolith = true;
        if (leaving_monolith) return false;
        // Already hitting this camp: that is the fight, not the walk to it.
        const auto range = me.attack_range();
        for (const auto& monster : combat::visible_camps(camp->camps))
            if (monster.health() > 0 && distance(me.position(), monster.position()) <= range) return false;
        const int altar = static_cast<int>(altar_field->get(me.position()));
        const auto& costs = nav::field_from(me.position());
        int travel = std::numeric_limits<int>::max();
        for (const auto p : camp->positions)
            if (costs.reached.is_set(p)) travel = std::min(travel, costs.costs.get(p));
        if (travel == std::numeric_limits<int>::max() || !(altar < travel)) return false;
        altar_divert = true;
        objective = nullptr;
        current_group.reset();
        banking = true;
        status("bank");
        bank(me, enemies, bc::vision::camps());
        altar_divert = false;
        return true;
    }

    virtual void farm(bc::champion& me, const std::vector<bc::champion>& enemies) {
        auto chosen = objective;
        if (chosen) {
            if (!(chosen->spawns & bc::vision::visible_tiles()).is_empty()) {
                const auto state = chosen->group.state();
                if (const auto* respawning = std::get_if<bc::map::camp_group_respawning>(&state)) {
                    respawns[chosen->handle] = bc::round_number() + respawning->timer;
                    chosen = nullptr;
                } else if (std::holds_alternative<bc::map::camp_group_reward_available>(state)) {
                    const auto owner = team->collector(chosen->handle, &chosen->spawns);
                    if (owner && *owner != team->slot) chosen = nullptr;
                }
            }
        }
        if (!chosen) {
            supporting_handle.reset();
            chosen = strategy::choose_group(metadata, me, respawns, current_group, *team, enemies);
        }
        if (!chosen) {
            chosen = strategy::choose_cooperative(metadata, me, respawns, *team);
            if (chosen && team->collector(chosen->handle, &chosen->spawns)) supporting_handle = chosen->handle;
        }
        objective = chosen;
        if (!chosen) {
            const auto now = static_cast<std::int64_t>(bc::round_number());
            idle_rounds = idle_last == now - 1 ? idle_rounds + 1 : 1;
            idle_last = now;
            team->claim();
            if (me.gem_count()) {
                banking = true;
                bank(me, enemies, {});
            } else if (held_at(me.position())) {
                bc::bitboard occupied;
                for (const auto& o : metadata) occupied |= o->spawns;
                nav::park_nearby(occupied);
            } else if ((me.gold_count() >= 150 ||
                        (idle_rounds >= IDLE_HOME && !gm::spawn_region(bc::team::ally).is_set(me.position()))) &&
                       recall_safe(me, enemies, std::vector<bc::camp>{})) {
                // Idle away from home with too little gold to shop: home reaches more
                // groups on foot, and the shop sells a crystal.
                turn::check();
                me.recall();
            }
            return;
        }
        if (deposit_before_camp(me, chosen, enemies)) return;
        current_group = chosen->handle;
        team->claim(chosen->handle, supporting_handle && *supporting_handle == chosen->handle);
        // Static routing deliberately ignores unknown camp occupancy. Detect
        // a blocked landing or choke rather than retrying it for 2,000 turns.
        // Record before the expensive planner so fuel suspension cannot skip
        // recovery. Damage and movement both count as measurable progress.
        const auto observed = combat::visible_camps(chosen->camps);
        std::vector<double> signature{D(chosen->handle), D(me.position().x), D(me.position().y)};
        for (const auto& camp : observed) {
            turn::check();
            signature.push_back(D(handle_of(camp)));
            signature.push_back(D(camp.health()));
        }
        if (progress.blocked(signature)) {
            respawns[chosen->handle] = bc::round_number() + 80;
            objective = nullptr;
            current_group.reset();
            team->claim();
            progress.reset();
            return;
        }
        const auto visible = bc::vision::visible_tiles();
        if (!(chosen->spawns & visible).is_empty()) {
            if (std::holds_alternative<bc::map::camp_group_reward_available>(chosen->group.state())) {
                status("capture");
                nav::move_to(chosen->spawns);
                return;
            }
        }
        const auto& targets = observed;
        if (targets.empty()) {
            nav::move_to(chosen->spawns);
            return;
        }
        auto picked = combat::choose_camp(targets);
        if (!picked) return;
        bc::camp target = *picked;
        status("farm");
        combat::fight(target, targets);
        // A spell or kill-reset can leave an ordinary attack unused. Immediately
        // switch to the next living monster instead of wasting the allowance.
        for (int i = 0; i < 3; ++i) {
            if (combat::live(target) || !(me.can_attack() || me.can_cast())) break;
            std::vector<bc::camp> remaining;
            for (const auto& c : targets)
                if (combat::live(c) && c.health() > 0) remaining.push_back(c);
            if (remaining.empty()) break;
            target = *first_min(remaining.begin(), remaining.end(), [&](const bc::camp& c) {
                return std::make_pair(!me.attack_tiles().is_set(c.position()), D(c.health()));
            });
            combat::fight(target, targets);
        }
        if (combat::live(target) && target.health() > 0) {
            if (nav::move_to(nav::around(target.position(), me.attack_range())))
                if (combat::live(target) && target.health() > 0) combat::fight(target, targets);
        }
        // When the last monster falls, start travelling onto the reward now.
        if (!combat::live(target)) {
            bool any = false;
            for (const auto& c : targets)
                if (combat::live(c) && c.health() > 0) any = true;
            if (!any) nav::move_to(chosen->spawns);
        }
    }

    // Keep an executing collector; helpers step away only after handover.
    bool reserve_capture(const ObjectivePtr& holding) {
        const auto owner = team->collector(holding->handle, &holding->spawns);
        const bool assisting = owner && *owner != team->slot;
        team->claim(holding->handle, assisting);
        if (assisting) {
            const auto& collector = team->allies[*owner];
            if (collector.is_visible() && holding->spawns.is_set(collector.position())) {
                nav::move_to(nav::around(collector.position(), 4) & ~holding->spawns, nullptr, false);
                return true;
            }
        }
        return false;
    }

    void play_turn() {
        auto& me = bc::self();
        if (!groups) {
            groups = gm::camp_groups();
            team = std::make_unique<Teamwork>();
            turn::check();
            me.set_priority(config::priority(me.champion_name()));
        }
        shop(me);
        if (!me.is_alive()) {
            team->claim();
            current_group.reset();
            objective = nullptr;
            status("dead");
            return;
        }
        if (me.is_recalling() || me.is_submitting_gems() || me.is_teleporting()) {
            const auto held = held_at(me.position());
            if (held && std::holds_alternative<bc::map::camp_group_reward_available>(held->group.state())) {
                const auto owner = team->collector(held->handle, &held->spawns);
                team->claim(held->handle, owner && *owner != team->slot);
            } else {
                team->claim();
            }
            return;
        }
        if (!(me.can_move() || me.can_attack() || me.can_cast())) return;
        const auto mode = nav::mobility();
        // The list holds the groups reachable from where it was prepared. A champion
        // that spent its last crystal reaching an island kept that island's one group
        // after dying or recalling (01big-world: Ryth idle 1,500 rounds); prepare again
        // whenever it stands outside the area the list was prepared for.
        if (!have_metadata || mobility_mode != mode || !prepared_reach.is_set(me.position())) {
            metadata = strategy::prepare(*groups);
            have_metadata = true;
            mobility_mode = mode;
            prepared_reach = nav::field_from(me.position()).reached;
            prepared_reach.set(me.position(), true);
            by_tile.clear();
            for (const auto& o : metadata)
                for (const auto p : o->positions) by_tile[key_of(p)] = o;
        }
        if (!altar_field) {
            bc::bitboard goals;
            for (const auto altar : gm::altars().positions()) goals |= nav::around(altar, bc::constants::submit_gems_range);
            altar_field.emplace();
            bc::bitboard ignored;
            altar_field->compute(nav::static_walls(), goals & ~nav::static_walls(), ignored);
        }
        turn::check();
        const bool at_spawn = gm::spawn_region(bc::team::ally).is_set(me.position());
        if (at_spawn && me.health() < me.max_health()) {
            team->claim();
            return;
        }
        std::vector<bc::champion> enemies;
        for (auto& e : bc::vision::champions(bc::team::enemy))
            if (e.is_alive()) enemies.push_back(e);
        const auto camps = bc::vision::camps();
        turn::check();
        combat::heal_allies(team->allies);
        const double threshold = me.gem_count() ? config::CARRIER_RETREAT_HEALTH : config::RETREAT_HEALTH;
        const auto position = me.position();
        double camp_pressure = 0;
        for (const auto& c : camps)
            if (c.is_awake() && distance(position, c.position()) <= c.attack_range()) camp_pressure += c.strength();
        // Monsters act before our next turn. Leave enough health for the two
        // attacks a melee champion may take while walking out of a dense pack.
        const double retreat_at = std::max(D(me.max_health()) * threshold, camp_pressure * 2 + D(me.max_health()) * 0.08);
        if (!at_spawn && D(me.health()) < retreat_at) {
            status("retreat");
            objective = nullptr;
            team->claim();
            if (recall_safe(me, enemies, camps)) {
                turn::check();
                me.recall();
            } else {
                // Damage/reset before withdrawing can kill a pursuer. Ranged
                // champions must preserve their ordinary move allowance.
                if (me.base_stats().base_attack_range <= 1) {
                    std::vector<bc::champion> close;
                    for (const auto& e : enemies)
                        if (distance(me.position(), e.position()) <= 1) close.push_back(e);
                    if (!close.empty())
                        combat::fight(*first_min(close.begin(), close.end(), [](const bc::champion& e) { return D(e.health()); }),
                                      close);
                }
                nav::retreat(enemies, camps);
            }
            return;
        }
        // Heal at home when nobody is hitting us. Not while standing on a camp
        // tile (that is a capture), not when a deposit is already close, and
        // not on a party map: those maps need the group to stay together, and
        // recalling at 60% splits it. Solo maps are where the trip pays.
        if (!policy::party() && !at_spawn && D(me.health()) < D(me.max_health()) * config::HEAL_RECALL &&
            !held_at(me.position()) && recall_safe(me, enemies, camps)) {
            const int altar_distance = altar_field->get(me.position());
            const bool bank_close = me.gem_count() && strategy::should_bank(!enemies.empty(), altar_distance) && altar_distance <= 8;
            if (!bank_close) {
                status("heal");
                objective = nullptr;
                team->claim();
                turn::check();
                me.recall();
                return;
            }
        }
        {
            const auto [ratio, threats] = combat::local_power(enemies, team->allies, config::DISENGAGE_RADIUS);
            const double leave = config::DISENGAGE_RATIO + (disengaging ? config::DISENGAGE_HYSTERESIS : 0);
            disengaging = !at_spawn && threats > 0 && ratio < leave;
            if (disengaging) {
                status("disengage");
                objective = nullptr;
                team->claim();
                // Take a kill already in reach before leaving. Only melee champions can: a
                // ranged champion moves or attacks in a turn, so the swing would cost it the
                // escape step.
                std::optional<bc::champion> target;
                if (me.base_stats().base_attack_range <= 1) target = combat::finishing_blow(enemies);
                if (target) combat::fight(*target, enemies);
                nav::retreat(enemies, camps);
                return;
            }
        }
        auto holding = held_at(me.position());
        if (holding && !std::holds_alternative<bc::map::camp_group_reward_available>(holding->group.state())) holding = nullptr;
        if (holding) {
            current_group = holding->handle;
            if (reserve_capture(holding)) return;
            status("capture");
            if (me.gem_count() && (policy::party() || channel_ok(me, enemies, camps))) {
                for (const auto altar : gm::altars().positions()) {
                    if (distance(me.position(), altar) <= bc::constants::submit_gems_range) {
                        if (!bc::vision::has_altar_lock(altar) || !bc::vision::altar_lock_at(altar).is_enemy()) {
                            turn::check();
                            me.submit_gems(altar);
                            return;
                        }
                    }
                }
            }
            const auto target = combat::choose_enemy(enemies, team->allies, true);
            if (target) combat::fight(*target, enemies);
            return;
        }
        if (!me.gem_count()) {
            banking = false;
            bank_progress.reset();
        }
        if (banking || strategy::should_bank(!enemies.empty(), altar_field->get(me.position()))) {
            banking = true;
            status("bank");
            objective = nullptr;
            bank(me, enemies, camps);
            return;
        }
        if (!at_spawn && me.gold_count() >= config::SHOP_GOLD &&
            static_cast<std::int64_t>(bc::round_number()) - last_purchase >= config::SHOP_INTERVAL &&
            bc::round_number() < bc::constants::max_rounds - 150 && recall_safe(me, enemies, camps)) {
            team->claim();
            objective = nullptr;
            turn::check();
            me.recall();
            return;
        }
        const auto& enemy_spawn = gm::spawn_region(bc::team::enemy);
        std::vector<bc::champion> pursuit;
        // Below HEAL_RECALL, do not walk toward an enemy to open a fight.
        // Enemies already within 4 tiles stay eligible: dropping that accept
        // cost about 159 gems. Capture defence and disengage are unchanged.
        const bool hurt = !policy::party() && D(me.health()) < D(me.max_health()) * config::HEAL_RECALL;
        for (const auto& e : enemies) {
            if (enemy_spawn.is_set(e.position())) continue;
            if (hurt && distance(me.position(), e.position()) > 4) continue;
            pursuit.push_back(e);
        }
        const auto target = combat::choose_enemy(pursuit, team->allies);
        if (target) {
            status("combat");
            bool acted = combat::fight(*target, pursuit);
            bool moved = false;
            if (combat::live(*target) && target->health() > 0) {
                moved = nav::move_to(nav::around(target->position(), me.attack_range()));
                if (moved && combat::live(*target) && target->health() > 0) acted = combat::fight(*target, pursuit) || acted;
            }
            if (acted || moved) return;
        }
        farm(me, enemies);
    }
};

// escort.py: keep Willow in healing range of a productive front-line farmer.
class EscortBot : public Bot {
public:
    void farm(bc::champion& me, const std::vector<bc::champion>& enemies) override {
        const auto claims = team->assignments();
        struct Candidate {
            double priority;
            int index;
            const bc::champion* ally;
            ObjectivePtr objective;
        };
        std::vector<Candidate> candidates;
        for (std::size_t index = 0; index < team->allies.size(); ++index) {
            turn::check();
            const auto& ally = team->allies[index];
            if (same(ally, me) || !ally.is_alive() || claims[index] < 0) continue;
            ObjectivePtr found;
            for (const auto& o : metadata)
                if (o->handle == claims[index]) {
                    found = o;
                    break;
                }
            if (!found) continue;
            double priority = ally.champion_name() == bc::champion_type::varg ? 0 : 1;
            if (ally.is_visible()) {
                priority += D(distance(me.position(), ally.position())) / 12;
                if (D(ally.health()) < D(ally.max_health()) * 0.7) priority -= 1;
            }
            candidates.push_back({priority, static_cast<int>(index), &ally, found});
        }
        if (candidates.empty()) return Bot::farm(me, enemies);
        const auto& chosen = *first_min(candidates.begin(), candidates.end(),
                                        [](const Candidate& c) { return std::make_pair(c.priority, c.index); });
        const auto& leader = *chosen.ally;
        const auto picked = chosen.objective;
        objective = picked;
        if (deposit_before_camp(me, picked, enemies)) return;
        current_group = picked->handle;
        team->claim(picked->handle, true);
        const auto visible = bc::vision::visible_tiles();
        if (!(picked->spawns & visible).is_empty()) {
            const auto state = picked->group.state();
            if (const auto* respawning = std::get_if<bc::map::camp_group_respawning>(&state)) {
                respawns[picked->handle] = bc::round_number() + respawning->timer;
                team->claim();
                objective = nullptr;
                return Bot::farm(me, enemies);
            }
        }
        const auto targets = combat::visible_camps(picked->camps);
        if (!targets.empty()) {
            const auto& target = *first_min(targets.begin(), targets.end(), [&](const bc::camp& c) {
                return std::make_pair(!me.attack_tiles().is_set(c.position()), D(c.health()));
            });
            combat::fight(target, targets);
            if (combat::live(target) && target.health() > 0)
                nav::move_to(nav::around(target.position(), leader.is_visible() ? 3 : 1));
        } else {
            const auto anchor = leader.is_visible() ? leader.position() : picked->positions[0];
            nav::move_to(nav::around(anchor, leader.is_visible() ? 3 : 1) & ~picked->spawns);
        }
        combat::heal_allies(team->allies);
    }
};

// boss.py: a shielded, healed harvest party for maps gated by a central monolith.
class BossBot : public Bot {
public:
    std::int64_t bank_retry_at = 0;

    BossBot() { bank_progress = Progress{}; }

    void bank(bc::champion& me, const std::vector<bc::champion>& enemies, const std::vector<bc::camp>& camps) override {
        const auto now = static_cast<std::int64_t>(bc::round_number());
        if (now >= bank_retry_at) {
            if (!bank_progress.blocked({D(me.position().x), D(me.position().y), D(me.gem_count())}))
                return Bot::bank(me, enemies, camps);
            bank_retry_at = now + 80;
            bank_progress.reset();
        }
        // A failed deposit route must not prevent the upgrades needed to open it.
        banking = false;
        if (me.gold_count() >= 30 && recall_safe(me, enemies, camps)) {
            team->claim();
            objective = nullptr;
            turn::check();
            me.recall();
            return;
        }
        farm(me, enemies);
    }

    void farm(bc::champion& me, const std::vector<bc::champion>& enemies) override {
        const auto now = static_cast<std::int64_t>(bc::round_number());
        const auto visible = bc::vision::visible_tiles();
        std::vector<const bc::champion*> nearby;
        for (const auto& a : team->allies)
            if (a.is_alive() && a.is_visible() && distance(a.position(), me.position()) <= 6) nearby.push_back(&a);
        double health = 0, damage = 0;
        for (const auto* a : nearby) health += a->max_health();
        bool boss_ready = now >= 650 && purchase_index >= 10 && nearby.size() >= 4 && health >= 7000;
        if (boss_ready) {
            for (const auto* a : nearby) damage += strategy::dps(*a, 2);
            boss_ready = damage >= 400;
        }
        const auto claims = team->assignments();
        std::optional<int> shared;
        for (std::size_t i = 0; i < team->allies.size() && i < claims.size(); ++i)
            if (team->allies[i].is_alive() && claims[i] >= 0) {
                shared = claims[i];
                break;
            }
        // On party maps (policy 3) every heavy objective waits for the full party,
        // not only monoliths: 00stampede's gems are a herd of six elks.
        const auto gated = [](const ObjectivePtr& o) { return policy::kind() == 3 ? o->heavy : o->monolith; };
        ObjectivePtr chosen;
        if (shared)
            for (const auto& o : metadata)
                if (o->handle == *shared && (!gated(o) || now >= 650) && (!boss_ready || gated(o))) {
                    chosen = o;
                    break;
                }
        if (chosen && !(chosen->spawns & visible).is_empty()) {
            const auto state = chosen->group.state();
            if (const auto* respawning = std::get_if<bc::map::camp_group_respawning>(&state)) {
                respawns[chosen->handle] = now + respawning->timer;
                chosen = nullptr;
            }
        }
        if (!chosen) {
            const auto& costs = nav::field_from(me.position());
            double power = 0;
            for (const auto& a : team->allies)
                if (a.is_alive()) power += D(a.base_stats().base_strength) + D(a.base_stats().base_focus) / 4;
            std::vector<bc::vec2> enemy_positions;
            for (const auto& enemy : enemies)
                if (enemy.is_visible() && enemy.is_alive()) enemy_positions.push_back(enemy.position());
            const int attack_range = static_cast<int>(me.attack_range());
            const auto here = me.position();
            double best = std::numeric_limits<double>::infinity();
            bool best_opens = false;
            for (const auto& o : metadata) {
                turn::check();
                if (strategy::respawn_at(respawns, o->handle) > now || (gated(o) && !boss_ready) ||
                    (boss_ready && !gated(o)))
                    continue;
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
                int gap = std::numeric_limits<int>::max();
                for (const auto p : positions) {
                    travel = std::min(travel, costs.costs.get(p));
                    gap = std::min(gap, static_cast<int>(distance(here, p)));
                }
                const double score = (travel + hp / std::max(1.0, power) + bc::constants::capture_time) /
                                     std::max(1.0, o->gems + o->gold * 0.4);
                std::int64_t nearest = std::numeric_limits<std::int64_t>::max();
                for (const auto p : positions)
                    for (const auto q : enemy_positions) nearest = std::min(nearest, distance(p, q));
                const bool opens = strategy::opens_before_enemy(gap, attack_range, hp == 0, nearest, !enemy_positions.empty());
                if (!chosen || (opens && !best_opens) || (opens == best_opens && score < best)) {
                    chosen = o;
                    best = score;
                    best_opens = opens;
                }
                if (chosen && bc::fuel_remaining() < turn::fuel(700'000)) break;
            }
        }
        objective = chosen;
        if (!chosen) {
            team->claim();
            if (me.gold_count() >= 30 && recall_safe(me, enemies, bc::vision::camps())) {
                turn::check();
                me.recall();
            }
            return;
        }
        if (deposit_before_camp(me, chosen, enemies)) return;
        current_group = chosen->handle;
        team->claim(chosen->handle);
        const auto targets = combat::visible_camps(chosen->camps);
        if (targets.empty()) {
            status("party-travel");
            nav::move_to(chosen->spawns);
            return;
        }
        const auto picked = combat::choose_camp(targets);
        if (!picked) return;
        const auto& target = *picked;
        status("party-clear");
        combat::fight(target, targets);
        if (combat::live(target) && target.health() > 0) {
            if (nav::move_to(nav::around(target.position(), me.attack_range())))
                if (combat::live(target) && target.health() > 0) combat::fight(target, targets);
        }
        bool any = false;
        for (const auto& c : targets)
            if (combat::live(c) && c.health() > 0) any = true;
        if (!any) nav::move_to(chosen->spawns);
    }
};
