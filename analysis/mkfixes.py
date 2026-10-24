#!/usr/bin/env python3
"""Build the fixes from the #1 analysis, each one change on version 93's tagged twin.

    mkfixes.py                     # builds every variant below
    mkfixes.py gs93_hurt60 ...     # or just the named ones
    mkfixes.py gs93_combo=hurt60+willow_farm+travel60   # stacked

Base: ws/bots/gs_seelie_dis050, which is the live version 93 plus a BOTTAG, so
every variant compares game for game with its full-pool results.
"""
from __future__ import annotations

import ast
import re
import shutil
import sys
from pathlib import Path

WS = Path(__file__).resolve().parent.parent / "ws"
BASE = "gs_seelie_dis050"

HURT = '''        # A hurt champion leaves when an enemy champion is within reach, instead of
        # fighting on down to 30%. We died 22.5 times a game over 510 ladder games;
        # the #1 team, which spends 2.5 times as much of the game farming, dies 7.1
        # times. A healthy champion still returns fire: removing the proximity
        # accept outright cost 159 gems, because champions stopped fighting back.
        for enemy in enemies:
            turn.check()
            if nav.distance(position, enemy.position()) <= config.HURT_RADIUS:
                threshold = max(threshold, config.HURT_RETREAT)
                break
'''
HURT_CFG = '''# Retreat threshold while an enemy champion is within HURT_RADIUS tiles.
HURT_RETREAT = {h}
HURT_RADIUS = 5
'''
ESCORT_OLD = '''                if ally.health() < ally.max_health() * 0.7:
                    priority -= 1
'''
ESCORT_NEW = '''                # Follow a farmer, not a fight. Moving towards hurt allies took the
                # team's lowest-health champion into the fights that hurt them:
                # Willow died 5.5 times a game for 0.3 kills. A leader with an enemy
                # champion near it is now the last choice instead of the first.
                for enemy in bc.vision.champions(bc.Team.ENEMY):
                    turn.check()
                    if enemy.is_alive() and nav.distance(ally.position(), enemy.position()) <= 5:
                        priority += 2
                        break
'''
WILLOW_OLD = '''    if bc.me().champion_name() == bc.ChampionType.WILLOW:
        from escort import EscortBot
        return EscortBot()
'''
WILLOW_NEW = '''    # Willow farms like everyone else. As an escort she banked 4% of the team's
    # gems and spent 5.7% of the game farming; heal_allies still runs every turn.
'''
TRAVEL_CFG = '''# Weight of travel in camp choice. The #1 team farms at depth 0.37-0.45 between
# the bases and banks at the central altar; we farmed at 0.11-0.21 and banked at
# home, because travel dominated the cost. Below 1, richer camps further out win.
TRAVEL_WEIGHT = {w}
'''


def edit(path: Path, old: str, new: str, count: int = 1) -> None:
    t = path.read_text()
    if t.count(old) != count:
        sys.exit(f"{path.name}: expected {count} of {old[:50]!r}, found {t.count(old)}")
    path.write_text(t.replace(old, new))


