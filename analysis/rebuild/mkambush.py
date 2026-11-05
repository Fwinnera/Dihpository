#!/usr/bin/env python3
"""Hidden attackers: stop recalling under fire (2026-11-05, CLOUD; fight execution).

Replay action streams (actions.mjs) of v166's 148 lab games: damage interrupts a recall, and v166 restarts the
recall on the next turn whenever no enemy is visible within 6, so a champion shot by an enemy hidden in a bush
stands still until it dies. 1,142 recalls were restarted straight after a hit (7.7 a game); 2.49 of our 14.8
deaths a game come within 7 turns of a recall attempt, 1.86 of them with the true attacker within 3 tiles
(profiled games: no enemy visible within 8 on those turns). Our champions die recalling 1.77 times a game, our
opponents 0.77, the top UK teams 0.60. v166 never reads gm::bushes().

    MODE=recall  every recall (all go through recall_safe) waits HIT_MEMORY rounds after we last lost health.
    MODE=react   as recall, and damage that no visible enemy or awake camp can explain makes the champion walk
                 home out of range of nearby bushes for UNSEEN_ROUNDS rounds (when below UNSEEN_HEALTH).
    FIGHTBACK=1  the low-health retreat and the disengage withdrawal hit the weakest enemy in reach when
                 nav::retreat found no step (v166 then wasted the turn: a ranged champion cut off from home stood
                 still and was shot dead without firing back).

    mkambush.py BOTDIR [MODE=recall] [HIT_MEMORY=1] [UNSEEN_ROUNDS=3] [UNSEEN_HEALTH=1.0] [FIGHTBACK=0]
"""
import sys
from pathlib import Path

src = Path(sys.argv[1]) / "src"
P = dict(MODE="recall", HIT_MEMORY="1", UNSEEN_ROUNDS="3", UNSEEN_HEALTH="1.0", FIGHTBACK="0")
P.update(dict(a.split("=", 1) for a in sys.argv[2:]))
if P["MODE"] not in ("recall", "react"):
    sys.exit("MODE must be recall or react")


def patch(name, olds):
    f = src / name
    text = f.read_text()
    for old, new in olds:
        n = text.count(old)
        if n != 1:
            sys.exit(f"{name}: expected one match, found {n}: {old[:70]!r}")
        text = text.replace(old, new)
    f.write_text(text)


patch("config.h", [(
    "inline constexpr bool DEBUG = false;\n",
    "inline constexpr bool DEBUG = false;\n"
    f"// Hidden attackers (mkambush.py, MODE={P['MODE']}).\n"
    f"inline constexpr std::int64_t HIT_MEMORY = {P['HIT_MEMORY']};\n"
    f"inline constexpr std::int64_t UNSEEN_ROUNDS = {P['UNSEEN_ROUNDS']};\n"
    f"inline constexpr double UNSEEN_HEALTH = {P['UNSEEN_HEALTH']};\n",
)])

patch("bot.h", [
    # Health seen on our previous turn, and the last round we had lost health since then.
    ("    std::int64_t contest_last = -1;\n",
     "    std::int64_t contest_last = -1;\n"
     "    // mkambush.py: health on our previous turn, the last round we had lost some since, and how long an\n"
     "    // unexplained hit keeps us walking away from bushes.\n"
     "    std::int64_t seen_round = -10;\n"
     "    double seen_hp = 0;\n"
     "    std::int64_t hit_round = -10;\n"
     "    std::int64_t unseen_until = -10;\n"),
    # Damage interrupts a recall: never start one while still being hit.
    ("    bool recall_safe(const bc::champion& me, const std::vector<bc::champion>& enemies, const Camps& camps) const {\n",
     "    bool recall_safe(const bc::champion& me, const std::vector<bc::champion>& enemies, const Camps& camps) const {\n"
     "        if (hit_round >= static_cast<std::int64_t>(bc::round_number()) - config::HIT_MEMORY) return false;\n"),
    ("            status(\"dead\");\n            return;\n        }\n",
     "            status(\"dead\");\n            return;\n        }\n"
     "        {\n"
     "            const auto now = static_cast<std::int64_t>(bc::round_number());\n"
     "            const double hp = D(me.health());\n"
     "            if (seen_round == now - 1 && hp < seen_hp - 0.5) hit_round = now;\n"
     "            seen_round = now;\n"
     "            seen_hp = hp;\n"
     "        }\n"),
])

