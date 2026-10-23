"""Native path fields, legal short dashes, and threat-aware withdrawal."""
import cambc as bc
from cambc import game_map as gm
import turn

terrain = None
last_ward = -100
last_field = None
route_goals = None
route_layers = None
route_mode = None
route_camps = None
crystal_needed = None
cost_key = None
cost_cache = None

def needs_crystal():
    global crystal_needed
    if crystal_needed is None:
        field, reached = bc.DistanceField(), bc.Bitboard()
        field.compute(static_walls(), gm.spawn_region(bc.Team.ALLY), reached)
        crystal_needed = any(not (g.spawn_tiles() & ~reached).is_empty() for g in gm.camp_groups())
        if not crystal_needed and gm.altars().count() == 1:
            crystal_needed = any(c.is_monolith() for g in gm.camp_groups() for c in g.camps())
    return crystal_needed

def mobility():
    me = bc.me()
    if any(a.is_dash() for a in me.abilities()):
        return 2, False
    if any(c.kind() == bc.ConsumableType.TP_CRYSTAL and c.count() for c in me.consumables()):
        return 3, True
    return 0, False

def expand(mask, radius, path_walls):
    """Native eight-neighbour dilation; every intermediate dash step is legal."""
    result = mask
    for _ in range(radius):
        horizontal = result | result.shift_right(1) | result.shift_right(-1)
        result = (horizontal | horizontal.shift_up(1) | horizontal.shift_up(-1)) & ~path_walls
    return result

def layers_from(roots, radius, crystal=False, first=None, stop=None, camps=None):
    """Flood walking components, then add legal jump portals between them."""
    walls = static_walls()
    path_walls = (bc.Bitboard() if crystal else
                  gm.walls() | gm.altars() | gm.spawn_region(bc.Team.ENEMY))
    if camps is not None:
        walls = walls | camps
        if not crystal:
            path_walls = path_walls | camps
    if first is None:
        reached, field = bc.Bitboard(), bc.DistanceField()
        field.compute(walls, roots & ~walls, reached)
    else:
        field, reached = first
    layers = [(field, reached)]
    # Native |= mutates its left operand. Keep each layer's component mask
    # independent from the cumulative frontier used by subsequent floods.
    union = reached.copy()
    if stop is not None and union.is_set(stop):
        return layers, union
    for _ in range(1 if crystal else 8):
        turn.check()
        frontier = expand(union, radius, path_walls) & ~walls & ~union
        if frontier.is_empty():
            break
        field, reached = bc.DistanceField(), bc.Bitboard()
        field.compute(walls, frontier, reached)
        if reached.is_empty():
            break
        union |= reached
        layers.append((field, reached))
        if stop is not None and union.is_set(stop):
            break
    return layers, union

class TravelCosts:
    def __init__(self, origin, layers):
        self.origin, self.layers = origin, layers
    def get(self, position):
        for index, (field, reached) in enumerate(self.layers):
            if reached.is_set(position):
                return max(distance(self.origin, position), field.get(position) + index * 8)
        return 65535

def distance(a, b):
    return a.chebyshev_distance(b)

def around(position, radius):
    turn.check()
    result = bc.Bitboard()
    result.draw_chebyshev(position, radius)
    return result

def static_walls():
    global terrain
    if terrain is None:
        terrain = gm.walls() | gm.holes() | gm.altars() | gm.spawn_region(bc.Team.ENEMY)
    return terrain

def blocked():
    mask = (static_walls() | bc.vision.champion_tiles() | bc.vision.camp_tiles()
            | bc.vision.teleport_tiles())
    position = bc.me().position()
    turn.check()
    mask.set(position, False)
    return mask

def field_from(position):
    global cost_key, cost_cache
    # Terrain distances depend only on origin and mobility. Preparation,
    # solo selection and a possible rally can all reuse this expensive flood.
    mode = mobility()
    key = (position.x, position.y, mode)
    if key == cost_key:
        return cost_cache
    field, reached = bc.DistanceField(), bc.Bitboard()
    turn.check()
    field.compute(static_walls(), around(position, 0), reached)
    turn.check()
    radius, crystal = mode
    if radius:
        layers, reached = layers_from(around(position, 0), radius, crystal, (field, reached))
        result = TravelCosts(position, layers), reached
    else:
        result = field, reached
    cost_key, cost_cache = key, result
    return result

