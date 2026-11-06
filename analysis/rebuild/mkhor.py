#!/usr/bin/env python3
"""Heart of Ruin, played (2026-11-04, CLOUD; the owner's "bigger bet").

Every top UK team drafts Heart of Ruin (34 of 34 decoded ranked games), with Vesper Vale, Marcella and
Vendetta; it tanks (16.5k shielding a game) and its dash lands with Focus x 1.5 damage and a one-round stun on
everything within one tile. Our code never casts a dash in a fight (nav::dash spends dashes on travel only),
which is one reason the October draft swap on v100 lost.

  - draft (non-party maps): Heart of Ruin takes SLOT's place (ryth, varg, or ryth5: Ryth's place only on
    rosters of five or more; on four-champion maps the plain swap cost 16 of 108 local games).
  - offensive dash (combat::fight, champions and camps): a dash with landing damage or stun lands on a legal
    tile within its radius of the target, scored by damage plus 0.8 x strength x stun rounds for every unit it
    hits (Marcella is not stunned); travel (nav::dash) no longer spends such a dash.
  - build: Heart of Ruin buys Durability health, then Bruiser Focus and Bruiser health, then alternates
    Bruiser Focus and Bruiser health (shield and dash scale with Focus).
  - HOR_RETREAT: its retreat health fraction (its damage grows with missing health); 0 keeps the default.

    mkhor.py BOTDIR [SLOT=ryth] [DASH=1] [BUILD=1] [HOR_RETREAT=0] [SHIELD=0] [ESCORT=0]

  - ESCORT=1: Heart of Ruin plays Willow's escort controller, joining the claimed group of Vesper Vale
    (else Vendetta or Marcella) and staying beside it, as the top teams' Heart of Ruin pairs with Vesper Vale.

  - SHIELD=1: below 90% health and under attack (an enemy champion within its reach + 1, or awake camps in
    range), a self-shield is cast before anything else unless a dash would hit an enemy champion.
"""
import sys
from pathlib import Path

src = Path(sys.argv[1]) / "src"
P = dict(SLOT="ryth", DASH="1", BUILD="1", HOR_RETREAT="0", SHIELD="0", ESCORT="0")
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
    "// Heart of Ruin (mkhor.py): offensive dash, Focus build, retreat fraction (0 = default).\n"
    f"inline constexpr bool HOR_DASH = {'true' if P['DASH'] == '1' else 'false'};\n"
    f"inline constexpr double HOR_RETREAT = {P['HOR_RETREAT']};\n",
)])

old_order = "        order = {D::varg, D::vendetta, D::vesper_vale, D::ryth, D::marcella, D::willow, D::tavi, D::cassi_and_issac, D::ren, D::stellar, D::prism, D::heart_of_ruin};\n"
if P["SLOT"] == "ryth":
    new_order = "        order = {D::varg, D::vendetta, D::vesper_vale, D::heart_of_ruin, D::marcella, D::willow, D::tavi, D::cassi_and_issac, D::ren, D::stellar, D::prism, D::ryth};\n"
elif P["SLOT"] == "ryth5":
    new_order = ("        order = bc::draft::team_size() >= 5\n"
                 "                    ? std::vector<D>{D::varg, D::vendetta, D::vesper_vale, D::heart_of_ruin, D::marcella, D::willow, D::tavi, D::cassi_and_issac, D::ren, D::stellar, D::prism, D::ryth}\n"
                 "                    : std::vector<D>{D::varg, D::vendetta, D::vesper_vale, D::ryth, D::marcella, D::willow, D::tavi, D::cassi_and_issac, D::ren, D::stellar, D::prism, D::heart_of_ruin};\n")
elif P["SLOT"] == "varg":
    new_order = "        order = {D::heart_of_ruin, D::vendetta, D::vesper_vale, D::ryth, D::marcella, D::willow, D::tavi, D::cassi_and_issac, D::ren, D::stellar, D::prism, D::varg};\n"
else:
    new_order = old_order
patch("draft.h", [(old_order, new_order)])

