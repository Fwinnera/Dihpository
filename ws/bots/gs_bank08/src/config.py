"""Tuning shared by the controller, economy and combat planner."""
import cambc as bc

# Lowered from 24. In the 34 ladder games where we submitted under 60 gems while
# collecting 80 or more, the ledger balances exactly: 127 collected, 99 lost to
# deaths, 1 still carried, and 1.0 deposits in the whole game. Five champions
# collecting 127 gems reach about 25 each, so a threshold of 24 means they are
# killed at twenty, just short of it, over and over.
BANK_GEMS = 8
RETREAT_HEALTH = 0.30
CARRIER_RETREAT_HEALTH = 0.43
HEAL_MIN_MISSING = 120
SHOP_GOLD = 150
SHOP_INTERVAL = 70
DEBUG = False
PRIORITY = {bc.ChampionType.WILLOW: 50, bc.ChampionType.RYTH: 40, bc.ChampionType.VARG: 30,
            bc.ChampionType.MARCELLA: 30, bc.ChampionType.VENDETTA: 20}
I = bc.ItemType
# Each entry completes one emblem. Duplicate passives do not stack, so the
# permanent late-game purchase is Power rather than another Monster emblem.
DEFAULT_BUILD = (I.JUNGLE_SHARD_OF_STRENGTH, I.MONSTER_SHARD_OF_STRENGTH,
                 I.DURABILITY_SHARD_OF_HEALTH)
BUILDS = {bc.ChampionType.WILLOW: (I.JUNGLE_SHARD_OF_FOCUS,
          I.DURABILITY_SHARD_OF_HEALTH, I.POWER_SHARD_OF_FOCUS)}
