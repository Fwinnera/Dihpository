// Which controller a map wants, decided from terrain rather than from its name.
//
// Ported from the Python policy.py. Exactly one altar plus a monolith somewhere
// means the map's only deposit point is gated: measured on 01boss-battle, the
// single altar at (25,20) is 20 tiles from spawn across bare terrain and
// *unreachable* once the two monoliths' tiles are treated as blocked. No gem can
// be banked there until a monolith dies, which no single champion can do alone --
// 20,000 health, 200 strength, attack range 5. So that map needs the whole team on
// one objective, which is what boss mode is.
//
// One map of the current 39 pool qualifies. Fourteen others hold a monolith but
// have two or more altars, so an ordinary champion can always bank somewhere and
// the normal controller is right for them.
#pragma once
#include <cambc.h>

namespace policy {

inline bool boss_map() {
    static int cached = -1;
    if (cached >= 0) return cached != 0;
    cached = 0;
    if (cambc::map::altars().count() != 1) return false;
    for (const auto& g : cambc::map::camp_groups())
        for (const auto& c : g.camps())
            if (c.is_monolith()) { cached = 1; return true; }
    return false;
}

}  // namespace policy
