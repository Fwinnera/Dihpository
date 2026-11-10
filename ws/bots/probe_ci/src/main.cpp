// Probe: Cassi & Issac and the meta picks: stats, abilities, targeting flags, ally list order.
#include <cambc.h>
#include <iostream>
#include <variant>
#include <algorithm>
#include <vector>
namespace bc = cambc;
int main() {
    bool done = false;
    while (true) {
        if (bc::is_draft()) {
            using D = bc::champion_draft;
            const auto chosen = bc::draft::current_draft(bc::team::ally);
            std::vector<D> order{D::prism, D::stellar, D::ren, D::willow, D::ryth, D::varg, D::tavi};
            for (auto pick : order)
                if (std::find(chosen.begin(), chosen.end(), pick) == chosen.end()) { bc::draft::pick(pick); break; }
        } else if (!done) {
            done = true;
            auto& me = bc::self();
            const auto s = me.base_stats();
            const auto allies = bc::champions(bc::team::ally);
            int slot = -1;
            for (std::size_t i = 0; i < allies.size(); ++i)
                if (static_cast<std::uint32_t>(static_cast<bc::handle_champion_t>(allies[i])) ==
                    static_cast<std::uint32_t>(static_cast<bc::handle_champion_t>(me))) slot = (int)i;
            std::cout << "CH " << bc::to_string(me.champion_name()) << " slot " << slot << "/" << allies.size()
                      << " pos " << me.position().x << "," << me.position().y
                      << " vision " << s.vision_radius << " speed " << s.base_move_speed
                      << " range " << s.base_attack_range << " hp " << s.base_health << "+" << s.health_growth << " str " << s.base_strength
                      << "+" << s.strength_growth << " focus " << s.base_focus << "+" << s.focus_growth << " campx " << s.camp_damage_multiplier
                      << " passive " << static_cast<int>(me.passive()) << " shmem " << bc::shared_memory.size();
            for (const auto& a : me.abilities()) {
                if (!a.info()) { std::cout << " | none"; continue; }
                std::cout << " | reset " << a.is_attack_reset() << " dmg " << a.is_damage() << " aoe " << a.is_aoe_damage() << " cc " << a.is_cc()
                          << " dash " << a.is_dash() << " shield " << a.is_shield() << " heal " << a.is_heal()
                          << " tEnemy " << a.can_target_enemies() << " tCamp " << a.can_target_camps() << " tGround " << a.can_target_ground()
                          << " amount " << a.damage_amount();
                std::visit([&](const auto& v) {
                    std::cout << " kind " << static_cast<int>(std::decay_t<decltype(v)>::kind) << " cd " << v.max_cooldown << " excl " << v.exclusive_with_movement;
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