if P["MODE"] == "react":
    patch("bot.h", [(
        "        const double threshold = me.gem_count() ? config::CARRIER_RETREAT_HEALTH : config::RETREAT_HEALTH;\n",
        "        {\n"
        "            // mkambush.py: damage no visible enemy or awake camp can have dealt comes from a hidden enemy;\n"
        "            // walk home out of reach of the bushes around us instead of standing in its fire.\n"
        "            const auto now = static_cast<std::int64_t>(bc::round_number());\n"
        "            const auto here = me.position();\n"
        "            bool visible_near = false;\n"
        "            for (const auto& e : enemies)\n"
        "                if (distance(here, e.position()) <= 6) visible_near = true;\n"
        "            if (hit_round == now && !at_spawn && !visible_near) {\n"
        "                bool explained = false;\n"
        "                for (const auto& c : camps)\n"
        "                    if (c.is_visible() && c.is_awake() && c.strength() > 0 && distance(here, c.position()) <= c.attack_range() + 1)\n"
        "                        explained = true;\n"
        "                if (!explained && D(me.health()) < D(me.max_health()) * config::UNSEEN_HEALTH) unseen_until = now + config::UNSEEN_ROUNDS;\n"
        "            }\n"
        "            if (unseen_until >= now && !at_spawn && !visible_near) {\n"
        "                status(\"unseen\");\n"
        "                objective = nullptr;\n"
        "                team->claim();\n"
        "                bc::bitboard threat;\n"
        "                for (const auto b : (gm::bushes() & nav::around(here, 5)).positions()) threat |= nav::around(b, 4);\n"
        "                threat.set(here, false);\n"
        "                if (nav::move_to(gm::spawn_region(bc::team::ally), &threat)) return;\n"
        "                if (nav::retreat(enemies, camps)) return;\n"
        "            }\n"
        "        }\n"
        "        const double threshold = me.gem_count() ? config::CARRIER_RETREAT_HEALTH : config::RETREAT_HEALTH;\n",
    )])
if P["FIGHTBACK"] == "1":
    patch("bot.h", [
        ("    virtual ~Bot() = default;\n",
         "    virtual ~Bot() = default;\n\n"
         "    // mkambush.py: a withdrawal that found no step must not waste the turn: hit the weakest enemy in reach.\n"
         "    static void fight_back(bc::champion& me, const std::vector<bc::champion>& enemies) {\n"
         "        if (!me.is_alive() || !me.can_attack()) return;\n"
         "        std::vector<bc::champion> reach;\n"
         "        const auto mask = me.attack_tiles();\n"
         "        for (const auto& e : enemies)\n"
         "            if (mask.is_set(e.position())) reach.push_back(e);\n"
         "        if (!reach.empty())\n"
         "            combat::fight(*first_min(reach.begin(), reach.end(), [](const bc::champion& e) { return D(e.health()); }), reach);\n"
         "    }\n"),
        ("                combat::shield_on_retreat(enemies);\n"
         "                nav::retreat(enemies, camps);\n"
         "            }\n"
         "            return;\n",
         "                combat::shield_on_retreat(enemies);\n"
         "                if (!nav::retreat(enemies, camps)) fight_back(me, enemies);\n"
         "            }\n"
         "            return;\n"),
        ("                combat::shield_on_retreat(enemies);\n"
         "                nav::retreat(enemies, camps);\n"
         "                return;\n"
         "            }\n"
         "        }\n",
         "                combat::shield_on_retreat(enemies);\n"
         "                if (!nav::retreat(enemies, camps)) fight_back(me, enemies);\n"
         "                return;\n"
         "            }\n"
         "        }\n"),
    ])
print("patched", src, P)
