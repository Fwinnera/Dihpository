// apex: the #1 team's decision layer on gs_cpp93_party's plumbing (docs/APEX-SPEC.md).
// gs_cpp: greatsage ported to C++. main.py: dispatch draft and gameplay; a failed turn is logged and still yields.
#include "bot.h"
#include "draft.h"
#include "policy.h"

#ifndef BOT_TAG
#define BOT_TAG "apex"
#endif

namespace {

std::unique_ptr<Bot> create_bot() {
    if (policy::party()) return std::make_unique<BossBot>();
    if (bc::self().champion_name() == bc::champion_type::willow) return std::make_unique<EscortBot>();
    return std::make_unique<Bot>();
}

}  // namespace

int main() {
    std::cout << "BOTTAG " << BOT_TAG << std::endl;
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
            // An uncaught exception would resign the whole team. Log and yield.
            std::cout << "ERROR " << error.what() << std::endl;
        } catch (...) {
            std::cout << "ERROR unknown exception" << std::endl;
        }
        bc::end_turn();
    }
}
