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
inline constexpr bool DEBUG = false;

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
    return {I::jungle_shard_of_strength, I::monster_shard_of_strength, I::durability_shard_of_health};
}

}  // namespace config