def cross_component(goals, extra_blocked=None):
    global route_goals, route_layers, route_mode, route_camps
    turn.check()
    me = bc.me()
    if not me.is_alive():
        return False
    radius, crystal = mobility()
    if not radius:
        return False
    mode = (radius, crystal)
    camps = bc.vision.camp_tiles()
    origin = me.position()
    turn.check()
    if not (0 <= origin.x < gm.width() and 0 <= origin.y < gm.height()):
        return False
    # A camp can occupy the only apparent portal. Keep it out of both the
    # walking flood and every intermediate dash step, not just the landing.
    rebuild = (route_goals is None or goals != route_goals or route_mode != mode
               or camps != route_camps
               or not any(reach.is_set(origin) for _, reach in route_layers))
    if rebuild:
        route_layers, reached = layers_from(goals, radius, crystal, stop=origin, camps=camps)
        route_goals, route_mode = goals.copy(), mode
        route_camps = camps.copy()
    turn.check()
    if not me.is_alive():
        return False
    origin = me.position()
    turn.check()
    if not (0 <= origin.x < gm.width() and 0 <= origin.y < gm.height()):
        return False
    layer = next((i for i, (_, reach) in enumerate(route_layers) if reach.is_set(origin)), None)
    if layer is None or layer == 0:
        return False
    field, reach = route_layers[layer]
    previous = route_layers[layer - 1][1]
    path_walls = (gm.walls() | gm.altars() | gm.spawn_region(bc.Team.ENEMY)
                  | bc.vision.champion_tiles() | bc.vision.camp_tiles()
                  | bc.vision.teleport_tiles())
    path_walls.set(origin, False)
    possible = (around(origin, radius) if crystal else path_walls.reachable_tiles(origin, radius))
    landings = possible & previous & ~blocked()
    if extra_blocked is not None:
        landings &= ~extra_blocked
    candidates = landings.positions()
    candidates.sort(key=route_layers[layer - 1][0].get)
    if candidates:
        if crystal:
            consumable = next(c for c in me.consumables() if c.kind() == bc.ConsumableType.TP_CRYSTAL)
            turn.check()
            if consumable.use(candidates[0]):
                return True
        else:
            for ability in me.abilities():
                if ability.is_dash() and ability.is_ready() and turn.may_cast(ability):
                    for p in candidates:
                        turn.check()
                        if ability.use(p):
                            return True
    # Walk to a portal, then wait for our dash rather than oscillating on shore.
    if me.can_move():
        for delta in field.next_moves_from(origin):
            turn.check()
            p = origin + delta
            if not blocked().is_set(p) and (extra_blocked is None or not extra_blocked.is_set(p)):
                if me.move(delta):
                    turn.walked = True
                    return True
    return field.get(origin) == 0

def teleport_past_blocker(goals, extra_blocked=None):
    """Bypass a camp choke without pretending that dashes can pass through units."""
    me = bc.me()
    if bc.BuffRestrictions.CONSUMABLE in me.restrictions():
        return False
    crystal = next((c for c in me.consumables()
                    if c.kind() == bc.ConsumableType.TP_CRYSTAL and c.count()), None)
    if crystal is None:
        return False
    field, reached = bc.DistanceField(), bc.Bitboard()
    field.compute(static_walls(), goals & ~static_walls(), reached)
    turn.check()
    if not me.is_alive():
        return False
    origin = me.position()
    candidates = around(origin, 3) & ~blocked()
    if extra_blocked is not None:
        candidates &= ~extra_blocked
    for p in sorted(candidates.positions(), key=field.get):
        if not reached.is_set(p) or field.get(p) >= field.get(origin) - 2:
            break
        turn.check()
        if crystal.use(p):
            return True
    return False

def scout(field):
    global last_ward
    me = bc.me()
    if (bc.round_number() - last_ward < 6 or me.ward_cooldown()
            or bc.BuffRestrictions.WARD in me.restrictions()):
        return
    tiles = (me.ward_placement_tiles() & bc.vision.visible_tiles()
             & ~static_walls() & ~bc.vision.ward_tiles(bc.Team.ALLY)).positions()
    if not tiles:
        return
    p = min(tiles, key=field.get)
    old = me.ward_positions()
    if old and distance(old[0], p) < 3:
        return
    turn.check()
    if me.place_ward(p):
        last_ward = bc.round_number()

