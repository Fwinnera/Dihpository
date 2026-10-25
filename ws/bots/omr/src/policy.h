// policy.py: choose a controller from terrain and producer structure, never map names.
#pragma once
#include "common.h"
#include "policy_table.h"

namespace policy {

inline int cached = -1;

// A gem-bearing group one champion can clear alone: no monolith, and no more
// combined strength than one golem. Clusters, wolves and a lone elk qualify.
inline constexpr double SOLO_STRENGTH = 120;

// Every gem on the map sits behind a monolith or a pack that kills a lone
// farmer (00contest: two monoliths; 00stampede: one herd of six elks). Solo
// selection skips all of them, so greatsage scores nothing all game. These maps
// are played as a party, by the same controller as single-altar boss maps.
inline bool party_map() {
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
        cached = pol::P().party_off ? 0 : gm::altars().count() == 1 && monolith ? 2 : party_map() ? 3 : 0;
    }
    return cached;
}

// Maps played by the party controller.
inline bool party() { return kind() == 2 || kind() == 3; }

}  // namespace policy
