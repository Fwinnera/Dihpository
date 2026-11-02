#!/usr/bin/env python3
"""Turn a copy of a j_hjt-line bot into a per-round profiler.

Every champion turn prints one line, PF round type label x y hp maxhp gems gold group,
where label names the branch of play_turn that decided the turn.

    mkprof.py BOTDIR
"""
import sys
from pathlib import Path

src = Path(sys.argv[1]) / "src"


def patch(name, pairs):
    f = src / name
    text = f.read_text()
    for old, new in pairs:
        n = text.count(old)
        if n != 1:
            sys.exit(f"{name}: expected one match, found {n}: {old[:60]!r}")
        text = text.replace(old, new)
    f.write_text(text)


patch("common.h", [(
    "inline std::pair<int, int> key_of(bc::vec2 p) { return {p.x, p.y}; }",
    "inline std::pair<int, int> key_of(bc::vec2 p) { return {p.x, p.y}; }\n\n"
    "namespace prof {\ninline std::string label = \"none\";\ninline int group = -1;\n}  // namespace prof",
)])

patch("bot.h", [
    ("        last_state = label;\n    }",
     "        last_state = label;\n        prof::label = label;\n    }"),
    # channels in progress
    ("        if (me.is_recalling() || me.is_submitting_gems() || me.is_teleporting()) {\n",
     "        if (me.is_recalling() || me.is_submitting_gems() || me.is_teleporting()) {\n"
     "            status(me.is_recalling() ? \"recalling\" : me.is_submitting_gems() ? \"submitting\" : \"teleporting\");\n"),
    ("        if (!(me.can_move() || me.can_attack() || me.can_cast())) return;",
     "        if (!(me.can_move() || me.can_attack() || me.can_cast())) {\n            status(\"no-action\");\n            return;\n        }"),
    ("        if (at_spawn && me.health() < me.max_health()) {\n            team->claim();\n            return;",
     "        if (at_spawn && me.health() < me.max_health()) {\n            status(\"spawn-heal\");\n            team->claim();\n            return;"),
    ("            if (reserve_capture(holding)) return;",
     "            if (reserve_capture(holding)) {\n                status(\"capture-assist\");\n                return;\n            }"),
    ("            bc::round_number() < bc::constants::max_rounds - 150 && recall_safe(me, enemies, camps)) {\n            team->claim();",
     "            bc::round_number() < bc::constants::max_rounds - 150 && recall_safe(me, enemies, camps)) {\n            status(\"shop-recall\");\n            team->claim();"),
    # farm(): no objective
    ("            idle_last = now;\n            team->claim();\n            if (me.gem_count()) {\n                banking = true;",
     "            idle_last = now;\n            team->claim();\n            status(\"idle\");\n            if (me.gem_count()) {\n                status(\"idle-bank\");\n                banking = true;"),
    ("        if (progress.blocked(signature)) {\n            respawns[chosen->handle] = bc::round_number() + 80;",
     "        if (progress.blocked(signature)) {\n            status(\"blocked\");\n            respawns[chosen->handle] = bc::round_number() + 80;"),
    ("                status(\"capture\");\n                nav::move_to(chosen->spawns);\n                return;",
     "                status(\"to-reward\");\n                prof::group = chosen->handle;\n                nav::move_to(chosen->spawns);\n                return;"),
    ("        const auto& targets = observed;\n        if (targets.empty()) {\n            nav::move_to(chosen->spawns);",
     "        const auto& targets = observed;\n        prof::group = chosen->handle;\n        if (targets.empty()) {\n            status(\"travel\");\n            nav::move_to(chosen->spawns);"),
    ("        auto picked = combat::choose_camp(targets);\n        if (!picked) return;\n        bc::camp target = *picked;\n        status(\"farm\");",
     "        auto picked = combat::choose_camp(targets);\n        if (!picked) return;\n        bc::camp target = *picked;\n        status(me.attack_tiles().is_set(target.position()) ? \"farm\" : \"approach\");"),
    # escort
    ("        objective = picked;\n        if (deposit_before_camp(me, picked, enemies)) return;\n        current_group = picked->handle;\n        team->claim(picked->handle, true);",
     "        objective = picked;\n        if (deposit_before_camp(me, picked, enemies)) return;\n        status(\"escort\");\n        prof::group = picked->handle;\n        current_group = picked->handle;\n        team->claim(picked->handle, true);"),
])

patch("main.cpp", [
    ("                turn::begin();\n                bot->play_turn();\n                nav::finish_turn();",
     "                turn::begin();\n                prof::label = \"none\";\n                prof::group = -1;\n"
     "                bot->play_turn();\n                nav::finish_turn();\n"
     "                {\n                    auto& me = bc::self();\n"
     "                    std::cout << \"PF \" << bc::round_number() << ' ' << static_cast<int>(me.champion_name()) << ' '\n"
     "                              << prof::label << ' ' << (me.is_alive() ? me.position().x : -1) << ' '\n"
     "                              << (me.is_alive() ? me.position().y : -1) << ' '\n"
     "                              << me.health() << ' ' << me.max_health() << ' ' << me.gem_count() << ' '\n"
     "                              << me.gold_count() << ' ' << prof::group << '\\n';\n"
     "                }"),
])
print("patched", src)
