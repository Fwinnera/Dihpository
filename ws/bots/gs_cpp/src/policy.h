// policy.py: choose a controller from terrain and producer structure, never map names.
#pragma once
#include "common.h"

namespace policy {

inline int cached = -1;

inline int kind() {
    if (cached < 0) {
        bool monolith = false;
        for (const auto& group : gm::camp_groups())
            for (const auto& camp : group.camps())
                if (camp.is_monolith()) monolith = true;
        cached = gm::altars().count() == 1 && monolith ? 2 : 0;
    }
    return cached;
}

}  // namespace policy
