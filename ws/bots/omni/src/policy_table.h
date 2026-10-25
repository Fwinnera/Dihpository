// Which measured arm each map-side plays (pol.h). Unknown maps play arm 0.
#pragma once
#include "pol.h"

namespace pol {

// Screening builds force one arm everywhere; the submitted bot uses the table.
inline constexpr int FORCE = -1;
// Decision-neutral re-roll for replicates: extra fuel spent at the start of a turn.
inline constexpr int REROLL = 0;

struct Row {
    int width, height, groups, gems, arm_a, arm_b;
};

inline const std::vector<Row>& rows() {
    static const std::vector<Row> table = {
        {100, 100, 12, 270, 0, 0},  // 00ambush
        {41, 41, 20, 280, 0, 0},  // 00collision
        {50, 50, 14, 400, 0, 0},  // 00contest
        {71, 71, 30, 396, 0, 0},  // 00corners
        {41, 30, 8, 230, 0, 0},  // 00eight
        {30, 30, 10, 220, 0, 0},  // 00elkring
        {80, 80, 24, 362, 0, 0},  // 00expanse
        {30, 30, 6, 68, 0, 0},  // 00fragment
        {50, 40, 18, 364, 0, 0},  // 00gem-fields
        {30, 30, 19, 200, 0, 0},  // 00gemfight
        {50, 40, 17, 1404, 0, 0},  // 00great-wall
        {40, 40, 14, 200, 0, 0},  // 00interlock
        {90, 30, 42, 294, 0, 0},  // 00lanes
        {35, 31, 34, 592, 0, 0},  // 00lost-world
        {50, 50, 20, 670, 0, 0},  // 00monolith
        {31, 31, 8, 148, 0, 0},  // 00packs
        {50, 65, 23, 184, 0, 0},  // 00pilgrimage
        {45, 45, 21, 763, 0, 0},  // 00quadrants
        {30, 30, 14, 334, 0, 0},  // 00reverse-spiral
        {40, 40, 51, 1158, 0, 0},  // 00road-of-riches
        {50, 50, 9, 584, 0, 0},  // 00rows
        {30, 80, 18, 258, 0, 0},  // 00rushbait-v2
        {45, 35, 32, 850, 0, 0},  // 00split
        {60, 50, 13, 160, 0, 0},  // 00stampede
        {45, 30, 22, 638, 0, 0},  // 00swirl
        {100, 100, 24, 832, 0, 0},  // 01big-world
        {50, 41, 31, 1180, 0, 0},  // 01boss-battle
        {40, 40, 22, 746, 0, 0},  // 01broken-curve
        {61, 61, 11, 177, 0, 0},  // 01concentrated-wealth
        {51, 40, 12, 752, 0, 0},  // 01corridors
        {50, 50, 29, 72, 0, 0},  // 01elk-arena
        {61, 71, 28, 844, 0, 0},  // 01fracture
        {31, 31, 15, 266, 0, 0},  // 01gold-rush
        {31, 31, 12, 88, 0, 0},  // 01hooks
        {60, 60, 46, 608, 0, 0},  // 01islands
        {40, 40, 21, 990, 0, 0},  // 01shortcut
        {50, 50, 16, 334, 0, 0},  // 01starfish
        {80, 80, 14, 532, 0, 0},  // 01starvation
        {50, 40, 28, 1096, 0, 0},  // 01the-farm
        {40, 30, 28, 472, 0, 0},  // 01yellow-brick-road
    };
    return table;
}

inline int chosen = -1;

inline int choose() {
    int groups = 0, gems = 0;
    for (const auto& group : gm::camp_groups()) {
        ++groups;
        gems += static_cast<int>(group.gem_value());
    }
    const bool side_b = bc::detail::sdk_my_team() == 1;
    for (const auto& row : rows())
        if (row.width == gm::width() && row.height == gm::height() && row.groups == groups && row.gems == gems)
            return FORCE >= 0 ? FORCE : side_b ? row.arm_b : row.arm_a;
    return FORCE >= 0 ? FORCE : 0;
}

inline const Policy& P() {
    if (chosen < 0) chosen = choose();
    return arms()[static_cast<std::size_t>(chosen)];
}

}  // namespace pol
