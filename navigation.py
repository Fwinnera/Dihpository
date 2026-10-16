"""Native shortest-path fields, with terrain and currently visible occupants."""
import cambc as bc
import turn
from cambc import game_map as gm


def distance(a, b):
    return a.chebyshev_distance(b)


def around(position, radius):
    mask = bc.Bitboard()
    mask.draw_chebyshev(position, radius)
    return mask


def blocked():
    mask = (gm.walls() | gm.holes() | gm.altars() | gm.spawn_region(bc.Team.ENEMY)
            | bc.vision.champion_tiles() | bc.vision.camp_tiles()
            | bc.vision.teleport_tiles())
    mask.set(bc.me().position(), False)
    return mask


def move_to(goals, extra_blocked=None):
    turn.check()
    me = bc.me()
    origin = me.position()
    if not me.can_move() or goals.is_set(origin):
        return False
    walls = blocked()
    if extra_blocked is not None:
        walls |= extra_blocked
        walls.set(origin, False)
    legal_goals = goals & ~walls
    if legal_goals.is_empty():
        return False
    field = bc.DistanceField()
    field.compute_to(walls, legal_goals, around(origin, 0), bc.Bitboard())
    # Retry another equally short step if an unseen enemy blocks the first one.
    for delta in field.next_moves_from(origin):
        turn.check()
        if not blocked().is_set(origin + delta) and me.move(delta):
            turn.walked = True
            return True
    return False


def threat_mask(enemies, camps):
    mask = bc.Bitboard()
    for enemy in enemies:
        mask |= around(enemy.position(), max(4, enemy.attack_range()) + 1)
    for camp in camps:
        if camp.strength() > 0:
            mask |= around(camp.position(), camp.attack_range())
    return mask


def retreat(enemies, camps):
    """Try a safe route home, then a legal step that creates more separation."""
    me = bc.me()
    if move_to(gm.spawn_region(bc.Team.ALLY), threat_mask(enemies, camps)):
        return True
    if not me.can_move():
        return False
    threats = [unit.position() for unit in (*enemies, *camps) if unit.strength() > 0]
    home = gm.spawn_region(bc.Team.ALLY).positions()
    origin = me.position()
    candidates = blocked().reachable_tiles(origin, me.base_stats().base_move_speed).positions()
    candidates.sort(key=lambda p: (
        -min((distance(p, t) for t in threats), default=100),
        min(distance(p, s) for s in home)))
    for step in candidates:
        turn.check()
        if step != origin and me.move_absolute(step):
            turn.walked = True
            return True
    return False
