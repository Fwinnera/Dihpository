"""Route-aware camp utility, live reward checks, and score-aware banking."""
import cambc as bc
from cambc import game_map as gm
import config
import turn
import navigation as nav

class Objective:
    def __init__(self, group):
        self.group = group
        self.handle = group.__index__()
        self.spawns = group.spawn_tiles()
        self.positions = self.spawns.positions()
        self.coords = tuple((p.x, p.y) for p in self.positions)
        self.count = len(self.positions)
        self.camps = group.camps()
        self.hp = sum(c.base_stats().base_health for c in self.camps)
        self.incoming = sum(c.base_stats().base_strength for c in self.camps)
        self.gems, self.gold = group.gem_value(), group.gold_value()
        self.monolith = any(c.is_monolith() for c in self.camps)
        # A monolith, or more strength than one champion can clear alone.
        self.heavy = self.monolith or self.incoming > 120

mono_share = None

def monolith_share():
    """The share of the map's gems held by monolith groups, computed once."""
    global mono_share
    if mono_share is None:
        total = mono = 0
        for g in gm.camp_groups():
            gems = g.gem_value()
            total += gems
            if any(c.is_monolith() for c in g.camps()):
                mono += gems
        mono_share = mono / max(1, total)
    return mono_share

def prepare(groups):
    field, reached = nav.field_from(bc.me().position())
    return [Objective(g) for g in groups
            if any(reached.is_set(p) for p in g.spawn_tiles().positions())]

def dps(me, count=1):
    strength = me.strength()
    damage = strength
    for ability in me.abilities():
        info = ability.info()
        if info is None:
            continue
        if ability.is_attack_reset():
            damage += strength / 8
        elif ability.is_damage() or ability.is_cc() or ability.is_aoe_damage():
            damage += info.modifier * me.focus() / 8 * (min(count, 3) if ability.is_aoe_damage() else 1)
    if me.champion_name() == bc.ChampionType.VARG:
        damage *= min(count, 3)
    return max(1, damage)

def should_bank(enemies, altar_distance):
    me = bc.me()
    gems = me.gem_count()
    if not gems:
        return False
    now = bc.round_number()
    ticks = (gems + 9) // 10
    ours = bc.global_submitted_gems(bc.Team.ALLY)
    theirs = bc.global_submitted_gems(bc.Team.ENEMY)
    # The race: gems carried when the game ends are worth nothing.
    if gems >= config.RACE_MIN and (theirs >= bc.constants.WINNING_GEMS - config.RACE_ENEMY
                                    or ours >= bc.constants.WINNING_GEMS - config.RACE_OURS):
        return True
    carried = gems
    for ally in bc.champions(bc.Team.ALLY):
        if ally != me and ally.is_alive() and ally.is_visible():
            carried += ally.gem_count()
    if ours + carried >= bc.constants.WINNING_GEMS:
        return True
    return (gems >= config.BANK_GEMS
            or (gems >= 22 and altar_distance <= 4)
            or bc.global_submitted_gems(bc.Team.ALLY) + gems >= bc.constants.WINNING_GEMS
            or now + altar_distance + ticks + 20 >= bc.constants.MAX_ROUNDS
            or (enemies and gems >= 22 and me.health() < me.max_health() * 0.70))

# Set while a choose_group call is running; a fuel Replan leaves it set, and
# the same champion's next call then takes the cheap path.
stalled = False

