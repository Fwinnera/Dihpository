// policy.py: choose a controller from terrain and producer structure, never map names.
#pragma once
#include "common.h"

namespace policy {

inline int cached = -1;

// A gem-bearing group one champion can clear alone: no monolith, and no more
// combined strength than one golem. Clusters, wolves and a lone elk qualify.
inline constexpr double SOLO_STRENGTH = 120;

// Every gem on the map sits behind a monolith or a pack that kills a lone
// farmer (00contest: two monoliths; 00stampede: one herd of six elks), or in at
// most two groups that both teams must fight over (01elk_arena: one central
// group, 28 gold-only ones). Solo selection skips the first kind and trickles
// into the second one champion at a time, dying about 35 times a game on the
// ladder. These maps are played as a party, by the boss-map controller.
inline constexpr int PARTY_GEM_GROUPS = 2;

inline bool party_map() {
    int gem_groups = 0;
    for (const auto& group : gm::camp_groups())
        if (group.gem_value()) ++gem_groups;
    if (gem_groups <= PARTY_GEM_GROUPS) return true;
    for (const auto& group : gm::camp_groups()) {
        if (!group.gem_value()) continue;
        bool monolith = false;
        double strength = 0;
        for (const auto& camp : group.camps()) {
            if (camp.is_monolith()) monolith = true;
            strength += camp.base_stats().base_strength;
        }
        if (!monolith && strength <= SOLO_STRENGTH) return false;
    }
    return true;
}

inline int kind() {
    if (cached < 0) {
        bool monolith = false;
        for (const auto& group : gm::camp_groups())
            for (const auto& camp : group.camps())
                if (camp.is_monolith()) monolith = true;
        cached = gm::altars().count() == 1 && monolith ? 2 : party_map() ? 3 : 0;
    }
    return cached;
}

// Maps played by the party controller.
inline bool party() { return kind() == 2 || kind() == 3; }

}  // namespace policy
