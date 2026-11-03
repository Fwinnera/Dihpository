#!/usr/bin/env python3
"""Danger response, learned on-policy (cHG-line bot): explore or apply a response policy.

    mkdr.py BOTDIR MODE [TABLE=ws/bench/danger_table.h] [POLICY=FILE]

MODE 1 (explore): in a danger state -- the retreat rule or the disengage rule would fire, or
the danger table (dzfit.py) puts death within 15 rounds above DR_P -- a champion commits for
DR_HOLD rounds to a response drawn at random: 0 the ordinary rule, 1 fall back to the nearest
healthy teammate, 2 fight the weakest enemy in reach. Each episode prints one DR line for
drfit.py, which scores the responses by what followed. MODE 2 (policy) takes the response
from dr_policy.h (written by drfit.py), indexed by a coarse state cell (health band x odds band
x enemies near). Party maps are left alone.
"""
import shutil
import sys
from pathlib import Path

ROOT = Path("/Users/faeezaullyar/Claude/battlecode")
src = Path(sys.argv[1]) / "src"
mode = int(sys.argv[2])
opts = dict(a.split("=", 1) for a in sys.argv[3:])
table = Path(opts.get("TABLE", ROOT / "ws/bench/danger_table.h"))
policy = opts.get("POLICY")
shutil.copy(table, src / "danger_table.h")
if policy:
    shutil.copy(policy, src / "dr_policy.h")
else:
    (src / "dr_policy.h").write_text("#pragma once\nnamespace dr {\ninline constexpr int policy[120] = {};\n}\n")


def patch(name, pairs):
    f = src / name
    text = f.read_text()
    for old, new in pairs:
        n = text.count(old)
        if n != 1:
            sys.exit(f"{name}: expected one match, found {n}: {old[:70]!r}")
        text = text.replace(old, new)
    f.write_text(text)


patch("config.h", [("inline constexpr bool DEBUG = false;",
                    "inline constexpr bool DEBUG = false;\n"
                    "// Danger response (dr.h; analysis/rebuild/mkdr.py): 0 off, 1 explore, 2 policy.\n"
                    f"inline constexpr int DR_MODE = {mode};\n"
                    "inline constexpr std::int64_t DR_HOLD = 5;\n"
                    "inline constexpr float DR_P = 0.35f;")])

(src / "dr.h").write_text(r'''// dr.h: danger response (analysis/rebuild/mkdr.py, drfit.py).
#pragma once
#include "combat.h"
#include "common.h"
#include "config.h"
#include "danger_table.h"
#include "dr_policy.h"
#include "nav.h"

namespace dr {

inline std::int64_t until = -1;  // last round of the current episode
inline int action = 0;           // 0 ordinary rule, 1 fall back to a teammate, 2 fight
inline std::uint64_t rng = 0;

inline std::uint64_t next() {
    rng = rng * 6364136223846793005ULL + 1442695040888963407ULL;
    return rng >> 33;
}

struct State {
    int idx, coarse;
    float p;
};

// The same cells dzlog logged: health band, square-law odds band, enemies within 6,
// allies within 5, far from home.
inline State state(const bc::champion& me, const std::vector<bc::champion>& enemies,
                   const std::vector<bc::champion>& allies) {
    double eh = 0, es = 0, ah = 0, as_ = 0;
    int ne = 0, na = 0;
    for (const auto& e : enemies)
        if (distance(e.position(), me.position()) <= 6) {
            eh += D(e.health());
            es += D(e.strength());
            ++ne;
        }
    for (const auto& a : allies)
        if (!same(a, me) && a.is_alive() && a.is_visible() && distance(a.position(), me.position()) <= 5) {
            ah += D(a.health());
            as_ += D(a.strength());
            ++na;
        }
    std::int64_t home = 99;
    for (const auto p : gm::spawn_region(bc::team::ally).positions()) home = std::min(home, distance(p, me.position()));
    const double frac = D(me.health()) / std::max(1.0, D(me.max_health()));
    const int hb = frac < 0.2 ? 0 : frac < 0.35 ? 1 : frac < 0.5 ? 2 : frac < 0.75 ? 3 : 4;
    int ob = 0;
    if (ne > 0) {
        const double ours = (D(me.health()) + ah) * (std::max(1.0, D(me.strength())) + as_);
        const double lr = std::log(std::max(1.0, ours) / std::max(1.0, eh * std::max(1.0, es)));
        ob = lr < -1.0 ? 1 : lr < -0.3 ? 2 : lr < 0.3 ? 3 : lr < 1.0 ? 4 : 5;
    }
    const int nb = std::min(ne, 3);
    const int idx = ((((hb * 6 + ob) * 4 + nb) * 3 + std::min(na, 2)) * 2 + (home <= 8 ? 0 : 1));
    return {idx, (hb * 6 + ob) * 4 + nb, danger::table[idx]};
}

// Fall back toward the nearest visible teammate above half health, 2-10 steps away.
inline bool fallback(const bc::champion& me, const std::vector<bc::champion>& enemies, const std::vector<bc::camp>& camps,
                     const std::vector<bc::champion>& allies) {
    const bc::champion* best = nullptr;
    std::int64_t gap = 11;
    for (const auto& a : allies) {
        if (same(a, me) || !a.is_alive() || !a.is_visible() || D(a.health()) < D(a.max_health()) * 0.5) continue;
        const auto d = distance(a.position(), me.position());
        if (d >= 2 && d < gap) {
            gap = d;
            best = &a;
        }
    }
    if (!best) return false;
    turn::check();
    const auto threat = nav::threat_mask(enemies, camps);
    const auto goal = nav::around(best->position(), 1);
    return nav::move_to(goal, &threat) || nav::move_to(goal);
}

// Stand and fight the weakest enemy in reach, or one within 3 steps.
inline bool fight(const bc::champion& me, const std::vector<bc::champion>& enemies) {
    const auto mask = me.attack_tiles();
    std::vector<bc::champion> reach, close;
    for (const auto& e : enemies) {
        if (!e.is_visible() || !e.is_alive()) continue;
        if (mask.is_set(e.position())) reach.push_back(e);
        else if (distance(e.position(), me.position()) <= 3) close.push_back(e);
    }
    auto& pool = reach.empty() ? close : reach;
    if (pool.empty()) return false;
    const auto& target = *first_min(pool.begin(), pool.end(), [](const bc::champion& e) { return D(e.health()); });
    bool acted = combat::fight(target, enemies);
    if (combat::live(target) && target.health() > 0 && !mask.is_set(target.position()) &&
        nav::move_to(nav::around(target.position(), me.attack_range())))
        acted = combat::fight(target, enemies) || true;
    return acted;
}

}  // namespace dr
''')

