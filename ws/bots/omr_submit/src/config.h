// config.py: tuning shared by the controller, economy and combat planner.
#pragma once
#include "common.h"
#include "policy_table.h"

namespace config {

inline constexpr int BANK_GEMS = 24;
inline constexpr double RETREAT_HEALTH = 0.30;
inline constexpr double CARRIER_RETREAT_HEALTH = 0.43;
inline constexpr double HEAL_MIN_MISSING = 120;
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
inline constexpr bool DEBUG = false;

// Early squads (bot.h, squad_follow). Games between near-equal bots are decided by
// the kill lead at round 300 (ahead: 89% won), and solo farmers meet the enemy
// one on one. Until SQUAD_ROUNDS each follower takes its leader's camp and stays
// within SQUAD_NEAR of it, so an enemy who finds one of us finds two.
inline constexpr std::int64_t SQUAD_NEAR = 2;
inline constexpr std::int64_t SQUAD_LEASH = 12;
// Leader of each team slot, by team size, or -1 to farm alone. Five: slot 0 (the
// first pick) leads 3 and 4; slot 1 leads 2. Four: 0 leads 3, 1 leads 2. Three: 0 leads 2.
inline int squad_leader(int slot, int size) {
    if (size >= 5) { const int map[5] = {-1, -1, 1, 0, 0}; return slot < 5 ? map[slot] : -1; }
    if (size == 4) { const int map[4] = {-1, -1, 1, 0}; return map[slot]; }
    if (size == 3) { const int map[3] = {-1, -1, 0}; return map[slot]; }
    return -1;
}

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
    switch (pol::P().build) {
    case 1: return {I::treasure_shard_of_strength, I::jungle_shard_of_strength, I::durability_shard_of_health};
    case 2: return {I::jungle_shard_of_strength, I::treasure_shard_of_strength, I::durability_shard_of_health};
    case 3: return {I::bruiser_shard_of_strength, I::treasure_shard_of_strength, I::durability_shard_of_health};
    case 4: return {I::durability_shard_of_health, I::treasure_shard_of_strength, I::jungle_shard_of_strength};
    case 5: return {I::jungle_shard_of_strength, I::bruiser_shard_of_strength, I::durability_shard_of_health};
    default: return {I::treasure_shard_of_strength, I::bruiser_shard_of_strength, I::durability_shard_of_health};
    }
}

}  // namespace config
