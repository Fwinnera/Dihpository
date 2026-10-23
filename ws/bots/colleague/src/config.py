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
# Each entry completes one emblem. Duplicate passives do not stack, so the
# permanent late-game purchase is Power rather than another Monster emblem.
DEFAULT_BUILD = (I.MONSTER_SHARD_OF_STRENGTH, I.JUNGLE_SHARD_OF_HEALTH,
                 I.DURABILITY_SHARD_OF_STRENGTH)
BUILDS = {bc.ChampionType.RYTH: (I.MONSTER_SHARD_OF_STRENGTH,
          I.JUNGLE_SHARD_OF_HEALTH, I.DURABILITY_SHARD_OF_HEALTH)}
