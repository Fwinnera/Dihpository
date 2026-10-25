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
        {100, 100, 12, 270, 29, 41},  // 00ambush
        {41, 41, 20, 280, 29, 41},  // 00collision
        {50, 50, 14, 400, 29, 21},  // 00contest
        {71, 71, 30, 396, 17, 26},  // 00corners
        {41, 30, 8, 230, 38, 29},  // 00eight
        {30, 30, 10, 220, 38, 26},  // 00elkring
        {80, 80, 24, 362, 23, 24},  // 00expanse
        {30, 30, 6, 68, 29, 31},  // 00fragment
        {50, 40, 18, 364, 30, 29},  // 00gem-fields
        {30, 30, 19, 200, 4, 41},  // 00gemfight
        {50, 40, 17, 1404, 41, 26},  // 00great-wall
        {40, 40, 14, 200, 30, 4},  // 00interlock
        {90, 30, 42, 294, 11, 12},  // 00lanes
        {35, 31, 34, 592, 29, 15},  // 00lost-world
        {50, 50, 20, 670, 38, 41},  // 00monolith
        {31, 31, 8, 148, 12, 12},  // 00packs
        {50, 65, 23, 184, 21, 23},  // 00pilgrimage
        {45, 45, 21, 763, 29, 29},  // 00quadrants
        {30, 30, 14, 334, 12, 12},  // 00reverse-spiral
        {40, 40, 51, 1158, 21, 8},  // 00road-of-riches
        {50, 50, 9, 584, 21, 6},  // 00rows
        {30, 80, 18, 258, 29, 1},  // 00rushbait-v2
        {45, 35, 32, 850, 21, 38},  // 00split
        {60, 50, 13, 160, 9, 34},  // 00stampede
        {45, 30, 22, 638, 29, 21},  // 00swirl
        {100, 100, 24, 832, 21, 29},  // 01big-world
        {50, 41, 31, 1180, 12, 4},  // 01boss-battle
        {40, 40, 22, 746, 27, 41},  // 01broken-curve
        {61, 61, 11, 177, 29, 12},  // 01concentrated-wealth
        {51, 40, 12, 752, 4, 31},  // 01corridors
        {50, 50, 29, 72, 22, 29},  // 01elk-arena
        {61, 71, 28, 844, 29, 24},  // 01fracture
        {31, 31, 15, 266, 29, 18},  // 01gold-rush
        {31, 31, 12, 88, 29, 29},  // 01hooks
        {60, 60, 46, 608, 29, 29},  // 01islands
        {40, 40, 21, 990, 31, 32},  // 01shortcut
        {50, 50, 16, 334, 27, 26},  // 01starfish
        {80, 80, 14, 532, 4, 14},  // 01starvation
        {50, 40, 28, 1096, 26, 29},  // 01the-farm
        {40, 30, 28, 472, 21, 9},  // 01yellow-brick-road
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
