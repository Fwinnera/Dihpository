"""Tuning shared by the controller, economy and combat planner."""
import cambc as bc

BANK_GEMS = 24
RETREAT_HEALTH = 0.30
CARRIER_RETREAT_HEALTH = 0.43
HEAL_MIN_MISSING = 120
SHOP_GOLD = 150
SHOP_INTERVAL = 70
DEBUG = False
PRIORITY = {bc.ChampionType.WILLOW: 50, bc.ChampionType.RYTH: 40, bc.ChampionType.VARG: 30,
            bc.ChampionType.MARCELLA: 30, bc.ChampionType.VENDETTA: 20}
I = bc.ItemType
# Each entry completes one emblem. Duplicate passives do not stack, so each
# passive family is worth one emblem and no more. Treasure leads because it is
# the only one that compounds: 20% more gold gained is worth the whole remaining
# game, so its value decays with every round it is delayed. The others are flat.
# Measured over 470 ladder games we earned 4,535 gold against the opponents'
# 9,964 while spending 94% of it, so the deficit is income, not discipline.
DEFAULT_BUILD = (I.TREASURE_SHARD_OF_STRENGTH, I.JUNGLE_SHARD_OF_STRENGTH,
                 I.MONSTER_SHARD_OF_STRENGTH, I.DURABILITY_SHARD_OF_HEALTH)
BUILDS = {bc.ChampionType.WILLOW: (I.TREASURE_SHARD_OF_FOCUS,
          I.JUNGLE_SHARD_OF_FOCUS, I.DURABILITY_SHARD_OF_HEALTH,
          I.POWER_SHARD_OF_FOCUS)}
