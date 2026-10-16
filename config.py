"""Strategy knobs. Thresholds are hypotheses; use benchmark.py to compare changes."""
import cambc as bc

BANK_GEMS = 44
RETREAT_HEALTH = 0.35
CARRIER_RETREAT_HEALTH = 0.50
HEAL_MIN_MISSING = 120
ENEMY_RECALL_CLEARANCE = 7
LATE_GAME_ROUND = 1700
ALLOW_MONOLITH = False
ROLE_SPREAD_PENALTY = 3.0
DEBUG = False

# Ryth controls before Vendetta finishes. Changes take effect next round.
PRIORITY = {bc.ChampionType.RYTH: 30, bc.ChampionType.WILLOW: 40,
            bc.ChampionType.MARCELLA: 30, bc.ChampionType.VENDETTA: 20}

# Rotate purchases, keeping both damage and survivability. No Focus on Vendetta.
I = bc.ItemType
BUILDS = {
    bc.ChampionType.RYTH: (I.MONSTER_SHARD_OF_STRENGTH, I.DURABILITY_SHARD_OF_HEALTH),
    bc.ChampionType.VENDETTA: (I.MONSTER_SHARD_OF_STRENGTH, I.DURABILITY_SHARD_OF_HEALTH),
    bc.ChampionType.WILLOW: (I.MONSTER_SHARD_OF_STRENGTH, I.DURABILITY_SHARD_OF_HEALTH),
    bc.ChampionType.MARCELLA: (I.MONSTER_SHARD_OF_STRENGTH, I.DURABILITY_SHARD_OF_HEALTH),
    bc.ChampionType.VARG: (I.MONSTER_SHARD_OF_STRENGTH, I.DURABILITY_SHARD_OF_HEALTH),
}
DEFAULT_BUILD = (I.MONSTER_SHARD_OF_STRENGTH, I.DURABILITY_SHARD_OF_HEALTH)
