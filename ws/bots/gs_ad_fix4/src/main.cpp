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
    std::cout << "BOTTAG gs_ad_fix4" << std::endl;
    std::unique_ptr<Bot> bot;
    while (true) {
        try {
            if (bc::is_draft()) {
                draft::play();
            } else {
                if (!bot) bot = create_bot();
                turn::begin();
                bot->play_turn();
                nav::finish_turn();
            }
        } catch (const turn::Replan&) {
            // Fuel exhaustion resumes inside the old call stack. Rebuild the
            // observation instead of executing yesterday's movement/attack plan.
            if (static_cast<std::int64_t>(bc::round_number()) != turn::started) continue;
            bc::end_turn();
            continue;
        } catch (const std::exception& error) {
            // A turn that ran out of fuel resumes next round inside the old call stack,
            // where a unit it saw may now be out of sight ("Unit is not in vision").
            // That is the Replan case above, not a bug: play a fresh turn this round.
            if (turn::started >= 0 && static_cast<std::int64_t>(bc::round_number()) != turn::started) continue;
            // An uncaught exception would resign the whole team. Log and yield.
            std::cout << "ERROR " << error.what() << std::endl;
        } catch (...) {
            std::cout << "ERROR unknown exception" << std::endl;
        }
        bc::end_turn();
    }
}