def dash(field, walls):
    me = bc.me()
    if not me.can_cast():
        return False
    origin = me.position()
    start = field.get(origin)
    for ability in me.abilities():
        if not ability.is_dash() or not ability.is_ready() or not turn.may_cast(ability):
            continue
        # A dash can cross a hole, but cannot cross a wall or land on an
        # occupied/impassable tile. Compute the actual two-step path mask.
        path_walls = (gm.walls() | gm.altars() | gm.spawn_region(bc.Team.ENEMY)
                      | bc.vision.champion_tiles() | bc.vision.camp_tiles()
                      | bc.vision.teleport_tiles())
        path_walls.set(origin, False)
        landings = (path_walls.reachable_tiles(origin, int(ability.info().range))
                    & ability.valid_tiles() & ~walls).positions()
        landings.sort(key=field.get)
        for p in landings:
            if field.get(p) > start - 2:
                break
            turn.check()
            if not blocked().is_set(p) and ability.use(p):
                return True
    return False

def move_to(goals, extra_blocked=None, use_dash=True):
    global last_field
    turn.check()
    me = bc.me()
    if not me.is_alive():
        return False
    origin = me.position()
    if goals.is_set(origin):
        return False
    if not me.can_move() and not me.can_cast():
        return False
    walls = blocked()
    if extra_blocked is not None:
        walls |= extra_blocked
        walls.set(origin, False)
    legal = goals & ~walls
    if legal.is_empty():
        return False
    field, reached = bc.DistanceField(), bc.Bitboard()
    field.compute_to(walls, legal, around(origin, 0), reached)
    turn.check()
    if not reached.is_set(origin):
        return cross_component(goals, extra_blocked) or teleport_past_blocker(goals, extra_blocked)
    moved = use_dash and dash(field, walls)
    if moved:
        origin = me.position()
        if goals.is_set(origin):
            return True
    if me.can_move():
        for delta in field.next_moves_from(origin):
            turn.check()
            if not blocked().is_set(origin + delta) and me.move(delta):
                turn.walked = True
                moved = True
                break
    last_field = field
    return bool(moved)

def threat_mask(enemies, camps, margin=0):
    mask = bc.Bitboard()
    for enemy in enemies:
        if not enemy.is_visible() or not enemy.is_alive():
            continue
        mask |= around(enemy.position(), max(4, enemy.attack_range()) + margin)
    for camp in camps:
        if camp.is_visible() and camp.strength() > 0 and camp.is_awake():
            mask |= around(camp.position(), camp.attack_range())
    return mask

def retreat(enemies, camps):
    me = bc.me()
    if move_to(gm.spawn_region(bc.Team.ALLY), threat_mask(enemies, camps, 1)):
        return True
    if not me.can_move() and not me.can_cast():
        return False
    origin = me.position()
    threats = [(e.position(), max(4, e.attack_range()), e.strength()) for e in enemies if e.is_visible() and e.is_alive()]
    threats += [(c.spawn_position(), c.attack_range(), c.strength()) for c in camps
                if c.is_visible() and c.strength() > 0 and c.is_awake()]
    home = gm.spawn_region(bc.Team.ALLY).positions()
    walls = blocked()
    candidates = walls.reachable_tiles(origin, 1).positions()
    def risk(p):
        damage = sum(s for q, r, s in threats if distance(p, q) <= r)
        gap = min((distance(p, q) - r for q, r, s in threats), default=10)
        return (damage, -gap, min(distance(p, h) for h in home))
    best = min(candidates, key=risk, default=origin)
    # Build a gradient towards the best escape square so dashes can also escape.
    if best != origin:
        return move_to(around(best, 0))
    return False


def finish_turn():
    # A carried lock denies enemy tributes and cancels an existing channel.
    me = bc.me()
    if (me.is_alive() and not me.is_recalling() and not me.is_submitting_gems()
            and not me.is_teleporting() and bc.fuel_remaining() > 400_000
            and bc.BuffRestrictions.CONSUMABLE not in me.restrictions()):
        lock = next((c for c in me.consumables() if c.kind() == bc.ConsumableType.ALTAR_LOCK and c.count()), None)
        if lock is not None:
            visible = bc.vision.visible_tiles()
            for altar in gm.altars().positions():
                if (distance(me.position(), altar) <= 2 and visible.is_set(altar)
                        and not bc.vision.has_altar_lock(altar)):
                    turn.check()
                    lock.use(altar)
                    break
    # Relocating a ward can remove vision. Do it after every decision/action.
    me = bc.me()
    if (last_field is not None and me.is_alive() and not me.is_recalling()
            and not me.is_submitting_gems() and not me.is_teleporting()
            and bc.fuel_remaining() > 200_000):
        turn.check()
        scout(last_field)


def park_nearby(forbidden):
    """Release task endpoints; a large region may need several ordinary steps."""
    turn.check()
    me = bc.me()
    if not me.is_alive() or not me.can_move():
        return False
    return move_to(around(me.position(),4) & ~forbidden, use_dash=False)
