// Map facts probe: prints one MI line (spawns, altars, size, symmetry) on the first gameplay turn.
#include <cambc.h>
#include <iostream>
namespace bc = cambc;
namespace gm = cambc::map;
static void dump(const char* key, const bc::bitboard& b) {
    std::cout << " \"" << key << "\":[";
    bool first = true;
    for (const auto p : b.positions()) {
        std::cout << (first ? "" : ",") << "[" << p.x << "," << p.y << "]";
        first = false;
    }
    std::cout << "]";
}
int main() {
    bool done = false;
    while (true) {
        if (!bc::is_draft() && !done) {
            done = true;
            std::cout << "MI {\"w\":" << gm::width() << ",\"h\":" << gm::height()
                      << ",\"sym\":" << static_cast<int>(gm::symmetry()) << ",";
            dump("spawn_ally", gm::spawn_region(bc::team::ally));
            std::cout << ",";
            dump("spawn_enemy", gm::spawn_region(bc::team::enemy));
            std::cout << ",";
            dump("altars", gm::altars());
            std::cout << "}" << std::endl;
        } else if (bc::is_draft()) {
            const auto chosen = bc::draft::current_draft(bc::team::ally);
            for (auto pick : {bc::champion_draft::varg, bc::champion_draft::ryth, bc::champion_draft::willow,
                              bc::champion_draft::vendetta, bc::champion_draft::marcella, bc::champion_draft::tavi}) {
                if (std::find(chosen.begin(), chosen.end(), pick) == chosen.end()) {
                    bc::draft::pick(pick);
                    break;
                }
            }
        }
        bc::end_turn();
    }
}
