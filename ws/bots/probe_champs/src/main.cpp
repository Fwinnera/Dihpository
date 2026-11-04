// Champion facts probe: each champion prints its base stats, growth and both abilities once.
// Draft order is chosen by the map's width parity so two runs cover every champion.
#include <cambc.h>
#include <iostream>
#include <variant>
namespace bc = cambc;
int main() {
    bool done = false;
    while (true) {
        if (bc::is_draft()) {
            using D = bc::champion_draft;
            const auto chosen = bc::draft::current_draft(bc::team::ally);
            const bool first = bc::map::width() % 2 == 0;
            std::vector<D> order = first ? std::vector<D>{D::prism, D::heart_of_ruin, D::ryth, D::vesper_vale, D::vendetta}
                                         : std::vector<D>{D::marcella, D::willow, D::ren, D::varg, D::tavi, D::heart_of_ruin};
            for (auto pick : order)
                if (std::find(chosen.begin(), chosen.end(), pick) == chosen.end()) { bc::draft::pick(pick); break; }
        } else if (!done) {
            done = true;
            auto& me = bc::self();
            const auto s = me.base_stats();
            std::cout << "CH " << static_cast<int>(me.champion_name()) << " vision " << s.vision_radius << " speed " << s.base_move_speed
                      << " range " << s.base_attack_range << " hp " << s.base_health << "+" << s.health_growth << " str " << s.base_strength
                      << "+" << s.strength_growth << " focus " << s.base_focus << "+" << s.focus_growth << " campx " << s.camp_damage_multiplier
                      << " now hp " << me.max_health() << " str " << me.strength() << " focus " << me.focus() << " passive " << static_cast<int>(me.passive());
            for (const auto& a : me.abilities()) {
                if (!a.info()) { std::cout << " | none"; continue; }
                std::visit([&](const auto& v) {
                    std::cout << " | kind " << static_cast<int>(std::decay_t<decltype(v)>::kind) << " cd " << v.max_cooldown << " excl " << v.exclusive_with_movement;
                    if constexpr (requires { v.range; }) std::cout << " range " << v.range;
                    if constexpr (requires { v.modifier; }) std::cout << " mod " << v.modifier;
                    if constexpr (requires { v.radius; }) std::cout << " radius " << v.radius;
                    if constexpr (requires { v.duration; }) std::cout << " dur " << v.duration;
                    if constexpr (requires { v.enhanced_attack; }) std::cout << " enhanced " << v.enhanced_attack;
                }, *a.info());
            }
            std::cout << std::endl;
        }
        bc::end_turn();
    }
}