def apply(src: Path, change: str) -> None:
    """One change, by its variant name without the gs93_ prefix."""
    cfg = src / "config.py"
    m = re.fullmatch(r"hurt(\d+)", change)
    if m:
        edit(src / "bot.py", "        position = me.position()\n        camp_pressure = ",
             "        position = me.position()\n" + HURT + "        camp_pressure = ")
        cfg.write_text(cfg.read_text() + HURT_CFG.format(h=int(m.group(1)) / 100))
    elif change == "willow_farm":
        edit(src / "policy.py", WILLOW_OLD, WILLOW_NEW)
    elif change == "escort_safe":
        edit(src / "escort.py", ESCORT_OLD, ESCORT_NEW)
    elif re.fullmatch(r"travel(\d+)", change):
        w = int(change[len("travel"):]) / 100
        st = src / "strategy.py"
        edit(st, "        estimate = cost + (travel + risk) * 100 / max(1, value) + bias",
             "        estimate = cost + (travel * config.TRAVEL_WEIGHT + risk) * 100 / max(1, value) + bias")
        edit(st, "        score = (travel + clear + capture + risk) * 100 / max(1, value) + bias",
             "        score = (travel * config.TRAVEL_WEIGHT + clear + capture + risk) * 100 / max(1, value) + bias")
        edit(st, "            score = (travel + capture) * 100 / max(1, value) - 15",
             "            score = (travel * config.TRAVEL_WEIGHT + capture) * 100 / max(1, value) - 15")
        cfg.write_text(cfg.read_text() + TRAVEL_CFG.format(w=w))
    elif re.fullmatch(r"bank(\d+)", change):
        # The #1 team's regular bankers deposit about 45 gems at a time and peak
        # at 44-70; ours deposit about 30 against BANK_GEMS 24. With disengage
        # cutting deaths, carrying a bigger load costs fewer of them.
        n = int(change[len("bank"):])
        edit(cfg, "BANK_GEMS = 24\n", f"BANK_GEMS = {n}\n")
    elif change in ("bruiser", "items"):
        # Bruiser grants seven stat points for the 150 gold Power spends on six,
        # and the #1 team stacks it after its opening; it holds almost no Power.
        edit(src / "bot.py", "bc.ItemType.POWER_SHARD_OF_HEALTH", "bc.ItemType.BRUISER_SHARD_OF_HEALTH")
        edit(src / "bot.py", "bc.ItemType.POWER_SHARD_OF_STRENGTH", "bc.ItemType.BRUISER_SHARD_OF_STRENGTH")
        if change == "items":
            # Their opening: Jungle first, Durability once, then Bruiser; Monster
            # only on their focus caster, which we do not field.
            edit(cfg, "DEFAULT_BUILD = (I.JUNGLE_SHARD_OF_STRENGTH, I.MONSTER_SHARD_OF_STRENGTH,\n"
                      "                 I.DURABILITY_SHARD_OF_HEALTH)",
                 "DEFAULT_BUILD = (I.JUNGLE_SHARD_OF_STRENGTH, I.DURABILITY_SHARD_OF_HEALTH)")
    elif change == "treasure":
        # Treasure first (+20% gold gained), the opening of #2, #3 and #4 and the
        # second emblem of #5. On greatsage it bought gold but no gems; v97 dies
        # less, so the extra gold may now reach the score. gs_treasure's order.
        edit(cfg, "DEFAULT_BUILD = (I.JUNGLE_SHARD_OF_STRENGTH, I.MONSTER_SHARD_OF_STRENGTH,\n"
                  "                 I.DURABILITY_SHARD_OF_HEALTH)",
             "DEFAULT_BUILD = (I.TREASURE_SHARD_OF_STRENGTH, I.JUNGLE_SHARD_OF_STRENGTH,\n"
             "                 I.MONSTER_SHARD_OF_STRENGTH, I.DURABILITY_SHARD_OF_HEALTH)")
        edit(cfg, "BUILDS = {bc.ChampionType.WILLOW: (I.JUNGLE_SHARD_OF_FOCUS,\n"
                  "          I.DURABILITY_SHARD_OF_HEALTH, I.POWER_SHARD_OF_FOCUS)}",
             "BUILDS = {bc.ChampionType.WILLOW: (I.TREASURE_SHARD_OF_FOCUS,\n"
             "          I.JUNGLE_SHARD_OF_FOCUS, I.DURABILITY_SHARD_OF_HEALTH,\n"
             "          I.POWER_SHARD_OF_FOCUS)}")
    elif change == "hunt":
        # Carriers are the richest targets: a kill pays 100 gold plus everything
        # carried. The top five kill 1.6-3.3 carriers a game; we kill 0.6, and a
        # carrier's gems were only the last tie-break. Within reach (7 tiles), a
        # carrier of HUNT_GEMS or more is accepted at HUNT_POWER of the local
        # strength rather than 1.15, and targets rank by gems before health.
        # Disengage still runs first, so a lost fight is still left.
        c = src / "combat.py"
        edit(c, "        if not (killable or interrupt or defending or gap <= 4 or allied_power > enemy_power * 1.15):\n",
             "        rich = enemy.gem_count() >= config.HUNT_GEMS and allied_power > enemy_power * config.HUNT_POWER\n"
             "        if not (killable or interrupt or defending or gap <= 4 or allied_power > enemy_power * 1.15 or rich):\n")
        edit(c, "        if gap > 4 and not (killable or interrupt or allied_power > enemy_power * 1.15):\n",
             "        if gap > 4 and not (killable or interrupt or allied_power > enemy_power * 1.15 or rich):\n")
        edit(c, "        score = (not attack_mask.is_set(enemy.position()), not interrupt, not killable, enemy.health() / max(1, me.strength()), gap, -enemy.gem_count())\n",
             "        score = (not attack_mask.is_set(enemy.position()), not interrupt, not killable, -enemy.gem_count(), enemy.health() / max(1, me.strength()), gap)\n")
        cfg.write_text(cfg.read_text() + "# Hunt carriers of HUNT_GEMS or more at HUNT_POWER of the local strength.\nHUNT_GEMS = 15\nHUNT_POWER = 0.8\n")
    elif change == "claimresp":
        # Champions see their allies' claims but not their captures, so each one
        # learns that a camp is respawning only by walking to it: up to a fifth
        # of a farmer's turns are travel, and a share of it ends on a respawning
        # camp. An ally whose claim moves straight from group G to another group
        # has just captured G or found it respawning, so G is marked respawning
        # for its full timer. A move to idle is a retreat, a bank trip or a death
        # and says nothing. A champion still walking to G re-chooses.
        b = src / "bot.py"
        edit(b, "        self.bank_progress = Progress(limit=10)\n",
             "        self.bank_progress = Progress(limit=10)\n        self.peer_claims = None\n        self.respawn_of = None\n")
        edit(b, "        enemies = [e for e in bc.vision.champions(bc.Team.ENEMY) if e.is_alive()]\n",
             "        self.infer_respawns()\n"
             "        enemies = [e for e in bc.vision.champions(bc.Team.ENEMY) if e.is_alive()]\n")
        edit(b, "    def farm(self, me, enemies):\n        objective = self.objective\n",
             "    def infer_respawns(self):\n"
             "        if self.respawn_of is None:\n"
             "            self.respawn_of = {g.__index__(): g.max_respawn_timer() for g in self.groups}\n"
             "        # Raw claim words: a support claim (Willow following a farmer) moves with\n"
             "        # its leader and says nothing about captures, so it counts as idle.\n"
             "        turn.check()\n"
             "        bc.shared_memory.read(0, self.team.buffer)\n"
             "        word = int.from_bytes(self.team.buffer, 'little')\n"
             "        claims = []\n"
             "        for i in range(len(self.team.allies)):\n"
             "            value = word >> (10 * i) & 1023\n"
             "            claims.append(-1 if value & 512 else (value & 511) - 1)\n"
             "        now = bc.round_number()\n"
             "        if self.peer_claims is not None:\n"
             "            for i, (before, after) in enumerate(zip(self.peer_claims, claims)):\n"
             "                if i != self.team.slot and before >= 0 and after >= 0 and after != before:\n"
             "                    until = now + self.respawn_of.get(before, 0)\n"
             "                    if until > self.respawns.get(before, 0):\n"
             "                        self.respawns[before] = until\n"
             "        self.peer_claims = claims\n\n"
             "    def farm(self, me, enemies):\n        objective = self.objective\n"
             "        if objective is not None and self.respawns.get(objective.handle, 0) > bc.round_number():\n"
             "            objective = None\n")
    elif re.fullmatch(r"raid(\d+)", change):
        # Monolith groups hold 35% of the gems on the 40 maps (mean 257 gems,
        # 24,086 health) and choose_group skipped them outright. The #1 team
        # clears 0.7 a game, three or more champions at once, median round 993,
        # for 167 gems a game -- 19% of its camp gems -- against our 21.
        st = src / "strategy.py"
        edit(st, "        if objective.monolith or respawns.get(handle, 0) > now:\n",
             "        if (objective.monolith and now < config.RAID_ROUND) or respawns.get(handle, 0) > now:\n")
        edit(st, "        clear = objective.hp / (damage * (min(objective.count, 3) if splash else 1) + helper_dps)\n",
             "        clear = objective.hp / (damage * (min(objective.count, 3) if splash else 1) + helper_dps)\n"
             "        # A monolith is a raid: costed with the allies already committed to it\n"
             "        # plus RAID_ASSUME expected to join, its time and its hits shared.\n"
             "        raiders = 1 + max(claimed.get(handle, 0), config.RAID_ASSUME) if objective.monolith else 1\n"
             "        clear /= raiders\n")
        edit(st, "        bias = (20 if objective.incoming < 70 else 5) if claimed.get(handle) else 0\n",
             "        bias = (20 if objective.incoming < 70 else 5) if claimed.get(handle) else 0\n"
             "        if objective.monolith:\n"
             "            # Pull teammates into a claimed raid instead of steering them off it.\n"
             "            bias = -config.RAID_PULL if claimed.get(handle) else 0\n")
        edit(st, "        risk = min(45, max(0, objective.incoming * clear * 0.55 / hp_budget - 0.7) * 12)\n",
             "        risk = min(45, max(0, objective.incoming / raiders * clear * 0.55 / hp_budget - 0.7) * 12)\n")
        edit(st, "        expected_damage = max(0, incoming * clear * 0.55 - heal_rate * clear)\n",
             "        raiders = 1 + max(claimed.get(objective.handle, 0), config.RAID_ASSUME) if objective.monolith else 1\n"
             "        expected_damage = max(0, incoming / raiders * clear * 0.55 - heal_rate * clear)\n")
        cfg.write_text(cfg.read_text() + (
            "# Monolith raids: eligible from RAID_ROUND, costed for 1 + RAID_ASSUME raiders\n"
            "# (or more if more have claimed it), and a claimed raid pulls teammates in.\n"
            f"RAID_ROUND = {int(change[len('raid'):])}\nRAID_ASSUME = 2\nRAID_PULL = 40\n"))
    elif re.fullmatch(r"safebank(\d+)", change):
        # A raid reward is 200 gems on one champion, and a kill hands the killer
        # everything carried. The first raid game collected 600 gems and lost all
        # 600 walking to the nearest altar. A big load goes home first: recall
        # when it is safe, back away from enemies until it is, then bank at the
        # home altar a few steps from spawn.
        edit(src / "bot.py",
             "    def bank(self, me, enemies, camps):\n        self.team.claim()\n",
             "    def bank(self, me, enemies, camps):\n        self.team.claim()\n"
             "        # Only while far from every altar: from spawn the home altar is close, so\n"
             "        # ordinary banking takes over instead of recalling again in a loop (the\n"
             "        # first version did, and two carriers ended a game holding 952 gems).\n"
             "        if me.gem_count() >= config.BIG_LOAD and self.altar_field.get(me.position()) > config.SAFE_BANK_DIST:\n"
             "            if self.recall_safe(me, enemies, camps):\n"
             "                turn.check()\n"
             "                me.recall()\n"
             "                return\n"
             "            for enemy in enemies:\n"
             "                turn.check()\n"
             "                if nav.distance(me.position(), enemy.position()) <= 6:\n"
             "                    nav.retreat(enemies, camps)\n"
             "                    return\n")
        cfg.write_text(cfg.read_text() + f"# Carriers of BIG_LOAD gems or more, further than SAFE_BANK_DIST from any\n# altar, recall home before banking.\nBIG_LOAD = {int(change[len('safebank'):])}\nSAFE_BANK_DIST = 8\n")
    elif re.fullmatch(r"heal(\d+)", change):
        # Spawn heals 100% of max health a round and a recall takes 5 rounds,
        # while a death costs 60. A hurt champion with nothing near it recalls to
        # heal instead of farming on at low health. Unlike the failed health gate,
        # this only fires when recall is already safe (no enemy within 6, no
        # awake camp in range), the same test the shopping recall uses.
        edit(src / "bot.py", "        ratio, threats = combat.local_power(",
             "        if (not at_spawn and me.health() < me.max_health() * config.HEAL_RECALL\n"
             "                and self.by_tile.get(me.position()) is None\n"
             "                and self.recall_safe(me, enemies, camps)):\n"
             "            # Never while standing on a camp's tiles: that is a capture in\n"
             "            # progress, and leaving it would forfeit a reward already earned.\n"
             "            self.status('heal')\n"
             "            self.objective = None\n"
             "            self.team.claim()\n"
             "            turn.check()\n"
             "            me.recall()\n"
             "            return\n"
             "        ratio, threats = combat.local_power(")
        cfg.write_text(cfg.read_text() + f"# Recall to heal below HEAL_RECALL of max health when recall is safe.\nHEAL_RECALL = {int(change[len('heal'):]) / 100}\n")
    elif change == "fieldresume":
        # On large maps a dash champion's travel field (a walking flood plus up
        # to eight jump layers) costs more fuel than a turn has left after
        # sensing, so choose_group was cut short at the same flood turn after
        # turn and the champion stood still: 11-35% of champion-turns on
        # 01the-farm, 01big-world and 01islands (timeprofile.py). The finished
        # layers now stay in a module global keyed by origin and mobility, and the
        # next turn resumes the flood where it stopped. The result is the same
        # field, layer for layer, so every choice it feeds is unchanged.
        n = src / "navigation.py"
        edit(n, "cost_key = None\ncost_cache = None\n",
             "cost_key = None\ncost_cache = None\n# (key, layers, union, done): a travel flood that a fuel suspension cut short.\nfield_partial = None\n")
        edit(n, "def layers_from(roots, radius, crystal=False, first=None, stop=None, camps=None):\n"
                "    \"\"\"Flood walking components, then add legal jump portals between them.\"\"\"\n",
             "def layers_from(roots, radius, crystal=False, first=None, stop=None, camps=None, partial=None):\n"
             "    \"\"\"Flood walking components, then add legal jump portals between them.\n\n"
             "    `partial` is a [key, layers, union, done] record that keeps the layers\n"
             "    finished so far across a fuel suspension; a later call resumes it.\n"
             "    \"\"\"\n")
        edit(n, "    if first is None:\n"
                "        reached, field = bc.Bitboard(), bc.DistanceField()\n"
                "        field.compute(walls, roots & ~walls, reached)\n"
                "    else:\n"
                "        field, reached = first\n"
                "    layers = [(field, reached)]\n"
                "    # Native |= mutates its left operand. Keep each layer's component mask\n"
                "    # independent from the cumulative frontier used by subsequent floods.\n"
                "    union = reached.copy()\n"
                "    if stop is not None and union.is_set(stop):\n"
                "        return layers, union\n"
                "    for _ in range(1 if crystal else 8):\n"
                "        turn.check()\n"
                "        frontier = expand(union, radius, path_walls) & ~walls & ~union\n"
                "        if frontier.is_empty():\n"
                "            break\n"
                "        field, reached = bc.DistanceField(), bc.Bitboard()\n"
                "        field.compute(walls, frontier, reached)\n"
                "        if reached.is_empty():\n"
                "            break\n"
                "        union |= reached\n"
                "        layers.append((field, reached))\n",
             "    if partial is not None:\n"
             "        layers, union = partial[1], partial[2]\n"
             "    else:\n"
             "        if first is None:\n"
             "            reached, field = bc.Bitboard(), bc.DistanceField()\n"
             "            field.compute(walls, roots & ~walls, reached)\n"
             "        else:\n"
             "            field, reached = first\n"
             "        layers = [(field, reached)]\n"
             "        # Native |= mutates its left operand. Keep each layer's component mask\n"
             "        # independent from the cumulative frontier used by subsequent floods.\n"
             "        union = reached.copy()\n"
             "    if stop is not None and union.is_set(stop):\n"
             "        return layers, union\n"
             "    while len(layers) <= (1 if crystal else 8) and not (partial is not None and partial[3]):\n"
             "        turn.check()\n"
             "        frontier = expand(union, radius, path_walls) & ~walls & ~union\n"
             "        if frontier.is_empty():\n"
             "            if partial is not None:\n"
             "                partial[3] = True\n"
             "            break\n"
             "        field, reached = bc.DistanceField(), bc.Bitboard()\n"
             "        field.compute(walls, frontier, reached)\n"
             "        if reached.is_empty():\n"
             "            if partial is not None:\n"
             "                partial[3] = True\n"
             "            break\n"
             "        # No turn.check() between these two lines: a resumed flood must\n"
             "        # see each layer in both the union and the list, or in neither.\n"
             "        union |= reached\n"
             "        layers.append((field, reached))\n")
        edit(n, "def field_from(position):\n"
                "    global cost_key, cost_cache\n",
             "def field_from(position):\n"
             "    global cost_key, cost_cache, field_partial\n")
        edit(n, "    if key == cost_key:\n"
                "        return cost_cache\n"
                "    field, reached = bc.DistanceField(), bc.Bitboard()\n"
                "    turn.check()\n"
                "    field.compute(static_walls(), around(position, 0), reached)\n"
                "    turn.check()\n"
                "    radius, crystal = mode\n"
                "    if radius:\n"
                "        layers, reached = layers_from(around(position, 0), radius, crystal, (field, reached))\n"
                "        result = TravelCosts(position, layers), reached\n"
                "    else:\n"
                "        result = field, reached\n"
                "    cost_key, cost_cache = key, result\n"
                "    return result\n",
             "    if key == cost_key:\n"
             "        return cost_cache\n"
             "    # A flood from this origin that fuel cut short resumes; any other is dropped.\n"
             "    if field_partial is None or field_partial[0] != key:\n"
             "        field, reached = bc.DistanceField(), bc.Bitboard()\n"
             "        turn.check()\n"
             "        field.compute(static_walls(), around(position, 0), reached)\n"
             "        field_partial = [key, [(field, reached)], reached.copy(), False]\n"
             "    turn.check()\n"
             "    radius, crystal = mode\n"
             "    if radius:\n"
             "        layers, reached = layers_from(around(position, 0), radius, crystal, partial=field_partial)\n"
             "        result = TravelCosts(position, layers), reached\n"
             "    else:\n"
             "        result = field_partial[1][0]\n"
             "    cost_key, cost_cache = key, result\n"
             "    field_partial = None\n"
             "    return result\n")
    elif change == "party":
        # Party maps (gs_cpp_party's rule, in Python): when every gem on the map
        # sits behind a monolith or a pack one champion cannot clear alone
        # (00contest: two monoliths; 00stampede: one herd of six elks), solo
        # selection skips all of it and the team scores nothing all game. Such a
        # map is played by the boss controller as a party, which gates every heavy
        # objective as it gates monoliths. It fires on those two maps of the 40;
        # in C++ it took them from 9 to 13 wins of 16.
        edit(src / "policy.py", "cached = None\n",
             "cached = None\n\n"
             "# A gem-bearing group one champion can clear alone: no monolith, and no more\n"
             "# combined strength than one golem. Clusters, wolves and a lone elk qualify.\n"
             "SOLO_STRENGTH = 120\n\n"
             "def party_map(groups):\n"
             "    \"\"\"Every gem sits behind a monolith or a pack that kills a lone farmer.\"\"\"\n"
             "    for g in groups:\n"
             "        if not g.gem_value():\n"
             "            continue\n"
             "        camps = g.camps()\n"
             "        if (not any(c.is_monolith() for c in camps)\n"
             "                and sum(c.base_stats().base_strength for c in camps) <= SOLO_STRENGTH):\n"
             "            return False\n"
             "    return True\n")
        edit(src / "policy.py", "            cached = 2\n        else:\n            cached = 0\n    return cached\n",
             "            cached = 2\n        elif party_map(groups):\n            cached = 3\n        else:\n            cached = 0\n    return cached\n\n"
             "def party():\n    \"\"\"Maps played by the party controller.\"\"\"\n    return kind() in (2, 3)\n")
        edit(src / "policy.py", "    variant = kind()\n    if variant == 2:\n", "    if party():\n")
        edit(src / "draft.py", "    if variant == 2:\n", "    if policy.party():\n")
        edit(src / "strategy.py", "        self.monolith = any(c.is_monolith() for c in self.camps)\n",
             "        self.monolith = any(c.is_monolith() for c in self.camps)\n"
             "        # A monolith, or more strength than one champion can clear alone.\n"
             "        self.heavy = self.monolith or self.incoming > 120\n")
        b = src / "boss.py"
        edit(b, "        claims = self.team.assignments()\n",
             "        # On party maps every heavy objective waits for the full party, not\n"
             "        # only monoliths: 00stampede's gems are a herd of six elks.\n"
             "        gated = (lambda o: o.heavy) if policy.kind() == 3 else (lambda o: o.monolith)\n"
             "        claims = self.team.assignments()\n")
        edit(b, "                          and (not o.monolith or now >= 650)\n"
                "                          and (not boss_ready or o.monolith)), None)\n",
             "                          and (not gated(o) or now >= 650)\n"
             "                          and (not boss_ready or gated(o))), None)\n")
        edit(b, "                if (self.respawns.get(o.handle, 0) > now or (o.monolith and not boss_ready)\n"
                "                        or (boss_ready and not o.monolith)):\n",
             "                if (self.respawns.get(o.handle, 0) > now or (gated(o) and not boss_ready)\n"
             "                        or (boss_ready and not gated(o))):\n")
        edit(b, "import turn\n", "import turn\nimport policy\n")
    elif change == "dangerskip":
        # On 01the-farm Vendetta finds every group too dangerous to clear alone,
        # but learns it only by scoring each one exactly, and scoring all of them
        # costs more fuel than a turn holds. choose_group never returned, so the
        # rally fallback never ran and Vendetta stood still from round 0 to the
        # end: 29% of our champion-turns on that map. The exact pass rejects an
        # unseen group on its design values, which the first pass already has,
        # so the first pass now drops it there. The exact pass sees the same
        # survivors in the same order: the same choice whenever fuel is not short.
        s = src / "strategy.py"
        edit(s, "    capture = bc.constants.CAPTURE_TIME\n    ranked = []\n",
             "    capture = bc.constants.CAPTURE_TIME\n    ranked = []\n    seen = bc.vision.visible_tiles()\n")
        edit(s, "        clear = objective.hp / (damage * (min(objective.count, 3) if splash else 1) + helper_dps)\n",
             "        clear = objective.hp / (damage * (min(objective.count, 3) if splash else 1) + helper_dps)\n"
             "        # The exact pass would reject this unseen group on these same values.\n"
             "        if (max(0, objective.incoming * clear * 0.55 - heal_rate * clear) > hp_budget\n"
             "                and (objective.spawns & seen).is_empty()):\n"
             "            continue\n")
    elif change == "reroll2":
        # A second, different decision-neutral perturbation, for an independent
        # re-roll when "reroll" has already been used in the selection.
        edit(src / "bot.py", "    def play_turn(self):\n        me = bc.me()\n",
             "    def play_turn(self):\n        me = bc.me()\n        _reroll2 = (me is None, 0)\n")
    elif change == "reroll":
        # Decision-identical: one extra statement per turn changes the fuel spent
        # and so re-rolls every trajectory, without changing any choice. A fresh
        # re-roll is the honest baseline for a bot that was itself selected as the
        # best on this pool (v93 sits about 19 gems above its own twin).
        edit(src / "bot.py", "    def play_turn(self):\n        me = bc.me()\n",
             "    def play_turn(self):\n        me = bc.me()\n        _reroll = me is None\n")
    else:
        sys.exit(f"unknown change {change}")


def build(name: str, changes: list[str] | None = None) -> None:
    """gs93_<change> builds one change; pass `changes` to stack several."""
    changes = changes or [name[len("gs93_"):]]
    dst = WS / "bots" / name
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(WS / "bots" / BASE, dst, ignore=shutil.ignore_patterns("__pycache__", ".cambc"))
    src = dst / "src"
    for change in changes:
        apply(src, change)
    main = src / "main.py"
    main.write_text(re.sub(r'print\("BOTTAG [^"]+", flush=True\)', f'print("BOTTAG {name}", flush=True)',
                           main.read_text(), count=1))
    for p in src.glob("*.py"):
        ast.parse(p.read_text())
    print(f"  {name}: {' + '.join(changes)}; parses, tagged")


ALL = ["gs93_hurt60", "gs93_willow_farm", "gs93_escort_safe", "gs93_travel60", "gs93_travel40",
       "gs93_bank36", "gs93_bank48", "gs93_bruiser", "gs93_items"]
if __name__ == "__main__":
    # mkfixes.py NAME=change+change ... stacks changes into one build.
    for n in sys.argv[1:] or ALL:
        if "=" in n:
            name, spec = n.split("=", 1)
            build(name, spec.split("+"))
        else:
            build(n)
