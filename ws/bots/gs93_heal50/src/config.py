"""Tuning shared by the controller, economy and combat planner."""
import cambc as bc

BANK_GEMS = 24
RETREAT_HEALTH = 0.30
CARRIER_RETREAT_HEALTH = 0.43
HEAL_MIN_MISSING = 120
SHOP_GOLD = 150
SHOP_INTERVAL = 70

# Leave a fight when our side's health-times-strength within DISENGAGE_RADIUS
# falls below DISENGAGE_RATIO of theirs, and stay out until it recovers past the
# ratio plus DISENGAGE_HYSTERESIS. Rebuilding all 15,225 ladder kills found 14.6
# fights a game at 8% odds or worse, because retreat counted health and camps
# only: a champion stayed in a lost fight until 30% health and, at move speed 1
# like everyone else, could not get out from there.
DISENGAGE_RATIO = 0.5
DISENGAGE_HYSTERESIS = 0.2
DISENGAGE_RADIUS = 5
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
# Recall to heal below HEAL_RECALL of max health when recall is safe.
HEAL_RECALL = 0.5