patch("bot.h", [
    ("#include \"combat.h\"\n", "#include \"combat.h\"\n#include \"dr.h\"\n"),
    ("        if (!at_spawn && D(me.health()) < retreat_at) {\n            status(\"retreat\");\n",
     "        if (config::DR_MODE && !at_spawn && !enemies.empty() && !policy::party()) {\n"
     "            const auto now = static_cast<std::int64_t>(bc::round_number());\n"
     "            if (!dr::rng) dr::rng = 0x9E3779B97F4A7C15ULL * (static_cast<std::uint64_t>(me.champion_name()) + 1) +\n"
     "                                    static_cast<std::uint64_t>(me.position().x * 131 + me.position().y * 7919 + 1);\n"
     "            const auto [ratio, threats] = combat::local_power(enemies, team->allies, config::DISENGAGE_RADIUS);\n"
     "            const bool rule = D(me.health()) < retreat_at;\n"
     "            const bool dis = threats > 0 && ratio < config::DISENGAGE_RATIO + (disengaging ? config::DISENGAGE_HYSTERESIS : 0);\n"
     "            const auto st = dr::state(me, enemies, team->allies);\n"
     "            if ((rule || dis || st.p > config::DR_P) && now > dr::until) {\n"
     "                dr::action = config::DR_MODE == 1 ? static_cast<int>(dr::next() % 3) : dr::policy[st.coarse];\n"
     "                dr::until = now + config::DR_HOLD - 1;\n"
     "                if (config::DR_MODE == 1)\n"
     "                    std::cout << \"DR \" << now << ' ' << static_cast<int>(me.champion_name()) << ' ' << dr::action << ' ' << st.idx << ' '\n"
     "                              << st.coarse << ' ' << (rule ? 1 : 0) << (dis ? 1 : 0) << ' ' << st.p << ' ' << me.gem_count() << '\\n';\n"
     "            }\n"
     "            if (now <= dr::until) {\n"
     "                if (dr::action == 1 && dr::fallback(me, enemies, camps, team->allies)) {\n"
     "                    status(\"dr-fallback\");\n"
     "                    return;\n"
     "                }\n"
     "                if (dr::action == 2 && dr::fight(me, enemies)) {\n"
     "                    status(\"dr-fight\");\n"
     "                    return;\n"
     "                }\n"
     "            }\n"
     "        }\n"
     "        if (!at_spawn && D(me.health()) < retreat_at) {\n            status(\"retreat\");\n"),
])
print("patched", src, "mode", mode)
