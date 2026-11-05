#!/usr/bin/env python3
"""Squad fights: engage or leave as a squad, with one shared target (2026-11-04, CLOUD; big plan, stage 2).

Apply after mkcofarm.py (squads are its PAIRS: a squad is a leader and its followers). Full co-farming squads
(cf3) keep the team together but did not lower our deaths locally (11.7 against v166's 11.2): each champion
still decides alone whether to fight, which enemy to hit and when to run.

For a squad member with a squad mate within SQ_RADIUS and an enemy within SQ_RADIUS (not on party maps, after
the individual low-health retreat):
  - engage when the squad's health x strength within SQ_RADIUS is at least SQ_ODDS of the enemies' within
    SQ_RADIUS of this champion: every member attacks the squad's shared target for the round (the first member
    to act picks the enemy with the least health in range of the squad and writes it to shared memory, bytes
    16-31, one 8-byte slot per squad: round and target handle), walking into reach;
  - otherwise leave together (the ordinary withdrawal: shield, then retreat).

    mksqfight.py BOTDIR [SQ_RADIUS=6] [SQ_ODDS=0.9]
"""
import re
import sys
from pathlib import Path

src = Path(sys.argv[1]) / "src"
P = dict(SQ_RADIUS="6", SQ_ODDS="0.9")
P.update(dict(a.split("=", 1) for a in sys.argv[2:]))


def patch(name, olds):
    f = src / name
    text = f.read_text()
    for old, new in olds:
        n = text.count(old)
        if n != 1:
            sys.exit(f"{name}: expected one match, found {n}: {old[:70]!r}")
        text = text.replace(old, new)
    f.write_text(text)


cfg = (src / "config.h").read_text()
m = re.search(r"// Co-farming squads \(mkcofarm.py, PAIRS=([^)]*)\)", cfg)
if not m:
    sys.exit("apply mkcofarm.py first")
pairs = [tuple(x.split(":")) for x in m.group(1).split(",") if x]
leaders = []
for _, b in pairs:
    if b not in leaders:
        leaders.append(b)
if len(leaders) > 2:
    sys.exit("at most two squads (two shared-memory slots)")
squad_cases = "".join(f"    case bc::champion_type::{a}: return {leaders.index(b)};\n" for a, b in pairs)
squad_cases += "".join(f"    case bc::champion_type::{b}: return {i};\n" for i, b in enumerate(leaders))

patch("config.h", [(
    "inline int cofarm_leader(bc::champion_type follower) {\n",
    f"// Squad fights (mksqfight.py).\n"
    f"inline constexpr int SQ_RADIUS = {P['SQ_RADIUS']};\n"
    f"inline constexpr double SQ_ODDS = {P['SQ_ODDS']};\n"
    "// Squad index (0 or 1) of a champion type, or -1.\n"
    "inline int squad_of(bc::champion_type type) {\n"
    "    switch (type) {\n"
    f"{squad_cases}"
    "    default: return -1;\n"
    "    }\n"
    "}\n"
    "inline int cofarm_leader(bc::champion_type follower) {\n",
)])

patch("bot.h", [(
    "        {\n"
    "            const auto [ratio, threats] = combat::local_power(enemies, team->allies, config::DISENGAGE_RADIUS);\n",
    "        if (!policy::party() && !enemies.empty() && bc::shared_memory.size() >= 32) {\n"
    "            const int squad = config::squad_of(me.champion_name());\n"
    "            if (squad >= 0) {\n"
    "                const auto position = me.position();\n"
    "                double ours = D(me.health()) * std::max(1.0, D(me.strength()));\n"
    "                int mates = 0;\n"
    "                for (const auto& a : team->allies)\n"
    "                    if (!same(a, me) && a.is_alive() && a.is_visible() && config::squad_of(a.champion_name()) == squad &&\n"
    "                        distance(position, a.position()) <= config::SQ_RADIUS) {\n"
    "                        ours += D(a.health()) * std::max(1.0, D(a.strength()));\n"
    "                        ++mates;\n"
    "                    }\n"
    "                std::vector<bc::champion> near;\n"
    "                double theirs = 0;\n"
    "                const auto& their_spawn = gm::spawn_region(bc::team::enemy);\n"
    "                for (const auto& e : enemies)\n"
    "                    if (distance(position, e.position()) <= config::SQ_RADIUS && !their_spawn.is_set(e.position())) {\n"
    "                        theirs += D(e.health()) * std::max(1.0, D(e.strength()));\n"
    "                        near.push_back(e);\n"
    "                    }\n"
    "                if (mates > 0 && !near.empty()) {\n"
    "                    objective = nullptr;\n"
    "                    team->claim();\n"
    "                    if (ours >= theirs * config::SQ_ODDS) {\n"
    "                        status(\"squad-fight\");\n"
    "                        const std::size_t slot = 16 + 8 * static_cast<std::size_t>(squad);\n"
    "                        const auto now = static_cast<std::uint32_t>(bc::round_number());\n"
    "                        std::array<std::byte, 8> buf{};\n"
    "                        turn::check();\n"
    "                        bc::shared_memory.read(slot, std::span<std::byte>{buf});\n"
    "                        const std::uint32_t when = std::uint32_t(buf[0]) | std::uint32_t(buf[1]) << 8 | std::uint32_t(buf[2]) << 16 | std::uint32_t(buf[3]) << 24;\n"
    "                        const std::uint32_t who = std::uint32_t(buf[4]) | std::uint32_t(buf[5]) << 8 | std::uint32_t(buf[6]) << 16 | std::uint32_t(buf[7]) << 24;\n"
    "                        std::optional<bc::champion> target;\n"
    "                        if (when == now)\n"
    "                            for (const auto& e : near)\n"
    "                                if (handle_of(e) == who) target = e;\n"
    "                        if (!target) {\n"
    "                            target = *first_min(near.begin(), near.end(), [](const bc::champion& e) { return D(e.health()); });\n"
    "                            const std::uint32_t h = handle_of(*target);\n"
    "                            const std::array<std::byte, 8> out{std::byte(now & 255), std::byte((now >> 8) & 255), std::byte((now >> 16) & 255), std::byte(now >> 24),\n"
    "                                                               std::byte(h & 255), std::byte((h >> 8) & 255), std::byte((h >> 16) & 255), std::byte(h >> 24)};\n"
    "                            turn::check();\n"
    "                            bc::shared_memory.write(slot, std::span<const std::byte>{out});\n"
    "                        }\n"
    "                        bool acted = combat::fight(*target, near);\n"
    "                        if (combat::live(*target) && target->health() > 0) {\n"
    "                            const bool moved = nav::move_to(nav::around(target->position(), me.attack_range()));\n"
    "                            if (moved && combat::live(*target) && target->health() > 0) acted = combat::fight(*target, near) || acted;\n"
    "                        }\n"
    "                        (void)acted;\n"
    "                        return;\n"
    "                    }\n"
    "                    status(\"squad-leave\");\n"
    "                    combat::shield_on_retreat(enemies);\n"
    "                    nav::retreat(enemies, camps);\n"
    "                    return;\n"
    "                }\n"
    "            }\n"
    "        }\n"
    "        {\n"
    "            const auto [ratio, threats] = combat::local_power(enemies, team->allies, config::DISENGAGE_RADIUS);\n",
)])
print("patched", src, P, "squads", leaders)
