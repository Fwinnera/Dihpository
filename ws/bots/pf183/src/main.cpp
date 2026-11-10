// gs_ad: the Downloads/src controller (v93 plus party play) ported to C++,
// with the measured-loss edits left out. A failed turn is logged and still yields.
#include "bot.h"
#include "draft.h"
#include "policy.h"

namespace {

std::unique_ptr<Bot> create_bot() {
    if (policy::party()) return std::make_unique<BossBot>();
    if (bc::self().champion_name() == bc::champion_type::willow) return std::make_unique<EscortBot>();
    return std::make_unique<Bot>();
}

}  // namespace

int main() {
    std::unique_ptr<Bot> bot;
    while (true) {
        try {
            if (bc::is_draft()) {
                draft::play();
            } else {
                if (!bot) bot = create_bot();
                turn::begin();
                bot->last_state = "cut";
                bot->play_turn();
                nav::finish_turn();
                {
                    auto& me = bc::self();
                    std::cout << "PF " << bc::round_number() << " " << static_cast<int>(me.champion_name()) << " " << bot->last_state << " "
                              << me.position().x << " " << me.position().y << " " << static_cast<int>(me.health()) << " "
                              << static_cast<int>(me.max_health()) << " " << me.gem_count() << " " << me.gold_count() << std::endl;
                }
            }
        } catch (const turn::Replan&) {
            // Fuel exhaustion resumes inside the old call stack. Rebuild the
            // observation instead of executing yesterday's movement/attack plan.
            if (static_cast<std::int64_t>(bc::round_number()) != turn::started) continue;
            std::cout << "PF " << bc::round_number() << " " << static_cast<int>(bc::self().champion_name()) << " replan 0 0 0 0 0 0" << std::endl;
            bc::end_turn();
            continue;
        } catch (const std::exception& error) {
            // An uncaught exception would resign the whole team. Log and yield.
            std::cout << "ERROR " << error.what() << std::endl;
        } catch (...) {
            std::cout << "ERROR unknown exception" << std::endl;
        }
        bc::end_turn();
    }
}
