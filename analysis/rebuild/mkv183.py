#!/usr/bin/env python3
"""mkv183.py SRC DST [VV=0]: rebuild the teammate's v182/v183 from mg4 (v180) source.

v182 and v183 were uploaded on the website by a teammate (8 and 9 Nov); their source was read from the
platform (submissions/<id>/files) and diffed against v180 line by line. v182 = mg4 +
  - draft: Tavi in Ryth's slot (tv1);
  - common.h threat_dps(): threat per round counting spell output (Focus) as well as Strength, used by
    combat.h (stun value, shield, CC value, choose_enemy powers and focus order, local_power) and by
    nav.h's retreat risk.
v183 = v182 + Vesper Vale's build Treasure > Hunter > Power (strength).
VV=0 gives v182. The result must match the platform's file sizes (checked below).
"""
import shutil
import sys
from pathlib import Path

src, dst = Path(sys.argv[1]), Path(sys.argv[2])
opts = dict(a.split("=", 1) for a in sys.argv[3:])
vv = int(opts.get("VV", "1"))
if dst.exists():
    sys.exit(f"{dst} exists")
dst.mkdir(parents=True)
shutil.copytree(src / "src", dst / "src")
S = dst / "src"


def sub(name, old, new, count=1):
    p = S / name
    t = p.read_text()
    assert t.count(old) == count, (name, old[:60], t.count(old))
    p.write_text(t.replace(old, new))


THREAT = """// Threat per round including spell output: a caster deals damage with Focus, not
// Strength. Review of the 04hourglass/03colosseum losses (Prism/Tavi/Stellar comps,
// 33 deaths to 1) showed the Strength-only model never disengaged against casters.
inline double threat_dps(const bc::champion& c) {
    double damage = D(c.strength());
    for (const auto& ability : c.abilities()) {
        if (!ability.info()) continue;
        if (ability.is_attack_reset()) damage += D(c.strength()) / 8;
        else if (ability.is_damage() || ability.is_cc() || ability.is_aoe_damage())
            damage += info_modifier(ability) * D(c.focus()) / 8;
    }
    return std::max(1.0, damage);
}

"""
anchor = "inline std::int64_t distance(bc::vec2 a, bc::vec2 b)"
sub("common.h", anchor, THREAT + anchor)

sub("combat.h",
    "inline double damage_against(const bc::ability& ability, const bc::camp&) { return ability.damage_amount(); }\n",
    "inline double damage_against(const bc::ability& ability, const bc::camp&) { return ability.damage_amount(); }\n"
    "inline double threat_of(const bc::champion& target) { return threat_dps(target); }\n"
    "inline double threat_of(const bc::camp& target) { return std::max(1.0, D(target.strength())); }\n")
sub("combat.h",
    "target.champion_name() != bc::champion_type::marcella) stun = D(target.strength()) * 0.8;",
    "target.champion_name() != bc::champion_type::marcella) stun = threat_of(target) * 0.8;")
sub("combat.h", "            const double incoming = target.strength();",
    "            const double incoming = threat_of(target);")
sub("combat.h", "                control = D(target.strength()) * 0.8 + (target.is_submitting_gems() ? 120 : 0);",
    "                control = threat_of(target) * 0.8 + (target.is_submitting_gems() ? 120 : 0);")
sub("combat.h", "        double allied_power = D(me.health()) * std::max(1.0, D(me.strength()));",
    "        double allied_power = D(me.health()) * threat_dps(me);")
sub("combat.h", "                allied_power += D(ally.health()) * std::max(1.0, D(ally.strength())) * 0.75;",
    "                allied_power += D(ally.health()) * threat_dps(ally) * 0.75;")
sub("combat.h", "enemy_power += D(e.health()) * std::max(1.0, D(e.strength()));",
    "enemy_power += D(e.health()) * threat_dps(e);")
sub("combat.h", "                    -std::max(1.0, D(enemy.strength())) / std::max(1.0, D(enemy.health())), gap,",
    "                    -threat_dps(enemy) / std::max(1.0, D(enemy.health())), gap,")
sub("combat.h", "            hostile += D(enemy.health()) * std::max(1.0, D(enemy.strength()));",
    "            hostile += D(enemy.health()) * threat_dps(enemy);")
sub("combat.h", "    double allied = D(me.health()) * std::max(1.0, D(me.strength()));",
    "    double allied = D(me.health()) * threat_dps(me);")
sub("combat.h", "            allied += D(ally.health()) * std::max(1.0, D(ally.strength())) * 0.75;",
    "            allied += D(ally.health()) * threat_dps(ally) * 0.75;")
sub("nav.h", "threats.push_back({e.position(), std::max(4, e.attack_range()), D(e.strength())});",
    "threats.push_back({e.position(), std::max(4, e.attack_range()), threat_dps(e)});")
sub("draft.h",
    "        order = {D::varg, D::vendetta, D::vesper_vale, D::ryth, D::marcella, D::willow, D::tavi,",
    "        // tv1 (2026-11-06): Tavi (ranged, shops in the field) in Ryth's slot. On v166's engine-3.0.0 lab games our\n"
    "        // Ryth collected 93 gems a game (opponents' Ryth 163; our other picks 158-331).\n"
    "        order = {D::varg, D::vendetta, D::vesper_vale, D::tavi, D::marcella, D::willow, D::ryth,")
if vv:
    sub("config.h",
        "    return {I::hunter_shard_of_strength, I::durability_shard_of_health, I::jungle_shard_of_strength};\n",
        "    if (type == bc::champion_type::vesper_vale)\n"
        "        return {I::treasure_shard_of_strength, I::hunter_shard_of_strength, I::power_shard_of_strength};\n"
        "    return {I::hunter_shard_of_strength, I::durability_shard_of_health, I::jungle_shard_of_strength};\n")

# Platform sizes (bytes) of the changed files.
want = {"combat.h": 15472, "common.h": 3583, "nav.h": 20754, "draft.h": 1486,
        "config.h": 4575 if vv else 4422}
got = {n: (S / n).stat().st_size for n in want}
print(f"{dst}: {'v183' if vv else 'v182'}", "sizes match" if got == want else f"SIZE MISMATCH {got} vs {want}")
