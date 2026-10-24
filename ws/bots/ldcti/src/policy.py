"""Choose a controller from terrain and producer structure, never map names."""
import cambc as bc
from cambc import game_map as gm
cached = None

# A gem-bearing group one champion can clear alone: no monolith, and no more
# combined strength than one golem. Clusters, wolves and a lone elk qualify.
SOLO_STRENGTH = 120

def party_map(groups):
    """Every gem sits behind a monolith or a pack that kills a lone farmer."""
    for g in groups:
        if not g.gem_value():
            continue
        camps = g.camps()
        if (not any(c.is_monolith() for c in camps)
                and sum(c.base_stats().base_strength for c in camps) <= SOLO_STRENGTH):
            return False
    return True

def kind():
    global cached
    if cached is None:
        groups = gm.camp_groups()
        if gm.altars().count() == 1 and any(c.is_monolith() for g in groups for c in g.camps()):
            cached = 2
        elif party_map(groups):
            cached = 3
        else:
            cached = 0
    return cached

def party():
    """Maps played by the party controller."""
    return kind() in (2, 3)

def create_bot():
    if party():
        from boss import BossBot
        return BossBot()
    if bc.me().champion_name() == bc.ChampionType.HEART_OF_RUIN:
        from escort import TankBot
        return TankBot()
    if bc.me().champion_name() == bc.ChampionType.WILLOW:
        from escort import EscortBot
        return EscortBot()
    from bot import Bot
    return Bot()
