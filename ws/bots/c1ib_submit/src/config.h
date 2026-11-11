// config.py: tuning shared by the controller, economy and combat planner.
#pragma once
#include "common.h"

namespace config {

inline constexpr int BANK_GEMS = 24;
inline constexpr double RETREAT_HEALTH = 0.30;
inline constexpr double CARRIER_RETREAT_HEALTH = 0.43;
inline constexpr double HEAL_MIN_MISSING = 120;
inline constexpr std::uint32_t SHOP_GOLD = 150;
inline constexpr int SHOP_INTERVAL = 70;
// Recall to heal below this fraction of max health, and only when the recall
// itself is safe. This is not the 60% retreat-while-an-enemy-is-close gate.
inline constexpr double HEAL_RECALL = 0.60;
// Monolith raids on maps where monolith groups hold most of the gems.
inline constexpr std::int64_t RAID_ROUND = 900;
inline constexpr int RAID_ASSUME = 2;
inline constexpr double RAID_PULL = 40;
inline constexpr double RAID_SHARE = 0.5;
// Break a nearby enemy altar lock instead of walking much further to a free one.
inline constexpr std::int64_t LOCK_BREAK = 6;
// Bank a small bag once either side is this close to the win, so carried gems
// are not still in a pocket when the game ends. The ordinary 24-gem threshold
// stays; 36 and 48 were measured losses.
inline constexpr std::int64_t RACE_MIN = 6;
inline constexpr std::int64_t RACE_ENEMY = 200;
inline constexpr std::int64_t RACE_OURS = 150;
// A tribute channels for 0.1 rounds per gem. Forty gems is four rounds of
// standing still; a monolith reward is about twenty. Do not start that channel
// alone. Ordinary 24-gem deposits are left alone.
inline constexpr std::uint32_t FAT_BAG = 40;
// Leave a fight when our side's health-times-strength within DISENGAGE_RADIUS
// falls below DISENGAGE_RATIO of theirs, and stay out until it recovers past the
// ratio plus DISENGAGE_HYSTERESIS.
inline constexpr double DISENGAGE_RATIO = 0.5;
inline constexpr double DISENGAGE_HYSTERESIS = 0.2;
inline constexpr int DISENGAGE_RADIUS = 5;
// pc (2026-11-10): decide before contact. 40% of our lab deaths are one champion against two to four (0v2 21%,
// 0v3 14%, 0v4 5%), and 1v2 at equal stats is a ratio of exactly 0.50, which the rule above does not leave.
// While no enemy is within PRE_CONTACT tiles, leave when our side within PRE_RADIUS is below PRE_RATIO of theirs.
inline constexpr double PRE_RATIO = 0.75;
inline constexpr int PRE_RADIUS = 7;
inline constexpr int PRE_CONTACT = 3;
inline constexpr bool DEBUG = false;
// Rewards go to Vesper Vale (gold +33%) or Marcella (2 gold per gem tributed) when
// either is claiming the group and within ROLE_NEAR of it (teamwork.h; mkrole.py).
inline constexpr int ROLE_NEAR = 3;
// Map fixes (analysis/rebuild/mkmaps.py): contested captures, walled-in altars,
// party size on three-pick maps, and maps with almost no gems.
inline constexpr bool CONTEST_HUNT = false;
inline constexpr bool BREACH = true;
inline constexpr bool PARTY_SIZE = true;
inline constexpr double SCARCE_GEMS = 20;
// Group-aware camp choice (strategy::choose_group). Teammates whose claim is a group
// add their damage to its clear and take their share of its hits; the joiner is
// credited value x (its share of the damage) ^ JOIN_ALPHA. Camp damage taken costs
// DMG_COST rounds per full health bar, the walk home to heal it back. A visible
// teammate counts only if it is no more than JOIN_SLACK steps further away than us.
inline constexpr bool JOIN = true;
inline constexpr double JOIN_ALPHA = 0.5;
inline constexpr double DMG_COST = 50;
inline constexpr int JOIN_SLACK = 8;
// Party-map fixes (analysis/rebuild/mkparty.py).
inline constexpr bool P_ALTAR = true;
inline constexpr int ALTAR_NEAR = 3;
inline constexpr double ALTAR_BONUS = 3;
inline constexpr std::int64_t ALTAR_WAIT = 30;
inline constexpr int ALTAR_BANK = 2;
inline constexpr std::int64_t ALTAR_UNTIL = 80;
inline constexpr bool P_GATE = false;
inline constexpr std::int64_t GATE_BOSS_ROUND = 650;
inline constexpr bool P_QUEUE = false;
inline constexpr bool P_NEAR = true;
inline constexpr bool NEAR_AUTO = false;
inline constexpr bool NEAR_NOALTAR = true;

inline int priority(bc::champion_type type) {
    switch (type) {
    case bc::champion_type::willow: return 50;
    case bc::champion_type::ryth: return 40;
    case bc::champion_type::varg: return 30;
    case bc::champion_type::marcella: return 30;
    case bc::champion_type::vendetta: return 20;
    default: return 10;
    }
}

// Each entry completes one emblem. Duplicate passives do not stack, so the
// permanent late-game purchase is Power rather than another Monster emblem.
inline std::vector<bc::item_type> build(bc::champion_type type) {
    using I = bc::item_type;
    if (type == bc::champion_type::willow)
        return {I::jungle_shard_of_focus, I::durability_shard_of_health, I::power_shard_of_focus};
    if (type == bc::champion_type::vesper_vale)
        return {I::treasure_shard_of_strength, I::monster_shard_of_strength, I::durability_shard_of_health, I::skirmish_shard_of_strength};
    return {I::monster_shard_of_strength, I::durability_shard_of_health, I::jungle_shard_of_strength, I::skirmish_shard_of_strength};
}

}  // namespace config
