"""Build the shop variants from pristine greatsage, each one a named arm."""
import ast, shutil, sys
from pathlib import Path

WS = Path("/Users/faeezaullyar/Claude/battlecode/ws")
SRC = WS / "bots/greatsage"

OLD_COMMENT = """# Each entry completes one emblem. Duplicate passives do not stack, so the
# permanent late-game purchase is Power rather than another Monster emblem."""
OLD_DEFAULT = """DEFAULT_BUILD = (I.JUNGLE_SHARD_OF_STRENGTH, I.MONSTER_SHARD_OF_STRENGTH,
                 I.DURABILITY_SHARD_OF_HEALTH)"""
OLD_WILLOW = """BUILDS = {bc.ChampionType.WILLOW: (I.JUNGLE_SHARD_OF_FOCUS,
          I.DURABILITY_SHARD_OF_HEALTH, I.POWER_SHARD_OF_FOCUS)}"""

TREASURE_COMMENT = """# Each entry completes one emblem. Duplicate passives do not stack, so each
# passive family is worth one emblem and no more. Treasure leads because it is
# the only one that compounds: 20% more gold gained is worth the whole remaining
# game, so its value decays with every round it is delayed. The others are flat.
# Measured over 470 ladder games we earned 4,535 gold against the opponents'
# 9,964 while spending 94% of it, so the deficit is income, not discipline."""

VARIANTS = {
    # Fallback only. Power buys a sixth shard's worth of one stat for 150 gold;
    # Bruiser buys a fifth plus one of each other stat, so seven points for the
    # same price and no passive given up, since Power has none either.
    "gs_bruiser": [("bot.py",
                    "bc.ItemType.POWER_SHARD_OF_HEALTH",
                    "bc.ItemType.BRUISER_SHARD_OF_HEALTH"),
                   ("bot.py",
                    "bc.ItemType.POWER_SHARD_OF_STRENGTH",
                    "bc.ItemType.BRUISER_SHARD_OF_STRENGTH")],
    # Opening only: reach Treasure at all.
    "gs_treasure": [("config.py", OLD_COMMENT, TREASURE_COMMENT),
                    ("config.py", OLD_DEFAULT,
                     "DEFAULT_BUILD = (I.TREASURE_SHARD_OF_STRENGTH, I.JUNGLE_SHARD_OF_STRENGTH,\n"
                     "                 I.MONSTER_SHARD_OF_STRENGTH, I.DURABILITY_SHARD_OF_HEALTH)"),
                    ("config.py", OLD_WILLOW,
                     "BUILDS = {bc.ChampionType.WILLOW: (I.TREASURE_SHARD_OF_FOCUS,\n"
                     "          I.JUNGLE_SHARD_OF_FOCUS, I.DURABILITY_SHARD_OF_HEALTH,\n"
                     "          I.POWER_SHARD_OF_FOCUS)}")],
}
# Both of the above.
VARIANTS["gs_shop"] = VARIANTS["gs_treasure"] + VARIANTS["gs_bruiser"]
# Every passive family once, then Bruiser.
VARIANTS["gs_shop5"] = [
    ("config.py", OLD_COMMENT, TREASURE_COMMENT),
    ("config.py", OLD_DEFAULT,
     "DEFAULT_BUILD = (I.TREASURE_SHARD_OF_STRENGTH, I.JUNGLE_SHARD_OF_STRENGTH,\n"
     "                 I.DURABILITY_SHARD_OF_HEALTH, I.MONSTER_SHARD_OF_STRENGTH,\n"
     "                 I.HOME_SHARD_OF_STRENGTH)"),
    ("config.py", OLD_WILLOW,
     "BUILDS = {bc.ChampionType.WILLOW: (I.TREASURE_SHARD_OF_FOCUS,\n"
     "          I.JUNGLE_SHARD_OF_FOCUS, I.DURABILITY_SHARD_OF_HEALTH,\n"
     "          I.MONSTER_SHARD_OF_FOCUS, I.HOME_SHARD_OF_FOCUS)}"),
] + VARIANTS["gs_bruiser"]

for name, edits in VARIANTS.items():
    dst = WS / "bots" / name
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(SRC, dst)
    for fn, old, new in edits:
        p = dst / "src" / fn
        t = p.read_text()
        if old not in t:
            sys.exit(f"{name}: pattern not found in {fn}: {old[:60]!r}")
        p.write_text(t.replace(old, new, 1))
    # A build that does not parse is silently replaced by the previous bot on
    # the platform, which has already cost us eighty wasted ladder games.
    for p in (dst / "src").glob("*.py"):
        ast.parse(p.read_text())
    # And tag it, so a replay proves which arm actually ran.
    m = dst / "src/main.py"
    t = m.read_text()
    m.write_text(t.replace("def main():", f'def main():\n    print("BOTTAG {name}", flush=True)\n', 1))
    ast.parse(m.read_text())
    print(f"  {name}: {len(edits)} edits, parses, tagged")
