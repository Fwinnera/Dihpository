// apex: tuning and switches. The decision layer is modelled on the #1 team
// (prism best girl); see docs/APEX-SPEC.md. Each switch below turns one part of
// that layer on, so an ablation differs from apex only in this file.
#pragma once
#include "common.h"

namespace config {

// #1's draft, by team size (draft.h).
inline constexpr bool DRAFT_TOP1 = false;
// #1's emblems, in its purchase order, then Bruiser (shop in bot.h).
inline constexpr bool BUILDS_TOP1 = false;
// Prism keeps its gems, which are its damage, and deposits to win or at the end.
inline constexpr bool PRISM_FINISHER = false;
// Heart of Ruin fights low and shields early: its damage grows as its health falls.
inline constexpr bool HOR_TANK = false;
// Monolith raids late, by several champions (v100's raid900 + monogate).
inline constexpr bool RAIDS = true;
// Break a nearby enemy altar lock rather than walk far to a free altar (v100's lockbreak).
inline constexpr bool LOCK_BREAK_ON = true;

inline constexpr int BANK_GEMS = 24;
inline constexpr double RETREAT_HEALTH = 0.30;
inline constexpr double CARRIER_RETREAT_HEALTH = 0.43;
inline constexpr double HEAL_MIN_MISSING = 120;
inline constexpr std::uint32_t SHOP_GOLD = 150;
inline constexpr int SHOP_INTERVAL = 70;
// Leave a fight when our side's health-times-strength within DISENGAGE_RADIUS
// falls below DISENGAGE_RATIO of theirs, and stay out until it recovers past the
// ratio plus DISENGAGE_HYSTERESIS.
inline constexpr double DISENGAGE_RATIO = 0.5;
inline constexpr double DISENGAGE_HYSTERESIS = 0.2;
inline constexpr int DISENGAGE_RADIUS = 5;
// Recall to heal below HEAL_RECALL of max health when recall is safe (v97); 0 disables.
inline constexpr double HEAL_RECALL = 0.60;
// Monolith raids: eligible from RAID_ROUND where monolith groups hold at least
// RAID_SHARE of the map's gems, costed for 1 + RAID_ASSUME raiders (or more if
// more have claimed it), and a claimed raid pulls teammates in.
inline constexpr std::int64_t RAID_ROUND = 900;
inline constexpr double RAID_SHARE = 0.5;
inline constexpr int RAID_ASSUME = 2;
inline constexpr double RAID_PULL = 40;
// Break an enemy altar lock rather than walk more than LOCK_BREAK tiles further to a free altar.
inline constexpr std::int64_t LOCK_BREAK = 6;
// Prism deposits at PRISM_CAP gems, or when the game would otherwise end within
// PRISM_END_MARGIN rounds of its arrival and channel. #1's Prism peaks at a
// median 196 gems and makes 82% of its deposits in the last 50 rounds.
inline constexpr std::int64_t PRISM_CAP = 200;
inline constexpr std::int64_t PRISM_END_MARGIN = 40;
// Heart of Ruin, not carrying, retreats only below this share of its health,
// and casts its self-shield below TANK_SHIELD_HEALTH.
inline constexpr double TANK_RETREAT_HEALTH = 0.15;
inline constexpr double TANK_SHIELD_HEALTH = 0.90;
inline constexpr bool DEBUG = false;

inline bool tank(bc::champion_type type) { return HOR_TANK && type == bc::champion_type::heart_of_ruin; }
inline bool finisher(bc::champion_type type) { return PRISM_FINISHER && type == bc::champion_type::prism; }

// Champions whose damage is focus-scaled: their late shards are Bruiser Focus or Health.
inline bool focus_scaler(bc::champion_type type) {
    return BUILDS_TOP1 && (type == bc::champion_type::prism || type == bc::champion_type::heart_of_ruin);
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
// permanent late-game purchase is Bruiser (seven stat points for 150 gold).
inline std::vector<bc::item_type> build(bc::champion_type type) {
    using I = bc::item_type;
    using C = bc::champion_type;
    if (type == C::willow) return {I::jungle_shard_of_focus, I::durability_shard_of_health, I::power_shard_of_focus};
    if (BUILDS_TOP1) {
        // #1's purchase orders, read from 60 of its ranked games.
        switch (type) {
        case C::prism:
            return {I::durability_shard_of_health, I::monster_shard_of_focus, I::jungle_shard_of_health,
                    I::bruiser_shard_of_health, I::home_shard_of_health};
        case C::vesper_vale:
            return {I::jungle_shard_of_strength, I::bruiser_shard_of_strength, I::bruiser_shard_of_health,
                    I::durability_shard_of_health};
        case C::marcella:
            return {I::bruiser_shard_of_strength, I::bruiser_shard_of_health, I::bruiser_shard_of_focus};
        case C::heart_of_ruin:
            return {I::jungle_shard_of_focus, I::bruiser_shard_of_health, I::durability_shard_of_health,
                    I::bruiser_shard_of_focus};
        case C::ryth:
            return {I::jungle_shard_of_strength, I::bruiser_shard_of_health, I::durability_shard_of_health};
        case C::vendetta:
            return {I::jungle_shard_of_strength, I::bruiser_shard_of_strength, I::bruiser_shard_of_health,
                    I::durability_shard_of_health};
        default: break;
        }
    }
    return {I::jungle_shard_of_strength, I::monster_shard_of_strength, I::durability_shard_of_health};
}

}  // namespace config
