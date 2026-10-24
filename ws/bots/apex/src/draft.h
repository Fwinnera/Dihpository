// draft.py: apex drafts as the #1 team does, Prism first, by team size.
#pragma once
#include "common.h"
#include "config.h"
#include "draft_table.h"
#include "policy.h"

namespace draft {

// #1's own order on a map it has played, found by the map's fingerprint.
inline std::optional<std::vector<bc::champion_draft>> known_map() {
    const int width = gm::width(), height = gm::height();
    int groups = 0, gems = 0;
    for (const auto& group : gm::camp_groups()) {
        ++groups;
        gems += static_cast<int>(group.gem_value());
    }
    if (config::DEBUG) std::cout << "DRAFTMAP " << width << " " << height << " " << groups << " " << gems << std::endl;
    for (const auto& row : top1_table())
        if (row.width == width && row.height == height && row.groups == groups && row.gems == gems) return row.order;
    return std::nullopt;
}

inline std::vector<bc::champion_draft> order() {
    using D = bc::champion_draft;
    if (config::DRAFT_TOP1 && config::DRAFT_PER_MAP) {
        if (auto known = known_map()) {
            // The rest of the default order backs up a pick that is unavailable.
            for (const auto pick : {D::prism, D::vesper_vale, D::marcella, D::ryth, D::heart_of_ruin, D::vendetta,
                                    D::tavi, D::cassi_and_issac, D::ren, D::stellar, D::varg, D::willow})
                if (std::find(known->begin(), known->end(), pick) == known->end()) known->push_back(pick);
            return *known;
        }
    }
    if (config::DRAFT_TOP1) {
        // #1 in 60 ranked games: Prism > Vesper Vale > Heart of Ruin with three
        // champions (8 of 10), Prism > Vesper Vale > Marcella > Ryth with four, and
        // Prism > Vesper Vale > Marcella > Ryth > Heart of Ruin with five (17 of 40,
        // the most common order). Vendetta is its usual substitute.
        if (bc::draft::team_size() <= 3)
            return {D::prism, D::vesper_vale, D::heart_of_ruin, D::marcella, D::ryth, D::vendetta,
                    D::tavi, D::cassi_and_issac, D::ren, D::stellar, D::varg, D::willow};
        return {D::prism, D::vesper_vale, D::marcella, D::ryth, D::heart_of_ruin, D::vendetta,
                D::tavi, D::cassi_and_issac, D::ren, D::stellar, D::varg, D::willow};
    }
    if (policy::party())
        return {D::varg, D::willow, D::ryth, D::vendetta, D::marcella, D::cassi_and_issac,
                D::tavi, D::stellar, D::heart_of_ruin, D::ren, D::prism, D::vesper_vale};
    return {D::marcella, D::vendetta, D::willow, D::varg, D::ryth, D::tavi,
            D::cassi_and_issac, D::vesper_vale, D::ren, D::stellar, D::prism, D::heart_of_ruin};
}

inline void play() {
    const auto chosen = bc::draft::current_draft(bc::team::ally);
    const int variant = policy::kind();
    const std::array<std::byte, 6> memory{std::byte{'b'}, std::byte{'o'}, std::byte{'m'}, std::byte{'b'}, std::byte{'a'},
                                          static_cast<std::byte>(variant)};
    bc::draft_memory = std::span<const std::byte>{memory};
    for (const auto pick : order()) {
        if (std::find(chosen.begin(), chosen.end(), pick) == chosen.end()) {
            bc::draft::pick(pick);
            return;
        }
    }
}

}  // namespace draft
