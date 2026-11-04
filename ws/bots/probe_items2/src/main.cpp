// Item facts probe: prints every item's cost, combination, stats and passive once.
#include <cambc.h>
#include <iostream>
namespace bc = cambc;
int main() {
    bool done = false;
    std::uint32_t next = 0;
    while (true) {
        if (bc::is_draft()) {
            const auto chosen = bc::draft::current_draft(bc::team::ally);
            for (auto pick : {bc::champion_draft::varg, bc::champion_draft::ryth, bc::champion_draft::willow})
                if (std::find(chosen.begin(), chosen.end(), pick) == chosen.end()) { bc::draft::pick(pick); break; }
        } else if (!done) {
            if (bc::self().champion_name() != bc::champion_type::varg) done = true;
            else {
                const std::uint32_t stop = next + 8;
                for (std::uint32_t i = next; i < stop; ++i, ++next) {
                    try {
                        const auto it = bc::item_type{static_cast<bc::item_type::enum_type>(i)};
                        const auto f = it.info();
                        std::cout << "IT " << i << " " << bc::to_string(it) << " cost " << f.cost << " combine " << f.combine_count
                                  << " result " << (f.result ? bc::to_string(*f.result) : std::string("-")) << " hp " << f.health_points
                                  << " str " << f.strength_points << " focus " << f.focus_points << " passive "
                                  << (f.passive ? static_cast<int>(*f.passive) : 0) << " mag " << f.passive_magnitude << " buy " << f.purchasable << "\n";
                    } catch (...) {
                        done = true;
                        break;
                    }
                }
                std::cout << std::flush;
            }
        }
        bc::end_turn();
    }
}
