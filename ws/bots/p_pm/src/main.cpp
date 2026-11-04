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
                prof::label = "none";
                prof::group = -1;
                bot->play_turn();
                nav::finish_turn();
                {
                    auto& me = bc::self();
                    // Diagnostic extras: visible enemies within 5 and 8, allies within 5, nearest enemy.
                    int ne5 = -1, ne8 = -1, na5 = -1, dmin = -1;
                    if (me.is_alive() && bc::fuel_remaining() > 20000) {
                        try {
                            ne5 = ne8 = na5 = 0;
                            dmin = 99;
                            const auto p = me.position();
                            for (const auto& e : bc::vision::champions(bc::team::enemy)) {
                                if (!e.is_alive()) continue;
                                const int d = static_cast<int>(distance(p, e.position()));
                                if (d <= 5) ++ne5;
                                if (d <= 8) ++ne8;
                                if (d < dmin) dmin = d;
                            }
                            for (const auto& a : bc::vision::champions(bc::team::ally))
                                if (!same(a, me) && a.is_alive() && distance(p, a.position()) <= 5) ++na5;
                        } catch (...) {
                        }
                    }
                    std::cout << "PF " << bc::round_number() << ' ' << static_cast<int>(me.champion_name()) << ' '
                              << prof::label << ' ' << (me.is_alive() ? me.position().x : -1) << ' '
                              << (me.is_alive() ? me.position().y : -1) << ' '
                              << me.health() << ' ' << me.max_health() << ' ' << me.gem_count() << ' '
                              << me.gold_count() << ' ' << prof::group << ' ' << ne5 << ' ' << ne8 << ' ' << na5
                              << ' ' << dmin << '\n';
                }
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