def choose_group(metadata, me, respawns, current, team, enemies):
    global stalled
    cheap, stalled = stalled, True
    now = bc.round_number()
    position = me.position()
    x, y = position.x, position.y
    damage = dps(me)
    splash = me.champion_name() == bc.ChampionType.VARG
    hp_budget = max(100, me.health() - me.max_health() * 0.20)
    heal_rate, helper_dps = 0, 0
    if splash:
        for ally in team.allies:
            if (ally != me and ally.champion_name() == bc.ChampionType.WILLOW
                    and ally.is_alive() and ally.is_visible()
                    and nav.distance(position, ally.position()) <= 8):
                helper_dps += ally.strength() * 0.8
                for ability in ally.abilities():
                    if ability.is_heal():
                        heal_rate += ability.heal_amount() / max(1, ability.info().max_cooldown)
    claims = team.assignments()
    claimed = {}
    for i, handle in enumerate(claims):
        if i != team.slot:
            claimed[handle] = claimed.get(handle, 0) + 1
    # Bound Python work before asking the native pathfinder for exact costs.
    # Evaluating every live group exhausts the turn on maps with 40+ groups.
    # Exact route evaluation is an anytime search: return the best objective
    # before the reserve for movement and combat is spent.
    capture = bc.constants.CAPTURE_TIME
    ranked = []
    seen = bc.vision.visible_tiles() if cheap else None
    for i, objective in enumerate(metadata):
        if i % 8 == 0:
            turn.check()
        handle = objective.handle
        if (objective.monolith and (now < config.RAID_ROUND or monolith_share() < config.RAID_SHARE)) or respawns.get(handle, 0) > now:
            continue
        if cheap:
            # The exact pass would reject this unseen group on these same values.
            clear = objective.hp / (damage * (min(objective.count, 3) if splash else 1) + helper_dps)
            if (max(0, objective.incoming * clear * 0.55 - heal_rate * clear) > hp_budget
                    and (objective.spawns & seen).is_empty()):
                continue
        travel = 10000
        for px, py in objective.coords:
            dx, dy = x - px, y - py
            if dx < 0:
                dx = -dx
            if dy < 0:
                dy = -dy
            gap = dx if dx > dy else dy
            if gap < travel:
                travel = gap
        clear = objective.hp / (damage * (min(objective.count, 3) if splash else 1) + helper_dps)
        # A monolith is a raid: costed with the allies already committed to it
        # plus RAID_ASSUME expected to join, its time and its hits shared.
        raiders = 1 + max(claimed.get(handle, 0), config.RAID_ASSUME) if objective.monolith else 1
        clear /= raiders
        value = objective.gems + objective.gold * (0.3 if now < 500 else 0.25)
        cost = (clear + capture) * 100 / max(1, value)
        bias = (20 if objective.incoming < 70 else 5) if claimed.get(handle) else 0
        if objective.monolith:
            # Pull teammates into a claimed raid instead of steering them off it.
            bias = -config.RAID_PULL if claimed.get(handle) else 0
        if handle == current:
            bias -= 5
        risk = min(45, max(0, objective.incoming / raiders * clear * 0.55 / hp_budget - 0.7) * 12)
        estimate = cost + (travel + risk) * 100 / max(1, value) + bias
        ranked.append((estimate, objective, clear, value, bias))
    ranked.sort(key=lambda row: row[0])
    field, reached = nav.field_from(position)
    visible = bc.vision.visible_tiles()
    enemy_positions = []
    for enemy in enemies:
        turn.check()
        if enemy.is_visible() and enemy.is_alive():
            enemy_positions.append(enemy.position())
    best, best_score = None, float('inf')
    for _, objective, clear, value, bias in ranked:
        turn.check()
        if best is not None and bc.fuel_remaining() < 950_000:
            break
        positions = [p for p in objective.positions if reached.is_set(p)]
        if not positions:
            continue
        travel = min(field.get(p) for p in positions)
        reward = False
        incoming = objective.incoming
        if not (objective.spawns & visible).is_empty():
            state = objective.group.state()
            if isinstance(state, gm.CampGroupRespawning):
                respawns[objective.handle] = now + state.timer
                continue
            if isinstance(state, gm.CampGroupRewardAvailable):
                owner = team.collector(objective.handle, objective.spawns)
                if owner is not None and owner != team.slot and not objective.spawns.is_set(position):
                    continue
                reward, clear, incoming = True, 0, 0
            elif not cheap:
                # A half-cleared camp is cheaper than its original design HP.
                remaining_hp, incoming = 0, 0
                for camp in objective.camps:
                    turn.check()
                    if camp.is_visible():
                        if not bc.vision.has_camp(camp.spawn_position()):
                            continue
                        remaining_hp += camp.health()
                        incoming += camp.strength()
                    else:
                        remaining_hp += camp.base_stats().base_health
                        incoming += camp.base_stats().base_strength
                clear *= remaining_hp / max(1, objective.hp)
        raiders = 1 + max(claimed.get(objective.handle, 0), config.RAID_ASSUME) if objective.monolith else 1
        expected_damage = max(0, incoming / raiders * clear * 0.55 - heal_rate * clear)
        if expected_damage > hp_budget:
            continue
        risk = min(45, max(0, expected_damage / hp_budget - 0.7) * 12)
        score = (travel + clear + capture + risk) * 100 / max(1, value) + bias
        if enemy_positions:
            nearest = min(nav.distance(p, q) for p in positions for q in enemy_positions)
            score += max(0, 5-nearest) * 4
        if reward:
            score = (travel + capture) * 100 / max(1, value) - 15
        if score < best_score:
            best, best_score = objective, score
    stalled = False
    return best


def choose_cooperative(metadata, me, respawns, team):
    """Break the zero-income deadlock by rallying at one affordable group.

    A claim is a rendezvous, never permission to read an unseen ally's stats.
    Existing leaders take precedence so stranded farmers combine their damage.
    """
    now = bc.round_number()
    claims = team.assignments()
    grouped = {}
    for index, ally in enumerate(team.allies):
        if index != team.slot and ally.is_alive() and claims[index] >= 0:
            grouped[claims[index]] = grouped.get(claims[index], 0) + 1
    field, reached = nav.field_from(me.position())
    visible = bc.vision.visible_tiles()
    best, score = None, float('inf')
    for o in metadata:
        turn.check()
        if o.monolith or respawns.get(o.handle, 0) > now:
            continue
        positions = [p for p in o.positions if reached.is_set(p)]
        if not positions:
            continue
        hp = o.hp
        if not (o.spawns & visible).is_empty():
            state = o.group.state()
            if isinstance(state, gm.CampGroupRespawning):
                respawns[o.handle] = now + state.timer
                continue
            if isinstance(state, gm.CampGroupRewardAvailable):
                hp = 0
        travel = min(field.get(p) for p in positions)
        # Bound the initial gamble. A team can bootstrap elk packs; it cannot
        # tank several golems with starter stats and no equipment.
        if o.incoming > 180 and not grouped.get(o.handle):
            continue
        cost = (travel + hp / 180 + bc.constants.CAPTURE_TIME) / max(1, o.gems + o.gold * 0.2)
        if grouped.get(o.handle):
            cost *= 0.35
        if cost < score:
            best, score = o, cost
        if best is not None and bc.fuel_remaining() < 800_000:
            break
    return best
