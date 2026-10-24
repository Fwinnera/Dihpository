// draft.py and roster.py: one legal pick per invocation, for any map's roster size.
#pragma once
#include "common.h"
#include "policy.h"

namespace draft {

inline void play() {
    using D = bc::champion_draft;
    const auto chosen = bc::draft::current_draft(bc::team::ally);
    // The runner resumes this instance for later picks. Gameplay instances are fresh.
    const int variant = policy::kind();
    std::vector<D> order;
    if (policy::party())
        order = {D::varg, D::willow, D::ryth, D::vendetta, D::marcella, D::cassi_and_issac,
                 D::tavi, D::stellar, D::heart_of_ruin, D::ren, D::prism, D::vesper_vale};
    else
        order = {D::varg, D::vendetta, D::vesper_vale, D::ryth, D::marcella, D::willow, D::tavi, D::cassi_and_issac, D::ren, D::stellar, D::prism, D::heart_of_ruin};
    const std::array<std::byte, 6> memory{std::byte{'b'}, std::byte{'o'}, std::byte{'m'}, std::byte{'b'}, std::byte{'a'},
                                          static_cast<std::byte>(variant)};
    bc::draft_memory = std::span<const std::byte>{memory};
    for (const auto pick : order) {
        if (std::find(chosen.begin(), chosen.end(), pick) == chosen.end()) {
            bc::draft::pick(pick);
            return;
        }
    }
}

}  // namespace draft