patch("combat.h", [(
    "        if (!(ability.is_damage() || ability.is_aoe_damage() || ability.is_cc())) continue;\n",
    "        if (ability.is_dash()) {\n"
    "            if (!config::HOR_DASH) continue;\n"
    "            const auto& dd = std::get<bc::ability_dash>(*ability.info());\n"
    "            if (dd.modifier <= 0 && dd.duration <= 0) continue;\n"
    "            auto path_walls = gm::walls() | gm::altars() | gm::spawn_region(bc::team::enemy) | bc::vision::champion_tiles() |\n"
    "                              bc::vision::camp_tiles() | bc::vision::teleport_tiles();\n"
    "            path_walls.set(me.position(), false);\n"
    "            const auto landings = (path_walls.reachable_tiles(me.position(), static_cast<std::uint16_t>(static_cast<int>(dd.range))) &\n"
    "                                   ability.valid_tiles() & ~nav::blocked()).positions();\n"
    "            const double amount = ability.damage_amount();\n"
    "            const int radius = static_cast<int>(dd.radius);\n"
    "            std::vector<const T*> units;\n"
    "            bool included = false;\n"
    "            for (const auto& u : nearby)\n"
    "                if (live(u) && u.health() > 0) {\n"
    "                    units.push_back(&u);\n"
    "                    if (same(u, target)) included = true;\n"
    "                }\n"
    "            if (!included) units.push_back(&target);\n"
    "            std::optional<bc::vec2> landing;\n"
    "            double landing_value = 0;\n"
    "            for (const auto p : landings) {\n"
    "                turn::check();\n"
    "                if (distance(p, position) > radius) continue;\n"
    "                double value = 0;\n"
    "                for (const auto* u : units) {\n"
    "                    if (distance(p, u->position()) > radius) continue;\n"
    "                    value += std::min(amount, D(u->health()));\n"
    "                    if (dd.duration > 0) {\n"
    "                        if constexpr (enemy) {\n"
    "                            if (u->champion_name() != bc::champion_type::marcella) value += D(u->strength()) * 0.8 * dd.duration;\n"
    "                        } else {\n"
    "                            if (u->strength()) value += D(u->strength()) * 0.8 * dd.duration;\n"
    "                        }\n"
    "                    }\n"
    "                }\n"
    "                if (value > landing_value) {\n"
    "                    landing = p;\n"
    "                    landing_value = value;\n"
    "                }\n"
    "            }\n"
    "            if (landing) choices.push_back({landing_value, &ability, 1, *landing});\n"
    "            continue;\n"
    "        }\n"
    "        if (!(ability.is_damage() || ability.is_aoe_damage() || ability.is_cc())) continue;\n",
)])

patch("nav.h", [(
    "        if (!ability.is_dash() || !ability.is_ready() || !turn::may_cast(ability)) continue;\n",
    "        if (!ability.is_dash() || !ability.is_ready() || !turn::may_cast(ability)) continue;\n"
    "        if (config::HOR_DASH) {\n"
    "            const auto& dd = std::get<bc::ability_dash>(*ability.info());\n"
    "            if (dd.modifier > 0 || dd.duration > 0) continue;\n"
    "        }\n",
)])

if P["BUILD"] == "1":
    patch("config.h", [(
        "    if (type == bc::champion_type::willow)\n"
        "        return {I::jungle_shard_of_focus, I::durability_shard_of_health, I::power_shard_of_focus};\n",
        "    if (type == bc::champion_type::willow)\n"
        "        return {I::jungle_shard_of_focus, I::durability_shard_of_health, I::power_shard_of_focus};\n"
        "    if (type == bc::champion_type::heart_of_ruin)\n"
        "        return {I::durability_shard_of_health, I::bruiser_shard_of_focus, I::bruiser_shard_of_health};\n",
    )])
    patch("bot.h", [(
        "                if (!scaling_item || purchase_index % 5 == 0) {\n",
        "                if (me.champion_name() == bc::champion_type::heart_of_ruin) {\n"
        "                    scaling_item = (purchase_index / 5) % 2 ? bc::item_type::bruiser_shard_of_health\n"
        "                                                            : bc::item_type::bruiser_shard_of_focus;\n"
        "                } else if (!scaling_item || purchase_index % 5 == 0) {\n",
    )])

