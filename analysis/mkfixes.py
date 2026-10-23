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
