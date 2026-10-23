"""Choose a controller from terrain and producer structure, never map names."""
import cambc as bc
from cambc import game_map as gm
cached = None

def kind():
    global cached
    if cached is None:
        groups = gm.camp_groups()
        if gm.altars().count() == 1 and any(c.is_monolith() for g in groups for c in g.camps()):
            cached = 2
        else:
            cached = 0
    return cached

def create_bot():
    variant = kind()
    if variant == 2:
        from boss import BossBot
        return BossBot()
    # Willow farms like everyone else. As an escort she banked 4% of the team's
    # gems and spent 5.7% of the game farming; heal_allies still runs every turn.
    from bot import Bot
    return Bot()
