// Camp table probe: one CG line per camp group (gems, gold, respawn, total health and strength, monolith,
// first camp tile), a few groups per turn to stay inside the fuel budget.
#include <cambc.h>
#include <iostream>
namespace bc = cambc;
namespace gm = cambc::map;
int main() {
    std::size_t next = 0;
    bool done = false;
    while (true) {
        if (bc::is_draft()) {
            const auto chosen = bc::draft::current_draft(bc::team::ally);
            for (auto pick : {bc::champion_draft::varg, bc::champion_draft::ryth, bc::champion_draft::willow,
                              bc::champion_draft::vendetta, bc::champion_draft::marcella, bc::champion_draft::tavi})
                if (std::find(chosen.begin(), chosen.end(), pick) == chosen.end()) { bc::draft::pick(pick); break; }
        } else if (!done && bc::self().champion_name() == bc::champion_type::varg) {
            const auto groups = gm::camp_groups();
            std::size_t stop = std::min(groups.size(), next + 6);
            for (; next < stop; ++next) {
                const auto& g = groups[next];
                double hp = 0, str = 0; bool mono = false; int x = -1, y = -1;
                for (const auto& c : g.camps()) {
                    const auto s = c.base_stats();
                    hp += s.base_health; str += s.base_strength;
                    if (c.is_monolith()) mono = true;
                    if (x < 0) { x = c.spawn_position().x; y = c.spawn_position().y; }
                }
                std::cout << "CG " << next << " " << g.gem_value() << " " << g.gold_value() << " " << g.max_respawn_timer() << " "
                          << hp << " " << str << " " << mono << " " << x << " " << y << " " << g.camps().size() << "\n";
            }
            std::cout << std::flush;
            if (next >= groups.size()) done = true;
        }
        bc::end_turn();
    }
}