if float(P["HOR_RETREAT"]) > 0:
    patch("bot.h", [(
        "        const double threshold = me.gem_count() ? config::CARRIER_RETREAT_HEALTH : config::RETREAT_HEALTH;\n",
        "        double threshold = me.gem_count() ? config::CARRIER_RETREAT_HEALTH : config::RETREAT_HEALTH;\n"
        "        if (me.champion_name() == bc::champion_type::heart_of_ruin) threshold = std::min(threshold, config::HOR_RETREAT);\n",
    )])
print("patched", src, P)

if P["SHIELD"] == "1":
    patch("combat.h", [(
        "    std::stable_sort(choices.begin(), choices.end(), [](const Choice& a, const Choice& b) { return a.value > b.value; });\n",
        "    if (me.champion_name() == bc::champion_type::heart_of_ruin && D(me.health()) < D(me.max_health()) * 0.9) {\n"
        "        bool attacked = false;\n"
        "        for (const auto& e : bc::vision::champions(bc::team::enemy))\n"
        "            if (e.is_alive() && distance(me.position(), e.position()) <= std::max<std::int64_t>(1, e.attack_range()) + 1) attacked = true;\n"
        "        if (!attacked)\n"
        "            for (const auto& c : bc::vision::camps())\n"
        "                if (c.is_visible() && c.is_awake() && c.strength() > 0 && distance(me.position(), c.position()) <= c.attack_range()) attacked = true;\n"
        "        bool dash_on_champion = false;\n"
        "        if constexpr (enemy)\n"
        "            for (const auto& c : choices)\n"
        "                if (c.ability->is_dash()) dash_on_champion = true;\n"
        "        if (attacked && !dash_on_champion)\n"
        "            for (auto& c : choices)\n"
        "                if (c.ability->is_shield()) c.value = 1e9;\n"
        "    }\n"
        "    std::stable_sort(choices.begin(), choices.end(), [](const Choice& a, const Choice& b) { return a.value > b.value; });\n",
    )])
    # The shield choice also exists when the target is a strength-less cluster: use camp pressure around us.
    patch("combat.h", [(
        "            const double incoming = target.strength();\n",
        "            double incoming = target.strength();\n"
        "            if (me.champion_name() == bc::champion_type::heart_of_ruin && !incoming) incoming = 1;\n",
    )])
print("shield", P["SHIELD"])

if P["ESCORT"] == "1":
    patch("main.cpp", [(
        "    if (bc::self().champion_name() == bc::champion_type::willow) return std::make_unique<EscortBot>();\n",
        "    if (bc::self().champion_name() == bc::champion_type::willow || bc::self().champion_name() == bc::champion_type::heart_of_ruin)\n"
        "        return std::make_unique<EscortBot>();\n",
    )])
    patch("bot.h", [(
        "            double priority = ally.champion_name() == bc::champion_type::varg ? 0 : 1;\n",
        "            double priority = ally.champion_name() == bc::champion_type::varg ? 0 : 1;\n"
        "            if (me.champion_name() == bc::champion_type::heart_of_ruin)\n"
        "                priority = ally.champion_name() == bc::champion_type::vesper_vale ? 0\n"
        "                           : (ally.champion_name() == bc::champion_type::vendetta || ally.champion_name() == bc::champion_type::marcella) ? 0.6\n"
        "                                                                                                                                : 1;\n",
    )])
print("escort", P["ESCORT"])

# Engine 3.0.0 (2026-11-06): the engine refuses some dash landing tiles the masks allow ("Forbidden landing
# tile"); the uncaught error cost the whole turn (about 900 error lines a game). Catch it at the call site.
patch("combat.h", [(
    "            else if (choice.aim == 1) acted = ability.use(choice.tile);\n",
    "            else if (choice.aim == 1) {\n"
    "                // Engine 3.0.0 refuses some landing tiles the masks allow; a refused dash must not cost the turn.\n"
    "                try {\n"
    "                    acted = ability.use(choice.tile);\n"
    "                } catch (const std::exception&) {\n"
    "                    acted = false;\n"
    "                }\n"
    "            }\n",
)])
print("dash landing guarded")
