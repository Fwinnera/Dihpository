// policy.py: choose a controller from terrain and producer structure, never map names.
#pragma once
#include "common.h"

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
        cached = gm::altars().count() == 1 && monolith ? 2 : party_map() ? 3 : 0;
    }
    return cached;
}

// mkparty2.py + mg6 (2026-11-10): PARTY_MONO 0.75 so 00anvil (mono share ~0.775) returns to party;
// a single-altar monolith map (kind 2) is played as a party only when its altar is gated by
// monoliths or monoliths hold most of its gems.
inline int party2_cache = -1;
inline bool kind2_party() {
    if (party2_cache < 0) {
        std::vector<bc::vec2> mono;
        double total = 0, mono_gems = 0;
        for (const auto& g : gm::camp_groups()) {
            bool m = false;
            for (const auto& c : g.camps())
                if (c.is_monolith()) {
                    m = true;
                    mono.push_back(c.spawn_position());
                }
            total += g.gem_value();
            if (m) mono_gems += g.gem_value();
        }
        bool gated = false;
        if (gm::altars().count() == 1) {
            const auto altar = gm::altars().positions()[0];
            bc::bitboard open;
            open.draw_chebyshev(altar, static_cast<float>(bc::constants::submit_gems_range));
            open = open & ~(gm::walls() | gm::holes() | gm::altars() | gm::spawn_region(bc::team::enemy));
            gated = !open.is_empty();
            for (const auto p : open.positions())
                if (std::find(mono.begin(), mono.end(), p) == mono.end()) gated = false;
        }
        party2_cache = (gated || (total > 0 && mono_gems / total >= 0.75)) ? 1 : 0;
    }
    return party2_cache == 1;
}

// Maps played by the party controller.
inline bool party() { return kind() == 3 || (kind() == 2 && kind2_party()); }

}  // namespace policy
