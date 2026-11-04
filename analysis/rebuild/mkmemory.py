#!/usr/bin/env python3
"""Enemy memory: count enemies seen recently but now out of sight (2026-11-04, CLOUD).

Ladder evidence (lab set 1, profiled v166 and decoded replays): at the first contact before one of our deaths
in our half or the middle, 1.4 enemies are visible within 8 tiles but 2.4 are within 12; the second enemy
arrives within rounds and the fight is lost. Every fight decision counts only the enemies in sight.

Each champion remembers, per enemy, the tile, round and health x strength at its last sighting (team vision),
for MEM_ROUNDS rounds. An enemy out of sight now counts with weight MEM_WEIGHT wherever it could have walked
to (its last tile plus one tile a round):
  - disengage: added to the enemy power around us when at least one enemy is in sight within the radius;
  - choose_enemy: added to the enemy power around the target, and the "enemy within 4" accept needs our power
    to be at least MEM_ACCEPT of that total;
  - choose_group: remembered positions join the visible enemies in the camp scores.

    mkmemory.py BOTDIR [MEM_ROUNDS=8] [MEM_WEIGHT=0.7] [MEM_ACCEPT=0.5] [MEM_GROUP=1]
"""
import sys
from pathlib import Path

src = Path(sys.argv[1]) / "src"
P = dict(MEM_ROUNDS="8", MEM_WEIGHT="0.7", MEM_ACCEPT="0.5", MEM_GROUP="1")
P.update(dict(a.split("=", 1) for a in sys.argv[2:]))


def patch(name, pairs):
    f = src / name
    text = f.read_text()
    for old, new in pairs:
        n = text.count(old)
        if n != 1:
            sys.exit(f"{name}: expected one match, found {n}: {old[:70]!r}")
        text = text.replace(old, new)
    f.write_text(text)


patch("config.h", [(
    "inline constexpr bool DEBUG = false;\n",
    "inline constexpr bool DEBUG = false;\n"
    "// Enemy memory (mkmemory.py): enemies seen in the last MEM_ROUNDS rounds count, out of sight, at MEM_WEIGHT.\n"
    f"inline constexpr std::int64_t MEM_ROUNDS = {P['MEM_ROUNDS']};\n"
    f"inline constexpr double MEM_WEIGHT = {P['MEM_WEIGHT']};\n"
    f"inline constexpr double MEM_ACCEPT = {P['MEM_ACCEPT']};\n"
    f"inline constexpr bool MEM_GROUP = {'true' if P['MEM_GROUP'] == '1' else 'false'};\n",
)])

patch("teamwork.h", [(
    "inline bool same(const bc::champion& a, const bc::champion& b) { return handle_of(a) == handle_of(b); }\n",
    "inline bool same(const bc::champion& a, const bc::champion& b) { return handle_of(a) == handle_of(b); }\n"
    "\n"
    "// Enemy memory (mkmemory.py): last sighting of each enemy champion under team vision.\n"
    "namespace memory {\n"
    "struct Seen {\n"
    "    bc::vec2 position;\n"
    "    std::int64_t round;\n"
    "    double power;\n"
    "};\n"
    "inline std::map<std::uint32_t, Seen> seen;\n"
    "inline std::int64_t updated = -1;\n"
    "\n"
    "inline void remember(const std::vector<bc::champion>& enemies) {\n"
    "    const auto now = static_cast<std::int64_t>(bc::round_number());\n"
    "    if (now == updated) return;\n"
    "    updated = now;\n"
    "    for (const auto& e : enemies)\n"
    "        seen[handle_of(e)] = {e.position(), now, static_cast<double>(e.health()) * std::max(1.0, static_cast<double>(e.strength()))};\n"
    "    for (auto it = seen.begin(); it != seen.end();)\n"
    "        it = now - it->second.round > config::MEM_ROUNDS ? seen.erase(it) : std::next(it);\n"
    "}\n"
    "\n"
    "// Health x strength (weighted) of remembered enemies out of sight that could be within `radius` of `at`.\n"
    "inline double ghosts(bc::vec2 at, std::int64_t radius) {\n"
    "    const auto now = static_cast<std::int64_t>(bc::round_number());\n"
    "    double total = 0;\n"
    "    for (const auto& [handle, s] : seen) {\n"
    "        if (s.round >= now) continue;\n"
    "        if (distance(at, s.position) <= radius + (now - s.round)) total += s.power * config::MEM_WEIGHT;\n"
    "    }\n"
    "    return total;\n"
    "}\n"
    "\n"
    "// Last tiles of remembered enemies out of sight.\n"
    "inline std::vector<bc::vec2> ghost_tiles() {\n"
    "    const auto now = static_cast<std::int64_t>(bc::round_number());\n"
    "    std::vector<bc::vec2> out;\n"
    "    for (const auto& [handle, s] : seen)\n"
    "        if (s.round < now) out.push_back(s.position);\n"
    "    return out;\n"
    "}\n"
    "}  // namespace memory\n",
)])

patch("bot.h", [(
    "        std::vector<bc::champion> enemies;\n"
    "        for (auto& e : bc::vision::champions(bc::team::enemy))\n"
    "            if (e.is_alive()) enemies.push_back(e);\n",
    "        std::vector<bc::champion> enemies;\n"
    "        for (auto& e : bc::vision::champions(bc::team::enemy))\n"
    "            if (e.is_alive()) enemies.push_back(e);\n"
    "        memory::remember(enemies);\n",
)])

patch("combat.h", [
    # choose_enemy: remembered enemies around the target, and a power floor on the within-4 accept.
    ("        double enemy_power = 0;\n"
     "        for (const auto& e : enemies)\n"
     "            if (distance(e.position(), enemy.position()) <= 4) enemy_power += D(e.health()) * std::max(1.0, D(e.strength()));\n",
     "        double enemy_power = 0;\n"
     "        for (const auto& e : enemies)\n"
     "            if (distance(e.position(), enemy.position()) <= 4) enemy_power += D(e.health()) * std::max(1.0, D(e.strength()));\n"
     "        enemy_power += memory::ghosts(enemy.position(), 4);\n"),
    ("        if (!(killable || interrupt || defending || gap <= 4 || allied_power > enemy_power * 1.15)) continue;\n",
     "        const bool close = gap <= 4 && allied_power >= enemy_power * config::MEM_ACCEPT;\n"
     "        if (!(killable || interrupt || defending || close || allied_power > enemy_power * 1.15)) continue;\n"),
    # disengage: remembered enemies around us count once one is in sight.
    ("    if (!threats) return {std::numeric_limits<double>::infinity(), 0};\n",
     "    if (!threats) return {std::numeric_limits<double>::infinity(), 0};\n"
     "    hostile += memory::ghosts(position, radius);\n"),
])

if P["MEM_GROUP"] == "1":
    patch("strategy.h", [(
        "        if (enemy.is_visible() && enemy.is_alive()) enemy_positions.push_back(enemy.position());\n"
        "    }\n",
        "        if (enemy.is_visible() && enemy.is_alive()) enemy_positions.push_back(enemy.position());\n"
        "    }\n"
        "    if (config::MEM_GROUP)\n"
        "        for (const auto p : memory::ghost_tiles()) enemy_positions.push_back(p);\n",
    )])
print("patched", src, P)
